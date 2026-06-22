"""M3-21 Incident Workspace keyboard navigation / accessibility 浏览器 E2E。

覆盖路径：

- 登录 Dashboard。
- 通过现有 UI 创建 contained 案件样本。
- 使用键盘完成状态筛选、列表 checkbox 选择、列表项 Enter 打开详情。
- 验证 status / severity radiogroup 方向键导航、保存、报告预览焦点进入与 Escape 焦点恢复。
- 使用键盘触发 Evidence Pack / Closure Review 刷新与复制、批量复制、导出队列加入与清空。
- 执行 accessible name、重复 id、storage、DOM / clipboard forbidden sentinel audit。
- 保存桌面 / 移动截图。

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
ARTIFACT_DIR = Path("docs/runs/artifacts/m3-21-incident-workspace-accessibility")

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

_COPY_DONE_MARKERS = ("已复制", "复制失败")


async def _collect_visible_text(page) -> str:
    return await page.evaluate(
        """
        () => {
            const body = document.body;
            if (!body) return '';
            const clone = body.cloneNode(true);
            clone.querySelectorAll('script, style, noscript').forEach((node) => node.remove());
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
        f"M3-21 contained {incident_id[-6:]}"
    )
    await page.get_by_test_id("incident-status-contained").first.click()
    await page.get_by_test_id("incident-note-input").first.fill(
        "m3-21 keyboard accessibility contained sample"
    )
    await page.get_by_test_id("incident-save").first.click()
    await page.wait_for_function(
        """
        () => {
            const panel = document.querySelector('[data-testid="incident-detail-panel"]');
            const active = document.querySelector('[data-testid="incident-status-contained"]');
            return panel
                && panel.innerText.includes('已保存')
                && active?.getAttribute('aria-checked') === 'true';
        }
        """,
        timeout=15000,
    )
    return incident_id


async def _go_to_incidents(page) -> None:
    route = page.get_by_test_id("dashboard-route-desktop-incidents").first
    await route.wait_for(state="visible", timeout=30000)
    await route.scroll_into_view_if_needed(timeout=5000)
    await route.click()
    await page.wait_for_function(
        """
        () => {
            const button = document.querySelector('[data-testid="dashboard-route-desktop-incidents"]');
            return button?.getAttribute('aria-current') === 'page';
        }
        """,
        timeout=15000,
    )
    await page.get_by_test_id("incident-section").first.wait_for(
        state="visible",
        timeout=30000,
    )


