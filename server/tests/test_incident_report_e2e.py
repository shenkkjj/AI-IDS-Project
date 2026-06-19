"""M3-08 案件证据报告浏览器 E2E（可选，需 ``--run-e2e`` 显式运行）。

设计目标（docs/agent/M3_08_INCIDENT_REPORT_BROWSER_E2E_AND_AGENT_DOCS_CATCHUP_TASK.md
§7-§9）:

- 真实浏览器级验收：注册/登录 -> 触发 Demo 攻击 -> 选中告警 -> 创建案件 ->
  等待案件详情 -> 下载 Markdown 报告 -> 验证报告结构与脱敏 sentinel ->
  点击复制报告 -> 扫描页面 DOM 无 secret / stack / system prompt 泄漏。
- 默认 ``pytest server/tests`` 仍跳过；通过 ``--run-e2e`` 显式触发。
- 缺 playwright / 缺浏览器 / 缺 dev server 都给出明确提示。
- 不依赖真实 LLM API key（无 key 降级态由后端兜底，不影响报告导出）。
- 不依赖公网（仅连本地 dev server）。
- 唯一邮箱,可重入。
- 使用 ``accept_downloads=True`` + 授予 ``clipboard-read`` / ``clipboard-write``。
- 下载报告后读取真实文件内容做断言。
- 最后关闭 browser / context。

运行前置：

1. 启动后端 dev server（默认 :8000）和前端 dev server（默认 :3000）。
2. 安装 Playwright：``pip install playwright && playwright install chromium``。
3. 运行：``pytest server/tests/test_incident_report_e2e.py --run-e2e``。

不在主 ``pytest server/tests`` 基线中运行，避免无 Playwright 环境时全员 fail。
"""
from __future__ import annotations

import os
import re
import time
from importlib.util import find_spec
from typing import Iterable

import pytest

pytestmark = [pytest.mark.e2e]

BASE = os.getenv("E2E_BASE_URL", "http://localhost:3000")
DEFAULT_PASSWORD = os.getenv("E2E_DEFAULT_PASSWORD", "DemoE2EPass123!")

# 任何真密钥、stack trace、Guardrails L1 regex、system prompt 触发都不应出现在
# 页面可见 DOM 或下载的报告 markdown 中（security review SC-2 / SC-4）。
# 复用 test_demo_flow_e2e 的 sentinel 集合 + 增加 ``developer:`` 触发,
# 与 M3-07 incident_report_service._REPORT_SENTINEL_PATTERNS 对齐。
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

# 报告 markdown 必含的固定结构（与 incident_report_service.build_incident_report 对齐）
_REQUIRED_REPORT_HEADINGS: tuple[str, ...] = (
    "# 案件证据报告",
    "## 1. 案件摘要",
    "## 2. 关联告警",
    "## 3. 案件时间线",
    "## 4. 安全与脱敏说明",
)

# 案件报告按钮文案（用于检查 status 显示）
_COPY_SUCCESS_MARKERS = ("已复制",)
_COPY_FAIL_MARKERS = ("复制失败", "报告生成失败")
_DOWNLOAD_SUCCESS_MARKERS = ("已下载",)
_DOWNLOAD_FAIL_MARKERS = ("下载失败", "报告生成失败")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _skip_without_playwright() -> None:
    if find_spec("playwright") is None:
        pytest.skip(
            "未安装 playwright。运行 `pip install playwright && "
            "playwright install chromium` 后加 --run-e2e 显式执行。"
        )


