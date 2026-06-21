"""M3-15 SOC 时间线筛选 / 展开详情浏览器 E2E。

覆盖路径：

- 注册 / 登录 Dashboard。
- 等待 SOC 安全时间线可见。
- 触发 Demo 攻击并刷新时间线。
- 验证筛选按钮、Demo 筛选、全部筛选、详情展开、复制摘要、Escape 收起。
- 保存桌面 / 移动截图。
- 扫描 DOM 和剪贴板文本 forbidden sentinel。

默认 ``pytest server/tests`` 跳过；通过 ``--run-e2e`` 显式触发。
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from server.tests.e2e_helpers import (
    assert_dev_server_reachable,
    register_or_login_for_e2e,
    skip_without_playwright,
)

pytestmark = [pytest.mark.e2e]

BASE = os.getenv("E2E_BASE_URL", "http://localhost:3000")
ARTIFACT_DIR = Path("docs/runs/artifacts/m3-15-soc-timeline-drilldown")

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


async def _click_desktop_route(page, route_key: str) -> None:
    button = page.locator(f'[data-testid="dashboard-route-desktop-{route_key}"]').first
    await button.wait_for(state="visible", timeout=15000)
    await button.click()


async def _trigger_demo_attack(page) -> None:
    await page.wait_for_selector(
        '[data-testid="trigger-demo-attack"]',
        state="visible",
        timeout=45000,
    )
    await page.get_by_test_id("trigger-demo-attack").click()
    for _ in range(20):
        rows = await page.query_selector_all('[data-testid="attack-log-row"]')
        if rows:
            return
        await page.wait_for_timeout(500)
    raise AssertionError("触发 Demo 攻击后告警表未出现新行。")


async def _refresh_timeline_until_item(page) -> None:
    timeline = page.get_by_test_id("security-timeline").first
    await timeline.wait_for(state="visible", timeout=15000)
    refresh = page.get_by_test_id("security-timeline-refresh").first

    for _ in range(12):
        await refresh.click()
        try:
            await page.wait_for_selector(
                '[data-testid="security-timeline-item"]',
                state="visible",
                timeout=2500,
            )
            return
        except Exception:
            await page.wait_for_timeout(500)
    raise AssertionError("刷新时间线后仍未看到 security-timeline-item。")


async def _screenshot(page, name: str) -> str:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / f"{name}.png"
    await page.screenshot(path=str(path), full_page=True)
    return str(path)


async def _read_clipboard_text(page) -> str:
    try:
        return await page.evaluate("() => navigator.clipboard.readText()")
    except Exception:
        return ""


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_security_timeline_drilldown_filter_browser_e2e() -> None:
    skip_without_playwright()
    from playwright.async_api import async_playwright

    diag: dict[str, object] = {
        "registered": False,
        "demo_items": 0,
        "copy_status": "",
        "screenshots": [],
        "forbidden": None,
        "clipboard_forbidden": None,
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
            _email, _password, register_status = await register_or_login_for_e2e(
                page, "e2e-timeline-drilldown"
            )
            diag["registered"] = register_status in {"created", "exists"}

            await _click_desktop_route(page, "overview")
            await page.get_by_test_id("security-timeline").first.scroll_into_view_if_needed()
            await page.get_by_test_id("security-timeline").first.wait_for(
                state="visible",
                timeout=15000,
            )

            await _trigger_demo_attack(page)
            await _click_desktop_route(page, "overview")
            await page.get_by_test_id("security-timeline").first.scroll_into_view_if_needed()
            await _refresh_timeline_until_item(page)

            for test_id in (
                "security-timeline-filter-all",
                "security-timeline-filter-demo",
                "security-timeline-filter-copilot",
                "security-timeline-filter-guardrails",
                "security-timeline-filter-system",
            ):
                await page.get_by_test_id(test_id).first.wait_for(
                    state="visible",
                    timeout=10000,
                )

            await page.get_by_test_id("security-timeline-filter-demo").first.click()
            demo_filter_pressed = await page.get_by_test_id(
                "security-timeline-filter-demo"
            ).first.get_attribute("aria-pressed")
            assert demo_filter_pressed == "true", (
                "Demo 筛选按钮点击后 aria-pressed 应为 true。"
            )

            demo_empty = page.get_by_test_id("security-timeline-filter-empty")
            visible_demo_items = page.locator(
                '[data-testid="security-timeline-item"]:visible'
            )
            demo_count = await visible_demo_items.count()
            diag["demo_items"] = demo_count
            if demo_count > 0:
                for index in range(demo_count):
                    category = await visible_demo_items.nth(index).get_attribute(
                        "data-category"
                    )
                    assert category == "demo_attack", (
                        f"Demo 筛选后出现非 demo_attack 项: {category!r}"
                    )
            else:
                await demo_empty.first.wait_for(state="visible", timeout=5000)
                assert "Demo" in (await demo_empty.first.inner_text())

            await page.get_by_test_id("security-timeline-filter-all").first.click()
            all_filter_pressed = await page.get_by_test_id(
                "security-timeline-filter-all"
            ).first.get_attribute("aria-pressed")
            assert all_filter_pressed == "true", (
                "全部筛选按钮点击后 aria-pressed 应为 true。"
            )

            first_item = page.get_by_test_id("security-timeline-item").first
            await first_item.wait_for(state="visible", timeout=10000)
            await first_item.click()
            await first_item.evaluate("node => node.scrollIntoView({ block: 'center' })")

            detail = page.get_by_test_id("security-timeline-detail").first
            await detail.wait_for(state="visible", timeout=10000)
            expanded = await first_item.get_attribute("data-expanded")
            aria_expanded = await first_item.get_attribute("aria-expanded")
            assert expanded == "true"
            assert aria_expanded == "true"

            detail_text = await detail.inner_text()
            for marker in ("时间", "来源", "类别", "状态", "脱敏摘要", "已隐藏敏感字段"):
                assert marker in detail_text, (
                    f"时间线详情缺少 {marker!r}: {detail_text!r}"
                )

            await page.get_by_test_id("security-timeline-copy-summary").first.click()
            copy_status = page.get_by_test_id("security-timeline-copy-status").first
            status_text = ""
            for _ in range(20):
                if await copy_status.count() > 0:
                    status_text = (await copy_status.inner_text()).strip()
                    if "已复制" in status_text or "复制失败" in status_text:
                        break
                await page.wait_for_timeout(250)
            diag["copy_status"] = status_text
            assert "已复制" in status_text or "复制失败" in status_text, (
                f"复制摘要状态异常: {status_text!r}"
            )

            clipboard_text = await _read_clipboard_text(page)
            if clipboard_text:
                assert clipboard_text.startswith("[SOC]"), (
                    f"复制摘要格式异常: {clipboard_text!r}"
                )
                clipboard_forbidden = _contains_forbidden(clipboard_text)
                diag["clipboard_forbidden"] = clipboard_forbidden
                assert clipboard_forbidden is None, (
                    f"复制摘要命中 forbidden sentinel: {clipboard_forbidden}"
                )

            diag["screenshots"].append(
                await _screenshot(page, "security-timeline-desktop")
            )

            await page.keyboard.press("Escape")
            await detail.wait_for(state="hidden", timeout=5000)

            await page.set_viewport_size({"width": 390, "height": 844})
            await page.get_by_test_id("security-timeline").first.scroll_into_view_if_needed()
            mobile_first = page.get_by_test_id("security-timeline-item").first
            await mobile_first.wait_for(state="visible", timeout=10000)
            await mobile_first.click()
            await page.get_by_test_id("security-timeline-detail").first.wait_for(
                state="visible",
                timeout=10000,
            )
            overflow = await page.evaluate(
                """
                () => Math.max(
                    document.documentElement.scrollWidth - document.documentElement.clientWidth,
                    document.body ? document.body.scrollWidth - document.body.clientWidth : 0
                )
                """
            )
            assert overflow <= 4, f"移动端时间线详情产生横向溢出: {overflow}"
            diag["screenshots"].append(
                await _screenshot(page, "security-timeline-mobile")
            )

            visible_text = await _collect_visible_text(page)
            forbidden = _contains_forbidden(visible_text)
            diag["forbidden"] = forbidden
            assert forbidden is None, (
                f"Dashboard DOM 出现 forbidden sentinel(命中模式: {forbidden})。"
                f"前 200 字: {visible_text[:200]!r}"
            )

            print(f"\n[Security Timeline Drilldown E2E 诊断] {diag}")
        finally:
            if context is not None:
                await context.close()
            await browser.close()
