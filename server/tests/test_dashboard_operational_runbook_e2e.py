"""M3-16 Dashboard 运维 runbook / 健康检查面板真实浏览器 E2E。

覆盖：
- 登录后在 Dashboard WAF route 与移动 WAF route 均可看到 runbook 面板。
- 面板暴露六项健康检查、五条关键命令、脱敏登录身份、安全诊断摘要。
- 复制摘要按钮给出状态反馈，摘要文本不包含 secret / stack trace / prompt sentinel。
- 保存桌面与移动截图。

默认 ``pytest server/tests`` 跳过；通过 ``--run-e2e`` 显式触发。
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import quote

import pytest

from server.tests.e2e_helpers import (
    assert_dev_server_reachable,
    register_or_login_for_e2e,
    skip_without_playwright,
)

pytestmark = [pytest.mark.e2e]

BASE = os.getenv("E2E_BASE_URL", "http://localhost:3000")
ARTIFACT_DIR = Path("docs/runs/artifacts/m3-16-dashboard-operational-runbook")

CHECK_TEST_IDS: tuple[str, ...] = (
    "runbook-check-backend-health",
    "runbook-check-proxy-health",
    "runbook-check-auth-session",
    "runbook-check-demo-readiness",
    "runbook-check-e2e-readiness",
    "runbook-check-env-security",
)

RUNBOOK_COMMANDS: tuple[str, ...] = (
    r".venv\Scripts\python.exe -m pytest server\tests -q --tb=short",
    r".venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short",
    "cd web-next && npm run typecheck",
    "cd web-next && npm run build",
    r".venv\Scripts\python.exe scripts\check_env_security.py",
)

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


async def _collect_visible_text(page) -> str:
    return (await page.locator("body").inner_text(timeout=15000)).strip()


def _contains_forbidden(text: str) -> str | None:
    for pattern in _FORBIDDEN_DOM_PATTERNS:
        if pattern.search(text):
            return pattern.pattern
    return None


async def _click_route(page, route_key: str, route_prefix: str) -> None:
    button = page.locator(f'[data-testid="{route_prefix}-{route_key}"]').first
    await button.wait_for(state="attached", timeout=15000)
    await button.scroll_into_view_if_needed(timeout=5000)
    await button.click()
    current = await button.get_attribute("aria-current")
    assert current == "page", (
        f"{route_prefix}-{route_key} 点击后 aria-current 应为 page，实际 {current!r}"
    )


async def _assert_runbook_visible(page, email: str) -> str:
    panel = page.get_by_test_id("operational-runbook-panel").first
    await panel.wait_for(state="visible", timeout=15000)
    await page.get_by_test_id("runbook-copy-summary").first.wait_for(
        state="visible",
        timeout=10000,
    )

    panel_text = await panel.inner_text(timeout=10000)
    assert "Operational Runbook" in panel_text
    assert "Health Checklist" in panel_text
    assert "***@" in panel_text
    assert email not in panel_text

    for test_id in CHECK_TEST_IDS:
        item = page.get_by_test_id(test_id).first
        await item.wait_for(state="visible", timeout=10000)
        tone = await item.get_attribute("data-tone")
        assert tone in {"ok", "warn", "manual", "blocked"}, (
            f"{test_id} data-tone 异常: {tone!r}"
        )

    for index, command in enumerate(RUNBOOK_COMMANDS):
        command_node = page.get_by_test_id(f"runbook-command-{index}").first
        await command_node.wait_for(state="visible", timeout=10000)
        assert command in (await command_node.inner_text(timeout=5000))

    summary = await page.get_by_test_id("runbook-summary-preview").first.inner_text(
        timeout=10000,
    )
    assert summary.startswith("[AI-CyberSentinel Runbook]")
    for marker in (
        "backend_health=",
        "proxy_probe=/api/backend/health",
        "auth_session=",
        "demo_readiness=",
        "e2e_readiness=",
        "env_security=",
    ):
        assert marker in summary, f"诊断摘要缺少 {marker!r}: {summary!r}"
    for command in RUNBOOK_COMMANDS:
        assert command in summary

    forbidden = _contains_forbidden(summary)
    assert forbidden is None, f"诊断摘要命中 forbidden sentinel: {forbidden}"
    return summary


async def _click_copy_and_assert_status(page) -> str:
    await page.get_by_test_id("runbook-copy-summary").first.click()
    status = page.get_by_test_id("runbook-copy-status").first
    await status.wait_for(state="visible", timeout=5000)
    status_text = ""
    for _ in range(20):
        status_text = (await status.inner_text(timeout=2000)).strip()
        if "已复制" in status_text or "复制失败" in status_text:
            break
        await page.wait_for_timeout(250)
    assert "已复制" in status_text or "复制失败" in status_text, (
        f"复制摘要状态异常: {status_text!r}"
    )
    return status_text


async def _paste_clipboard_text(context) -> str:
    html = '<textarea data-testid="clipboard-target" autofocus></textarea>'
    paste_page = await context.new_page()
    try:
        await paste_page.goto(f"data:text/html;charset=utf-8,{quote(html)}")
        target = paste_page.get_by_test_id("clipboard-target").first
        await target.wait_for(state="visible", timeout=5000)
        await target.click()
        await paste_page.keyboard.press("Control+V")
        return await target.input_value(timeout=3000)
    except Exception:
        return ""
    finally:
        await paste_page.close()


async def _screenshot(page, name: str) -> str:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / f"{name}.png"
    await page.screenshot(path=str(path), full_page=True)
    return str(path)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_dashboard_operational_runbook_health_checklist_browser_e2e() -> None:
    skip_without_playwright()
    from playwright.async_api import async_playwright

    diag: dict[str, object] = {
        "registered": False,
        "copy_status": "",
        "clipboard_checked": False,
        "screenshots": [],
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
                "无法启动 chromium 浏览器。请运行 `playwright install chromium`。"
                f"原始错误: {exc}"
            )

        context = None
        try:
            context = await browser.new_context(viewport={"width": 1366, "height": 900})
            try:
                await context.grant_permissions(
                    ["clipboard-read", "clipboard-write"],
                    origin=BASE,
                )
            except Exception:
                pass

            page = await context.new_page()
            await assert_dev_server_reachable(page)
            email, _password, register_status = await register_or_login_for_e2e(
                page, "e2e-runbook"
            )
            diag["registered"] = register_status in {"created", "exists"}

            await _click_route(page, "waf", "dashboard-route-desktop")
            await page.get_by_test_id("dashboard-section-system-status").first.wait_for(
                state="visible",
                timeout=15000,
            )
            summary = await _assert_runbook_visible(page, email)
            diag["copy_status"] = await _click_copy_and_assert_status(page)

            clipboard_text = await _paste_clipboard_text(context)
            if clipboard_text:
                diag["clipboard_checked"] = True
                assert clipboard_text == summary
                clipboard_forbidden = _contains_forbidden(clipboard_text)
                assert clipboard_forbidden is None, (
                    f"剪贴板摘要命中 forbidden sentinel: {clipboard_forbidden}"
                )

            diag["screenshots"].append(
                await _screenshot(page, "operational-runbook-desktop")
            )

            await page.set_viewport_size({"width": 390, "height": 844})
            await _click_route(page, "waf", "dashboard-route-mobile")
            await page.get_by_test_id("dashboard-section-system-status").first.wait_for(
                state="visible",
                timeout=15000,
            )
            await _assert_runbook_visible(page, email)
            diag["screenshots"].append(
                await _screenshot(page, "operational-runbook-mobile")
            )

            visible_text = await _collect_visible_text(page)
            forbidden = _contains_forbidden(visible_text)
            diag["forbidden"] = forbidden
            assert forbidden is None, (
                f"Dashboard runbook DOM 出现 forbidden sentinel(命中模式: {forbidden})。"
                f"前 200 字: {visible_text[:200]!r}"
            )

            print(f"\n[Operational Runbook E2E 诊断] {diag}")
        finally:
            if context is not None:
                await context.close()
            await browser.close()
