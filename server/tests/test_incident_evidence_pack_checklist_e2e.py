"""M3-17 Incident / Alert evidence pack checklist 浏览器 E2E。

覆盖路径：

- 注册 / 登录 Dashboard。
- 触发 Demo 攻击并从最新告警创建案件。
- 验证案件详情中的 Evidence Pack Checklist。
- 点击检查报告元信息，只消费已有 report JSON meta。
- 复制安全证据包摘要，必要时读取 clipboard 验证格式与 forbidden sentinel。
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
    "docs/runs/artifacts/m3-17-incident-alert-evidence-pack-checklist"
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
    "evidence-pack-check-report",
    "evidence-pack-check-linked-alerts",
    "evidence-pack-check-timeline",
    "evidence-pack-check-triage",
    "evidence-pack-check-redaction",
    "evidence-pack-check-missing",
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
    await page.wait_for_selector(
        '[data-testid="trigger-demo-attack"]',
        state="visible",
        timeout=45000,
    )
    await page.get_by_test_id("trigger-demo-attack").click()

    first_row = None
    for _ in range(20):
        rows = await page.query_selector_all('[data-testid="attack-log-row"]')
        if rows:
            first_row = rows[0]
            break
        await page.wait_for_timeout(500)
    assert first_row is not None, "触发 Demo 攻击后告警表未出现新行。"

    alert_id = await first_row.get_attribute("data-alert-id") or ""
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
    await page.get_by_test_id("evidence-pack-copy-summary").first.click()
    status = page.get_by_test_id("evidence-pack-copy-status").first
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


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_incident_evidence_pack_checklist_browser_e2e() -> None:
    skip_without_playwright()
    from playwright.async_api import async_playwright

    diag: dict[str, object] = {
        "registered": False,
        "alert_id": "",
        "report_meta": False,
        "copy_status": "",
        "clipboard_checked": False,
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
                page, "e2e-evidence-pack"
            )
            diag["registered"] = register_status in {"created", "exists"}

            diag["alert_id"] = await _trigger_demo_and_create_incident(page)

            checklist = page.get_by_test_id("incident-evidence-pack-checklist")
            await checklist.first.wait_for(state="visible", timeout=15000)

            for test_id in _CHECKLIST_IDS:
                await page.get_by_test_id(test_id).first.wait_for(
                    state="visible",
                    timeout=10000,
                )

            await page.get_by_test_id("evidence-pack-refresh-report").first.click()
            report_meta = page.get_by_test_id("evidence-pack-report-meta").first
            await report_meta.wait_for(state="visible", timeout=20000)
            diag["report_meta"] = True
            meta_text = await report_meta.inner_text()
            for marker in ("告警", "事件", "脱敏", "截断"):
                assert marker in meta_text, f"报告 meta 缺少 {marker!r}: {meta_text!r}"

            filename = (
                await page.get_by_test_id("evidence-pack-report-filename")
                .first.inner_text()
            ).strip()
            diag["filename"] = filename
            assert filename.startswith("incident-")
            assert filename.endswith("-report.md")

            copy_status = await _click_copy_summary(page)
            diag["copy_status"] = copy_status
            assert "已复制" in copy_status or "复制失败" in copy_status, (
                f"复制证据包摘要状态异常: {copy_status!r}"
            )

            clipboard_text = await _read_clipboard_text(page)
            if clipboard_text:
                diag["clipboard_checked"] = True
                for marker in (
                    "AI-CyberSentinel Evidence Pack",
                    "incident_id=",
                    "linked_alerts=",
                    "triage_reviewed=",
                    "redactions=",
                ):
                    assert marker in clipboard_text, (
                        f"复制摘要缺少 {marker!r}: {clipboard_text!r}"
                    )
                clipboard_forbidden = _contains_forbidden(clipboard_text)
                diag["clipboard_forbidden"] = clipboard_forbidden
                assert clipboard_forbidden is None, (
                    f"复制摘要命中 forbidden sentinel: {clipboard_forbidden}"
                )

            diag["screenshots"].append(await _screenshot(page, "evidence-pack-desktop"))

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
            await _assert_no_horizontal_overflow(page, "mobile evidence pack")
            diag["screenshots"].append(await _screenshot(page, "evidence-pack-mobile"))

            print(f"\n[Incident Evidence Pack Checklist E2E 诊断] {diag}")
        finally:
            if context is not None:
                await context.close()
            await browser.close()
