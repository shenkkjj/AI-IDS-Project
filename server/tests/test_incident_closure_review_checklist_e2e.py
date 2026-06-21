"""M3-18 Incident closure / post-incident review checklist 浏览器 E2E。

覆盖路径：

- 注册 / 登录 Dashboard。
- 触发 Demo 攻击并从最新告警创建案件。
- 验证 M3-17 Evidence Pack Checklist 仍可见。
- 验证案件详情中的 Closure Review Checklist。
- 点击检查报告元信息，只消费已有 report JSON meta。
- 复制安全关闭前复盘摘要，必要时读取 clipboard 验证格式与 forbidden sentinel。
- 使用既有状态控件保存 ``contained`` + 复盘备注，确认新 checklist 不自动关闭案件。
- 下载既有 Markdown 报告，确认 checklist 不破坏报告下载与脱敏。
- 保存桌面 / 移动截图并检查整页横向溢出。

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
ARTIFACT_DIR = Path(
    "docs/runs/artifacts/m3-18-incident-closure-post-incident-review-checklist"
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

_CHECKLIST_IDS: tuple[str, ...] = (
    "closure-check-status-ready",
    "closure-check-evidence-pack",
    "closure-check-report-meta",
    "closure-check-linked-alerts",
    "closure-check-triage-coverage",
    "closure-check-timeline-events",
    "closure-check-final-note",
    "closure-check-missing",
)

_REQUIRED_REPORT_HEADINGS: tuple[str, ...] = (
    "# 案件证据报告",
    "## 1. 案件摘要",
    "## 2. 关联告警",
    "## 3. 案件时间线",
    "## 4. 安全与脱敏说明",
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


async def _trigger_demo_and_create_incident(page) -> str:
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
    last_error = ""
    for _ in range(3):
        try:
            async with page.expect_response(
                lambda response: (
                    "/api/backend/alerts/demo" in response.url
                    and response.request.method == "POST"
                ),
                timeout=8000,
            ) as response_info:
                await trigger.click()

            response = await response_info.value
            body = await response.text()
            assert response.ok, (
                f"Demo 攻击接口返回 HTTP {response.status}: {body[:240]!r}"
            )
            payload = await response.json()
            alert_payload = payload.get("alert") if isinstance(payload, dict) else {}
            if isinstance(alert_payload, dict):
                alert_id = str(
                    alert_payload.get("alert_id")
                    or alert_payload.get("id")
                    or ""
                )
            break
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            await page.wait_for_timeout(750)

    assert alert_id, f"Demo 攻击未生成可识别告警 id: {last_error}"

    first_row = None
    for _ in range(30):
        rows = await page.query_selector_all('[data-testid="attack-log-row"]')
        for row in rows:
            row_alert_id = await row.get_attribute("data-alert-id")
            if row_alert_id == alert_id:
                first_row = row
                break
        if first_row is not None:
            break
        await page.wait_for_timeout(500)
    assert first_row is not None, "触发 Demo 攻击后告警表未出现新行。"

    await first_row.click()

    create_btn = page.get_by_test_id("alert-detail-create-incident").first
    await create_btn.wait_for(state="visible", timeout=10000)
    await create_btn.click()
    await page.wait_for_selector(
        '[data-testid="incident-detail-panel"]',
        state="visible",
        timeout=30000,
    )
    return alert_id


async def _click_copy_summary(page) -> str:
    await page.get_by_test_id("closure-copy-summary").first.click()
    status = page.get_by_test_id("closure-copy-status").first
    final_text = ""
    for _ in range(20):
        if await status.count() > 0:
            final_text = (await status.inner_text()).strip()
            if "已复制" in final_text or "复制失败" in final_text:
                break
        await page.wait_for_timeout(250)
    return final_text


async def _read_clipboard_text(page) -> str:
    try:
        return await page.evaluate("() => navigator.clipboard.readText()")
    except Exception:
        return ""


async def _download_report(page) -> tuple[str, str]:
    async with page.expect_download(timeout=20000) as download_info:
        await page.get_by_test_id("incident-download-report").first.click()
    download = await download_info.value
    suggested_filename = download.suggested_filename
    file_path = await download.path()
    assert file_path is not None, "Playwright 未返回下载文件路径。"
    with open(file_path, "r", encoding="utf-8") as fh:
        return suggested_filename, fh.read()


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


def _assert_report_markdown_safe(markdown: str) -> None:
    for heading in _REQUIRED_REPORT_HEADINGS:
        assert heading in markdown, (
            f"下载 markdown 缺少 {heading!r}。前 400 字: {markdown[:400]!r}"
        )
    assert "payload_length" in markdown, "报告缺少 payload_length 字段"
    assert "payload_preview" in markdown, "报告缺少 payload_preview 字段"
    for pattern in _FORBIDDEN_DOM_PATTERNS:
        match = pattern.search(markdown)
        assert not match, (
            f"下载 markdown 命中 forbidden sentinel: {pattern.pattern} -> "
            f"{markdown[max(0, match.start() - 20):match.end() + 20]!r}"
        )


async def _save_contained_with_review_note(page) -> None:
    await page.get_by_test_id("incident-status-contained").first.click()
    await page.get_by_test_id("incident-note-input").first.fill(
        "post incident review note captured"
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


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_incident_closure_review_checklist_browser_e2e() -> None:
    skip_without_playwright()
    from playwright.async_api import async_playwright

    diag: dict[str, object] = {
        "registered": False,
        "alert_id": "",
        "report_meta": False,
        "copy_status": "",
        "clipboard_checked": False,
        "save_contained": False,
        "filename": "",
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
                page, "e2e-closure-review"
            )
            diag["registered"] = register_status in {"created", "exists"}

            diag["alert_id"] = await _trigger_demo_and_create_incident(page)

            evidence = page.get_by_test_id("incident-evidence-pack-checklist")
            await evidence.first.wait_for(state="visible", timeout=15000)

            checklist = page.get_by_test_id("incident-closure-review-checklist")
            await checklist.first.wait_for(state="visible", timeout=15000)

            for test_id in _CHECKLIST_IDS:
                await page.get_by_test_id(test_id).first.wait_for(
                    state="visible",
                    timeout=10000,
                )

            recommendation = page.get_by_test_id("closure-recommendation").first
            await recommendation.wait_for(state="visible", timeout=10000)
            initial_recommendation = (await recommendation.inner_text()).strip()
            assert initial_recommendation, "关闭建议不能为空。"

            await page.get_by_test_id("closure-refresh-report").first.click()
            report_meta = page.get_by_test_id("closure-report-meta").first
            await report_meta.wait_for(state="visible", timeout=20000)
            diag["report_meta"] = True
            meta_text = await report_meta.inner_text()
            for marker in ("告警", "事件", "脱敏", "截断"):
                assert marker in meta_text, f"报告 meta 缺少 {marker!r}: {meta_text!r}"

            filename = (
                await page.get_by_test_id("closure-report-filename")
                .first.inner_text()
            ).strip()
            diag["filename"] = filename
            assert filename.startswith("incident-")
            assert filename.endswith("-report.md")

            copy_status = await _click_copy_summary(page)
            diag["copy_status"] = copy_status
            assert "已复制" in copy_status or "复制失败" in copy_status, (
                f"复制复盘摘要状态异常: {copy_status!r}"
            )

            clipboard_text = await _read_clipboard_text(page)
            if clipboard_text:
                diag["clipboard_checked"] = True
                for marker in (
                    "AI-CyberSentinel Closure Review",
                    "incident_id=",
                    "status=",
                    "triage_reviewed=",
                    "recommendation=",
                    "missing=",
                ):
                    assert marker in clipboard_text, (
                        f"复盘摘要缺少 {marker!r}: {clipboard_text!r}"
                    )
                clipboard_forbidden = _contains_forbidden(clipboard_text)
                diag["clipboard_forbidden"] = clipboard_forbidden
                assert clipboard_forbidden is None, (
                    f"复盘摘要命中 forbidden sentinel: {clipboard_forbidden}"
                )

            await _save_contained_with_review_note(page)
            diag["save_contained"] = True
            await page.get_by_test_id("incident-detail-refresh").first.click()
            await checklist.first.wait_for(state="visible", timeout=15000)
            updated_recommendation = (await recommendation.inner_text()).strip()
            assert "contained" not in updated_recommendation.lower(), (
                "状态保存为 contained 后，关闭建议不应继续要求先推进到 contained。"
            )

            diag["screenshots"].append(await _screenshot(page, "closure-review-desktop"))

            suggested_filename, markdown = await _download_report(page)
            assert suggested_filename.startswith("incident-")
            assert suggested_filename.endswith("-report.md")
            _assert_report_markdown_safe(markdown)

            visible_text = await _collect_visible_text(page)
            forbidden = _contains_forbidden(visible_text)
            diag["forbidden"] = forbidden
            assert forbidden is None, (
                f"Dashboard DOM 出现 forbidden sentinel(命中模式: {forbidden})。"
                f"前 200 字: {visible_text[:200]!r}"
            )

            await page.set_viewport_size({"width": 390, "height": 844})
            await checklist.first.scroll_into_view_if_needed(timeout=5000)
            await checklist.first.wait_for(state="visible", timeout=10000)
            await _assert_no_horizontal_overflow(page, "mobile closure review")
            diag["screenshots"].append(await _screenshot(page, "closure-review-mobile"))

            print(f"\n[Incident Closure Review Checklist E2E 诊断] {diag}")
        finally:
            if context is not None:
                await context.close()
            await browser.close()
