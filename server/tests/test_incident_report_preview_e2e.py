"""M3-14 案件报告预览 UX 浏览器 E2E（可选，需 ``--run-e2e``）。

覆盖路径：

- 注册 / 登录 Dashboard。
- 触发 Demo 攻击并从最新告警创建案件。
- 点击 ``预览报告``，验证内联预览面板展示文件名、报告 meta、固定结构、
  ``payload_preview`` 与脱敏 / 截断说明。
- 预览打开时继续验证复制 / 下载报告可用。
- 桌面与移动截图落盘。
- 按 Escape / 关闭按钮可关闭预览，整页 DOM 不含 forbidden sentinel。

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
ARTIFACT_DIR = Path("docs/runs/artifacts/m3-14-incident-report-preview")

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

_REQUIRED_REPORT_BODY_TEXT: tuple[str, ...] = (
    "案件证据报告",
    "案件摘要",
    "关联告警",
    "案件时间线",
    "安全与脱敏说明",
    "payload_preview",
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


async def _download_report(page) -> tuple[str, str]:
    async with page.expect_download(timeout=20000) as download_info:
        await page.get_by_test_id("incident-download-report").first.click()
    download = await download_info.value
    suggested_filename = download.suggested_filename
    file_path = await download.path()
    assert file_path is not None, "Playwright 未返回下载文件路径。"
    with open(file_path, "r", encoding="utf-8") as fh:
        return suggested_filename, fh.read()


async def _click_copy_report(page) -> str:
    await page.get_by_test_id("incident-copy-report").first.click()
    status_locator = page.get_by_test_id("incident-report-status")
    allowed = ("已复制", "复制失败", "报告生成失败", "已下载", "下载失败")
    final_text = ""
    for _ in range(20):
        if await status_locator.count() > 0:
            final_text = (await status_locator.first.inner_text()).strip()
            if any(marker in final_text for marker in allowed):
                break
        await page.wait_for_timeout(250)
    return final_text


async def _screenshot(page, name: str) -> str:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / f"{name}.png"
    await page.screenshot(path=str(path), full_page=True)
    return str(path)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_incident_report_preview_browser_e2e() -> None:
    skip_without_playwright()
    from playwright.async_api import async_playwright

    diag: dict[str, object] = {
        "registered": False,
        "alert_id": "",
        "preview": False,
        "copy_status": "",
        "filename": "",
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
                viewport={"width": 1280, "height": 800},
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
                page, "e2e-report-preview"
            )
            diag["registered"] = register_status in {"created", "exists"}

            diag["alert_id"] = await _trigger_demo_and_create_incident(page)

            preview_button = page.get_by_test_id("incident-preview-report").first
            await preview_button.wait_for(state="visible", timeout=10000)
            await preview_button.click()

            preview = page.get_by_test_id("incident-report-preview")
            await preview.wait_for(state="visible", timeout=20000)
            diag["preview"] = True

            filename = (
                await page.get_by_test_id("incident-report-preview-filename")
                .first.inner_text()
            ).strip()
            diag["filename"] = filename
            assert filename.startswith("incident-"), (
                f"预览文件名应以 incident- 开头，实际 {filename!r}"
            )
            assert filename.endswith("-report.md"), (
                f"预览文件名应以 -report.md 结尾，实际 {filename!r}"
            )

            meta_text = (
                await page.get_by_test_id("incident-report-preview-meta")
                .first.inner_text()
            )
            for marker in ("告警", "事件", "脱敏", "截断"):
                assert marker in meta_text, f"预览 meta 缺少 {marker!r}: {meta_text!r}"

            body_text = (
                await page.get_by_test_id("incident-report-preview-body")
                .first.inner_text()
            )
            for marker in _REQUIRED_REPORT_BODY_TEXT:
                assert marker in body_text, (
                    f"预览 markdown 片段缺少 {marker!r}。前 400 字: {body_text[:400]!r}"
                )
            assert "已脱敏" in body_text or "脱敏" in body_text, (
                "预览正文必须说明报告已脱敏。"
            )
            assert "截断" in body_text, "预览正文必须说明截断状态。"

            diag["screenshots"].append(
                await _screenshot(page, "incident-report-preview-desktop")
            )
            await page.set_viewport_size({"width": 390, "height": 844})
            await preview.wait_for(state="visible", timeout=10000)
            overflow = await page.evaluate(
                """
                () => Math.max(
                    document.documentElement.scrollWidth - document.documentElement.clientWidth,
                    document.body ? document.body.scrollWidth - document.body.clientWidth : 0
                )
                """
            )
            assert overflow <= 4, f"移动端报告预览产生横向溢出: {overflow}"
            diag["screenshots"].append(
                await _screenshot(page, "incident-report-preview-mobile")
            )

            copy_status = await _click_copy_report(page)
            diag["copy_status"] = copy_status
            assert any(
                marker in copy_status
                for marker in ("已复制", "复制失败", "报告生成失败", "已下载")
            ), f"复制报告后状态文案异常: {copy_status!r}"

            suggested_filename, markdown = await _download_report(page)
            assert suggested_filename.startswith("incident-")
            assert suggested_filename.endswith("-report.md")
            for marker in _REQUIRED_REPORT_BODY_TEXT:
                assert marker in markdown, (
                    f"下载 markdown 缺少 {marker!r}。前 400 字: {markdown[:400]!r}"
                )
            for pattern in _FORBIDDEN_DOM_PATTERNS:
                match = pattern.search(markdown)
                assert not match, (
                    f"下载 markdown 命中 forbidden sentinel: {pattern.pattern} -> "
                    f"{markdown[max(0, match.start() - 20):match.end() + 20]!r}"
                )

            await page.keyboard.press("Escape")
            await preview.wait_for(state="hidden", timeout=5000)

            await page.get_by_test_id("incident-preview-report").first.click()
            await preview.wait_for(state="visible", timeout=10000)
            await page.get_by_test_id("incident-report-preview-close").first.click()
            await preview.wait_for(state="hidden", timeout=5000)

            visible_text = await _collect_visible_text(page)
            forbidden = _contains_forbidden(visible_text)
            diag["forbidden"] = forbidden
            assert forbidden is None, (
                f"Dashboard DOM 出现 forbidden sentinel(命中模式: {forbidden})。"
                f"前 200 字: {visible_text[:200]!r}"
            )

            print(f"\n[Incident Report Preview E2E 诊断] {diag}")
        finally:
            if context is not None:
                await context.close()
            await browser.close()
