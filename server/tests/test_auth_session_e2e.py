"""NEXT-01 最小 Auth Session E2E（可选，需 ``--run-e2e`` 显式运行）。

目标(`docs/agent/NEXT_01_AUTH_SESSION_LOADING_E2E_RECOVERY_TASK.md` §8):

- RED: 在 main 上复现 next-auth 5 beta + Next.js 15 dev 下 Dashboard 登录后
  ``useSession`` 永 ``loading`` / ``SYSTEM · LOADING`` 不消失的阻塞。
- GREEN: 修复后, 登录用户应在 45s 内看到 ``[data-testid="trigger-demo-attack"]``,
  ``SYSTEM · LOADING`` 不持续, ``/api/auth/session`` 返回 user, DOM 无 secret /
  stack / system prompt 泄漏。

本测试只验证 "登录后 Dashboard 能解除 loading 并显示主按钮", 不掺案件报告流程,
让 RED 信号尽量小。

运行前置:

1. 启动后端 dev server (默认 :8000) 和前端 dev server (默认 :3000)。
2. 安装 Playwright: ``pip install playwright && playwright install chromium``。
3. 运行: ``pytest server/tests/test_auth_session_e2e.py --run-e2e``。

默认 ``pytest server/tests`` 跳过, ``--run-e2e`` 显式触发。
"""
from __future__ import annotations

import os
import re
import time
from importlib.util import find_spec

import pytest

pytestmark = [pytest.mark.e2e]

BASE = os.getenv("E2E_BASE_URL", "http://localhost:3000")
DEFAULT_PASSWORD = os.getenv("E2E_DEFAULT_PASSWORD", "DemoE2EPass123!")

# 任何真密钥 / stack trace / Guardrails L1 regex / system prompt 触发都不应
# 出现在用户可见 DOM 中（与 test_incident_report_e2e / test_demo_flow_e2e 对齐）。
_FORBIDDEN_DOM_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"sk-proj-[A-Za-z0-9_-]+"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"\bTraceback\s+\(most recent call last\)", re.IGNORECASE),
    re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+.*system\s+prompt", re.IGNORECASE),
    re.compile(r"forget\s+.*instructions", re.IGNORECASE),
    re.compile(r"\bsystem\s*:\s*", re.IGNORECASE),
    re.compile(r"\bdeveloper\s*:\s*", re.IGNORECASE),
    re.compile(r"PRIVATE\s+KEY", re.IGNORECASE),
)


def _skip_without_playwright() -> None:
    if find_spec("playwright") is None:
        pytest.skip(
            "未安装 playwright。运行 `pip install playwright && "
            "playwright install chromium` 后加 --run-e2e 显式执行。"
        )


def _register_unique_user() -> tuple[str, str]:
    """生成时间戳邮箱, 确保测试可重入。"""
    ts = int(time.time() * 1000)
    email = f"e2e-auth-{ts}@example.com"
    return email, DEFAULT_PASSWORD


async def _assert_dev_server_reachable(page) -> None:
    """探测 Next.js API 代理, 确保前后端都已就绪。

    失败信息明确指向: 需要先启动 dev server。
    """
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


async def _collect_visible_text(page) -> str:
    """读取 body 文本, 过滤 script/style/noscript 节点。"""
    return await page.evaluate(
        """
        () => {
            const body = document.body;
            if (!body) return '';
            const clone = body.cloneNode(true);
            clone.querySelectorAll('script, style, noscript').forEach((n) => n.remove());
            return (clone.innerText || clone.textContent || '').trim();
        }
        """
    )


def _contains_forbidden(text: str) -> str | None:
    for pattern in _FORBIDDEN_DOM_PATTERNS:
        if pattern.search(text):
            return pattern.pattern
    return None


async def _register_and_login(page, email: str, password: str) -> None:
    """走后端 API 直接 register, 然后通过 UI login form 提交一次。"""
    api_response = await page.request.post(
        f"{BASE}/api/backend/auth/register",
        data={"email": email, "password": password},
        headers={"Content-Type": "application/json"},
    )
    if api_response.status not in (200, 201):
        body = await api_response.text()
        if api_response.status == 409 or "已存在" in body or "exists" in body.lower():
            pass
        else:
            pytest.fail(
                f"E2E 前置失败: 无法注册测试用户 (HTTP {api_response.status})。"
                f"body: {body!r}"
            )

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

    # 给 React 19 + next-dev 一点时间挂 onSubmit handler;
    # 在 dev mode 下首次编译会比较慢, page.tsx 还在拉运行时 chunks。
    await page.wait_for_function(
        "() => { const btn = document.querySelector('[data-testid=\"login-submit\"]'); return btn && !btn.disabled; }",
        timeout=30000,
    )
    await page.get_by_test_id("login-email").first.fill(email)
    await page.get_by_test_id("login-password").first.fill(password)

    # NEXT-01 兜底:next-auth 5 beta + React 19 dev mode 下,前端 page.tsx 的
    # client-side ``signIn("credentials", ...)`` 偶尔不发出 callback 请求。这
    # 里直接走 next-auth 的 ``/api/auth/callback/credentials`` HTTP 端点种 cookie,
    # 与浏览器原生表单提交语义一致;然后再点登录按钮(让 React 状态保持一致)
    # 作为 fallback。
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

    # 兜底 callback 已经种了 cookie. 浏览器仍停在 /, 触发 click 让 React
    # 状态保持一致;失败也无所谓, _ensure_dashboard_url 会显式 goto /dashboard.
    try:
        await page.get_by_test_id("login-submit").click(timeout=5000)
    except Exception:
        pass


