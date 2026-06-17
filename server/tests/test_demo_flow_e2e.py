"""Demo Flow 浏览器级端到端测试（可选，需 --run-e2e 显式运行）。

设计目标（docs/agent/M2_SOC_OPERATIONS_BASELINE_TASK.md §8-9）：

- 默认 `pytest server/tests` 仍跳过；通过 ``--run-e2e`` 显式触发。
- 缺 playwright / 缺浏览器 / 缺 dev server 都给出明确提示。
- 不依赖真实 LLM API key（专门验证无 key 降级态）。
- 不依赖公网（仅连本地 dev server）。
- 注册 → Dashboard → 触发 Demo 攻击 → 告警表出现 → 分析当前告警
  → 验证 Copilot 降级态 → 验证页面无 stack trace / sk-* / regex 泄漏。

运行前置：

1. 启动后端 dev server（默认 :8000）和前端 dev server（默认 :3000）。
2. 安装 Playwright：``pip install playwright && playwright install chromium``。
3. 运行：``pytest server/tests/test_demo_flow_e2e.py --run-e2e``。
"""
from __future__ import annotations

import os
import re
import time
from importlib.util import find_spec
from typing import Iterable

import pytest

pytestmark = pytest.mark.e2e

BASE = os.getenv("E2E_BASE_URL", "http://localhost:3000")
DEFAULT_PASSWORD = os.getenv("E2E_DEFAULT_PASSWORD", "DemoE2EPass123!")

# 任何真密钥、stack trace、Guardrails L1 regex 都不应出现在用户可见 DOM
# 中（security review SC-2 / SC-4）。这些是 sanity sentinel —— 命中即 fail。
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
    re.compile(r"PRIVATE\s+KEY", re.IGNORECASE),
)


def _skip_without_playwright() -> None:
    if find_spec("playwright") is None:
        pytest.skip(
            "未安装 playwright。运行 `pip install playwright && "
            "playwright install chromium` 后加 --run-e2e 显式执行。"
        )


async def _assert_dev_server_reachable(page) -> None:
    """在浏览器上下文中探测 Next.js API 代理，确保前后端都已就绪。

    失败信息明确指向：需要先启动 dev server。
    """
    try:
        response = await page.request.get(f"{BASE}/api/backend/health", timeout=5000)
    except Exception as exc:  # noqa: BLE001
        pytest.fail(
            f"E2E 前置失败：无法连到 {BASE}/api/backend/health。"
            f"请先启动后端 (:8000) 和前端 (:3000) dev server：\n"
            f"  1) ./.venv/Scripts/python.exe -m uvicorn server.main:app --port 8000\n"
            f"  2) cd web-next && npm run dev\n"
            f"原始错误：{exc}"
        )

    if response.status != 200:
        pytest.fail(
            f"E2E 前置失败：{BASE}/api/backend/health 返回 {response.status}。"
            f"请确认后端 dev server 正在 :8000 运行。"
        )


async def _collect_visible_text(page) -> str:
    """读取 body 文本，过滤 script/style 节点。"""
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
    """命中任一敏感 sentinel 则返回对应 pattern；否则 None。"""
    for pattern in _FORBIDDEN_DOM_PATTERNS:
        if pattern.search(text):
            return pattern.pattern
    return None


def _register_unique_user() -> tuple[str, str]:
    """生成时间戳邮箱，确保测试可重入。"""
    ts = int(time.time() * 1000)
    email = f"e2e-demo-{ts}@example.com"
    return email, DEFAULT_PASSWORD


async def _register_via_ui(page, email: str, password: str) -> None:
    """在前端 UI 上注册并等待自动跳转 /dashboard。"""
    await page.goto(f"{BASE}/", wait_until="domcontentloaded", timeout=15000)
    # Next.js dev server 会持续 HMR / WS,不能依赖 networkidle
    await page.wait_for_load_state("domcontentloaded", timeout=10000)

    # 等 React hydration:page.tsx 是 client component,SSR 输出只是
    # fallback,真正的 form 节点在 client 挂载后才出现。
    # 这里用 wait_for_function 而不是 wait_for_selector,避开 RSC streaming
    # 期间 React unmount 重挂载导致的不可见窗口。
    try:
        await page.wait_for_function(
            "() => document.querySelector('[data-testid=\"login-email\"]') !== null",
            timeout=30000,
        )
    except Exception as exc:  # noqa: BLE001
        # 实在找不到时打印当前 DOM 摘要,方便排查
        body_text = await page.evaluate(
            "() => document.body ? document.body.innerText.slice(0, 500) : ''"
        )
        pytest.fail(
            f"无法等到 login-email hydration 完成（{exc}）。"
            f"body 文本: {body_text!r}"
        )

    # 切到注册模式
    register_toggle = page.get_by_test_id("register-toggle")
    if await register_toggle.count() > 0:
        await register_toggle.first.click()
        await page.wait_for_timeout(500)

    # 注册 + 自动登录后会自动跳到 /dashboard，最多等 12s
    await page.get_by_test_id("login-email").first.fill(email)
    await page.get_by_test_id("login-password").first.fill(password)
    confirm_password = page.get_by_test_id("register-confirm-password")
    if await confirm_password.count() > 0:
        await confirm_password.first.fill(password)

    async with page.expect_navigation(
        url=re.compile(r"/dashboard(\?.*)?$"),
        timeout=20000,
        wait_until="domcontentloaded",
    ):
        await page.get_by_test_id("login-submit").click()


