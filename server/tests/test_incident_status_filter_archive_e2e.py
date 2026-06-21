"""M3-19 Closed Incident Archive / Status Filter 浏览器 E2E。

覆盖路径：

- 注册 / 登录 Dashboard。
- 通过现有 UI 创建 4 个案件样本：open、contained、resolved、false_positive。
- 验证案件列表状态筛选栏、活跃聚合、单状态筛选、关闭态归档和 ``closed_at`` 展示。
- 验证筛选切换后详情区不会显示已经不在当前列表中的 stale incident。
- 保存桌面 / 移动截图并扫描 DOM forbidden sentinel。

默认 ``pytest server/tests`` 跳过；通过 ``--run-e2e`` 显式触发。
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Literal

import pytest

from server.tests.e2e_helpers import (
    assert_dev_server_reachable,
    register_or_login_for_e2e,
    skip_without_playwright,
)

pytestmark = [pytest.mark.e2e]

BASE = os.getenv("E2E_BASE_URL", "http://localhost:3000")
ARTIFACT_DIR = Path(
    "docs/runs/artifacts/m3-19-closed-incident-archive-status-filter"
)

IncidentStatus = Literal["open", "investigating", "contained", "resolved", "false_positive"]

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

_FILTER_TEST_IDS: tuple[str, ...] = (
    "incident-filter-all",
    "incident-filter-active",
    "incident-filter-open",
    "incident-filter-investigating",
    "incident-filter-contained",
    "incident-filter-resolved",
    "incident-filter-false-positive",
    "incident-filter-closed",
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


async def _trigger_demo_and_create_incident(page, suffix: str) -> str:
    trigger = page.get_by_test_id("trigger-demo-attack").first
    await trigger.wait_for(state="visible", timeout=45000)
    await page.wait_for_function(
        """
        () => {
            const btn = document.querySelector('[data-testid="trigger-demo-attack"]');
            return btn && !btn.disabled;
        }
        """,
        timeout=45000,
    )

    alert_id = ""
    async with page.expect_response(
        lambda response: (
            "/api/backend/alerts/demo" in response.url
            and response.request.method == "POST"
        ),
        timeout=15000,
    ) as response_info:
        await trigger.click()
    response = await response_info.value
    body = await response.text()
    assert response.ok, f"Demo 攻击接口返回 HTTP {response.status}: {body[:240]!r}"
    payload = await response.json()
    alert_payload = payload.get("alert") if isinstance(payload, dict) else {}
    if isinstance(alert_payload, dict):
        alert_id = str(alert_payload.get("alert_id") or alert_payload.get("id") or "")
    assert alert_id, f"Demo 攻击未生成可识别告警 id: {payload!r}"

    row = None
    for _ in range(30):
        rows = await page.query_selector_all('[data-testid="attack-log-row"]')
        for candidate in rows:
            if (await candidate.get_attribute("data-alert-id")) == alert_id:
                row = candidate
                break
        if row is not None:
            break
        await page.wait_for_timeout(500)
    assert row is not None, f"触发 Demo 后告警表未出现新行: {alert_id}"

    await row.click()
    create_btn = page.get_by_test_id("alert-detail-create-incident").first
    await create_btn.wait_for(state="visible", timeout=10000)
    await create_btn.click()
    detail = page.get_by_test_id("incident-detail-panel").first
    await detail.wait_for(state="visible", timeout=30000)
    incident_id = await detail.get_attribute("data-incident-id")
    assert incident_id, "创建案件后 detail-panel 缺少 data-incident-id。"

    await page.get_by_test_id("incident-title-input").first.fill(
        f"M3-19 {suffix} {incident_id[-6:]}"
    )
    await page.get_by_test_id("incident-save").first.click()
    await page.wait_for_function(
        """
        () => {
            const panel = document.querySelector('[data-testid="incident-detail-panel"]');
            return panel && panel.innerText.includes('已保存');
        }
        """,
        timeout=15000,
    )
    return incident_id


async def _create_status_sample(
    page,
    suffix: str,
    target_status: IncidentStatus,
) -> str:
    await page.get_by_test_id("dashboard-route-desktop-overview").first.click()
    incident_id = await _trigger_demo_and_create_incident(page, suffix)
    if target_status != "open":
        await page.get_by_test_id(f"incident-status-{target_status}").first.click()
        await page.get_by_test_id("incident-note-input").first.fill(
            f"m3-19 status sample {target_status}"
        )
        await page.get_by_test_id("incident-save").first.click()
        await page.wait_for_function(
            """
            (status) => {
                const panel = document.querySelector('[data-testid="incident-detail-panel"]');
                const active = document.querySelector(`[data-testid="incident-status-${status}"]`);
                return panel && panel.innerText.includes('已保存') && active?.getAttribute('aria-checked') === 'true';
            }
            """,
            arg=target_status,
            timeout=15000,
        )
    return incident_id


async def _go_to_incidents(page) -> None:
    route = page.get_by_test_id("dashboard-route-desktop-incidents").first
    await route.wait_for(state="visible", timeout=30000)
    await route.click()
    await page.wait_for_function(
        """
        () => {
            const button = document.querySelector('[data-testid="dashboard-route-desktop-incidents"]');
            return button?.getAttribute('aria-current') === 'page';
        }
        """,
        timeout=10000,
    )
    await page.get_by_test_id("incident-section").first.wait_for(
        state="visible",
        timeout=30000,
    )


async def _wait_for_list_ids(page) -> list[str]:
    await page.wait_for_function(
        """
        () => {
            const state = document.querySelector('[data-testid="incident-filter-summary"]');
            const list = document.querySelector('[data-testid="incident-list"]');
            const empty = document.querySelector('[data-testid="incident-list-empty-filtered"]');
            return (state && !state.innerText.includes('加载中')) && (list || empty);
        }
        """,
        timeout=20000,
    )
    return await page.locator('[data-testid="incident-list-item"]').evaluate_all(
        "(items) => items.map((item) => item.getAttribute('data-incident-id') || '')"
    )


async def _list_statuses(page) -> list[str]:
    return await page.locator('[data-testid="incident-status-badge"]').evaluate_all(
        "(items) => items.map((item) => item.getAttribute('data-status') || '')"
    )


async def _click_filter(page, test_id: str) -> list[str]:
    await page.get_by_test_id(test_id).first.click()
    await page.get_by_test_id(test_id).first.wait_for(state="visible", timeout=5000)
    pressed = await page.get_by_test_id(test_id).first.get_attribute("aria-pressed")
    assert pressed == "true", f"{test_id} 点击后 aria-pressed 应为 true, 实际 {pressed!r}"
    return await _wait_for_list_ids(page)


async def _assert_filter_result(
    page,
    *,
    expected_ids: set[str],
    excluded_ids: set[str],
    allowed_statuses: set[str],
    label: str,
) -> None:
    ids = set(await _wait_for_list_ids(page))
    assert expected_ids.issubset(ids), f"{label} 缺少预期案件: expected={expected_ids} actual={ids}"
    leaked = ids & excluded_ids
    assert not leaked, f"{label} 出现本轮其他状态样本: {leaked}"
    statuses = set(await _list_statuses(page))
    assert statuses.issubset(allowed_statuses), (
        f"{label} 出现不属于当前筛选的状态: statuses={statuses} allowed={allowed_statuses}"
    )


async def _screenshot(page, name: str) -> str:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / f"{name}.png"
    await page.screenshot(path=str(path), full_page=True)
    return str(path)


async def _assert_no_horizontal_overflow(page, label: str) -> None:
    overflow = await page.evaluate(
        """
        () => Math.max(
            document.documentElement.scrollWidth - document.documentElement.clientWidth,
            document.body ? document.body.scrollWidth - document.body.clientWidth : 0
        )
        """
    )
    assert overflow <= 4, f"{label} 产生整页横向溢出: {overflow}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_incident_status_filter_archive_browser_e2e() -> None:
    skip_without_playwright()
    from playwright.async_api import async_playwright

    diag: dict[str, object] = {
        "registered": False,
        "samples": {},
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
            context = await browser.new_context(
                viewport={"width": 1366, "height": 900},
                accept_downloads=True,
            )
            page = await context.new_page()
            await assert_dev_server_reachable(page)
            _email, _password, register_status = await register_or_login_for_e2e(
                page, "e2e-incident-status-filter"
            )
            diag["registered"] = register_status in {"created", "exists"}

            samples = {
                "open": await _create_status_sample(page, "open", "open"),
                "contained": await _create_status_sample(page, "contained", "contained"),
                "resolved": await _create_status_sample(page, "resolved", "resolved"),
                "false_positive": await _create_status_sample(
                    page,
                    "false positive",
                    "false_positive",
                ),
            }
            diag["samples"] = samples

            await _go_to_incidents(page)
            filter_bar = page.get_by_test_id("incident-status-filter-bar")
            await filter_bar.first.wait_for(state="visible", timeout=15000)
            for test_id in _FILTER_TEST_IDS:
                await page.get_by_test_id(test_id).first.wait_for(
                    state="visible",
                    timeout=10000,
                )

            await _click_filter(page, "incident-filter-closed")
            await _assert_filter_result(
                page,
                expected_ids={samples["resolved"], samples["false_positive"]},
                excluded_ids={samples["open"], samples["contained"]},
                allowed_statuses={"resolved", "false_positive"},
                label="已关闭归档筛选",
            )
            closed_times = page.get_by_test_id("incident-closed-at")
            assert await closed_times.count() >= 2, "关闭态列表必须展示 closed_at。"
            for index in range(await closed_times.count()):
                text = (await closed_times.nth(index).inner_text()).strip()
                assert text and "—" not in text, f"closed_at 展示不能为空: {text!r}"

            first_closed = page.get_by_test_id("incident-list-item").first
            await first_closed.click()
            detail = page.get_by_test_id("incident-detail-panel").first
            await detail.wait_for(state="visible", timeout=15000)
            selected_closed_id = await first_closed.get_attribute("data-incident-id")
            assert await detail.get_attribute("data-incident-id") == selected_closed_id
            await page.get_by_test_id("incident-closure-review-checklist").first.wait_for(
                state="visible",
                timeout=15000,
            )
            diag["screenshots"].append(await _screenshot(page, "status-filter-desktop"))

            await _click_filter(page, "incident-filter-active")
            await _assert_filter_result(
                page,
                expected_ids={samples["open"], samples["contained"]},
                excluded_ids={samples["resolved"], samples["false_positive"]},
                allowed_statuses={"open", "investigating", "contained"},
                label="活跃筛选",
            )
            assert await page.get_by_test_id("incident-closed-at").count() == 0, (
                "活跃案件列表不应展示 incident-closed-at。"
            )
            selected_after_active = page.get_by_test_id("incident-detail-panel")
            if await selected_after_active.count() > 0:
                detail_id = await selected_after_active.first.get_attribute("data-incident-id")
                assert detail_id in {samples["open"], samples["contained"]}, (
                    f"筛选为活跃后详情仍显示关闭态 stale incident: {detail_id}"
                )

            await _click_filter(page, "incident-filter-contained")
            await _assert_filter_result(
                page,
                expected_ids={samples["contained"]},
                excluded_ids={samples["open"], samples["resolved"], samples["false_positive"]},
                allowed_statuses={"contained"},
                label="contained 筛选",
            )

            await _click_filter(page, "incident-filter-resolved")
            await _assert_filter_result(
                page,
                expected_ids={samples["resolved"]},
                excluded_ids={samples["open"], samples["contained"], samples["false_positive"]},
                allowed_statuses={"resolved"},
                label="resolved 筛选",
            )

            await _click_filter(page, "incident-filter-false-positive")
            await _assert_filter_result(
                page,
                expected_ids={samples["false_positive"]},
                excluded_ids={samples["open"], samples["contained"], samples["resolved"]},
                allowed_statuses={"false_positive"},
                label="false_positive 筛选",
            )

            storage_state = await page.evaluate(
                """
                () => ({
                    local: Object.keys(window.localStorage).filter((key) => key.toLowerCase().includes('incident')),
                    session: Object.keys(window.sessionStorage).filter((key) => key.toLowerCase().includes('incident')),
                })
                """
            )
            assert storage_state == {"local": [], "session": []}, (
                f"筛选状态不应写入浏览器 storage: {storage_state}"
            )
            await _click_filter(page, "incident-filter-all")
            all_pressed = await page.get_by_test_id("incident-filter-all").first.get_attribute(
                "aria-pressed"
            )
            assert all_pressed == "true", "点击全部后筛选应回到默认全部。"

            visible_text = await _collect_visible_text(page)
            forbidden = _contains_forbidden(visible_text)
            diag["forbidden"] = forbidden
            assert forbidden is None, (
                f"Dashboard DOM 出现 forbidden sentinel(命中模式: {forbidden})。"
                f"前 200 字: {visible_text[:200]!r}"
            )

            await page.set_viewport_size({"width": 390, "height": 844})
            await page.get_by_test_id("incident-status-filter-bar").first.wait_for(
                state="visible",
                timeout=10000,
            )
            await _assert_no_horizontal_overflow(page, "mobile status filter")
            diag["screenshots"].append(await _screenshot(page, "status-filter-mobile"))

            print(f"\n[Incident Status Filter Archive E2E 诊断] {diag}")
        finally:
            if context is not None:
                await context.close()
            await browser.close()