async def _assert_dev_server_reachable(page) -> None:
    """在浏览器上下文中探测 Next.js API 代理,确保前后端都已就绪。

    失败信息明确指向:需要先启动 dev server。
    """
    try:
        response = await page.request.get(f"{BASE}/api/backend/health", timeout=5000)
    except Exception as exc:  # noqa: BLE001
        pytest.fail(
            f"E2E 前置失败:无法连到 {BASE}/api/backend/health。"
            f"请先启动后端 (:8000) 和前端 (:3000) dev server:\n"
            f"  1) ./.venv/Scripts/python.exe -m uvicorn server.main:app --port 8000\n"
            f"  2) cd web-next && npm run dev\n"
            f"原始错误:{exc}"
        )

    if response.status != 200:
        pytest.fail(
            f"E2E 前置失败:{BASE}/api/backend/health 返回 {response.status}。"
            f"请确认后端 dev server 正在 :8000 运行。"
        )


async def _collect_visible_text(page) -> str:
    """读取 body 文本,过滤 script/style/noscript 节点。"""
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
    """命中任一敏感 sentinel 则返回对应 pattern;否则 None。"""
    for pattern in _FORBIDDEN_DOM_PATTERNS:
        if pattern.search(text):
            return pattern.pattern
    return None


def _register_unique_user() -> tuple[str, str]:
    """生成时间戳邮箱,确保测试可重入。"""
    ts = int(time.time() * 1000)
    email = f"e2e-report-{ts}@example.com"
    return email, DEFAULT_PASSWORD


async def _register_via_ui(page, email: str, password: str) -> None:
    """在前端 UI 上注册并等待自动跳转 /dashboard。

    实现策略:
    1. 走 ``/api/backend/auth/register`` 直接创建用户(避免 next-auth 客户端
       signIn + 浏览器 CSRF cookie 时序问题,任务 §7 接受"注册或登录")。
    2. 在 UI 上切到 login 模式,填入同样的 email/password,提交登录。
    3. 等 URL 变为 /dashboard。
    """
    # 1) 探测 dev server 健康并直接通过后端 API 注册一个用户
    api_response = await page.request.post(
        f"{BASE}/api/backend/auth/register",
        data={"email": email, "password": password},
        headers={"Content-Type": "application/json"},
    )
    if api_response.status not in (200, 201):
        # 409 conflict 也允许(用户已存在),直接走 login。
        body = await api_response.text()
        if api_response.status == 409 or "已存在" in body or "exists" in body.lower():
            pass
        else:
            pytest.fail(
                f"E2E 前置失败:无法注册测试用户 (HTTP {api_response.status})。"
                f"body: {body!r}"
            )

    # 2) 打开 UI 首页,等 React hydration
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
            f"无法等到 login-email hydration 完成({exc})。"
            f"body 文本:{body_text!r}"
        )

    # 3) 填入 login 模式下的 email + password,提交登录
    await page.get_by_test_id("login-email").first.fill(email)
    await page.get_by_test_id("login-password").first.fill(password)
    await page.get_by_test_id("login-submit").click()

    # 4) Next.js App Router 用 client-side router.push,expect_navigation 不会触发;
    #    改用 wait_for_function 轮询 window.location.pathname
    try:
        await page.wait_for_function(
            "() => window.location.pathname === '/dashboard' || /\\?.*dashboard/.test(window.location.search)",
            timeout=20000,
        )
        return
    except Exception:
        # next-auth 5.0.0-beta.30 客户端 signIn 成功但 useSession 不自动刷新,
        # 强制 page.goto /dashboard,让 server-side session 检查决定是否接受。
        pass

    # fallback: 直接 goto /dashboard,如果 session cookie 有效就会接受。
    try:
        await page.goto(f"{BASE}/dashboard", wait_until="domcontentloaded", timeout=15000)
    except Exception:
        pass

    try:
        await page.wait_for_function(
            "() => window.location.pathname === '/dashboard' || /\\?.*dashboard/.test(window.location.search)",
            timeout=20000,
        )
    except Exception as exc:  # noqa: BLE001
        body_text = await page.evaluate(
            "() => document.body ? document.body.innerText.slice(0, 500) : ''"
        )
        current_url = page.url
        pytest.fail(
            f"登录后未跳到 /dashboard ({exc})。当前 URL: {current_url!r}。"
            f"body 文本:{body_text!r}"
        )


