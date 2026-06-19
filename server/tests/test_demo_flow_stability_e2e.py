"""M3-12 Demo Flow stability E2E（可选，需 --run-e2e）。

目标：
- 在同一浏览器会话里连续两次触发 Demo 攻击并分析当前告警。
- 每次都必须看到 Copilot no-key fallback 用户可见消息。
- 失败时保存 screenshot + sanitized diagnostic JSON。
- 不使用真实 LLM API，不放宽生产 rate limit，不写 storage。
"""
from __future__ import annotations

import os
import re

import pytest

from server.tests.e2e_copilot_helpers import (
    collect_visible_text,
    install_network_diagnostics,
    save_copilot_failure_artifacts,
    wait_for_copilot_fallback_message,
)
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


def _contains_forbidden(text: str) -> str | None:
    for pattern in _FORBIDDEN_DOM_PATTERNS:
        if pattern.search(text):
            return pattern.pattern
    return None


async def _wait_for_demo_button(page) -> None:
    await page.wait_for_selector(
        '[data-testid="trigger-demo-attack"]',
        state="visible",
        timeout=45000,
    )


async def _run_one_demo_analysis(page, diag: dict, iteration: int) -> str:
    await _wait_for_demo_button(page)
    await page.get_by_test_id("trigger-demo-attack").click()

    row_count = 0
    for _ in range(30):
        row_count = len(await page.query_selector_all('[data-testid="attack-log-row"]'))
        if row_count >= iteration:
            break
        await page.wait_for_timeout(500)
    assert row_count >= iteration, (
        f"第 {iteration} 次 Demo 攻击后告警表行数不足。row_count={row_count}"
    )

    analyze_btn = page.get_by_test_id("analyze-current-alert")
    await analyze_btn.wait_for(state="visible", timeout=15000)
    await analyze_btn.click()

    try:
        assistant_text = await wait_for_copilot_fallback_message(
            page,
            timeout_ms=45000,
        )
    except Exception as exc:  # noqa: BLE001
        diag["artifacts"] = await save_copilot_failure_artifacts(
            page,
            diag,
            prefix=f"demo-flow-stability-iteration-{iteration}",
        )
        pytest.fail(
            f"第 {iteration} 次 Demo 分析未看到 Copilot fallback。"
            f" artifacts={diag['artifacts']} error={exc}"
        )

    assert "API Key" in assistant_text or "Base URL" in assistant_text, (
        f"第 {iteration} 次 Copilot fallback 文案异常: {assistant_text!r}"
    )
    return assistant_text


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_demo_flow_copilot_fallback_survives_two_consecutive_runs() -> None:
    skip_without_playwright()
    from playwright.async_api import async_playwright

    diag: dict[str, object] = {
        "registered": False,
        "iterations": [],
        "forbidden": None,
        "artifacts": {},
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
            context = await browser.new_context(viewport={"width": 1280, "height": 800})
            page = await context.new_page()
            install_network_diagnostics(page, diag)
            await assert_dev_server_reachable(page)

            _email, _password, register_status = await register_or_login_for_e2e(
                page,
                "e2e-demo-stability",
            )
            diag["registered"] = register_status in {"created", "exists"}

            for iteration in (1, 2):
                assistant_text = await _run_one_demo_analysis(page, diag, iteration)
                diag["iterations"].append(
                    {
                        "iteration": iteration,
                        "assistant_len": len(assistant_text),
                    }
                )

            visible_text = await collect_visible_text(page, limit=1600)
            forbidden = _contains_forbidden(visible_text)
            diag["forbidden"] = forbidden
            assert forbidden is None, (
                f"Dashboard 出现禁止外泄内容(命中模式: {forbidden})。"
                f"前 200 字: {visible_text[:200]!r}"
            )

            print(f"\n[E2E 诊断] {diag}")
        finally:
            await context.close()
            await browser.close()