async def _go_to_mobile_incidents(page) -> None:
    route = page.get_by_test_id("dashboard-route-mobile-incidents").first
    await route.wait_for(state="visible", timeout=30000)
    await route.scroll_into_view_if_needed(timeout=5000)
    await route.click()
    await page.wait_for_function(
        """
        () => {
            const button = document.querySelector('[data-testid="dashboard-route-mobile-incidents"]');
            return button?.getAttribute('aria-current') === 'page';
        }
        """,
        timeout=15000,
    )
    await page.get_by_test_id("incident-section").first.wait_for(
        state="visible",
        timeout=30000,
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


async def _checkbox_for_incident(page, incident_id: str):
    row = page.locator(
        f'[data-testid="incident-list-item"][data-incident-id="{incident_id}"]'
    ).first
    await row.wait_for(state="visible", timeout=10000)
    checkbox = row.locator(
        'xpath=preceding-sibling::input[@data-testid="incident-select-checkbox"]'
    ).first
    await checkbox.wait_for(state="visible", timeout=5000)
    return checkbox


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


async def _press_button_and_wait_status(page, button_test_id: str, status_test_id: str) -> str:
    button = page.get_by_test_id(button_test_id).first
    await button.wait_for(state="visible", timeout=10000)
    await button.focus()
    await page.keyboard.press("Enter")
    status = page.get_by_test_id(status_test_id).first
    final_text = ""
    for _ in range(30):
        final_text = (await status.inner_text()).strip()
        if any(marker in final_text for marker in _COPY_DONE_MARKERS):
            break
        await page.wait_for_timeout(250)
    assert any(marker in final_text for marker in _COPY_DONE_MARKERS), (
        f"{button_test_id} 触发后状态异常: {final_text!r}"
    )
    return final_text


async def _read_clipboard_text(page) -> str:
    try:
        return await page.evaluate("() => navigator.clipboard.readText()")
    except Exception:
        return ""


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


async def _accessible_name_audit(page) -> list[dict[str, str]]:
    return await page.evaluate(
        """
        () => {
            const root = document.querySelector('[data-testid="incident-section"]');
            if (!root) return [{ testId: 'incident-section', tag: 'missing', text: '' }];
            const selector = [
                'button',
                'input',
                'textarea',
                'select',
                '[role="button"]',
                '[role="radio"]',
                '[tabindex]:not([tabindex="-1"])',
            ].join(',');
            const visible = (node) => {
                const style = window.getComputedStyle(node);
                const rect = node.getBoundingClientRect();
                return style.display !== 'none'
                    && style.visibility !== 'hidden'
                    && rect.width > 0
                    && rect.height > 0;
            };
            const valueOf = (node) => {
                if (node instanceof HTMLInputElement || node instanceof HTMLTextAreaElement) {
                    return node.value || '';
                }
                return node.getAttribute('value') || '';
            };
            return Array.from(root.querySelectorAll(selector))
                .filter(visible)
                .filter((node) => {
                    const ariaLabel = node.getAttribute('aria-label') || '';
                    const labelledBy = node.getAttribute('aria-labelledby') || '';
                    const title = node.getAttribute('title') || '';
                    const text = node.textContent || '';
                    const placeholder = node.getAttribute('placeholder') || '';
                    const value = valueOf(node);
                    return !(ariaLabel || labelledBy || title || text.trim() || placeholder || value);
                })
                .map((node) => ({
                    testId: node.getAttribute('data-testid') || '',
                    tag: node.tagName,
                    role: node.getAttribute('role') || '',
                }));
        }
        """
    )


async def _duplicate_id_audit(page) -> list[str]:
    return await page.evaluate(
        """
        () => {
            const root = document.querySelector('[data-testid="incident-section"]');
            if (!root) return ['missing incident-section'];
            const seen = new Set();
            const dupes = new Set();
            for (const node of root.querySelectorAll('[id]')) {
                const id = node.getAttribute('id');
                if (!id) continue;
                if (seen.has(id)) dupes.add(id);
                seen.add(id);
            }
            return Array.from(dupes);
        }
        """
    )


async def _storage_feature_keys(page) -> dict[str, list[str]]:
    return await page.evaluate(
        """
        () => {
            const matches = (key) =>
                /incident-accessibility|incident-keyboard|incident-bulk|incident-export|incident-focus/i.test(key);
            return {
                local: Object.keys(window.localStorage).filter(matches),
                session: Object.keys(window.sessionStorage).filter(matches),
            };
        }
        """
    )


async def _assert_tab_focus_stays_in_view(page, steps: int = 12) -> None:
    await page.get_by_test_id("incident-filter-contained").first.focus()
    offenders: list[dict[str, object]] = []
    for index in range(steps):
        await page.keyboard.press("Tab")
        result = await page.evaluate(
            """
            (index) => {
                const node = document.activeElement;
                if (!(node instanceof HTMLElement) || node === document.body) {
                    return null;
                }
                const rect = node.getBoundingClientRect();
                const ok = rect.bottom >= -4
                    && rect.top <= window.innerHeight + 4
                    && rect.right >= -4
                    && rect.left <= window.innerWidth + 4;
                if (ok) return null;
                return {
                    index,
                    testId: node.getAttribute('data-testid') || '',
                    tag: node.tagName,
                    top: rect.top,
                    bottom: rect.bottom,
                    left: rect.left,
                    right: rect.right,
                };
            }
            """,
            arg=index,
        )
        if result:
            offenders.append(result)
    assert offenders == [], f"Tab 导航后焦点不在 viewport 内: {offenders}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_incident_workspace_keyboard_navigation_accessibility_browser_e2e() -> None:
    skip_without_playwright()
    from playwright.async_api import async_playwright

    diag: dict[str, object] = {
        "registered": False,
        "incident_id": "",
        "checkbox_aria": "",
        "preview_focus": "",
        "restore_focus": "",
        "evidence_copy_status": "",
        "closure_copy_status": "",
        "bulk_copy_status": "",
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
                page, "e2e-incident-accessibility"
            )
            diag["registered"] = register_status in {"created", "exists"}

            incident_id = await _trigger_demo_and_create_incident(
                page, "contained"
            )
            diag["incident_id"] = incident_id

            await _go_to_incidents(page)
            await page.get_by_test_id("incident-status-filter-bar").first.wait_for(
                state="visible",
                timeout=15000,
            )

            filter_button = page.get_by_test_id("incident-filter-contained").first
            await filter_button.focus()
            await page.keyboard.press("Enter")
            await page.wait_for_function(
                """
                () => {
                    const button = document.querySelector('[data-testid="incident-filter-contained"]');
                    const summary = document.querySelector('[data-testid="incident-filter-summary"]');
                    return button?.getAttribute('aria-pressed') === 'true'
                        && summary
                        && !summary.textContent.includes('加载中');
                }
                """,
                timeout=20000,
            )
            ids = await _wait_for_list_ready(page)
            assert incident_id in ids, (
                f"contained 筛选后应包含本轮样本 {incident_id}, 实际 {ids}"
            )

            checkbox = await _checkbox_for_incident(page, incident_id)
            checkbox_aria = await checkbox.get_attribute("aria-label")
            diag["checkbox_aria"] = checkbox_aria
            assert checkbox_aria and incident_id in checkbox_aria, (
                f"checkbox aria-label 应包含 incident_id, 实际 {checkbox_aria!r}"
            )
            assert "M3-21 contained" not in checkbox_aria, (
                f"checkbox aria-label 不应包含完整 title 正文: {checkbox_aria!r}"
            )

            await checkbox.focus()
            await page.keyboard.press("Space")
            assert await checkbox.is_checked(), "Space 聚焦 checkbox 时应只切换选中状态。"
            await _assert_selected_count(page, 1)

            await page.keyboard.press("Tab")
            active_after_tab = await page.evaluate(
                """
                () => ({
                    testId: document.activeElement?.getAttribute('data-testid') || '',
                    incidentId: document.activeElement?.getAttribute('data-incident-id') || '',
                })
                """
            )
            assert active_after_tab == {
                "testId": "incident-list-item",
                "incidentId": incident_id,
            }, f"checkbox 后 Tab 应进入对应列表项按钮, 实际 {active_after_tab!r}"

            await page.keyboard.press("Enter")
            detail = page.get_by_test_id("incident-detail-panel").first
            await detail.wait_for(state="visible", timeout=15000)
            assert await detail.get_attribute("data-incident-id") == incident_id
            row_button = page.locator(
                f'[data-testid="incident-list-item"][data-incident-id="{incident_id}"]'
            ).first
            current = await row_button.get_attribute("aria-current")
            selected = await row_button.get_attribute("aria-selected")
            assert current or selected, "当前详情案件应通过 aria-current 或 aria-selected 暴露。"

            status_contained = page.get_by_test_id("incident-status-contained").first
            await status_contained.focus()
            await page.keyboard.press("ArrowRight")
            await page.wait_for_function(
                """
                () => document
                    .querySelector('[data-testid="incident-status-resolved"]')
                    ?.getAttribute('aria-checked') === 'true'
                """,
                timeout=5000,
            )

            severity_group = page.locator('[role="radiogroup"][aria-label="事件严重度"]').first
            active_severity = severity_group.locator('[role="radio"][aria-checked="true"]').first
            before_severity = await active_severity.get_attribute("data-testid")
            await active_severity.focus()
            await page.keyboard.press("ArrowRight")
            await page.wait_for_function(
                """
                (before) => {
                    const active = document.querySelector(
                        '[role="radiogroup"][aria-label="事件严重度"] [role="radio"][aria-checked="true"]'
                    );
                    return active && active.getAttribute('data-testid') !== before;
                }
                """,
                arg=before_severity,
                timeout=5000,
            )

            save = page.get_by_test_id("incident-save").first
            await save.focus()
            await page.keyboard.press("Enter")
            await page.wait_for_function(
                """
                () => {
                    const panel = document.querySelector('[data-testid="incident-detail-panel"]');
                    return panel && panel.innerText.includes('已保存');
                }
                """,
                timeout=15000,
            )

            preview_button = page.get_by_test_id("incident-preview-report").first
            await preview_button.focus()
            await page.keyboard.press("Enter")
            await page.get_by_test_id("incident-report-preview").first.wait_for(
                state="visible",
                timeout=20000,
            )
            preview_focus = await page.evaluate(
                "() => document.activeElement?.getAttribute('data-testid') || ''"
            )
            diag["preview_focus"] = preview_focus
            assert preview_focus in {
                "incident-report-preview",
                "incident-report-preview-close",
            }, f"打开预览后焦点应进入 preview 或 close button, 实际 {preview_focus!r}"

            await page.keyboard.press("Escape")
            await page.get_by_test_id("incident-report-preview").first.wait_for(
                state="detached",
                timeout=10000,
            )
            restore_focus = await page.evaluate(
                "() => document.activeElement?.getAttribute('data-testid') || ''"
            )
            diag["restore_focus"] = restore_focus
            assert restore_focus == "incident-preview-report", (
                f"Escape 关闭预览后焦点应回到预览按钮, 实际 {restore_focus!r}"
            )

            refresh_evidence = page.get_by_test_id("evidence-pack-refresh-report").first
            await refresh_evidence.focus()
            await page.keyboard.press("Enter")
            await page.get_by_test_id("evidence-pack-report-meta").first.wait_for(
                state="visible",
                timeout=20000,
            )
            diag["evidence_copy_status"] = await _press_button_and_wait_status(
                page,
                "evidence-pack-copy-summary",
                "evidence-pack-copy-status",
            )

            refresh_closure = page.get_by_test_id("closure-refresh-report").first
            await refresh_closure.focus()
            await page.keyboard.press("Enter")
            await page.get_by_test_id("closure-report-meta").first.wait_for(
                state="visible",
                timeout=20000,
            )
            diag["closure_copy_status"] = await _press_button_and_wait_status(
                page,
                "closure-copy-summary",
                "closure-copy-status",
            )

            diag["bulk_copy_status"] = await _press_button_and_wait_status(
                page,
                "incident-bulk-copy-summary",
                "incident-bulk-copy-status",
            )
            add_to_queue = page.get_by_test_id("incident-add-export-queue").first
            await add_to_queue.focus()
            await page.keyboard.press("Enter")
            await page.wait_for_function(
                """
                () => {
                    const node = document.querySelector('[data-testid="incident-export-queue-count"]');
                    return node && (node.textContent || '').includes('1');
                }
                """,
                timeout=10000,
            )
            clear_queue = page.get_by_test_id("incident-export-queue-clear").first
            await clear_queue.focus()
            await page.keyboard.press("Enter")
            await page.wait_for_function(
                """
                () => {
                    const node = document.querySelector('[data-testid="incident-export-queue-count"]');
                    return node && (node.textContent || '').includes('0');
                }
                """,
                timeout=10000,
            )

            accessible_name_offenders = await _accessible_name_audit(page)
            assert accessible_name_offenders == [], (
                f"incident-section 存在无 accessible name 的交互元素: {accessible_name_offenders}"
            )
            duplicate_ids = await _duplicate_id_audit(page)
            assert duplicate_ids == [], f"incident-section 内存在重复 id: {duplicate_ids}"
            await _assert_tab_focus_stays_in_view(page)
            await _assert_no_horizontal_overflow(page, "desktop accessibility")

            storage = await _storage_feature_keys(page)
            diag["storage"] = storage
            assert storage == {"local": [], "session": []}, (
                f"M3-21 keyboard/a11y 不应写入浏览器 storage: {storage}"
            )

            visible_text = await _collect_visible_text(page)
            forbidden = _contains_forbidden(visible_text)
            diag["forbidden"] = forbidden
            assert forbidden is None, (
                f"Dashboard DOM 出现 forbidden sentinel(命中模式: {forbidden})。"
                f"前 200 字: {visible_text[:200]!r}"
            )

            clipboard_text = await _read_clipboard_text(page)
            if clipboard_text:
                clipboard_forbidden = _contains_forbidden(clipboard_text)
                diag["clipboard_forbidden"] = clipboard_forbidden
                assert clipboard_forbidden is None, (
                    f"clipboard 命中 forbidden sentinel: {clipboard_forbidden}"
                )

            diag["screenshots"].append(await _screenshot(page, "accessibility-desktop"))

            await page.set_viewport_size({"width": 390, "height": 844})
            await _go_to_mobile_incidents(page)
            await _assert_no_horizontal_overflow(page, "mobile accessibility")
            diag["screenshots"].append(await _screenshot(page, "accessibility-mobile"))

            print(f"\n[Incident Workspace Accessibility E2E 诊断] {diag}")
        finally:
            if context is not None:
                await context.close()
            await browser.close()
