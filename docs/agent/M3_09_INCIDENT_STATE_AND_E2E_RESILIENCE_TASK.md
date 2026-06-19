# M3-09 Incident State and E2E Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or the local equivalent task-by-task execution workflow. This repository also requires the skill-first workflow in `AGENTS.md`: before editing, check and read the relevant skills. Reply in Chinese.

**Goal:** 收口 NEXT-02 后留下的两个产品级韧性问题：让 Dashboard 案件工作台只有一个 incident state 事实源，并让三条 Playwright E2E 在连续运行时不再因为注册限流而需要重启 dev server。

**Architecture:** 把 `useIncidents()` 实例提升到 `dashboard-client.tsx` 父层，由父组件统一传给 `IncidentSection`，从而让“从告警创建案件”后案件列表、选中案件、详情面板、报告下载按钮共享同一份状态。E2E 侧新增轻量测试 helper，把 register + NextAuth callback cookie seeding 复用到 Auth / Demo Flow / Incident Report 三条浏览器测试；遇到注册 409 或测试账号已存在时直接登录，遇到 429 时优先使用稳定测试账号登录而不是要求重启后端，不改生产注册限流策略。

**Tech Stack:** Next.js 15 App Router + React 19 + TypeScript hooks + pytest + pytest-asyncio + Playwright Python + FastAPI auth endpoints.

---

## 0. 为什么这是下一条优先任务

NEXT-02 已交付：

- `test_demo_flow_e2e.py --run-e2e` 真实通过。
- `test_auth_session_e2e.py --run-e2e` 真实通过。
- `test_incident_report_e2e.py --run-e2e` 真实通过。
- `test_ssrf.py` 在受限 DNS 环境下确定性通过。
- 后端全量、Guardrails、前端 typecheck/build 全绿。

但 NEXT-02 run log 留下两条明确后续债：

1. `IncidentSection` 和 `dashboard-client.tsx` 各自独立调用 `useIncidents()`。父层从告警创建案件后，`IncidentSection` 内部 hook 不知道父层已经创建并选中了案件，M3-08 / NEXT-01 E2E 只能点击 `incident-list-item` 来规避。
2. 三条 E2E 连续运行会多次 `POST /api/backend/auth/register`，命中 `REGISTER_RATE_LIMIT_MAX=5/小时` 后需要重启 dev server 解锁。这是测试韧性问题，不应靠改生产限流解决。

本任务要把这两个“靠人工和点击兜底”的点变成稳定产品 / 测试设计。

## 1. 启动前必读

