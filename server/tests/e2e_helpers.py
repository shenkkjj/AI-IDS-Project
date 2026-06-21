"""M3-09: E2E 浏览器测试共享 helper。

把 Auth / Demo Flow / Incident Report 三条 Playwright 测试里复制了三份的
注册 / NextAuth callback cookie 种入 / dashboard URL 等待逻辑统一到这里,
减少漂移,并在多次连续运行命中 ``REGISTER_RATE_LIMIT_MAX=5/小时`` 时优雅
fallback 到稳定测试账号路径,避免重启 dev server。

严格安全约束:

- 仅使用 ``page.request.post /api/backend/auth/register`` + NextAuth
  ``/api/auth/callback/credentials`` 表单 POST 种 httpOnly cookie。
- 不写 ``localStorage`` / ``sessionStorage`` / DOM / 日志。
- 不打印 cookie / token / password。
- 429 时只尝试稳定测试账号的 ``register or login`` 路径;若仍被限流,
  显式 ``pytest.fail`` 并提示等待限流窗口或重启本地测试 backend,
  绝不放宽生产 ``REGISTER_RATE_LIMIT_MAX``。
- 稳定账号默认邮箱 ``{prefix}-stable@example.com``,密码取
  ``E2E_DEFAULT_PASSWORD``,与生产真实账户隔离。
"""
from __future__ import annotations

import os
import re
import time
from importlib.util import find_spec
from typing import Literal, Tuple

import pytest

BASE = os.getenv("E2E_BASE_URL", "http://localhost:3000")
DEFAULT_PASSWORD = os.getenv("E2E_DEFAULT_PASSWORD", "DemoE2EPass123!")

RegisterStatus = Literal["created", "exists", "rate_limited", "error"]
_STABLE_ENV_ACCOUNTS_READY: set[str] = set()


def skip_without_playwright() -> None:
    """Playwright 缺失时给出明确 skip 文案。"""
    if find_spec("playwright") is None:
        pytest.skip(
            "未安装 playwright。运行 `pip install playwright && "
            "playwright install chromium` 后加 --run-e2e 显式执行。"
        )


