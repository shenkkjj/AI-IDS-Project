# M3-12 Demo Flow E2E Stability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:systematic-debugging` first, then use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 M3-11 暴露的 Demo Flow Copilot fallback 串跑偶发 15s 超时，收口成可诊断、可重复、不过度放宽断言的稳定浏览器 E2E。

**Architecture:** 先复现并采集证据，确认失败发生在账号前置、Demo 告警生成、`analyze-current-alert` 点击、`/copilot/stream` SSE、前端 SSE 解析还是 DOM 渲染层。再把 `test_demo_flow_e2e.py` 的 15s 手写轮询改成可复用的条件等待 + 失败 artifact；新增稳定化 E2E 验证同一浏览器会话内连续两次 Demo 分析，以及 Auth/Demo/Incident/Dashboard/Responsive 五条关键 E2E 串跑。只允许测试层、运行日志、必要的轻量测试可观测性改动；默认不改生产 Copilot、认证、Guardrails、SSRF、DB schema 或速率限制常量。

**Tech Stack:** pytest, Playwright async Python API, FastAPI dev server, Next.js Dashboard, existing `server/tests/e2e_helpers.py`, SSE over `/api/backend/copilot/stream`.

---

## 0. 必读上下文

执行前必须完整阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/runs/2026-06-19-m3-11-dashboard-section-responsive-qa.md`
- `docs/agent/M3_11_DASHBOARD_SECTION_RESPONSIVE_QA_TASK.md`
- `server/tests/e2e_helpers.py`
- `server/tests/test_demo_flow_e2e.py`
- `server/tests/test_auth_session_e2e.py`
- `server/tests/test_incident_report_e2e.py`
- `server/tests/test_dashboard_route_sections_e2e.py`
- `server/tests/test_dashboard_responsive_e2e.py`
- `web-next/hooks/useCopilot.ts`
- `web-next/hooks/useAlerts.ts`
- `web-next/components/dashboard/CopilotPanel.tsx`
- `web-next/app/dashboard/dashboard-client.tsx`
- `server/services/copilot_service.py`
- `server/services/llm_providers.py`
- `server/core/config.py`
- `server/core/state.py`

启动时创建运行日志：

```text
docs/runs/2026-06-19-m3-12-demo-flow-e2e-stability.md
```

运行日志必须记录：

- 当前 `git status --short --branch`
- 最近 12 个 commit
- dev server 状态
- 是否存在 `.coverage`、真实 `.env`、数据库、密钥文件
- 每轮命令、结果、失败截图和诊断摘要
- 最终 staged set 与未提交文件

---

## 1. 边界

允许修改：

- `server/tests/e2e_copilot_helpers.py`（新增）
- `server/tests/test_demo_flow_e2e.py`
- `server/tests/test_demo_flow_stability_e2e.py`（新增）
- `server/tests/test_e2e_helpers.py`（只在确有 helper 纯函数扩展时）
- `docs/runs/2026-06-19-m3-12-demo-flow-e2e-stability.md`
- `docs/runs/artifacts/m3-12-demo-flow-stability/**`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

默认禁止修改：

- `server/services/auth_service.py`
- `server/core/auth*`
- `server/routers/auth*`
- `server/security/**`
- `server/analyzer.py`
- `server/core/utils.py`
- `server/core/config.py` 中的 `REGISTER_RATE_LIMIT_*` / `LOGIN_RATE_LIMIT_*` / `COPILOT_RATE_LIMIT_*`
- Alembic migration / DB schema
- 后端 API contract
- npm 依赖
- `.env` / `.coverage` / 数据库 / 密钥

只有在完成系统排障并能证明是生产 bug 时，才允许提出非常小的生产修复；若修复会触碰认证、Guardrails、SSRF、DB schema 或速率限制常量，必须停止并在最终报告中写成“需要 owner 单独授权的新工单”，不要继续改。

---

## 2. 成功标准

必须全部满足：

1. `test_demo_flow_e2e.py` 失败时能保存截图、DOM 摘要、assistant 消息列表、关键 network status、console/pageerror 摘要。
2. Copilot fallback 等待不再是裸 15s 手写轮询，而是条件等待；仍必须验证用户可见 assistant 消息包含 `API Key` 或 `Base URL`。
3. 新增 `server/tests/test_demo_flow_stability_e2e.py`，同一浏览器会话内连续两次触发 Demo → 分析当前告警 → 等待 Copilot fallback，并扫描 DOM forbidden sentinel。
4. 单条 Demo Flow E2E 通过。
5. 新增稳定化 E2E 通过。
6. Auth / Demo / Incident report / Dashboard route / Dashboard responsive / Demo stability 六组关键 E2E 连续通过。
7. 至少执行一次 Demo 相关 E2E repeat，不靠重启 backend 才能通过。
8. 默认后端测试、Guardrails、前端 typecheck/build 通过。
9. 没有放宽生产 rate limit，没有删除/skip 断言，没有提交 `.coverage`、真实 env、数据库或密钥。

---

## 3. 排障阶段：先取证，不许先修

- [ ] **Step 1: 记录当前状态**

运行：

```powershell
git status --short --branch
git log --oneline --decorate -12
```

写入运行日志。若除 `.coverage` 外已有用户改动，不要覆盖；只在本任务允许文件内继续。

- [ ] **Step 2: 确认 dev server**

运行或检查：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_auth_session_e2e.py -q --tb=short --run-e2e -s
```

期望：`1 passed`。若前后端 dev server 未启动，按现有项目方式启动；如果端口被占用，记录 PID 和处理方式。不要打印 `.env` 内容。

- [ ] **Step 3: 复现 M3-11 串跑场景**

运行：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_auth_session_e2e.py server\tests\test_demo_flow_e2e.py server\tests\test_incident_report_e2e.py server\tests\test_dashboard_route_sections_e2e.py server\tests\test_dashboard_responsive_e2e.py -q --tb=short --run-e2e -s
```

如果失败，必须记录：

- 失败测试名
- 是注册/登录失败、Demo row 未出现、Analyze 按钮不可见、Copilot 消息未出现、triage 未保存，还是 DOM sentinel 命中
- 是否出现 429
- 是否出现 `/api/backend/copilot/stream` 非 200
- 失败前页面前 500 字 body 文本

如果通过，仍继续本任务；M3-11 已留下历史失败证据，本任务目标是把下一次失败变得可诊断并提升稳定性。

---

## 4. Task 1 RED：新增 Copilot E2E 诊断 helper

**Files:**

- Create: `server/tests/e2e_copilot_helpers.py`
- Modify: `docs/runs/2026-06-19-m3-12-demo-flow-e2e-stability.md`

- [ ] **Step 1: 创建 helper 文件**

创建 `server/tests/e2e_copilot_helpers.py`：

```python
"""Copilot E2E diagnostic helpers for Playwright tests.

These helpers are test-only. They never print cookies, tokens, passwords,
API keys, raw payloads, or full response bodies. They only capture DOM text,
assistant message text, sanitized console errors, and selected HTTP status
metadata needed to debug flaky browser E2E failures.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

ARTIFACT_DIR = Path("docs/runs/artifacts/m3-12-demo-flow-stability")

_SENSITIVE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9]{8,}"),
    re.compile(r"sk-proj-[A-Za-z0-9_-]+"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+", re.IGNORECASE),
)


def _sanitize_text(text: str, *, limit: int = 1200) -> str:
    value = str(text or "")
    for pattern in _SENSITIVE_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value[:limit]


def _artifact_name(prefix: str, suffix: str) -> str:
    safe_prefix = re.sub(r"[^a-zA-Z0-9_.-]+", "-", prefix).strip("-") or "artifact"
    safe_suffix = re.sub(r"[^a-zA-Z0-9_.-]+", "-", suffix).strip("-") or "txt"
    return f"{safe_prefix}.{safe_suffix}"


def write_json_artifact(prefix: str, payload: dict) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / _artifact_name(prefix, "json")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


async def collect_visible_text(page, *, limit: int = 1200) -> str:
    text = await page.evaluate(
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
    return _sanitize_text(str(text or ""), limit=limit)


async def collect_assistant_messages(page) -> list[str]:
    return await page.evaluate(
        """
        () => Array.from(
            document.querySelectorAll('[data-testid="copilot-message"][data-role="assistant"]')
        ).map((node) => (node.innerText || node.textContent || '').trim()).filter(Boolean)
        """
    )


async def wait_for_copilot_fallback_message(page, *, timeout_ms: int = 45000) -> str:
    """Wait until a visible assistant message contains the no-key fallback.

    This keeps the original product assertion strict: the user-visible Copilot
    message must mention API Key or Base URL. The only change from the old test
    is condition-based waiting with a longer budget and better diagnostics.
    """
    handle = await page.wait_for_function(
        """
        () => {
            const nodes = Array.from(
                document.querySelectorAll('[data-testid="copilot-message"][data-role="assistant"]')
            );
            const texts = nodes
                .map((node) => (node.innerText || node.textContent || '').trim())
                .filter(Boolean);
            for (let i = texts.length - 1; i >= 0; i -= 1) {
                const text = texts[i];
                if (text.includes('API Key') || text.includes('Base URL')) {
                    return text;
                }
            }
            return false;
        }
        """,
        timeout=timeout_ms,
    )
    value = await handle.json_value()
    return str(value or "")


def install_network_diagnostics(page, diag: dict) -> None:
    diag.setdefault("console", [])
    diag.setdefault("page_errors", [])
    diag.setdefault("responses", [])

    def on_console(message) -> None:
        if message.type not in {"error", "warning"}:
            return
        diag["console"].append(
            {
                "type": message.type,
                "text": _sanitize_text(message.text, limit=500),
            }
        )

    def on_page_error(error) -> None:
        diag["page_errors"].append(_sanitize_text(str(error), limit=500))

    def on_response(response) -> None:
        parsed = urlparse(response.url)
        path = parsed.path
        if not (
            path.endswith("/api/backend/copilot/stream")
            or path.endswith("/api/backend/alerts/demo")
            or path.endswith("/api/backend/health")
            or path.endswith("/api/auth/session")
        ):
            return
        diag["responses"].append(
            {
                "method": response.request.method,
                "path": path,
                "status": response.status,
            }
        )

    page.on("console", on_console)
    page.on("pageerror", on_page_error)
    page.on("response", on_response)


async def save_copilot_failure_artifacts(page, diag: dict, *, prefix: str) -> dict:
    """Save screenshot + sanitized JSON diagnostics and return artifact paths."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    screenshot_path = ARTIFACT_DIR / _artifact_name(prefix, "png")
    await page.screenshot(path=str(screenshot_path), full_page=True)
    diag["assistant_messages"] = [
        _sanitize_text(item, limit=800) for item in await collect_assistant_messages(page)
    ]
    diag["body_text"] = await collect_visible_text(page, limit=1200)
    json_path = write_json_artifact(prefix, diag)
    return {
        "screenshot": str(screenshot_path),
        "diagnostics": str(json_path),
    }
```

- [ ] **Step 2: 跑一个导入 RED**

运行：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow_e2e.py -q --tb=short --run-e2e -s
```

期望：此时如果还没接入 helper，测试可能仍按旧逻辑通过或失败。记录原始状态即可。不要为了“制造失败”删除断言。

---

## 5. Task 2 GREEN：把 Demo Flow E2E 接入条件等待和失败 artifact

**Files:**

- Modify: `server/tests/test_demo_flow_e2e.py`
- Test: `server/tests/test_demo_flow_e2e.py`

- [ ] **Step 1: 更新 import**

在 `server/tests/test_demo_flow_e2e.py` 中加入：

```python
from server.tests.e2e_copilot_helpers import (
    install_network_diagnostics,
    save_copilot_failure_artifacts,
    wait_for_copilot_fallback_message,
)
```

- [ ] **Step 2: 初始化诊断字典后安装监听**

在创建 `page = await context.new_page()` 后加入：

```python
            install_network_diagnostics(page, diag)
```

保留现有 `diag` 字段，并可扩展：

```python
    diag: dict = {
        "registered": False,
        "demo": False,
        "copilot": False,
        "triage": False,
        "forbidden": None,
        "artifacts": {},
    }
```

- [ ] **Step 3: 替换 Copilot 15s 手写轮询**

把旧的“等待 Copilot 出现可验证 assistant 降级消息（最多 15s）”轮询替换为：

```python
            try:
                assistant_text = await wait_for_copilot_fallback_message(
                    page,
                    timeout_ms=45000,
                )
            except Exception as exc:  # noqa: BLE001
                diag["artifacts"] = await save_copilot_failure_artifacts(
                    page,
                    diag,
                    prefix="demo-flow-copilot-timeout",
                )
                pytest.fail(
                    "Copilot 未在 45s 内返回可验证的降级态消息。"
                    f" artifacts={diag['artifacts']} error={exc}"
                )

            assert assistant_text, "Copilot fallback helper 返回了空文本。"
            diag["copilot"] = True
```

保留后续断言：

```python
            assert (
                "API Key" in assistant_text or "Base URL" in assistant_text
            ), f"Copilot 降级态文案异常：{assistant_text!r}"
```

- [ ] **Step 4: 单条 Demo Flow 验证**

运行：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow_e2e.py -q --tb=short --run-e2e -s
```

期望：`1 passed`。若失败，必须检查 artifact JSON 和截图，不许直接继续加 timeout。

---

## 6. Task 3 RED/GREEN：新增 Demo Flow 稳定化 E2E

**Files:**

- Create: `server/tests/test_demo_flow_stability_e2e.py`
- Test: `server/tests/test_demo_flow_stability_e2e.py`

- [ ] **Step 1: 创建稳定化测试**

创建 `server/tests/test_demo_flow_stability_e2e.py`：

```python
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
```

- [ ] **Step 2: 运行新测试**

运行：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow_stability_e2e.py -q --tb=short --run-e2e -s
```

期望：`1 passed`。若失败，读取 `docs/runs/artifacts/m3-12-demo-flow-stability/*.json` 和截图，先定位失败层，再做最小修复。

---

## 7. Task 4：repeat 与串跑验证

**Files:**

- Modify: `docs/runs/2026-06-19-m3-12-demo-flow-e2e-stability.md`

- [ ] **Step 1: 单条 Demo Flow repeat**

至少连续运行 3 次：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow_e2e.py -q --tb=short --run-e2e -s
```

在运行日志中记录每次结果。不要在每次之间重启 backend；如果必须重启，说明原因并把任务状态标记为部分完成。

- [ ] **Step 2: 稳定化测试 repeat**

至少连续运行 2 次：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow_stability_e2e.py -q --tb=short --run-e2e -s
```

期望：每次 `1 passed`。如果出现 429，先确认 `register_or_login_for_e2e` 是否正确回落到 stable account；不要修改生产 rate limit。

- [ ] **Step 3: 六组关键 E2E 连续**

运行：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_auth_session_e2e.py server\tests\test_demo_flow_e2e.py server\tests\test_incident_report_e2e.py server\tests\test_dashboard_route_sections_e2e.py server\tests\test_dashboard_responsive_e2e.py server\tests\test_demo_flow_stability_e2e.py -q --tb=short --run-e2e -s
```

期望：`7 passed`。解释：Auth 1、Demo 1、Incident 1、Route 1、Responsive 2、Demo stability 1。

---

## 8. Task 5：全量质量门

按顺序运行：

```powershell
.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

```powershell
.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

```powershell
cd web-next
npm run typecheck
```

```powershell
cd web-next
npm run build
```

要求：

- 后端默认测试不得因为 Playwright 缺失而 collection 失败；E2E 仍默认 skip。
- Guardrails 不能回归。
- `npm run typecheck` 和 `npm run build` 必须顺序运行，不要并行。
- 如 `web-next/.next` stale chunk 导致 dev/build 异常，可删除 `.next` 并在运行日志记录原因；不要删除源代码或 lockfile。

---

## 9. Task 6：de-sloppify 与安全审查

运行：

```powershell
rg -n "console\\.log|localStorage|sessionStorage|innerHTML|dangerouslySetInnerHTML|REGISTER_RATE_LIMIT|COPILOT_RATE_LIMIT|pytest\\.skip|xfail" server\tests\test_demo_flow_e2e.py server\tests\test_demo_flow_stability_e2e.py server\tests\e2e_copilot_helpers.py web-next\hooks web-next\components\dashboard server\core server\services
```

要求：

- 允许命中 `server/tests/e2e_helpers.py` 文档字符串中的 rate limit 说明。
- 不允许新增生产 `console.log`。
- 不允许新增 `localStorage` / `sessionStorage`。
- 不允许新增 `innerHTML` / `dangerouslySetInnerHTML`。
- 不允许新增跳过关键 E2E 的 `pytest.skip`，除非是现有“缺 Playwright / 缺浏览器”前置 skip 模式。
- 不允许改 `REGISTER_RATE_LIMIT_*` / `COPILOT_RATE_LIMIT_*` 常量。

检查 artifact 大小：

```powershell
Get-ChildItem -Path docs\runs\artifacts\m3-12-demo-flow-stability -Recurse | Select-Object FullName,Length
```

如果 artifact 总量超过 5 MB，只提交最小必要截图和 JSON；其余在运行日志中说明不提交。

---

## 10. Task 7：文档同步

更新：

- `docs/runs/2026-06-19-m3-12-demo-flow-e2e-stability.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

必须写清：

- M3-12 修的是 E2E 稳定性和诊断能力，不是业务功能。
- 旧问题：M3-11 串跑时 Demo Flow Copilot fallback 偶发 15s 超时。
- 新行为：失败有 artifact，等待是条件式，仍要求 `API Key` / `Base URL` 降级态文案。
- 验证矩阵和具体通过数字。
- 未改认证/授权、Guardrails、SSRF、DB schema、后端 API、npm 依赖、rate limit 常量。

把 `docs/agent/UNATTENDED_LONG_TASKS.md` 的推荐启动口令更新为下一条候选，不要继续指向 M3-12。

---

## 11. 精确 commit 策略

严禁 `git add .`。

建议拆成 3 个 commit：

1. `test(e2e): 增加 copilot fallback 诊断工具`
   - `server/tests/e2e_copilot_helpers.py`
   - `server/tests/test_demo_flow_e2e.py`

2. `test(e2e): 加固 demo flow 连续运行稳定性`
   - `server/tests/test_demo_flow_stability_e2e.py`
   - 必要的 artifact 文件

3. `docs(e2e): 记录 demo flow 稳定性收口`
   - `docs/runs/2026-06-19-m3-12-demo-flow-e2e-stability.md`
   - `docs/agent/M3_12_DEMO_FLOW_E2E_STABILITY_TASK.md`
   - `docs/agent/UNATTENDED_LONG_TASKS.md`
   - `PRODUCT.md`
   - `docs/plans/M2_PRODUCT_ROADMAP.md`

提交前必须运行：

```powershell
git status --short
git diff --check
git diff --cached --check
git diff --cached --name-only
```

确认 staged set 不含：

- `.coverage`
- `.env` / `.env.local` / `web-next/.env*`
- `*.db` / `*.sqlite`
- `*.key` / `*.pem` / `*.p12`
- 真实 token / secret

通过后 push：

```powershell
git push origin main
```

---

## 12. 停止条件

遇到以下情况必须停止并报告，不要继续尝试第四种修复：

- 连续 3 次都无法复现也无法获得任何诊断证据。
- 需要修改认证/授权、Guardrails、SSRF、DB schema、后端 API contract 或速率限制常量才能继续。
- Playwright / Chromium / dev server 环境缺失且无法在本机恢复。
- 关键 E2E 必须靠删除断言、skip、xfail 或重启 backend 才能通过。
- artifact 中出现真实 secret 或 token；立即停止，删除本地 artifact，不提交，报告命中的文件路径和处理方式，不要贴 secret 内容。

---

## 13. 最终报告模板

完成后输出：

```text
M3-12 Demo Flow E2E 稳定性收口完成。

变更：
- 新增/修改文件：
- 诊断 artifact：
- 根因/证据：
- 修复方式：

验证：
- Demo Flow E2E：
- Demo Flow stability E2E：
- 六组关键 E2E 连续：
- 后端全量：
- Guardrails：
- 前端 typecheck/build：

安全边界：
- 未改 auth / Guardrails / SSRF / DB schema / API / rate limit：
- 未提交 .coverage / env / DB / 密钥：

提交：
- commit 列表：
- push 状态：

下一条建议工单：
- ...
```