必须按顺序阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/agent/M3_04_INCIDENT_CASE_WORKBENCH_TASK.md`
- `docs/agent/M3_07_INCIDENT_EVIDENCE_REPORT_EXPORT_TASK.md`
- `docs/agent/M3_08_INCIDENT_REPORT_BROWSER_E2E_AND_AGENT_DOCS_CATCHUP_TASK.md`
- `docs/agent/NEXT_01_AUTH_SESSION_LOADING_E2E_RECOVERY_TASK.md`
- `docs/agent/NEXT_02_E2E_AND_SSRF_QUALITY_GATE_HARDENING_TASK.md`
- `docs/runs/2026-06-19-next-02-e2e-and-ssrf-quality-gate-hardening.md`
- `web-next/app/dashboard/dashboard-client.tsx`
- `web-next/components/dashboard/IncidentSection.tsx`
- `web-next/components/dashboard/IncidentList.tsx`
- `web-next/components/dashboard/IncidentDetailPanel.tsx`
- `web-next/hooks/useIncidents.ts`
- `web-next/types/incident.ts`
- `server/tests/test_auth_session_e2e.py`
- `server/tests/test_demo_flow_e2e.py`
- `server/tests/test_incident_report_e2e.py`
- `server/services/auth_service.py`（只读，理解注册限流；默认禁止改）
- `server/core/state.py`（只读，理解 rate limit state；默认禁止改）

## 2. 必用 skill

执行前必须检查并使用：

- `superpowers:executing-plans`：按本文逐项执行。
- `tdd-workflow`：先写 / 修改 E2E 复现双 hook race 和 register 429 场景，再改。
- `frontend-patterns`：处理 React hook 状态提升、props 传递、避免重复状态源。
- `e2e-testing`：处理 Playwright 稳定等待、helper 复用、连续运行韧性。
- `security-review`：注册 / cookie / session / rate limit 是安全敏感面，确认不降级。
- `verification-loop`：最终质量门。

如需查库文档，使用 `context7` 查 Next.js / React / next-auth 当前文档，不靠记忆。

## 3. 风险等级与预算

- 运行模式：L5 高风险产品韧性收口战役。
- 风险分类：前端共享状态 + E2E auth helper；默认不改生产认证 / 注册限流 / Guardrails。
- 预计时长：3-5 小时。
- 同一失败最多修复：3 轮。
- diff 预算：约 1200 行；如果抽取 E2E helper 并替换三条测试可到 1600 行，但必须解释。
- 允许通过质量门后精确 commit 并 push 到 `origin/main`。
- 禁止 `git add .`。
- 禁止提交 `.coverage`、真实 `.env`、数据库、证书、私钥、token。

## 4. 初始审计

先创建运行日志：

```text
docs/runs/2026-06-19-m3-09-incident-state-and-e2e-resilience.md
```

记录：

- 当前分支。
- `git status --short --branch`。
- `git log --oneline --decorate -15`。
- `.coverage` 是否 modified。
- `dashboard-client.tsx` 中 `const incidentsCtx = useIncidents()` 的位置。
- `IncidentSection.tsx` 中是否仍独立 `const incidents = useIncidents()`。
- `test_incident_report_e2e.py` 是否仍需要点击 `incident-list-item` 才能等到 `incident-detail-panel`。
- 三条 E2E 是否各自复制 register / callback helper。
- `server/core/config.py` 当前 `REGISTER_RATE_LIMIT_MAX` 和 `REGISTER_RATE_LIMIT_WINDOW`。

推荐命令：

```powershell
git status --short --branch
git log --oneline --decorate -15
Test-Path .coverage
Select-String -Path web-next\app\dashboard\dashboard-client.tsx -Pattern "useIncidents|IncidentSection|createIncidentFromAlert" -Context 2,4
Select-String -Path web-next\components\dashboard\IncidentSection.tsx -Pattern "useIncidents|initialIncidentId|selectedIncident|loadIncidentDetail" -Context 2,4
Select-String -Path server\tests\test_incident_report_e2e.py -Pattern "incident-list-item|incident-detail-panel|auth/register|callback/credentials|429" -Context 2,4
Select-String -Path server\tests\test_auth_session_e2e.py,server\tests\test_demo_flow_e2e.py,server\tests\test_incident_report_e2e.py -Pattern "auth/register|callback/credentials|_register_unique_user|_register_via_ui|_register_and_login|429" -Context 1,3
```

## 5. 允许修改

优先允许修改：

- `web-next/app/dashboard/dashboard-client.tsx`
- `web-next/components/dashboard/IncidentSection.tsx`
- `web-next/hooks/useIncidents.ts`
- `web-next/types/incident.ts`
- `server/tests/e2e_helpers.py`（建议新增）
- `server/tests/test_auth_session_e2e.py`
- `server/tests/test_demo_flow_e2e.py`
- `server/tests/test_incident_report_e2e.py`
- `docs/runs/2026-06-19-m3-09-incident-state-and-e2e-resilience.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

条件允许修改：

- `web-next/components/dashboard/IncidentList.tsx`：仅为增加更稳定的 `data-testid` / `data-incident-id` / 可访问状态，不改变视觉结构。
- `web-next/components/dashboard/IncidentDetailPanel.tsx`：仅当单一事实源后需要补一个等待稳定的 `data-testid` 或状态文案，不改报告生成逻辑。