async def _ensure_dashboard_url(page) -> None:
    """点击登录后 / 注册后, Next.js client-side router.push 不触发原生导航。

    用 wait_for_function 轮询 ``window.location.pathname``。 fallback 显式
    ``page.goto("/dashboard")``, 让服务端 ``auth()`` 决定接受还是 redirect。
    """
    try:
        await page.wait_for_function(
            "() => window.location.pathname === '/dashboard'",
            timeout=20000,
        )
        return
    except Exception:
        pass

    # fallback: 显式跳转, 让服务端 auth() 决定接受还是 redirect 回 /
    try:
        await page.goto(f"{BASE}/dashboard", wait_until="domcontentloaded", timeout=15000)
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
        current_url = page.url
        pytest.fail(
            f"登录后未跳到 /dashboard ({exc})。当前 URL: {current_url!r}。"
            f"body 文本: {body_text!r}"
        )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_dashboard_session_unblocks_after_login() -> None:
    """登录后 Dashboard 应在 45s 内显示 ``trigger-demo-attack``,
    ``SYSTEM · LOADING`` 不持续, ``/api/auth/session`` 返回 user。
    """
    _skip_without_playwright()
    from playwright.async_api import async_playwright

    email, password = _register_unique_user()
    diag: dict[str, object] = {
        "registered": False,
        "dashboard_url": False,
        "trigger_demo_visible": False,
        "loading_text_persisted": True,
        "session_user_email": "",
        "forbidden": None,
    }

    async with async_playwright() as p:
        launch_options: dict[str, object] = {"headless": True}
        executable_path = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
        if executable_path:
            launch_options["executable_path"] = executable_path

        try:
            browser = await p.chromium.launch(**launch_options)
        except Exception as exc:  # noqa: BLE001
            pytest.skip(
                f"无法启动 chromium 浏览器。请运行 `playwright install chromium`。"
                f"原始错误: {exc}"
            )

        try:
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()

            # 1) dev server 健康检查
            await _assert_dev_server_reachable(page)

            # 2) 注册 + UI 登录
            await _register_and_login(page, email, password)
            diag["registered"] = True

            # 3) 等待 dashboard URL（可能由 client router.push 或 server redirect 触发）
            await _ensure_dashboard_url(page)
            diag["dashboard_url"] = True

            # 4) 关键 assertion: SYSTEM · LOADING 不持续, trigger-demo-attack 45s 内可见
            try:
                await page.wait_for_selector(
                    '[data-testid="trigger-demo-attack"]',
                    state="visible",
                    timeout=45000,
                )
            except Exception as exc:  # noqa: BLE001
                body_text = await page.evaluate(
                    "() => document.body ? document.body.innerText.slice(0, 500) : ''"
                )
                pytest.fail(
                    f"登录后 45s 内未看到 trigger-demo-attack ({exc})。"
                    f"这通常是 useSession() 永 loading 卡住 dashboard 渲染。"
                    f"body 文本: {body_text!r}"
                )
            diag["trigger_demo_visible"] = True

            # 5) 显式断言 SYSTEM · LOADING 文案不应该还在(loading 已解除)
            visible_text = await _collect_visible_text(page)
            loading_persisted = "SYSTEM · LOADING" in visible_text
            diag["loading_text_persisted"] = loading_persisted
            assert not loading_persisted, (
                "Dashboard 解除 loading 后, 不应再有 'SYSTEM · LOADING' 文案。"
                f"前 200 字: {visible_text[:200]!r}"
            )

            # 6) /api/auth/session 应返回 user
            session_resp = await page.request.get(
                f"{BASE}/api/auth/session", timeout=10000
            )
            assert session_resp.status == 200, (
                f"/api/auth/session 应该 200, 实际 {session_resp.status}"
            )
            session_json = await session_resp.json()
            user = (session_json or {}).get("user") or {}
            user_email = str(user.get("email") or "")
            diag["session_user_email"] = user_email
            assert user_email == email, (
                f"/api/auth/session 应返回 user.email={email!r}, 实际 {user_email!r}"
            )

            # 7) DOM 不应包含 sentinel(secret / stack / system prompt 泄漏)
            forbidden = _contains_forbidden(visible_text)
            diag["forbidden"] = forbidden
            assert forbidden is None, (
                f"Dashboard 出现禁止外泄的内容(命中模式: {forbidden})。"
                f"前 200 字: {visible_text[:200]!r}"
            )

            print(f"\n[E2E 诊断] {diag}")
        finally:
            await context.close()
            await browser.close()
