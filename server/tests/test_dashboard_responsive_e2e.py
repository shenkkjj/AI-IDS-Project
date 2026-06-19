"""M3-11 Dashboard 响应式与可访问性 E2E（可选，需 --run-e2e）。

覆盖：
- 桌面 / 移动视口下六个 Dashboard route 都可点击。
- active route button 暴露 aria-current="page"。
- 核心 section wrapper 可见。
- 页面没有整页横向溢出。
- 可见按钮文字不撑破按钮盒子。
- icon-only 按钮有 title 或 aria-label。
- route button 可通过键盘 Enter 切换。
- DOM 不出现 secret / stack trace / system prompt sentinel。

运行前置：
1. 启动后端 dev server（默认 :8000）和前端 dev server（默认 :3000）。
2. 安装 Playwright：``pip install playwright && playwright install chromium``。
3. 运行：``pytest server/tests/test_dashboard_responsive_e2e.py --run-e2e -q --tb=short -s``。
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

ARTIFACT_DIR = Path("docs/runs/artifacts/m3-11-dashboard-responsive")

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

ROUTE_SECTIONS: dict[str, tuple[str, ...]] = {
    "overview": (
        "dashboard-section-stats",
        "dashboard-section-briefing",
        "dashboard-section-trends",
        "dashboard-section-alerts",
        "dashboard-section-terminal-report",
        "dashboard-section-security-timeline",
        "dashboard-section-copilot",
        "dashboard-section-ai-config",
        "dashboard-section-webhook",
        "dashboard-section-report",
    ),
    "monitor": (
        "dashboard-section-stats",
        "dashboard-section-briefing",
        "dashboard-section-trends",
        "dashboard-section-alerts",
        "dashboard-section-terminal-report",
        "dashboard-section-security-timeline",
    ),
    "incidents": (
        "dashboard-section-stats",
        "dashboard-section-briefing",
        "dashboard-section-incidents",
        "incident-section",
    ),
    "waf": (
        "dashboard-section-stats",
        "dashboard-section-briefing",
        "dashboard-section-system-status",
    ),
    "ai": (
        "dashboard-section-stats",
        "dashboard-section-briefing",
        "dashboard-section-copilot",
        "dashboard-section-ai-config",
        "dashboard-section-webhook",
    ),
    "report": (
        "dashboard-section-stats",
        "dashboard-section-briefing",
        "dashboard-section-report",
    ),
}

VIEWPORTS: tuple[tuple[str, dict[str, int], str], ...] = (
    ("desktop", {"width": 1366, "height": 900}, "dashboard-route-desktop"),
    ("mobile", {"width": 390, "height": 844}, "dashboard-route-mobile"),
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


async def _expect_section(page, test_id: str) -> None:
    await page.locator(f'[data-testid="{test_id}"]').first.wait_for(
        state="visible",
        timeout=15000,
    )


async def _click_route(page, route_key: str, route_prefix: str) -> None:
    button = page.locator(f'[data-testid="{route_prefix}-{route_key}"]').first
    await button.wait_for(state="attached", timeout=15000)
    await button.scroll_into_view_if_needed(timeout=5000)
    await button.click()
    await button.wait_for(state="visible", timeout=5000)
    current = await button.get_attribute("aria-current")
    assert current == "page", (
        f"{route_prefix}-{route_key} 点击后 aria-current 应为 page, 实际 {current!r}"
    )


async def _assert_no_page_horizontal_overflow(page, label: str) -> None:
    metrics = await page.evaluate(
        """
        () => ({
            scrollWidth: Math.ceil(document.documentElement.scrollWidth),
            clientWidth: Math.ceil(document.documentElement.clientWidth),
            bodyScrollWidth: Math.ceil(document.body ? document.body.scrollWidth : 0),
            bodyClientWidth: Math.ceil(document.body ? document.body.clientWidth : 0),
        })
        """
    )
    overflow = max(
        metrics["scrollWidth"] - metrics["clientWidth"],
        metrics["bodyScrollWidth"] - metrics["bodyClientWidth"],
    )
    assert overflow <= 4, f"{label} 存在整页横向溢出: {metrics}"


async def _assert_visible_buttons_fit(page, label: str) -> None:
    offenders = await page.evaluate(
        """
        () => {
            const visible = (el) => {
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== 'none'
                    && style.visibility !== 'hidden'
                    && rect.width > 0
                    && rect.height > 0;
            };
            const okOverflow = (el) => {
                const style = window.getComputedStyle(el);
                return style.overflowX === 'auto'
                    || style.overflowX === 'scroll'
                    || style.textOverflow === 'ellipsis';
            };
            return Array.from(document.querySelectorAll('button'))
                .filter(visible)
                .filter((button) => button.scrollWidth > button.clientWidth + 4)
                .filter((button) => !okOverflow(button))
                .map((button) => ({
                    testId: button.getAttribute('data-testid') || '',
                    text: (button.innerText || button.textContent || '').trim().slice(0, 120),
                    scrollWidth: button.scrollWidth,
                    clientWidth: button.clientWidth,
                    className: button.className,
                }));
        }
        """
    )
    assert offenders == [], f"{label} 存在按钮文字溢出: {offenders}"


async def _assert_icon_buttons_named(page, label: str) -> None:
    offenders = await page.evaluate(
        """
        () => {
            const visible = (el) => {
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== 'none'
                    && style.visibility !== 'hidden'
                    && rect.width > 0
                    && rect.height > 0;
            };
            const textOf = (el) => (el.innerText || el.textContent || '').trim();
            return Array.from(document.querySelectorAll('button'))
                .filter(visible)
                .filter((button) => textOf(button).length === 0)
                .filter((button) => !button.getAttribute('aria-label') && !button.getAttribute('title'))
                .map((button) => ({
                    testId: button.getAttribute('data-testid') || '',
                    className: button.className,
                    html: button.outerHTML.slice(0, 200),
                }));
        }
        """
    )
    assert offenders == [], f"{label} 存在未命名 icon-only 按钮: {offenders}"


async def _assert_keyboard_route_activation(page, route_key: str, route_prefix: str) -> None:
    button = page.locator(f'[data-testid="{route_prefix}-{route_key}"]').first
    await button.scroll_into_view_if_needed(timeout=5000)
    await button.focus()
    await page.keyboard.press("Enter")
    current = await button.get_attribute("aria-current")
    assert current == "page", (
        f"键盘 Enter 激活 {route_prefix}-{route_key} 后 aria-current 应为 page, 实际 {current!r}"
    )


async def _screenshot(page, name: str) -> str:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / f"{name}.png"
    await page.screenshot(path=str(path), full_page=False)
    return str(path)


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.parametrize("viewport_name,viewport,route_prefix", VIEWPORTS)
async def test_dashboard_routes_are_responsive_and_accessible(
    viewport_name: str,
    viewport: dict[str, int],
    route_prefix: str,
) -> None:
    skip_without_playwright()
    from playwright.async_api import async_playwright

    diag: dict[str, object] = {
        "viewport": viewport_name,
        "registered": False,
        "routes": [],
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
            context = await browser.new_context(viewport=viewport)
            page = await context.new_page()
            await assert_dev_server_reachable(page)

            _email, _password, register_status = await register_or_login_for_e2e(
                page, "e2e-auth"
            )
            diag["registered"] = register_status in {"created", "exists"}

            await _assert_no_page_horizontal_overflow(page, f"{viewport_name}:initial")
            await _assert_icon_buttons_named(page, f"{viewport_name}:initial")

            for route_key, section_ids in ROUTE_SECTIONS.items():
                await _click_route(page, route_key, route_prefix)
                for section_id in section_ids:
                    await _expect_section(page, section_id)
                await _assert_no_page_horizontal_overflow(page, f"{viewport_name}:{route_key}")
                await _assert_visible_buttons_fit(page, f"{viewport_name}:{route_key}")
                await _assert_icon_buttons_named(page, f"{viewport_name}:{route_key}")
                if route_key in {"overview", "incidents"}:
                    screenshot = await _screenshot(page, f"{viewport_name}-{route_key}")
                    diag["screenshots"].append(screenshot)
                diag["routes"].append(route_key)

            await _assert_keyboard_route_activation(page, "overview", route_prefix)

            visible_text = await _collect_visible_text(page)
            forbidden = _contains_forbidden(visible_text)
            diag["forbidden"] = forbidden
            assert forbidden is None, (
                f"{viewport_name} Dashboard 出现禁止外泄内容(命中模式: {forbidden})。"
                f"前 200 字: {visible_text[:200]!r}"
            )

            print(f"\n[Responsive E2E 诊断] {diag}")
        except Exception:
            if context is not None:
                page = context.pages[-1] if context.pages else None
                if page is not None:
                    await _screenshot(page, f"{viewport_name}-failure")
            raise
        finally:
            if context is not None:
                await context.close()
            await browser.close()