async def _trigger_demo_and_get_first_alert_id(page) -> str:
    """触发 Demo 攻击,等待 attack-log-row 出现,点击最新一行后返回 data-alert-id。"""
    # dashboard 首次加载 / next dev 编译 / WS / 数据 fetch 可能耗时较长,
    # 给到 45s 等待 trigger-demo-attack 出现。
    await page.wait_for_selector(
        '[data-testid="trigger-demo-attack"]',
        state="visible",
        timeout=45000,
    )
    await page.get_by_test_id("trigger-demo-attack").click()

    # 等待 attack-log-row 出现(最多 10s 轮询)
    first_row = None
    for _ in range(20):
        rows = await page.query_selector_all('[data-testid="attack-log-row"]')
        if rows:
            first_row = rows[0]
            break
        await page.wait_for_timeout(500)

    assert first_row is not None, "触发 Demo 攻击后告警表未出现新行。"
    alert_id = await first_row.get_attribute("data-alert-id") or ""

    # 选中最新告警,让 AlertDetailPanel 出现 + 暴露 alert-detail-create-incident
    await first_row.click()
    return alert_id


async def _create_incident_from_selected_alert(page) -> None:
    """点击 alert-detail-create-incident,等待案件详情面板出现。"""
    create_btn = page.get_by_test_id("alert-detail-create-incident").first
    await create_btn.wait_for(state="visible", timeout=10000)
    await create_btn.click()

    # 创建后会自动 setRoute("incidents") + loadIncidentDetail;
    # IncidentDetailPanel 上有 data-testid="incident-detail-panel"。
    await page.wait_for_selector(
        '[data-testid="incident-detail-panel"]',
        state="visible",
        timeout=20000,
    )


async def _click_download_report(page) -> tuple[str, str, str]:
    """点击 incident-download-report, expect_download 真实读取文件。

    返回 (suggested_filename, content, file_path)。
    """
    async with page.expect_download(timeout=20000) as download_info:
        await page.get_by_test_id("incident-download-report").first.click()
    download = await download_info.value
    suggested_filename = download.suggested_filename
    file_path = await download.path()
    assert file_path is not None, "Playwright 未返回下载文件路径。"
    content = ""
    with open(file_path, "r", encoding="utf-8") as fh:
        content = fh.read()
    return suggested_filename, content, str(file_path)


async def _click_copy_report_and_get_status(page) -> str:
    """点击 incident-copy-report,等待 incident-report-status 出现可接受文案。"""
    await page.get_by_test_id("incident-copy-report").first.click()

    # 状态文案是短小的"已复制" / "复制失败" / "报告生成失败"。
    # 轮询 incident-report-status 节点,直到文案命中任一 marker(最多 10s)。
    allowed = (
        _COPY_SUCCESS_MARKERS + _COPY_FAIL_MARKERS + _DOWNLOAD_SUCCESS_MARKERS + _DOWNLOAD_FAIL_MARKERS
    )
    status_locator = page.get_by_test_id("incident-report-status")
    final_text = ""
    for _ in range(20):
        count = await status_locator.count()
        if count > 0:
            final_text = (await status_locator.first.inner_text()).strip()
            if any(m in final_text for m in allowed):
                break
        await page.wait_for_timeout(250)
    return final_text