## 6. 禁止修改

禁止修改：

- `server/services/auth_service.py` 生产注册 / 登录逻辑。
- `server/core/state.py` 生产 rate limit state。
- `server/core/config.py` 生产 `REGISTER_RATE_LIMIT_MAX` / `REGISTER_RATE_LIMIT_WINDOW` 默认值。
- `server/core/auth*`
- `server/routers/auth*`
- `server/security/**`
- `/mcp` 鉴权逻辑。
- Alembic migration / 数据库 schema。
- `server/analyzer.py` / `server/core/utils.py` SSRF 逻辑。
- 真实 `.env` / `.env.local` / `web-next/.env` / `web-next/.env.local`。
- `.coverage`
- `data/*.db`

禁止行为：

- 不允许为了 E2E 方便关闭或放宽注册限流。
- 不允许把 token 写进 `localStorage` / `sessionStorage`。
- 不允许把 backend access token 写入 DOM。
- 不允许删除 E2E 的 DOM forbidden sentinel。
- 不允许跳过 / xfail 三条浏览器 E2E。
- 不允许把 `IncidentSection` 改成只展示父层静态数据而失去刷新 / 更新 / 报告下载能力。

## 7. 目标用户行为

完成后真实用户 / E2E 应能：

1. 在告警详情点击“从此告警创建案件”。
2. 页面切换到“案件”路由。
3. 案件列表立即出现新案件并自动选中。
4. `incident-detail-panel` 自动出现，不需要用户再点列表项。
5. “下载报告 / 复制报告 / 用 AI 分析案件 / 状态更新 / 关联告警”继续可用。
6. 连续运行 Auth E2E、Demo Flow E2E、Incident Report E2E 不再因为注册 429 需要重启 dev server。

## 8. RED A：复现 incident 双 hook race

先确认当前 E2E 仍包含点击列表项规避：

```powershell
Select-String -Path server\tests\test_incident_report_e2e.py -Pattern "incident-list-item|IncidentSection 自己持有 useIncidents"
```

然后修改 `server/tests/test_incident_report_e2e.py`，把“点击列表项”的兼容段临时变成断言：创建案件后直接等待 `incident-detail-panel`，不要点击列表项。

期望 RED：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_incident_report_e2e.py -q --tb=short --run-e2e -s
```

预期当前代码会失败在 `incident-detail-panel` 不出现，或必须靠列表项点击才出现。把这个失败写进 run log。

不要在 RED 前改前端生产代码。

## 9. GREEN A：提升 incident state 到父层

目标：`dashboard-client.tsx` 只创建一个 `incidentsCtx = useIncidents()`，并把它传给 `IncidentSection`。`IncidentSection` 不再自己调用 `useIncidents()`。

### 9.1 导出 hook 返回类型

在 `web-next/hooks/useIncidents.ts` 末尾增加类型：

```ts
export type IncidentsController = ReturnType<typeof useIncidents>;
```

如果 TypeScript 对 `ReturnType` 在同文件中不满意，可改成显式 interface，但优先保持简单。

### 9.2 修改 IncidentSection props

把 `web-next/components/dashboard/IncidentSection.tsx` 从内部 hook 改成接收 controller：

```tsx
import type { IncidentsController } from "@/hooks/useIncidents";

export interface IncidentSectionProps {
  incidents: IncidentsController;
  initialIncidentId?: string | null;
  renderCreateShortcut?: (args: {
    defaultTitle: string;
    defaultSeverity: IncidentSeverity;
    onCreate: (input: {
      title: string;
      summary?: string | null;
      severity: IncidentSeverity;
      alert_id?: string | null;
    }) => Promise<boolean>;
  }) => React.ReactNode;
}

