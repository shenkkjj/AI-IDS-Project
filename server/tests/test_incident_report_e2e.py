"""M3-08 案件证据报告浏览器 E2E（可选，需 ``--run-e2e`` 显式运行）。

设计目标（docs/agent/M3_08_INCIDENT_REPORT_BROWSER_E2E_AND_AGENT_DOCS_CATCHUP_TASK.md
§7-§9）:

- 真实浏览器级验收：注册/登录 -> 触发 Demo 攻击 -> 选中告警 -> 创建案件 ->
  等待案件详情 -> 下载 Markdown 报告 -> 验证报告结构与脱敏 sentinel ->
  点击复制报告 -> 扫描页面 DOM 无 secret / stack / system prompt 泄漏。
- 默认 ``pytest server/tests`` 仍跳过；通过 ``--run-e2e`` 显式触发。
- 缺 playwright / 缺浏览器 / 缺 dev server 都给出明确提示。
- 不依赖真实 LLM API key（无 key 降级态由后端兜底，不影响报告导出）。
- 不依赖公网（仅连本地 dev server）。
- 唯一邮箱,可重入。
- 使用 ``accept_downloads=True`` + 授予 ``clipboard-read`` / ``clipboard-write``。
- 下载报告后读取真实文件内容做断言。
- 最后关闭 browser / context。

运行前置：

1. 启动后端 dev server（默认 :8000）和前端 dev server（默认 :3000）。
2. 安装 Playwright：``pip install playwright && playwright install chromium``。
3. 运行：``pytest server/tests/test_incident_report_e2e.py --run-e2e``。

不在主 ``pytest server/tests`` 基线中运行，避免无 Playwright 环境时全员 fail。
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

# 任何真密钥、stack trace、Guardrails L1 regex、system prompt 触发都不应出现在
# 页面可见 DOM 或下载的报告 markdown 中（security review SC-2 / SC-4）。
# 复用 test_demo_flow_e2e 的 sentinel 集合 + 增加 ``developer:`` 触发,
# 与 M3-07 incident_report_service._REPORT_SENTINEL_PATTERNS 对齐。
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

# 报告 markdown 必含的固定结构（与 incident_report_service.build_incident_report 对齐）
_REQUIRED_REPORT_HEADINGS: tuple[str, ...] = (
    "# 案件证据报告",
    "## 1. 案件摘要",
    "## 2. 关联告警",
    "## 3. 案件时间线",
    "## 4. 安全与脱敏说明",
)

# 案件报告按钮文案（用于检查 status 显示）
_COPY_SUCCESS_MARKERS = ("已复制",)
_COPY_FAIL_MARKERS = ("复制失败", "报告生成失败")
_DOWNLOAD_SUCCESS_MARKERS = ("已下载",)
_DOWNLOAD_FAIL_MARKERS = ("下载失败", "报告生成失败")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _collect_visible_text(page) -> str:
    """读取 body 文本,过滤 script/style/noscript 节点。"""
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
    """命中任一敏感 sentinel 则返回对应 pattern;否则 None。"""
    for pattern in _FORBIDDEN_DOM_PATTERNS:
        if pattern.search(text):
            return pattern.pattern
    return None


async def _trigger_demo_and_get_first_alert_id(page) -> str:
    """触发 Demo 攻击,等待 attack-log-row 出现,点击最新一行后返回 data-alert-id。"""
    # dashboard 首次加载 / next dev 编译 / WS / 数据 fetch 可能耗时较长,
    # 给到 45s 等待 trigger-demo-attack 出现。
    await page.wait_for_selector(
        '[data-testid="trigger-demo-attack"]',
        state="visible",
        timeout=45000,
    )
    await page.get_by_test_id("trigger-demo-attack").click()

    # 等待 attack-log-row 出现(最多 10s 轮询)
    first_row = None
    for _ in range(20):
        rows = await page.query_selector_all('[data-testid="attack-log-row"]')
        if rows:
            first_row = rows[0]
            break
        await page.wait_for_timeout(500)

    assert first_row is not None, "触发 Demo 攻击后告警表未出现新行。"
    alert_id = await first_row.get_attribute("data-alert-id") or ""

    # 选中最新告警,让 AlertDetailPanel 出现 + 暴露 alert-detail-create-incident
    await first_row.click()
    return alert_id


async def _create_incident_from_selected_alert(page) -> None:
    """点击 alert-detail-create-incident,等待案件详情面板出现。"""
    create_btn = page.get_by_test_id("alert-detail-create-incident").first
    await create_btn.wait_for(state="visible", timeout=10000)
    await create_btn.click()

    # 创建后会自动 setRoute("incidents") + loadIncidentDetail;
    # IncidentDetailPanel 上有 data-testid="incident-detail-panel"。
    await page.wait_for_selector(
        '[data-testid="incident-detail-panel"]',
        state="visible",
        timeout=20000,
    )


async def _click_download_report(page) -> tuple[str, str, str]:
    """点击 incident-download-report, expect_download 真实读取文件。

    返回 (suggested_filename, content, file_path)。
    """
    async with page.expect_download(timeout=20000) as download_info:
        await page.get_by_test_id("incident-download-report").first.click()
    download = await download_info.value
    suggested_filename = download.suggested_filename
    file_path = await download.path()
    assert file_path is not None, "Playwright 未返回下载文件路径。"
    content = ""
    with open(file_path, "r", encoding="utf-8") as fh:
        content = fh.read()
    return suggested_filename, content, str(file_path)


async def _click_copy_report_and_get_status(page) -> str:
    """点击 incident-copy-report,等待 incident-report-status 出现可接受文案。"""
    await page.get_by_test_id("incident-copy-report").first.click()

    # 状态文案是短小的"已复制" / "复制失败" / "报告生成失败"。
    # 轮询 incident-report-status 节点,直到文案命中任一 marker(最多 10s)。
    allowed = (
        _COPY_SUCCESS_MARKERS + _COPY_FAIL_MARKERS + _DOWNLOAD_SUCCESS_MARKERS + _DOWNLOAD_FAIL_MARKERS
    )
    status_locator = page.get_by_test_id("incident-report-status")
    final_text = ""
    for _ in range(20):
        count = await status_locator.count()
        if count > 0:
            final_text = (await status_locator.first.inner_text()).strip()
            if any(m in final_text for m in allowed):
                break
        await page.wait_for_timeout(250)
    return final_text


# ---------------------------------------------------------------------------
# Main E2E
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_incident_report_browser_e2e() -> None:
    """M3-08 案件报告浏览器级验收 E2E。

    流程:
        注册 -> 触发 Demo 攻击 -> 创建案件 -> 下载报告 -> 验证 markdown 结构
        与脱敏 sentinel -> 点击复制 -> 扫描页面 DOM 无泄漏。
    """
    skip_without_playwright()
    from playwright.async_api import async_playwright

    diag: dict[str, object] = {
        "registered": False,
        "demo": False,
        "create": False,
        "download": False,
        "copy_status": "",
        "forbidden": None,
        "filename": "",
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
                f"无法启动 chromium 浏览器。请运行 `playwright install chromium`。"
                f"原始错误:{exc}"
            )

        try:
            # accept_downloads + clipboard 权限(本地 http://localhost 被授予)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                accept_downloads=True,
            )
            # grants 只在 chromium 下生效;在权限被拒时复制按钮会走降级。
            try:
                await context.grant_permissions(
                    ["clipboard-read", "clipboard-write"],
                    origin=BASE,
                )
            except Exception:
                # 权限授予失败不致命:复制按钮会显示"复制失败"并降级。
                pass

            page = await context.new_page()

            # 1) 探测 dev server 健康
            await assert_dev_server_reachable(page)

            # 2) 注册唯一用户并自动跳到 /dashboard
            email, _password, register_status = await register_or_login_for_e2e(
                page, "e2e-report"
            )
            diag["registered"] = register_status in {"created", "exists"}

            # 3) 触发 Demo 攻击 + 选中最新告警
            alert_id = await _trigger_demo_and_get_first_alert_id(page)
            diag["demo"] = True

            # 4) 等待 AlertDetailPanel 出现,点击"从此告警创建案件"
            create_btn = page.get_by_test_id("alert-detail-create-incident").first
            await create_btn.wait_for(state="visible", timeout=10000)
            await create_btn.click()

            # 5) M3-09 单一事实源:dashboard-client.tsx 父层持有唯一 useIncidents()
            #    实例并通过 props 传给 IncidentSection。父层 createIncidentFromAlert
            #    + loadIncidentDetail 直接驱动列表 / selectedIncident / detail,
            #    不再需要点击 incident-list-item 兜底。
            #
            #    这里直接等待 detail-panel,严禁回退到列表点击 workaround;
            #    点击兜底就是双 hook race 复发的标志(M3_09 RED A)。
            await page.wait_for_selector(
                '[data-testid="incident-detail-panel"]',
                state="visible",
                timeout=30000,
            )
            diag["create"] = True

            # 5.1) 列表项必须同步 selected 状态:即父层 selectedIncident 已经把
            #     第一行高亮并暴露 data-incident-id。失败说明列表 hook 与 detail
            #     hook 不共享 state(双 useIncidents() race 仍存在)。
            selected_item = page.locator('[data-testid="incident-list-item"]').first
            await selected_item.wait_for(state="visible", timeout=20000)
            list_incident_id = await selected_item.get_attribute("data-incident-id")
            assert list_incident_id, (
                "案件列表项缺少 data-incident-id;父层 useIncidents 未把 selectedIncident "
                "同步到 IncidentSection 列表。"
            )
            detail_panel = page.locator('[data-testid="incident-detail-panel"]').first
            detail_incident_id = await detail_panel.get_attribute("data-incident-id")
            assert detail_incident_id == list_incident_id, (
                f"detail-panel 与 list-item 指向不同 incident_id: "
                f"detail={detail_incident_id!r} list={list_incident_id!r}"
            )

            # 6) 点击"下载报告" -> expect_download
            suggested_filename, markdown, _path = await _click_download_report(page)
            diag["filename"] = suggested_filename
            diag["download"] = True

            # 7) 文件名断言
            assert suggested_filename.startswith("incident-"), (
                f"下载文件名应以 'incident-' 开头,实际 {suggested_filename!r}"
            )
            assert suggested_filename.endswith("-report.md"), (
                f"下载文件名应以 '-report.md' 结尾,实际 {suggested_filename!r}"
            )

            # 8) 报告必含的 4 段结构
            for heading in _REQUIRED_REPORT_HEADINGS:
                assert heading in markdown, (
                    f"报告 markdown 缺少必要标题 {heading!r}。"
                    f"首 200 字:{markdown[:200]!r}"
                )

            # 9) 必含 payload_length / payload_preview 字段
            assert "payload_length" in markdown, "报告缺少 payload_length 字段"
            assert "payload_preview" in markdown, "报告缺少 payload_preview 字段"

            # 10) 报告不含敏感 sentinel / 完整 raw payload / 完整 note
            for pattern in _FORBIDDEN_DOM_PATTERNS:
                match = pattern.search(markdown)
                assert not match, (
                    f"报告 markdown 命中禁止 sentinel: {pattern.pattern} -> "
                    f"...{markdown[max(0, match.start()-20):match.end()+20]!r}..."
                )

            # 11) 点击"复制报告" -> 验证 status 文案命中合法降级
            copy_status = await _click_copy_report_and_get_status(page)
            diag["copy_status"] = copy_status
            allowed = (
                _COPY_SUCCESS_MARKERS + _COPY_FAIL_MARKERS + _DOWNLOAD_SUCCESS_MARKERS + _DOWNLOAD_FAIL_MARKERS
            )
            assert any(m in copy_status for m in allowed), (
                f"复制报告后 incident-report-status 文案异常:{copy_status!r}。"
                f"允许的 marker:{allowed}"
            )

            # 12) 整页 DOM 扫描,禁止出现敏感字面量
            body_text = await _collect_visible_text(page)
            forbidden = _contains_forbidden(body_text)
            diag["forbidden"] = forbidden
            assert forbidden is None, (
                f"Dashboard 出现禁止外泄的内容(命中模式:{forbidden})。"
                f"首 200 字:{body_text[:200]!r}"
            )

            print(
                f"\n[E2E 诊断] alert_id={alert_id!r} "
                f"filename={suggested_filename!r} copy_status={copy_status!r} {diag}"
            )
        finally:
            await context.close()
            await browser.close()
