"""NEXT-01 最小 Auth Session E2E（可选，需 ``--run-e2e`` 显式运行）。

目标(`docs/agent/NEXT_01_AUTH_SESSION_LOADING_E2E_RECOVERY_TASK.md` §8):

- RED: 在 main 上复现 next-auth 5 beta + Next.js 15 dev 下 Dashboard 登录后
  ``useSession`` 永 ``loading`` / ``SYSTEM · LOADING`` 不消失的阻塞。
- GREEN: 修复后, 登录用户应在 45s 内看到 ``[data-testid="trigger-demo-attack"]``,
  ``SYSTEM · LOADING`` 不持续, ``/api/auth/session`` 返回 user, DOM 无 secret /
  stack / system prompt 泄漏。

本测试只验证 "登录后 Dashboard 能解除 loading 并显示主按钮", 不掺案件报告流程,
让 RED 信号尽量小。

运行前置:

1. 启动后端 dev server (默认 :8000) 和前端 dev server (默认 :3000)。
2. 安装 Playwright: ``pip install playwright && playwright install chromium``。
3. 运行: ``pytest server/tests/test_auth_session_e2e.py --run-e2e``。

默认 ``pytest server/tests`` 跳过, ``--run-e2e`` 显式触发。
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

# 任何真密钥 / stack trace / Guardrails L1 regex / system prompt 触发都不应
# 出现在用户可见 DOM 中（与 test_incident_report_e2e / test_demo_flow_e2e 对齐）。
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
    """读取 body 文本, 过滤 script/style/noscript 节点。"""
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


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_dashboard_session_unblocks_after_login() -> None:
    """登录后 Dashboard 应在 45s 内显示 ``trigger-demo-attack``,
    ``SYSTEM · LOADING`` 不持续, ``/api/auth/session`` 返回 user。
    """
    skip_without_playwright()
    from playwright.async_api import async_playwright

    diag: dict[str, object] = {
        "registered": False,
        "dashboard_url": False,
        "trigger_demo_visible": False,
        "loading_text_persisted": True,
        "session_user_email": "",
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
                f"无法启动 chromium 浏览器。请运行 `playwright install chromium`。"
                f"原始错误: {exc}"
            )

        try:
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()

            await assert_dev_server_reachable(page)

            email, _password, register_status = await register_or_login_for_e2e(
                page, "e2e-auth"
            )
            diag["registered"] = register_status in {"created", "exists"}
            diag["dashboard_url"] = True

            try:
                await page.wait_for_selector(
                    '[data-testid="trigger-demo-attack"]',
                    state="visible",
                    timeout=45000,
                )
            except Exception as exc:  # noqa: BLE001
                body_text = await page.evaluate(
                    "() => document.body ? document.body.innerText.slice(0, 500) : ''"
                )
                pytest.fail(
                    f"登录后 45s 内未看到 trigger-demo-attack ({exc})。"
                    f"这通常是 useSession() 永 loading 卡住 dashboard 渲染。"
                    f"body 文本: {body_text!r}"
                )
            diag["trigger_demo_visible"] = True

            visible_text = await _collect_visible_text(page)
            loading_persisted = "SYSTEM · LOADING" in visible_text
            diag["loading_text_persisted"] = loading_persisted
            assert not loading_persisted, (
                "Dashboard 解除 loading 后, 不应再有 'SYSTEM · LOADING' 文案。"
                f"前 200 字: {visible_text[:200]!r}"
            )

            session_resp = await page.request.get(
                f"{BASE}/api/auth/session", timeout=10000
            )
            assert session_resp.status == 200, (
                f"/api/auth/session 应该 200, 实际 {session_resp.status}"
            )
            session_json = await session_resp.json()
            user = (session_json or {}).get("user") or {}
            user_email = str(user.get("email") or "")
            diag["session_user_email"] = user_email
            assert user_email == email, (
                f"/api/auth/session 应返回 user.email={email!r}, 实际 {user_email!r}"
            )

            forbidden = _contains_forbidden(visible_text)
            diag["forbidden"] = forbidden
            assert forbidden is None, (
                f"Dashboard 出现禁止外泄的内容(命中模式: {forbidden})。"
                f"前 200 字: {visible_text[:200]!r}"
            )

            print(f"\n[E2E 诊断] {diag}")
        finally:
            await context.close()
            await browser.close()