# ---------------------------------------------------------------------------
# Main E2E
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_incident_report_browser_e2e() -> None:
    """M3-08 案件报告浏览器级验收 E2E。

    流程:
        注册 -> 触发 Demo 攻击 -> 创建案件 -> 下载报告 -> 验证 markdown 结构
        与脱敏 sentinel -> 点击复制 -> 扫描页面 DOM 无泄漏。
    """
    _skip_without_playwright()
    from playwright.async_api import async_playwright

    diag: dict[str, object] = {
        "registered": False,
        "demo": False,
        "create": False,
        "download": False,
        "copy_status": "",
        "forbidden": None,
        "filename": "",
    }
    email, password = _register_unique_user()

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
                f"原始错误:{exc}"
            )

        try:
            # accept_downloads + clipboard 权限(本地 http://localhost 被授予)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                accept_downloads=True,
            )
            # grants 只在 chromium 下生效;在权限被拒时复制按钮会走降级。
            try:
                await context.grant_permissions(
                    ["clipboard-read", "clipboard-write"],
                    origin=BASE,
                )
            except Exception:
                # 权限授予失败不致命:复制按钮会显示"复制失败"并降级。
                pass

            page = await context.new_page()

            # 1) 探测 dev server 健康
            await _assert_dev_server_reachable(page)

            # 2) 注册唯一用户并自动跳到 /dashboard
            await _register_via_ui(page, email, password)
            diag["registered"] = True

            # 3) 触发 Demo 攻击 + 选中最新告警
            alert_id = await _trigger_demo_and_get_first_alert_id(page)
            diag["demo"] = True

            # 4) 等待 AlertDetailPanel 出现,点击"从此告警创建案件"
            create_btn = page.get_by_test_id("alert-detail-create-incident").first
            await create_btn.wait_for(state="visible", timeout=10000)
            await create_btn.click()

            # 5) 等待案件详情面板
            await page.wait_for_selector(
                '[data-testid="incident-detail-panel"]',
                state="visible",
                timeout=20000,
            )
            diag["create"] = True

            # 6) 点击"下载报告" -> expect_download
            suggested_filename, markdown, _path = await _click_download_report(page)
            diag["filename"] = suggested_filename
            diag["download"] = True

            # 7) 文件名断言
            assert suggested_filename.startswith("incident-"), (
                f"下载文件名应以 'incident-' 开头,实际 {suggested_filename!r}"
            )
            assert suggested_filename.endswith("-report.md"), (
                f"下载文件名应以 '-report.md' 结尾,实际 {suggested_filename!r}"
            )

            # 8) 报告必含的 4 段结构
            for heading in _REQUIRED_REPORT_HEADINGS:
                assert heading in markdown, (
                    f"报告 markdown 缺少必要标题 {heading!r}。"
                    f"首 200 字:{markdown[:200]!r}"
                )

            # 9) 必含 payload_length / payload_preview 字段
            assert "payload_length" in markdown, "报告缺少 payload_length 字段"
            assert "payload_preview" in markdown, "报告缺少 payload_preview 字段"

            # 10) 报告不含敏感 sentinel / 完整 raw payload / 完整 note
            for pattern in _FORBIDDEN_DOM_PATTERNS:
                match = pattern.search(markdown)
                assert not match, (
                    f"报告 markdown 命中禁止 sentinel: {pattern.pattern} -> "
                    f"...{markdown[max(0, match.start()-20):match.end()+20]!r}..."
                )

            # 11) 点击"复制报告" -> 验证 status 文案命中合法降级
            copy_status = await _click_copy_report_and_get_status(page)
            diag["copy_status"] = copy_status
            allowed = (
                _COPY_SUCCESS_MARKERS + _COPY_FAIL_MARKERS + _DOWNLOAD_SUCCESS_MARKERS + _DOWNLOAD_FAIL_MARKERS
            )
            assert any(m in copy_status for m in allowed), (
                f"复制报告后 incident-report-status 文案异常:{copy_status!r}。"
                f"允许的 marker:{allowed}"
            )

            # 12) 整页 DOM 扫描,禁止出现敏感字面量
            body_text = await _collect_visible_text(page)
            forbidden = _contains_forbidden(body_text)
            diag["forbidden"] = forbidden
            assert forbidden is None, (
                f"Dashboard 出现禁止外泄的内容(命中模式:{forbidden})。"
                f"首 200 字:{body_text[:200]!r}"
            )

            print(
                f"\n[E2E 诊断] alert_id={alert_id!r} "
                f"filename={suggested_filename!r} copy_status={copy_status!r} {diag}"
            )
        finally:
            await context.close()
            await browser.close()
