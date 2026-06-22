"""M3-20 Incident bulk selection / export queue 浏览器 E2E。

覆盖路径：
- 登录 Dashboard。
- 通过现有 UI 创建 open / contained / resolved 三个案件样本。
- 验证案件列表多选、全选当前筛选、批量复制安全摘要、前端导出队列提示。
- 验证切换 M3-19 状态筛选后清理不可见 selection。
- 验证 checkbox 点击不打开详情，列表主体点击仍打开详情。
- 验证刷新页面后 selection / queue 不持久化。
- 保存桌面 / 移动截图并扫描 DOM、clipboard、storage forbidden sentinel。

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
    "docs/runs/artifacts/m3-20-incident-workbench-bulk-selection-export-queue"
)

IncidentStatus = Literal[
    "open",
    "investigating",
    "contained",
    "resolved",
    "false_positive",
]

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

_BULK_CLIPBOARD_REQUIRED: tuple[str, ...] = (
    "AI-CyberSentinel Incident Bulk Summary",
    "count=2",
    "incident_id=",
    "title_length=",
    "status=",
    "severity=",
    "alert_count=",
    "updated_at=",
    "closed_at=",
)

_BULK_CLIPBOARD_FORBIDDEN_FRAGMENTS: tuple[str, ...] = (
    "payload",
    "note=",
    "markdown",
    "secret",
    "token",
    "m3-20 open",
    "m3-20 contained",
    "m3-20 resolved",
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
    assert row is not None, f"触发 Demo 后告警表未出现新行 {alert_id}"

    await row.click()
    create_btn = page.get_by_test_id("alert-detail-create-incident").first
    await create_btn.wait_for(state="visible", timeout=10000)
    await create_btn.click()
    detail = page.get_by_test_id("incident-detail-panel").first
    await detail.wait_for(state="visible", timeout=30000)
    incident_id = await detail.get_attribute("data-incident-id")
    assert incident_id, "创建案件后 detail-panel 缺少 data-incident-id。"

    await page.get_by_test_id("incident-title-input").first.fill(
        f"M3-20 {suffix} {incident_id[-6:]}"
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
            f"m3-20 bulk selection sample {target_status}"
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
    async def _wait_for_incident_section(timeout: int) -> bool:
        try:
            await page.get_by_test_id("incident-section").first.wait_for(
                state="visible",
                timeout=timeout,
            )
            return True
        except Exception:
            return False

    await page.wait_for_load_state("domcontentloaded", timeout=15000)
    await page.get_by_test_id("dashboard-section-stats").first.wait_for(
        state="visible",
        timeout=30000,
    )
    await page.wait_for_timeout(750)
    route = page.get_by_test_id("dashboard-route-desktop-incidents").first
    await route.wait_for(state="visible", timeout=30000)
    await route.scroll_into_view_if_needed(timeout=5000)
    await page.wait_for_function(
        """
        () => {
            const button = document.querySelector('[data-testid="dashboard-route-desktop-incidents"]');
            return button && !button.disabled;
        }
        """,
        timeout=30000,
    )
    await route.click()
    if await _wait_for_incident_section(12000):
        return

    await route.focus()
    await page.keyboard.press("Enter")
    if await _wait_for_incident_section(12000):
        return

    await page.evaluate(
        """
        () => {
            const button = document.querySelector('[data-testid="dashboard-route-desktop-incidents"]');
            if (button instanceof HTMLElement) {
                button.click();
            }
        }
        """
    )
    if await _wait_for_incident_section(30000):
        return

    visible_testids = await page.locator("[data-testid]").evaluate_all(
        """
        (nodes) => nodes
            .filter((node) => {
                const element = node;
                const style = window.getComputedStyle(element);
                return style && style.visibility !== 'hidden' && style.display !== 'none';
            })
            .slice(0, 80)
            .map((node) => node.getAttribute('data-testid'))
        """
    )
    main_text = await page.locator("main").first.inner_text(timeout=5000)
    raise AssertionError(
        "点击 incidents 路由后未出现 incident-section; "
        f"visible_testids={visible_testids}; main_text={main_text[:500]!r}"
    )


async def _wait_for_list_ready(page) -> list[str]:
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


async def _click_filter(page, test_id: str) -> list[str]:
    await page.get_by_test_id(test_id).first.click()
    await page.get_by_test_id(test_id).first.wait_for(state="visible", timeout=5000)
    pressed = await page.get_by_test_id(test_id).first.get_attribute("aria-pressed")
    assert pressed == "true", f"{test_id} 点击后 aria-pressed 应为 true, 实际 {pressed!r}"
    return await _wait_for_list_ready(page)


async def _select_checkbox_by_incident_id(page, incident_id: str) -> None:
    row = page.locator(
        f'[data-testid="incident-list-item"][data-incident-id="{incident_id}"]'
    ).first
    await row.wait_for(state="visible", timeout=10000)
    checkbox = row.locator(
        'xpath=preceding-sibling::input[@data-testid="incident-select-checkbox"]'
    ).first
    await checkbox.wait_for(state="visible", timeout=5000)
    await checkbox.click()


async def _assert_selected_count(page, expected: int) -> str:
    await page.wait_for_function(
        """
        (expected) => {
            const node = document.querySelector('[data-testid="incident-bulk-selected-count"]');
            return node && (node.textContent || '').includes(String(expected));
        }
        """,
        arg=expected,
        timeout=10000,
    )
    return (await page.get_by_test_id("incident-bulk-selected-count").first.inner_text()).strip()


async def _read_clipboard_text(page) -> str:
    try:
        return await page.evaluate("() => navigator.clipboard.readText()")
    except Exception:
        return ""


def _assert_bulk_clipboard_safe(text: str) -> None:
    for marker in _BULK_CLIPBOARD_REQUIRED:
        assert marker in text, f"批量摘要缺少安全字段 marker: {marker}"
    lowered = text.lower()
    for fragment in _BULK_CLIPBOARD_FORBIDDEN_FRAGMENTS:
        assert fragment not in lowered, f"批量摘要不应包含敏感或标题片段: {fragment}"
    forbidden = _contains_forbidden(text)
    assert forbidden is None, f"批量摘要命中 forbidden sentinel: {forbidden}"


async def _storage_feature_keys(page) -> dict[str, list[str]]:
    return await page.evaluate(
        """
        () => {
            const matches = (key) => /incident|bulk|export|queue/i.test(key);
            return {
                local: Object.keys(window.localStorage).filter(matches),
                session: Object.keys(window.sessionStorage).filter(matches),
            };
        }
        """
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
async def test_incident_bulk_selection_export_queue_browser_e2e() -> None:
    skip_without_playwright()
    from playwright.async_api import async_playwright

    diag: dict[str, object] = {
        "registered": False,
        "samples": {},
        "copy_status": "",
        "clipboard_checked": False,
        "screenshots": [],
        "forbidden": None,
        "clipboard_forbidden": None,
        "storage": {},
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
                page, "e2e-incident-bulk-export"
            )
            diag["registered"] = register_status in {"created", "exists"}

            samples = {
                "open": await _create_status_sample(page, "open", "open"),
                "contained": await _create_status_sample(page, "contained", "contained"),
                "resolved": await _create_status_sample(page, "resolved", "resolved"),
            }
            diag["samples"] = samples

            await _go_to_incidents(page)
            await page.get_by_test_id("incident-status-filter-bar").first.wait_for(
                state="visible",
                timeout=15000,
            )
            await page.get_by_test_id("incident-bulk-action-bar").first.wait_for(
                state="visible",
                timeout=15000,
            )
            await _wait_for_list_ready(page)

            # 列表主体点击仍能打开详情。先打开 open，后续切换 closed 时可验证 stale detail 被清理。
            await page.locator(
                f'[data-testid="incident-list-item"][data-incident-id="{samples["open"]}"]'
            ).first.click()
            detail = page.get_by_test_id("incident-detail-panel").first
            await detail.wait_for(state="visible", timeout=15000)
            assert await detail.get_attribute("data-incident-id") == samples["open"]

            list_items = page.locator('[data-testid="incident-list-item"]')
            item_count = await list_items.count()
            assert item_count >= 3, f"案件列表应至少包含本轮 3 个样本, 实际 {item_count}"
            for index in range(min(item_count, 6)):
                checkbox = list_items.nth(index).locator(
                    'xpath=preceding-sibling::input[@data-testid="incident-select-checkbox"]'
                )
                assert await checkbox.count() == 1, "每个可见案件列表项都应有多选 checkbox"
                aria = await checkbox.first.get_attribute("aria-label")
                assert aria and (
                    "案件" in aria or samples["open"][:4] in aria or "选择" in aria
                ), "checkbox aria-label 应包含案件语义或 id"

            await _select_checkbox_by_incident_id(page, samples["open"])
            await _select_checkbox_by_incident_id(page, samples["contained"])
            await _assert_selected_count(page, 2)

            await page.get_by_test_id("incident-bulk-copy-summary").first.click()
            status = page.get_by_test_id("incident-bulk-copy-status").first
            copy_status = ""
            for _ in range(20):
                copy_status = (await status.inner_text()).strip()
                if "已复制" in copy_status or "复制失败" in copy_status:
                    break
                await page.wait_for_timeout(250)
            diag["copy_status"] = copy_status
            assert "已复制" in copy_status or "复制失败" in copy_status, (
                f"批量复制状态异常: {copy_status!r}"
            )

            clipboard_text = await _read_clipboard_text(page)
            if clipboard_text:
                diag["clipboard_checked"] = True
                _assert_bulk_clipboard_safe(clipboard_text)

            await page.get_by_test_id("incident-add-export-queue").first.click()
            queue_panel = page.get_by_test_id("incident-export-queue-panel")
            await queue_panel.first.wait_for(state="visible", timeout=10000)
            await page.wait_for_function(
                """
                () => {
                    const node = document.querySelector('[data-testid="incident-export-queue-count"]');
                    return node && (node.textContent || '').includes('2');
                }
                """,
                timeout=10000,
            )
            assert await page.get_by_test_id("incident-export-queue-item").count() >= 2
            queue_text = await queue_panel.first.inner_text()
            assert "前端" in queue_text and "准备队列" in queue_text, (
                "导出队列提示必须说明这是前端准备队列，不是后台任务"
            )
            assert samples["open"] in queue_text or samples["contained"] in queue_text
            diag["screenshots"].append(await _screenshot(page, "bulk-selection-desktop"))

            await _click_filter(page, "incident-filter-closed")
            closed_ids = await _wait_for_list_ready(page)
            assert samples["resolved"] in set(closed_ids), "已关闭归档应包含 resolved 样本"
            assert samples["open"] not in set(closed_ids)
            assert samples["contained"] not in set(closed_ids)
            await _assert_selected_count(page, 0)

            await page.get_by_test_id("incident-bulk-select-page").first.click()
            await _assert_selected_count(page, len(closed_ids))
            await page.get_by_test_id("incident-add-export-queue").first.click()
            await page.set_viewport_size({"width": 390, "height": 844})
            await queue_panel.first.wait_for(state="visible", timeout=10000)
            await _assert_no_horizontal_overflow(page, "mobile bulk selection")
            diag["screenshots"].append(await _screenshot(page, "bulk-selection-mobile"))

            await page.get_by_test_id("incident-export-queue-clear").first.click()
            await page.wait_for_function(
                """
                () => {
                    const node = document.querySelector('[data-testid="incident-export-queue-count"]');
                    return node && (node.textContent || '').includes('0');
                }
                """,
                timeout=10000,
            )

            closed_first_id = closed_ids[0]
            if await page.get_by_test_id("incident-detail-panel").count() > 0:
                detail_id = await page.get_by_test_id("incident-detail-panel").first.get_attribute(
                    "data-incident-id"
                )
                assert detail_id != closed_first_id, "切换 closed 后不应保留隐藏筛选项外的详情"

            await _select_checkbox_by_incident_id(page, closed_first_id)
            if await page.get_by_test_id("incident-detail-panel").count() > 0:
                detail_id = await page.get_by_test_id("incident-detail-panel").first.get_attribute(
                    "data-incident-id"
                )
                assert detail_id != closed_first_id, "点击 checkbox 不应打开案件详情"

            await page.get_by_test_id("incident-bulk-select-page").first.click()
            await _assert_selected_count(page, len(closed_ids))
            await page.get_by_test_id("incident-add-export-queue").first.click()
            await page.wait_for_function(
                """
                (expected) => {
                    const node = document.querySelector('[data-testid="incident-export-queue-count"]');
                    return node && (node.textContent || '').includes(String(expected));
                }
                """,
                arg=len(closed_ids),
                timeout=10000,
            )

            await page.locator(
                f'[data-testid="incident-list-item"][data-incident-id="{closed_first_id}"]'
            ).first.click()
            await page.get_by_test_id("incident-detail-panel").first.wait_for(
                state="visible",
                timeout=15000,
            )
            assert (
                await page.get_by_test_id("incident-detail-panel").first.get_attribute(
                    "data-incident-id"
                )
            ) == closed_first_id
            await page.get_by_test_id("incident-closure-review-checklist").first.wait_for(
                state="visible",
                timeout=15000,
            )

            fresh_page = page
            await fresh_page.set_viewport_size({"width": 1366, "height": 900})
            await fresh_page.get_by_test_id("dashboard-route-desktop-overview").first.click()
            await fresh_page.wait_for_function(
                """
                () => {
                    const button = document.querySelector('[data-testid="dashboard-route-desktop-overview"]');
                    return button?.getAttribute('aria-current') === 'page';
                }
                """,
                timeout=10000,
            )
            await _go_to_incidents(fresh_page)
            await fresh_page.get_by_test_id("incident-bulk-action-bar").first.wait_for(
                state="visible",
                timeout=15000,
            )
            await _assert_selected_count(fresh_page, 0)
            await fresh_page.wait_for_function(
                """
                () => {
                    const node = document.querySelector('[data-testid="incident-export-queue-count"]');
                    return node && (node.textContent || '').includes('0');
                }
                """,
                timeout=15000,
            )

            storage_before_reload = await _storage_feature_keys(fresh_page)
            diag["storage_before_reload"] = storage_before_reload
            assert storage_before_reload == {"local": [], "session": []}, (
                f"批量选择/导出队列不应写入浏览器 storage: {storage_before_reload}"
            )

            await fresh_page.reload(wait_until="domcontentloaded", timeout=30000)
            await fresh_page.get_by_test_id("dashboard-section-stats").first.wait_for(
                state="visible",
                timeout=30000,
            )

            storage_state = await _storage_feature_keys(fresh_page)
            diag["storage"] = storage_state
            assert storage_state == {"local": [], "session": []}, (
                f"批量选择/导出队列不应写入浏览器 storage: {storage_state}"
            )

            visible_text = await _collect_visible_text(fresh_page)
            forbidden = _contains_forbidden(visible_text)
            diag["forbidden"] = forbidden
            assert forbidden is None, (
                f"Dashboard DOM 出现 forbidden sentinel(命中模式: {forbidden})。"
                f"前 200 字: {visible_text[:200]!r}"
            )

            if clipboard_text:
                clipboard_forbidden = _contains_forbidden(clipboard_text)
                diag["clipboard_forbidden"] = clipboard_forbidden
                assert clipboard_forbidden is None, (
                    f"批量摘要 clipboard 命中 forbidden sentinel: {clipboard_forbidden}"
                )

            print(f"\n[Incident Bulk Selection Export Queue E2E 诊断] {diag}")
        finally:
            if context is not None:
                await context.close()
            await browser.close()