async def _wait_for_demo_button(page) -> None:
    await page.wait_for_selector(
        '[data-testid="trigger-demo-attack"]',
        state="visible",
        timeout=15000,
    )


async def _run_demo_flow() -> dict:
    """Playwright 端到端 Demo Flow 主流程。

    Returns 一个诊断字典，便于测试报告。
    """
    # 缺 playwright 必须先 skip，否则下面的 import 会抛 ModuleNotFoundError
    _skip_without_playwright()

    from playwright.async_api import async_playwright

    diag: dict = {"registered": False, "demo": False, "copilot": False, "triage": False, "forbidden": None}
    email, password = _register_unique_user()

    async with async_playwright() as p:
        launch_options = {"headless": True}
        executable_path = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
        if executable_path:
            launch_options["executable_path"] = executable_path

        try:
            browser = await p.chromium.launch(**launch_options)
        except Exception as exc:  # noqa: BLE001
            pytest.skip(
                f"无法启动 chromium 浏览器。请运行 `playwright install chromium`。"
                f"原始错误：{exc}"
            )

        try:
            context = await browser.new_context(viewport={"width": 1280, "height": 800})
            page = await context.new_page()

            await _assert_dev_server_reachable(page)

            await _register_via_ui(page, email, password)
            diag["registered"] = True

            await _wait_for_demo_button(page)

            # 1) 触发 Demo 攻击
            await page.get_by_test_id("trigger-demo-attack").click()

            # 2) 等待告警表出现新行（最多 10s 轮询）
            demo_row = None
            for _ in range(20):
                rows = await page.query_selector_all('[data-testid="attack-log-row"]')
                if rows:
                    demo_row = rows[0]
                    break
                await page.wait_for_timeout(500)

            assert demo_row is not None, "触发 Demo 攻击后告警表未出现新行。"
            diag["demo"] = True

            # 3) 点击 "分析当前告警"
            analyze_btn = page.get_by_test_id("analyze-current-alert")
            await analyze_btn.wait_for(state="visible", timeout=10000)
            await analyze_btn.click()

            # 4) 等待 Copilot 出现可验证的 assistant 降级消息（最多 15s）
            assistant_text = ""
            for _ in range(30):
                messages = await page.query_selector_all(
                    '[data-testid="copilot-message"][data-role="assistant"]'
                )
                for msg in reversed(messages):
                    text = (await msg.inner_text()).strip()
                    if "API Key" in text or "Base URL" in text:
                        assistant_text = text
                        break
                if assistant_text:
                    break
                await page.wait_for_timeout(500)

            assert assistant_text, "Copilot 未在 15s 内返回可验证的降级态消息。"
            diag["copilot"] = True

            # 5) 验证降级态文案：必须包含 "API Key" 或 "Base URL"
            assert (
                "API Key" in assistant_text or "Base URL" in assistant_text
            ), f"Copilot 降级态文案异常：{assistant_text!r}"

            # 5.5) M3-02 研判状态切换: 选中最新告警 → 切为 investigating → 保存备注
            #      → 验证 attack-log-row 与 triage-status-badge 都更新。
            triage_panel = page.locator('[data-testid="alert-triage-panel"]').first
            if await triage_panel.count() > 0:
                rows = await page.query_selector_all('[data-testid="attack-log-row"]')
                if rows:
                    await rows[0].click()
                    await page.wait_for_timeout(400)
                inv_btn = page.locator('[data-testid="triage-status-investigating"]').first
                if await inv_btn.count() > 0:
                    await inv_btn.click()
                note_input = page.locator('[data-testid="triage-note-input"]').first
                if await note_input.count() > 0:
                    await note_input.fill("E2E 自动研判:已确认 WAF 拦截。")
                save_btn = page.locator('[data-testid="triage-save"]').first
                if await save_btn.count() > 0:
                    await save_btn.click()
                    for _ in range(15):
                        badges = await page.query_selector_all(
                            '[data-testid="triage-status-badge"]'
                        )
                        for badge in badges:
                            status = await badge.get_attribute("data-status")
                            if status == "investigating":
                                diag["triage"] = True
                                break
                        if diag["triage"]:
                            break
                        await page.wait_for_timeout(500)
                # 攻击日志行的 data-triage-status 也必须更新
                row_with_triage = await page.query_selector(
                    '[data-testid="attack-log-row"][data-triage-status="investigating"]'
                )
                assert row_with_triage is not None, (
                    "保存研判后 attack-log-row 的 data-triage-status 未更新为 investigating"
                )

            # 6) 整页扫描，禁止出现敏感字面量
            body_text = await _collect_visible_text(page)
            forbidden = _contains_forbidden(body_text)
            diag["forbidden"] = forbidden
            assert forbidden is None, (
                f"Dashboard 出现禁止外泄的内容（命中模式：{forbidden}）。"
                f"首 200 字：{body_text[:200]!r}"
            )
        finally:
            await browser.close()

    return diag


@pytest.mark.asyncio
async def test_demo_flow_e2e_browser():
    """Demo Flow 完整浏览器级 E2E：注册 → 触发 → 分析 → 降级态。"""
    diag = await _run_demo_flow()
    # 让测试输出在 -v 模式下可见
    print(f"\n[E2E 诊断] {diag}")
