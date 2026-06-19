"""M3-10 Dashboard route sections E2E（可选，需 --run-e2e）。

目标：
- 登录后 Dashboard 桌面导航必须暴露所有核心 route，包括 M3-09 后的 incidents。
- 点击每个 route 后，对应核心 section 必须可见。
- 整页 DOM 不得泄漏 secret / stack trace / system prompt sentinel。

运行前置：
1. 启动后端 dev server（默认 :8000）和前端 dev server（默认 :3000）。
2. 安装 Playwright：``pip install playwright && playwright install chromium``。
3. 运行：``pytest server/tests/test_dashboard_route_sections_e2e.py --run-e2e -q --tb=short -s``。
"""
from __future__ import annotations

import os
import re

import pytest

from server.tests.e2e_helpers import (
    assert_dev_server_reachable,
    register_or_login_for_e2e,
    skip_without_playwright,
)

pytestmark = [pytest.mark.e2e]

BASE = os.getenv("E2E_BASE_URL", "http://localhost:3000")

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


async def _expect_section(page, test_id: str) -> None:
    await page.locator(f'[data-testid="{test_id}"]').first.wait_for(
        state="visible",
        timeout=15000,
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_dashboard_route_tabs_render_core_sections() -> None:
    skip_without_playwright()
    from playwright.async_api import async_playwright

    diag: dict[str, object] = {
        "registered": False,
        "routes": [],
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

        try:
            context = await browser.new_context(
                viewport={"width": 1366, "height": 900},
            )
            page = await context.new_page()
            await assert_dev_server_reachable(page)

            # 复用 M3-09 已验证的稳定账号前缀，避免本地 dev backend
            # REGISTER_RATE_LIMIT 窗口把本测试卡在登录前置。
            _email, _password, register_status = await register_or_login_for_e2e(
                page, "e2e-auth"
            )
            diag["registered"] = register_status in {"created", "exists"}

            await _expect_section(page, "dashboard-section-stats")
            await _expect_section(page, "dashboard-section-briefing")

            checks: list[tuple[str, tuple[str, ...]]] = [
                (
                    "overview",
                    (
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
                ),
                (
                    "monitor",
                    (
                        "dashboard-section-stats",
                        "dashboard-section-briefing",
                        "dashboard-section-trends",
                        "dashboard-section-alerts",
                        "dashboard-section-terminal-report",
                        "dashboard-section-security-timeline",
                    ),
                ),
                (
                    "incidents",
                    (
                        "dashboard-section-stats",
                        "dashboard-section-briefing",
                        "dashboard-section-incidents",
                        "incident-section",
                    ),
                ),
                (
                    "waf",
                    (
                        "dashboard-section-stats",
                        "dashboard-section-briefing",
                        "dashboard-section-system-status",
                    ),
                ),
                (
                    "ai",
                    (
                        "dashboard-section-stats",
                        "dashboard-section-briefing",
                        "dashboard-section-copilot",
                        "dashboard-section-ai-config",
                        "dashboard-section-webhook",
                    ),
                ),
                (
                    "report",
                    (
                        "dashboard-section-stats",
                        "dashboard-section-briefing",
                        "dashboard-section-report",
                    ),
                ),
            ]

            for route_key, section_ids in checks:
                await _click_desktop_route(page, route_key)
                for section_id in section_ids:
                    await _expect_section(page, section_id)
                diag["routes"].append(route_key)

            visible_text = await _collect_visible_text(page)
            forbidden = _contains_forbidden(visible_text)
            diag["forbidden"] = forbidden
            assert forbidden is None, (
                f"Dashboard route sections 出现禁止外泄内容(命中模式: {forbidden})。"
                f"前 200 字: {visible_text[:200]!r}"
            )

            print(f"\n[E2E 诊断] {diag}")
        finally:
            await context.close()
            await browser.close()