def _safe_slug(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", text).strip("-")
    return cleaned or "e2e"


def _stable_email_env_key(prefix: str) -> str:
    safe_prefix = _safe_slug(prefix.lower())
    return f"E2E_{safe_prefix.upper().replace('-', '_')}_EMAIL"


def unique_e2e_user(prefix: str) -> Tuple[str, str]:
    """生成时间戳 + worker 隔离的唯一邮箱,确保测试可重入。"""
    ts = int(time.time() * 1000)
    worker = os.getenv("PYTEST_XDIST_WORKER", "local")
    safe_worker = _safe_slug(worker)
    safe_prefix = _safe_slug(prefix)
    return f"{safe_prefix}-{safe_worker}-{ts}@example.com", DEFAULT_PASSWORD


def stable_e2e_user(prefix: str) -> Tuple[str, str]:
    """稳定测试账号(限流降级路径)。

    优先读取 ``E2E_<UPPER_PREFIX>_EMAIL`` 环境变量;否则使用
    ``{prefix}-stable@example.com`` 默认值。密码统一来自
    ``E2E_DEFAULT_PASSWORD``。
    """
    safe_prefix = _safe_slug(prefix.lower())
    env_key = _stable_email_env_key(prefix)
    env_email = (os.getenv(env_key) or "").strip()
    if env_email:
        return env_email, DEFAULT_PASSWORD
    return f"{safe_prefix}-stable@example.com", DEFAULT_PASSWORD


def _has_stable_email_override(prefix: str) -> bool:
    return bool((os.getenv(_stable_email_env_key(prefix)) or "").strip())


def classify_register_response(status: int, body: str) -> RegisterStatus:
    """根据后端 ``/api/backend/auth/register`` 响应判定后续动作。

    - 200/201 -> ``created``。
    - 409 / 含 "已存在" / "已注册" / "exists" -> ``exists``(直接走登录)。
    - 429 / 含 "频繁" / "rate" -> ``rate_limited``(尝试稳定账号或停)。
    - 其他 -> ``error``(测试前置失败)。
    """
    text = (body or "").lower()
    raw = body or ""
    if status in (200, 201):
        return "created"
    if status == 409 or "已存在" in raw or "已注册" in raw or "exists" in text:
        return "exists"
    if status == 429 or "频繁" in raw or "rate" in text:
        return "rate_limited"
    return "error"


async def ensure_registered_or_rate_limited(
    page, email: str, password: str
) -> RegisterStatus:
    """直接走后端 ``/api/backend/auth/register``,根据状态码归类。

    error 路径直接 ``pytest.fail`` 并给出 HTTP 状态,但不打印 password。
    """
    response = await page.request.post(
        f"{BASE}/api/backend/auth/register",
        data={"email": email, "password": password},
        headers={"Content-Type": "application/json"},
    )
    body = await response.text()
    status = classify_register_response(response.status, body)
    if status == "error":
        pytest.fail(
            f"E2E 前置失败: 无法注册测试用户 (HTTP {response.status})。body: {body!r}"
        )
    return status


async def login_with_nextauth_callback(
    page, email: str, password: str
) -> None:
    """走 NextAuth ``/api/auth/callback/credentials`` 种 httpOnly cookie。

    前置: 已在后端 register 过该用户(或 409 已存在,见 ensure_registered)。
    流程参考 NEXT-01 / NEXT-02 验证过的稳定路径:

    1. 打开 ``/`` 等 React hydration。
    2. 等 ``login-email`` + ``login-submit`` 都出现且未 disabled。
    3. 填入 email / password(便于按钮点击 fallback 时 React 状态一致)。
    4. 拿 ``/api/auth/csrf`` token,直接 POST ``/api/auth/callback/credentials``
       form 表单种 cookie(语义与浏览器原生表单提交一致)。
    5. 尝试点击 ``login-submit``(失败也无所谓,后续 ``ensure_dashboard_url``
       会显式 goto)。

    严禁把 token 写入 ``localStorage`` / ``sessionStorage`` / DOM / 日志。
    """
    await page.goto(f"{BASE}/", wait_until="domcontentloaded", timeout=15000)
    await page.wait_for_load_state("domcontentloaded", timeout=10000)
    try:
        await page.wait_for_function(
            "() => document.querySelector('[data-testid=\"login-email\"]') !== null",
            timeout=30000,
        )
    except Exception as exc:  # noqa: BLE001
        body_text = await page.evaluate(
            "() => document.body ? document.body.innerText.slice(0, 500) : ''"
        )
        pytest.fail(
            f"无法等到 login-email hydration 完成 ({exc})。body 文本: {body_text!r}"
        )

    await page.wait_for_function(
        "() => { const btn = document.querySelector('[data-testid=\"login-submit\"]'); return btn && !btn.disabled; }",
        timeout=30000,
    )
    await page.get_by_test_id("login-email").first.fill(email)
    await page.get_by_test_id("login-password").first.fill(password)

    csrf_resp = await page.request.get(f"{BASE}/api/auth/csrf", timeout=10000)
    csrf_token = (await csrf_resp.json()).get("csrfToken", "")
    if csrf_token:
        await page.request.post(
            f"{BASE}/api/auth/callback/credentials",
            form={
                "email": email,
                "password": password,
                "csrfToken": csrf_token,
                "callbackUrl": f"{BASE}/dashboard",
                "json": "true",
            },
            timeout=15000,
        )

    try:
        await page.get_by_test_id("login-submit").click(timeout=5000)
    except Exception:
        # callback cookie 已种,按钮点击失败不致命;
        # ensure_dashboard_url 会显式 goto /dashboard。
        pass


async def ensure_dashboard_url(page) -> None:
    """登录后等 ``window.location.pathname == '/dashboard'``,fallback 显式 goto。

    Next.js App Router 的 ``router.push`` 是 client-side,不触发原生导航事件,
    所以不能用 ``page.expect_navigation``。
    """
    try:
        await page.wait_for_function(
            "() => window.location.pathname === '/dashboard'",
            timeout=20000,
        )
        return
    except Exception:
        pass

    try:
        await page.goto(
            f"{BASE}/dashboard", wait_until="domcontentloaded", timeout=15000
        )
    except Exception:
        pass

    try:
        await page.wait_for_function(
            "() => window.location.pathname === '/dashboard'",
            timeout=15000,
        )
    except Exception as exc:  # noqa: BLE001
        body_text = await page.evaluate(
            "() => document.body ? document.body.innerText.slice(0, 500) : ''"
        )
        pytest.fail(
            f"登录后未跳到 /dashboard ({exc})。当前 URL: {page.url!r}。"
            f"body 文本: {body_text!r}"
        )


async def assert_dev_server_reachable(page) -> None:
    """探测 Next.js API 代理,确保前后端 dev server 都已就绪。"""
    try:
        response = await page.request.get(f"{BASE}/api/backend/health", timeout=5000)
    except Exception as exc:  # noqa: BLE001
        pytest.fail(
            f"E2E 前置失败: 无法连到 {BASE}/api/backend/health。"
            f"请先启动后端 (:8000) 和前端 (:3000) dev server:\n"
            f"  1) ./.venv/Scripts/python.exe -m uvicorn server.main:app --port 8000\n"
            f"  2) cd web-next && npm run dev\n"
            f"原始错误: {exc}"
        )

    if response.status != 200:
        pytest.fail(
            f"E2E 前置失败: {BASE}/api/backend/health 返回 {response.status}。"
            f"请确认后端 dev server 正在 :8000 运行。"
        )


async def _stable_account_can_login(page, email: str, password: str) -> bool:
    """检测稳定账号是否已经存在(走后端 ``/auth/login/password``)。

    后端登录端点是按 IP 限流(``LOGIN_RATE_LIMIT_MAX=10/5min``,远比
    register 宽松),用于在 register 被 429 阻塞时验证 stable 账号是否
    可登录。返回 ``True`` 表示账号已存在且密码匹配,可走 NextAuth
    callback 种 cookie。
    """
    try:
        response = await page.request.post(
            f"{BASE}/api/backend/auth/login/password",
            data={"email": email, "password": password},
            headers={"Content-Type": "application/json"},
            timeout=10000,
        )
    except Exception:
        return False
    return response.status in (200, 201)


async def register_or_login_for_e2e(
    page, prefix: str
) -> Tuple[str, str, RegisterStatus]:
    """注册唯一测试账号 -> 登录 -> 等 dashboard URL,封装三步。

    遇到 429 时回落到稳定账号 ``{prefix}-stable@example.com``。后端
    ``REGISTER_RATE_LIMIT`` 是按客户端 IP 计数(``server/core/state.py``),
    本机连续运行多次 E2E 后稳定账号的 register 同样会被同一 IP 名额耗尽。
    因此 fallback 路径优先走登录探测(``/auth/login/password`` 限流更宽松),
    若 stable 账号已存在则直接走 NextAuth callback 种 cookie,不再消耗
    register 名额;若 stable 账号不存在再 best-effort register 一次。

    若 register 仍被限流且 stable 账号也无法登录,显式 ``pytest.fail`` 让
    人等待限流窗口过期或重启本地 dev backend,严禁通过放宽生产
    ``REGISTER_RATE_LIMIT_MAX`` 来规避。

    Returns ``(email, password, register_status)``,``register_status`` 反映
    本次实际走的注册路径(``created`` / ``exists`` / ``rate_limited``)。
    """
    if _has_stable_email_override(prefix):
        email, password = stable_e2e_user(prefix)
        if email in _STABLE_ENV_ACCOUNTS_READY or await _stable_account_can_login(
            page, email, password
        ):
            _STABLE_ENV_ACCOUNTS_READY.add(email)
            await login_with_nextauth_callback(page, email, password)
            await ensure_dashboard_url(page)
            return email, password, "exists"

    email, password = unique_e2e_user(prefix)
    status = await ensure_registered_or_rate_limited(page, email, password)

    if status == "rate_limited":
        # 切到稳定账号。先尝试直接登录(不消耗 register 名额);若已存在
        # 则把 status 改为 "exists" 走 NextAuth callback 种 cookie。
        email, password = stable_e2e_user(prefix)
        if await _stable_account_can_login(page, email, password):
            status = "exists"
        else:
            # 稳定账号还不存在: best-effort register 一次。仍 429 时,
            # 显式 fail 提示等待限流窗口或重启本地 dev backend。
            stable_status = await ensure_registered_or_rate_limited(
                page, email, password
            )
            if stable_status == "rate_limited":
                pytest.fail(
                    "E2E 注册被 rate limit 阻塞,且稳定测试账号无法登录。"
                    "请等待限流窗口过期(默认 1 小时)或重启本地 dev backend。"
                    "严禁放宽生产 REGISTER_RATE_LIMIT_MAX。"
                )
            status = stable_status

    await login_with_nextauth_callback(page, email, password)
    await ensure_dashboard_url(page)
    return email, password, status