export default function IncidentSection({
  incidents,
  initialIncidentId,
  renderCreateShortcut,
}: IncidentSectionProps) {
  // 不再调用 useIncidents()
}
```

保留现有 UI 布局、按钮、`data-testid`。

### 9.3 修复加载列表 effect

当前 effect 每次进入 `IncidentSection` 时 `void incidents.loadIncidents({ limit: 50 })`。共享父层后仍可保留，但要避免覆盖刚创建的 selected detail。

推荐实现：

```tsx
useEffect(() => {
  void incidents.loadIncidents({ limit: 50 });
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, []);
```

保留即可；因为 `createIncidentFromAlert` 已乐观写入列表，后端列表刷新也应包含新案件。

### 9.4 修复 detail effect

当前：

```tsx
const id = incidents.selectedIncident?.incident_id || initialIncidentId;
```

保留这个语义，但要避免已经有 ready detail 时重复拉取同一个 id 造成闪烁。推荐：

```tsx
useEffect(() => {
  const id = incidents.selectedIncident?.incident_id || initialIncidentId;
  if (!id) return;
  if (incidents.detail?.incident.incident_id === id && incidents.detailState === "ready") {
    return;
  }
  void incidents.loadIncidentDetail(id, { eventLimit: 20 });
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, [
  incidents.selectedIncident?.incident_id,
  initialIncidentId,
  incidents.detail?.incident.incident_id,
  incidents.detailState,
]);
```

如果 dependency 导致 `loadIncidentDetail` identity 问题，保持 eslint disable，但不要制造无限循环。

### 9.5 修改 dashboard-client 传入 controller

把：

```tsx
<IncidentSection />
```

改为：

```tsx
<IncidentSection incidents={incidentsCtx} />
```

`handleCreateIncidentFromAlert` 已经使用同一个 `incidentsCtx`：

```tsx
const result = await incidentsCtx.createIncidentFromAlert(...);
if (result.ok && result.incident) {
  setRoute("incidents");
  await incidentsCtx.loadIncidentDetail(result.incident.incident_id, { eventLimit: 20 });
}
```

保留这段，但确保切换到案件路由后 `IncidentSection` 看到的是同一个 `selectedIncident` 和 `detail`。

## 10. GREEN A 回归：删除 E2E 列表点击规避

回到 `server/tests/test_incident_report_e2e.py`：

删除或改写这段兼容逻辑：

```python
await page.wait_for_selector('[data-testid="incident-list-item"]', ...)
first_item = page.locator('[data-testid="incident-list-item"]').first
await first_item.click()
```

改成创建后直接等待：

```python
await page.wait_for_selector(
    '[data-testid="incident-detail-panel"]',
    state="visible",
    timeout=30000,
)
```

再加一个明确断言，证明列表也同步了父层状态：

```python
selected_item = page.locator('[data-testid="incident-list-item"]').first
await selected_item.wait_for(state="visible", timeout=20000)
incident_id = await selected_item.get_attribute("data-incident-id")
assert incident_id, "案件列表项缺少 data-incident-id"
```

不要要求点击该列表项。

运行：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_incident_report_e2e.py -q --tb=short --run-e2e -s
```

期望：

- `1 passed`。
- `diag["create"] == True`。
- 不再依赖列表点击。
- `copy_status='已复制'` 或允许的降级 marker。
- forbidden sentinel `None`。

## 11. RED B：复现 E2E register 429 韧性问题

不要求真的刷 5 次打爆服务；可以用单元式 helper 测试复现“register 返回 429 时，helper 不应直接失败，而应尝试登录稳定用户”。

新增：

```text
server/tests/test_e2e_helpers.py
```

先写纯函数测试，不启动浏览器：

```python
from server.tests.e2e_helpers import classify_register_response


def test_classify_register_response_allows_existing_user_text():
    assert classify_register_response(409, "邮箱已注册") == "exists"
    assert classify_register_response(400, "user exists") == "exists"


def test_classify_register_response_marks_rate_limited():
    assert classify_register_response(429, "注册尝试过于频繁，请1小时后再试") == "rate_limited"


def test_classify_register_response_marks_created():
    assert classify_register_response(200, "{}") == "created"
    assert classify_register_response(201, "{}") == "created"
```

运行：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_e2e_helpers.py -q --tb=short
```

预期 RED：`server.tests.e2e_helpers` 不存在。

## 12. GREEN B：新增 E2E helper

新增：

```text
server/tests/e2e_helpers.py
```

建议内容：

```python
from __future__ import annotations

import os
import re
import time
from importlib.util import find_spec
from typing import Literal

import pytest

BASE = os.getenv("E2E_BASE_URL", "http://localhost:3000")
DEFAULT_PASSWORD = os.getenv("E2E_DEFAULT_PASSWORD", "DemoE2EPass123!")

RegisterStatus = Literal["created", "exists", "rate_limited", "error"]


def skip_without_playwright() -> None:
    if find_spec("playwright") is None:
        pytest.skip(
            "未安装 playwright。运行 `pip install playwright && "
            "playwright install chromium` 后加 --run-e2e 显式执行。"
        )


def unique_e2e_user(prefix: str) -> tuple[str, str]:
    ts = int(time.time() * 1000)
    worker = os.getenv("PYTEST_XDIST_WORKER", "local")
    safe_worker = re.sub(r"[^a-zA-Z0-9_-]+", "-", worker)
    return f"{prefix}-{safe_worker}-{ts}@example.com", DEFAULT_PASSWORD


def stable_e2e_user(prefix: str) -> tuple[str, str]:
    safe_prefix = re.sub(r"[^a-zA-Z0-9_-]+", "-", prefix.lower()).strip("-") or "e2e"
    env_email = os.getenv(f"E2E_{safe_prefix.upper().replace('-', '_')}_EMAIL", "").strip()
    if env_email:
        return env_email, DEFAULT_PASSWORD
    return f"{safe_prefix}-stable@example.com", DEFAULT_PASSWORD


def classify_register_response(status: int, body: str) -> RegisterStatus:
    text = (body or "").lower()
    if status in (200, 201):
        return "created"
    if status == 409 or "已存在" in body or "已注册" in body or "exists" in text:
        return "exists"
    if status == 429 or "频繁" in body or "rate" in text:
        return "rate_limited"
    return "error"
```

再补 async helper：

```python
async def ensure_registered_or_rate_limited(page, email: str, password: str) -> RegisterStatus:
    response = await page.request.post(
        f"{BASE}/api/backend/auth/register",
        data={"email": email, "password": password},
        headers={"Content-Type": "application/json"},
    )
    body = await response.text()
    status = classify_register_response(response.status, body)
    if status == "error":
        pytest.fail(
            f"E2E 前置失败: 无法注册测试用户 (HTTP {response.status})。body: {body!r}"
        )
    return status
```

以及登录 helper：

```python
async def login_with_nextauth_callback(page, email: str, password: str) -> None:
    await page.goto(f"{BASE}/", wait_until="domcontentloaded", timeout=15000)
    await page.wait_for_load_state("domcontentloaded", timeout=10000)
    try:
        await page.wait_for_function(
            "() => document.querySelector('[data-testid=\"login-email\"]') !== null",
            timeout=30000,
        )
    except Exception as exc:  # noqa: BLE001
        body_text = await page.evaluate(
            "() => document.body ? document.body.innerText.slice(0, 500) : ''"
        )
        pytest.fail(
            f"无法等到 login-email hydration 完成 ({exc})。body 文本: {body_text!r}"
        )

    await page.wait_for_function(
        "() => { const btn = document.querySelector('[data-testid=\"login-submit\"]'); return btn && !btn.disabled; }",
        timeout=30000,
    )
    await page.get_by_test_id("login-email").first.fill(email)
    await page.get_by_test_id("login-password").first.fill(password)

    csrf_resp = await page.request.get(f"{BASE}/api/auth/csrf", timeout=10000)
    csrf_token = (await csrf_resp.json()).get("csrfToken", "")
    if csrf_token:
        await page.request.post(
            f"{BASE}/api/auth/callback/credentials",
            form={
                "email": email,
                "password": password,
                "csrfToken": csrf_token,
                "callbackUrl": f"{BASE}/dashboard",
                "json": "true",
            },
            timeout=15000,
        )

    try:
        await page.get_by_test_id("login-submit").click(timeout=5000)
    except Exception:
        pass
```

以及 dashboard wait helper：

```python
async def ensure_dashboard_url(page) -> None:
    try:
        await page.wait_for_function(
            "() => window.location.pathname === '/dashboard'",
            timeout=20000,
        )
        return
    except Exception:
        pass

    try:
        await page.goto(f"{BASE}/dashboard", wait_until="domcontentloaded", timeout=15000)
    except Exception:
        pass

    try:
        await page.wait_for_function(
            "() => window.location.pathname === '/dashboard'",
            timeout=15000,
        )
    except Exception as exc:  # noqa: BLE001
        body_text = await page.evaluate(
            "() => document.body ? document.body.innerText.slice(0, 500) : ''"
        )
        pytest.fail(
            f"登录后未跳到 /dashboard ({exc})。当前 URL: {page.url!r}。"
            f"body 文本: {body_text!r}"
        )
```

组合 helper：

```python
async def register_or_login_for_e2e(page, prefix: str) -> tuple[str, str, RegisterStatus]:
    email, password = unique_e2e_user(prefix)
    status = await ensure_registered_or_rate_limited(page, email, password)

    if status == "rate_limited":
        email, password = stable_e2e_user(prefix)
        stable_status = await ensure_registered_or_rate_limited(page, email, password)
        if stable_status == "rate_limited":
            pytest.fail(
                "E2E 注册被 rate limit 阻塞,且稳定测试账号也无法确认存在。"
                "请等待窗口过期或重启本地 dev backend;不要放宽生产注册限流。"
            )
        status = stable_status

    await login_with_nextauth_callback(page, email, password)
    await ensure_dashboard_url(page)
    return email, password, status
```

重要：如果 rate limit 已经打满，稳定账号第一次也可能无法创建；这是停止条件，不允许改生产限流。真实解决方式可以是开发者预先设置稳定账号，或等待 / 重启测试服务。本任务只让“已有账号 / 409 / 可创建稳定账号”路径自动恢复，不承诺无限绕过生产限流。

运行：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_e2e_helpers.py -q --tb=short
```

期望：helper 单测通过。

## 13. 替换三条 E2E 的重复 auth helper

### 13.1 Auth Session E2E

在 `server/tests/test_auth_session_e2e.py`：

- 保留 `_FORBIDDEN_DOM_PATTERNS` / `_collect_visible_text` / `_contains_forbidden`。
- 删除本文件内 `_register_unique_user`、`_skip_without_playwright`、`_register_and_login`、`_ensure_dashboard_url` 的重复实现，或先保留但不再使用。
- import：

```python
from server.tests.e2e_helpers import register_or_login_for_e2e, skip_without_playwright
```

测试中：

```python
skip_without_playwright()
...
email, _password, register_status = await register_or_login_for_e2e(page, "e2e-auth")
diag["registered"] = register_status in {"created", "exists"}
diag["dashboard_url"] = True
```

确保 `/api/auth/session` 断言仍用 email 对比。

### 13.2 Demo Flow E2E

在 `server/tests/test_demo_flow_e2e.py`：

- 保留 Demo / Copilot / triage / forbidden 断言。
- 删除或停用本文件内 `_register_unique_user` / `_register_via_ui` 重复实现。
- import：

```python
from server.tests.e2e_helpers import register_or_login_for_e2e, skip_without_playwright
```

流程中：

```python
email, _password, register_status = await register_or_login_for_e2e(page, "e2e-demo")
diag["registered"] = register_status in {"created", "exists"}
```

### 13.3 Incident Report E2E

在 `server/tests/test_incident_report_e2e.py`：

- 保留报告结构 / 下载 / 复制 / forbidden sentinel 断言。
- 删除或停用本文件内 `_register_unique_user` / `_register_via_ui` 重复实现。
- import：

```python
from server.tests.e2e_helpers import register_or_login_for_e2e, skip_without_playwright
```

流程中：

```python
email, _password, register_status = await register_or_login_for_e2e(page, "e2e-report")
diag["registered"] = register_status in {"created", "exists"}
```

不要把 helper 改成读取真实 `.env` secret。不要打印密码 / token / cookie。

## 14. E2E helper 安全审查

helper 必须满足：

- 只使用 `page.request.post /api/backend/auth/register`。
- 只使用 NextAuth `/api/auth/callback/credentials` 种 httpOnly cookie。
- 不读 / 不写 `localStorage` / `sessionStorage`。
- 不打印 cookie / token / password。
- 429 时不改服务端限流，只尝试稳定测试账号路径；若仍被限流，明确 fail 并提示等待或重启本地测试服务。
- 稳定账号邮箱默认是 `prefix-stable@example.com`，密码来自 `E2E_DEFAULT_PASSWORD` 或默认测试密码，不是真实账号。

## 15. 质量门

后端 helper 单测：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_e2e_helpers.py -q --tb=short
```

三条 E2E：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_auth_session_e2e.py -q --tb=short --run-e2e -s
```

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow_e2e.py -q --tb=short --run-e2e -s
```

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_incident_report_e2e.py -q --tb=short --run-e2e -s
```

连续 E2E 回归（同一 dev server，不重启）：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_auth_session_e2e.py server\tests\test_demo_flow_e2e.py server\tests\test_incident_report_e2e.py -q --tb=short --run-e2e -s
```

后端默认：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

Guardrails：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

前端：

```powershell
cd web-next
npm run typecheck
npm run build
```

不要并行跑 `npm run typecheck` 和 `npm run build`。

## 16. 文档收口

必须更新：

- `docs/runs/2026-06-19-m3-09-incident-state-and-e2e-resilience.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`

如果真实修复并跑通质量门，更新：

- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

文档要写清：

- `IncidentSection` 不再拥有独立 `useIncidents()`，incident state 由 `dashboard-client.tsx` 父层统一持有。
- Incident Report E2E 不再需要点击 `incident-list-item` 才能看到 detail。
- E2E auth helper 已统一，减少三份重复 callback cookie 代码。
- 生产注册限流未降级；429 时 helper 只做测试账号 fallback，不能无限绕过。
- 后续建议工单可以进入 M3-10：拆分 `dashboard-client.tsx` 过大的 route section / provider composition，但不在本任务做。

## 17. 提交策略

通过质量门后精确 commit。

推荐 commit 1：

```text
test(e2e): 复现案件详情自动选中链路
```

包含：

- `server/tests/test_incident_report_e2e.py`（移除列表点击规避前的 RED 断言，或最终保留的更强断言）

推荐 commit 2：

```text
fix(dashboard): 统一案件工作台状态源
```

包含：

- `web-next/app/dashboard/dashboard-client.tsx`
- `web-next/components/dashboard/IncidentSection.tsx`
- `web-next/hooks/useIncidents.ts`
- 如有必要，`web-next/types/incident.ts` / `IncidentList.tsx` / `IncidentDetailPanel.tsx`

推荐 commit 3：

```text
test(e2e): 复用浏览器登录辅助工具
```

包含：

- `server/tests/e2e_helpers.py`
- `server/tests/test_e2e_helpers.py`
- `server/tests/test_auth_session_e2e.py`
- `server/tests/test_demo_flow_e2e.py`
- `server/tests/test_incident_report_e2e.py`

推荐 commit 4：

```text
docs(incidents): 记录案件状态与 E2E 韧性收口
```

包含：

- run log
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

精确 stage 示例：

```powershell
git add server\tests\test_incident_report_e2e.py
git commit -m "test(e2e): 复现案件详情自动选中链路"

git add web-next\app\dashboard\dashboard-client.tsx web-next\components\dashboard\IncidentSection.tsx web-next\hooks\useIncidents.ts
git commit -m "fix(dashboard): 统一案件工作台状态源"

git add server\tests\e2e_helpers.py server\tests\test_e2e_helpers.py server\tests\test_auth_session_e2e.py server\tests\test_demo_flow_e2e.py server\tests\test_incident_report_e2e.py
git commit -m "test(e2e): 复用浏览器登录辅助工具"

git add docs\runs\2026-06-19-m3-09-incident-state-and-e2e-resilience.md docs\agent\UNATTENDED_LONG_TASKS.md PRODUCT.md docs\plans\M2_PRODUCT_ROADMAP.md
git commit -m "docs(incidents): 记录案件状态与 E2E 韧性收口"
```

不要 stage 示例里未实际修改的文件。不要使用 `git add .`。

## 18. Push 策略

提交前：

```powershell
git status --short --branch
git diff --cached --check
git diff --cached --name-only
git log --oneline --decorate -10
```

确认：

- `.coverage` 未 stage。
- `.env` / `.env.local` 未 stage。
- `web-next/.env` / `web-next/.env.local` 未 stage。
- 数据库 / 证书 / 私钥未 stage。

然后：

```powershell
git push origin main
```

如果 push 失败：

- 最多重试 3 次。
- 记录错误摘要。
- 不要无限重试。
- 本地 commit 完成但 push 阻塞时，最终状态写“本地完成，push 阻塞”。

## 19. 停止条件

任一条件满足必须停止：

- 需要修改生产注册限流才能让 E2E 通过。
- 需要改后端 auth API / token / cookie 语义。
- 需要改数据库 schema / migration。
- 需要改 Guardrails / MCP / SSRF 生产安全逻辑。
- `IncidentSection` 状态提升导致大面积 dashboard 重构超过本任务范围。
- 同一个 E2E 失败连续修复 3 轮仍失败。
- Playwright / dev server 环境不可用且无法在本地修复。
- 后端全量或 Guardrails 出现大面积无关失败。
- 需要把 token 放入浏览器 storage 才能跑通。

停止时必须给出：

- 已完成内容。
- 未完成内容。
- 阻塞证据。
- 下一条最小工单。

## 20. 最终报告格式

完成后中文输出：

```text
完成状态：完成 / 部分完成 / 阻塞

根因：
- ...

改动文件：
- ...

验证命令：
- pytest server/tests/test_e2e_helpers.py -> ...
- pytest server/tests/test_auth_session_e2e.py --run-e2e -> ...
- pytest server/tests/test_demo_flow_e2e.py --run-e2e -> ...
- pytest server/tests/test_incident_report_e2e.py --run-e2e -> ...
- 连续 E2E 三文件 --run-e2e -> ...
- pytest server/tests -> ...
- pytest server/tests/security/llm_guardrails -> ...
- npm run typecheck -> ...
- npm run build -> ...

安全审查：
- 生产注册限流未改
- auth cookie / token 语义未改
- 无 token storage / DOM 泄漏
- Guardrails / SSRF 未改

提交与推送：
- commit: ...
- push: 成功 / 阻塞

运行日志：
- docs/runs/2026-06-19-m3-09-incident-state-and-e2e-resilience.md

剩余本地噪声：
- .coverage（如仍存在，说明未提交）

下一条建议工单：
- M3-10 Dashboard route sections / provider composition 拆分
```

不要只说“好了”。必须写清 Incident Report E2E 是否已经不依赖列表点击、连续 E2E 是否不需要重启 dev server。
