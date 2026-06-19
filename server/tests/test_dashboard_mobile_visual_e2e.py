"""M3-13 Dashboard 移动视觉 QA E2E（可选，需 --run-e2e）。

目标：
- 基于 M3-11 截图暴露的移动端统计卡片空白、section 间距和 nav 可读性问题，
  给出浏览器级尺寸断言和截图证据。
- 只验证真实 DOM 和真实布局，不伪造数据。
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

ARTIFACT_DIR = Path("docs/runs/artifacts/m3-13-dashboard-mobile-visual")

VIEWPORTS: tuple[tuple[str, dict[str, int]], ...] = (
    ("mobile-390", {"width": 390, "height": 844}),
    ("mobile-430", {"width": 430, "height": 932}),
)

ROUTES: tuple[str, ...] = ("overview", "incidents")

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


async def _click_mobile_route(page, route: str) -> None:
    button = page.locator(f'[data-testid="dashboard-route-mobile-{route}"]').first
    await button.wait_for(state="visible", timeout=15000)
    await button.scroll_into_view_if_needed(timeout=5000)
    await button.click()
    await page.wait_for_timeout(250)
    active = await button.get_attribute("aria-current")
    assert active == "page", f"{route} mobile nav should be active, got {active!r}"


async def _expect_no_page_horizontal_overflow(page) -> None:
    metrics = await page.evaluate(
        """
        () => ({
            scrollWidth: document.documentElement.scrollWidth,
            clientWidth: document.documentElement.clientWidth,
            bodyScrollWidth: document.body ? document.body.scrollWidth : 0,
            bodyClientWidth: document.body ? document.body.clientWidth : 0,
        })
        """
    )
    overflow = max(
        metrics["scrollWidth"] - metrics["clientWidth"],
        metrics["bodyScrollWidth"] - metrics["bodyClientWidth"],
    )
    assert overflow <= 4, f"page horizontal overflow: {metrics}"


async def _expect_active_mobile_tab_visible(page, route: str) -> None:
    result = await page.evaluate(
        """
        (route) => {
            const button = document.querySelector(`[data-testid="dashboard-route-mobile-${route}"]`);
            const scroller = button?.closest('.overflow-x-auto');
            if (!button || !scroller) return { ok: false, reason: 'missing' };
            const b = button.getBoundingClientRect();
            const s = scroller.getBoundingClientRect();
            const visible = b.left >= s.left - 2 && b.right <= s.right + 2;
            return {
                ok: visible,
                buttonLeft: b.left,
                buttonRight: b.right,
                scrollerLeft: s.left,
                scrollerRight: s.right,
                text: button.textContent,
            };
        }
        """,
        route,
    )
    assert result["ok"], f"active mobile tab is not fully visible: {result}"


async def _expect_mobile_stats_density(page, viewport_height: int) -> None:
    result = await page.evaluate(
        """
        () => {
            const statsSection = document.querySelector('[data-testid="dashboard-section-stats"]');
            if (!statsSection) return { ok: false, reason: 'missing stats section' };
            const grid = statsSection.querySelector('[data-testid="stats-card-grid"]')
                || statsSection.querySelector('.grid');
            const cards = Array.from(statsSection.querySelectorAll('.grid > div'));
            const sectionRect = statsSection.getBoundingClientRect();
            const gridRect = grid ? grid.getBoundingClientRect() : sectionRect;
            const cardRects = cards.map((card) => {
                const rect = card.getBoundingClientRect();
                const text = (card.textContent || '').trim();
                return { height: rect.height, width: rect.width, text };
            });
            return {
                ok: true,
                sectionHeight: sectionRect.height,
                gridHeight: gridRect.height,
                cardRects,
            };
        }
        """
    )
    assert result["ok"], result
    max_card_height = max((item["height"] for item in result["cardRects"]), default=0)
    assert result["gridHeight"] <= viewport_height * 0.42, (
        f"mobile stats grid too tall: {result}"
    )
    assert max_card_height <= 160, f"mobile stat card too tall: {result}"


async def _wait_for_stats_cards_painted(page) -> None:
    await page.wait_for_function(
        """
        () => {
            const cards = Array.from(
                document.querySelectorAll('[data-testid="stats-card-grid"] > div')
            );
            return cards.length >= 4
                && cards.every((card) => Number(window.getComputedStyle(card).opacity) >= 0.99);
        }
        """,
        timeout=5000,
    )


async def _expect_mobile_section_gap(page) -> None:
    result = await page.evaluate(
        """
        () => {
            const stats = document.querySelector('[data-testid="dashboard-section-stats"]');
            const briefing = document.querySelector('[data-testid="dashboard-section-briefing"]');
            if (!stats || !briefing) return { ok: false, reason: 'missing section' };
            const a = stats.getBoundingClientRect();
            const b = briefing.getBoundingClientRect();
            return { ok: true, gap: b.top - a.bottom, statsBottom: a.bottom, briefingTop: b.top };
        }
        """
    )
    assert result["ok"], result
    assert result["gap"] <= 64, f"mobile section gap too large: {result}"


async def _detect_n_overlay(page) -> dict[str, object]:
    return await page.evaluate(
        """
        () => {
            const candidates = Array.from(document.querySelectorAll('body *'))
                .map((node) => {
                    const rect = node.getBoundingClientRect();
                    const text = (node.textContent || '').trim();
                    const style = window.getComputedStyle(node);
                    return {
                        tag: node.tagName,
                        text,
                        left: rect.left,
                        top: rect.top,
                        width: rect.width,
                        height: rect.height,
                        position: style.position,
                        zIndex: style.zIndex,
                        className: String(node.className || ''),
                    };
                })
                .filter((item) => (
                    item.text === 'N'
                    && item.width >= 24
                    && item.width <= 60
                    && item.height >= 24
                    && item.height <= 60
                    && item.left <= 80
                ));
            return { count: candidates.length, candidates };
        }
        """
    )


async def _screenshot(page, name: str) -> str:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / f"{name}.png"
    await page.screenshot(path=str(path), full_page=True)
    return str(path)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_dashboard_mobile_visual_density() -> None:
    skip_without_playwright()
    from playwright.async_api import async_playwright

    diag: dict[str, object] = {
        "viewports": [],
        "routes": [],
        "screenshots": [],
        "n_overlay": None,
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
            context = await browser.new_context(viewport=VIEWPORTS[0][1])
            page = await context.new_page()
            await assert_dev_server_reachable(page)
            await register_or_login_for_e2e(page, "e2e-mobile-visual")

            for viewport_name, viewport in VIEWPORTS:
                await page.set_viewport_size(viewport)
                diag["viewports"].append(viewport_name)
                for route in ROUTES:
                    await _click_mobile_route(page, route)
                    await page.locator('[data-testid="dashboard-section-stats"]').first.wait_for(
                        state="visible",
                        timeout=15000,
                    )
                    await _wait_for_stats_cards_painted(page)
                    await _expect_active_mobile_tab_visible(page, route)
                    await _expect_no_page_horizontal_overflow(page)
                    await _expect_mobile_stats_density(page, int(viewport["height"]))
                    await _expect_mobile_section_gap(page)
                    diag["routes"].append(f"{viewport_name}:{route}")
                    diag["screenshots"].append(
                        await _screenshot(page, f"{viewport_name}-{route}")
                    )

            overlay = await _detect_n_overlay(page)
            diag["n_overlay"] = overlay
            assert overlay["count"] == 0, (
                "Found app DOM that looks like the circular N overlay. "
                f"If this is browser/plugin injected, document evidence and update the test. {overlay}"
            )

            visible_text = await _collect_visible_text(page)
            forbidden = _contains_forbidden(visible_text)
            diag["forbidden"] = forbidden
            assert forbidden is None, (
                f"Dashboard mobile visual QA 出现禁止外泄内容(命中模式: {forbidden})。"
                f"前 200 字: {visible_text[:200]!r}"
            )

            print(f"\n[Mobile Visual E2E 诊断] {diag}")
        finally:
            if context is not None:
                await context.close()
            await browser.close()
