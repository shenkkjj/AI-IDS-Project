# M3-10 Dashboard Route Composition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `web-next/app/dashboard/dashboard-client.tsx` 从 800+ 行的 route 渲染大文件，收口成“父层持有状态 + 子组件渲染路由区块 + 单一路由元数据”的结构，同时用浏览器 E2E 锁住所有 Dashboard 路由入口和核心 section。

**Architecture:** `dashboard-client.tsx` 保留所有 hook、跨区块事件编排和安全边界，新增的 route section 组件只接收 props 并渲染 UI，不在内部重新创建业务 hook。路由元数据抽到 `web-next/constants/dashboardRoutes.ts`，`SystemStatusBar` 与 `dashboard-client.tsx` 共同读取同一份 route/nav 配置，避免 M3-09 后 `incidents` 路由只能程序化进入、顶部导航不可见的漂移。先写 E2E 复现当前缺口，再拆 section、补 `data-testid`、跑完整质量门。

**Tech Stack:** Next.js App Router, React Client Components, TypeScript, Playwright via pytest, existing FastAPI dev backend, existing `server/tests/e2e_helpers.py`.

---

## 0. 必读上下文

执行前必须完整阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/runs/2026-06-19-m3-09-incident-state-and-e2e-resilience.md`
- `docs/agent/M3_09_INCIDENT_STATE_AND_E2E_RESILIENCE_TASK.md`
- `web-next/app/dashboard/dashboard-client.tsx`
- `web-next/components/dashboard/SystemStatusBar.tsx`
- `web-next/components/dashboard/AlertSection.tsx`
- `web-next/components/dashboard/CopilotSection.tsx`
- `web-next/components/dashboard/SystemStatusSection.tsx`
- `web-next/components/dashboard/IncidentSection.tsx`
- `web-next/hooks/useAlerts.ts`
- `web-next/hooks/useConfig.ts`
- `web-next/hooks/useCopilot.ts`
- `web-next/hooks/useIncidents.ts`
- `server/tests/e2e_helpers.py`
- `server/tests/test_auth_session_e2e.py`
- `server/tests/test_demo_flow_e2e.py`
- `server/tests/test_incident_report_e2e.py`

启动时创建运行日志：

```powershell
docs/runs/2026-06-19-m3-10-dashboard-route-composition.md
```

运行日志必须记录：

- 启动时 `git status --short --branch`
- 启动时 `git log --oneline --decorate -12`
- 当前 `dashboard-client.tsx` 行数
- RED / GREEN / IMPROVE 每阶段命令和结果
- 最终验证矩阵
- 精确 commit / push 结果
- 未解决问题与下一条建议工单

---

## 1. 当前问题与目标行为

### 1.1 当前问题

M3-09 修复了案件 state 单一事实源，但 Dashboard 仍有一个产品维护性问题：

- `web-next/app/dashboard/dashboard-client.tsx` 当前约 836 行，混合了 state hook、跨模块事件、路由判断、section 标题、表单原子组件、AI 配置表单、Webhook 表单、日报渲染、footer 子组件。
- `dashboard-client.tsx` 内部有 `NAV_ITEMS`，`SystemStatusBar.tsx` 内部也有一份 `NAV_ITEMS`，两者已经漂移：`dashboard-client.tsx` 有 `incidents`，`SystemStatusBar.tsx` 没有 `incidents`。
- 目前用户可以通过“从此告警创建案件”程序化切到 `incidents`，但顶部导航没有稳定的“案件”入口，后续 agent 很容易继续在两个 nav 源里改丢。
- 浏览器 E2E 已覆盖 Auth / Demo Flow / Incident Report，但没有单独锁住所有 Dashboard route tab 的可达性与核心 section。
- 继续往 `dashboard-client.tsx` 堆 UI 会让后续长任务 diff 过大、审查困难、局部回归难定位。

### 1.2 完成后用户可见行为

完成后必须满足：

1. 登录 Dashboard 后，桌面导航能看到并点击 `概览 / 监测 / 案件 / WAF 管理 / AI 配置 / 安全日报`。
2. 点击 `案件` 直接进入案件工作台，不需要先从告警创建案件。
3. 每个路由至少有一个稳定 section wrapper test id：
   - `dashboard-section-stats`
   - `dashboard-section-briefing`
   - `dashboard-section-trends`
   - `dashboard-section-alerts`
   - `dashboard-section-terminal-report`
   - `dashboard-section-security-timeline`
   - `dashboard-section-incidents`
   - `dashboard-section-system-status`
   - `dashboard-section-copilot`
   - `dashboard-section-ai-config`
   - `dashboard-section-webhook`
   - `dashboard-section-report`
4. `dashboard-client.tsx` 仍持有这些 controller/hook：`useAlerts`、`useConfig`、`useCopilot`、`useTerminal`、`useReport`、`useSiteHealth`、`useSecurityTimeline`、`useThreatConfirm`、`useIncidents`。
5. 新增 section 组件不得在内部重新调用上述业务 hook，特别是不得重新创建 `useIncidents()` 或 `useAlerts()`。
6. M3-09 的案件创建后自动打开 detail 行为不回退。
7. Auth / Demo Flow / Incident Report 三条 E2E 仍通过。

---

## 2. 修改范围

### 2.1 允许修改

- `web-next/app/dashboard/dashboard-client.tsx`
- `web-next/components/dashboard/SystemStatusBar.tsx`
- `web-next/components/dashboard/SectionHeading.tsx`（新增）
- `web-next/components/dashboard/DashboardFields.tsx`（新增）
- `web-next/components/dashboard/DashboardRows.tsx`（新增）
- `web-next/components/dashboard/sections/*.tsx`（新增）
- `web-next/constants/dashboardRoutes.ts`（新增）
- `web-next/types/route.ts`（仅必要时补注释，不改 union 语义）
- `server/tests/test_dashboard_route_sections_e2e.py`（新增）
- `docs/runs/2026-06-19-m3-10-dashboard-route-composition.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

### 2.2 禁止修改

- `server/services/auth_service.py`
- `server/core/auth*`
- `server/routers/auth*`
- `server/security/**`
- `server/core/state.py`
- `server/core/config.py`
- `server/analyzer.py`
- `server/core/utils.py`
- Alembic migration / 数据库 schema
- `REGISTER_RATE_LIMIT_MAX` / `REGISTER_RATE_LIMIT_WINDOW`
- `.env` / 真实 env / 数据库文件 / 密钥 / 证书
- `.coverage`

### 2.3 不做内容

- 不重做视觉设计，不改页面配色，不新增营销页。
- 不把 Dashboard 改成全局 Context Provider 大重构。
- 不迁移业务 state 到 Zustand/Redux/Context。
- 不新增后端 API。
- 不新增认证逻辑。
- 不引入新 npm 依赖。
- 不删除或弱化现有 E2E 断言。

---

## 3. 文件结构目标

新增或调整后的结构应该接近：

```text
web-next/
  constants/
    dashboardRoutes.ts
  components/dashboard/
    DashboardFields.tsx
    DashboardRows.tsx
    SectionHeading.tsx
    SystemStatusBar.tsx
    sections/
      DashboardBriefingSection.tsx
      DashboardTrendsSection.tsx
      DashboardAlertWorkspaceSection.tsx
      DashboardTerminalReportSection.tsx
      DashboardSecurityTimelineSection.tsx
      DashboardIncidentWorkspaceSection.tsx
      DashboardSystemStatusRouteSection.tsx
      DashboardCopilotRouteSection.tsx
      DashboardAiConfigSection.tsx
      DashboardWebhookSection.tsx
      DashboardReportSection.tsx
server/tests/
  test_dashboard_route_sections_e2e.py
```

`dashboard-client.tsx` 的职责收窄为：

- 创建 route state。
- 创建所有业务 hook/controller。
- 维护跨区块 handler：demo attack、CSV export、refresh alerts、analyze selected alert、create incident、triage submit、incident copilot custom event。
- 根据 route 组合 section 组件。
- 传入 props。

新增 section 组件的职责：

- 只负责渲染某个区块。
- 使用已传入的数据和 callback。
- 不直接调用后端 hook。
- 不持有跨业务状态。

---

## 4. TDD 计划

### Task 1: RED - 新增 Dashboard 路由可达性 E2E

**Files:**

- Create: `server/tests/test_dashboard_route_sections_e2e.py`
- Modify: `docs/runs/2026-06-19-m3-10-dashboard-route-composition.md`

- [ ] **Step 1: 写失败测试**

新增文件：

```python
"""M3-10 Dashboard route sections E2E（可选，需 --run-e2e）。

目标：
- 登录后 Dashboard 桌面导航必须暴露所有核心 route，包括 M3-09 后的 incidents。
- 点击每个 route 后，对应核心 section 必须可见。
- 整页 DOM 不得泄漏 secret / stack trace / system prompt sentinel。

运行前置：
1. 启动后端 dev server（默认 :8000）和前端 dev server（默认 :3000）。
2. 安装 Playwright：``pip install playwright && playwright install chromium``。
3. 运行：``pytest server/tests/test_dashboard_route_sections_e2e.py --run-e2e -q --tb=short -s``。
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

_FORBIDDEN_DOM_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"sk-proj-[A-Za-z0-9_-]+"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"\\bTraceback\\s+\\(most recent call last\\)", re.IGNORECASE),
    re.compile(r"ignore\\s+previous\\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\\s+.*system\\s+prompt", re.IGNORECASE),
    re.compile(r"forget\\s+.*instructions", re.IGNORECASE),
    re.compile(r"\\bsystem\\s*:\\s*", re.IGNORECASE),
    re.compile(r"\\bdeveloper\\s*:\\s*", re.IGNORECASE),
    re.compile(r"PRIVATE\\s+KEY", re.IGNORECASE),
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


async def _click_desktop_route(page, route_key: str) -> None:
    button = page.locator(f'[data-testid="dashboard-route-desktop-{route_key}"]').first
    await button.wait_for(state="visible", timeout=15000)
    await button.click()


async def _expect_section(page, test_id: str) -> None:
    await page.locator(f'[data-testid="{test_id}"]').first.wait_for(
        state="visible",
        timeout=15000,
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_dashboard_route_tabs_render_core_sections() -> None:
    skip_without_playwright()
    from playwright.async_api import async_playwright

    diag: dict[str, object] = {
        "registered": False,
        "routes": [],
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

        try:
            context = await browser.new_context(
                viewport={"width": 1366, "height": 900},
            )
            page = await context.new_page()
            await assert_dev_server_reachable(page)

            _email, _password, register_status = await register_or_login_for_e2e(
                page, "e2e-routes"
            )
            diag["registered"] = register_status in {"created", "exists"}

            await _expect_section(page, "dashboard-section-stats")
            await _expect_section(page, "dashboard-section-briefing")

            checks: list[tuple[str, tuple[str, ...]]] = [
                (
                    "overview",
                    (
                        "dashboard-section-stats",
                        "dashboard-section-briefing",
                        "dashboard-section-trends",
                        "dashboard-section-alerts",
                        "dashboard-section-terminal-report",
                        "dashboard-section-security-timeline",
                        "dashboard-section-copilot",
                        "dashboard-section-ai-config",
                        "dashboard-section-webhook",
                        "dashboard-section-report",
                    ),
                ),
                (
                    "monitor",
                    (
                        "dashboard-section-stats",
                        "dashboard-section-briefing",
                        "dashboard-section-trends",
                        "dashboard-section-alerts",
                        "dashboard-section-terminal-report",
                        "dashboard-section-security-timeline",
                    ),
                ),
                (
                    "incidents",
                    (
                        "dashboard-section-stats",
                        "dashboard-section-briefing",
                        "dashboard-section-incidents",
                        "incident-section",
                    ),
                ),
                (
                    "waf",
                    (
                        "dashboard-section-stats",
                        "dashboard-section-briefing",
                        "dashboard-section-system-status",
                    ),
                ),
                (
                    "ai",
                    (
                        "dashboard-section-stats",
                        "dashboard-section-briefing",
                        "dashboard-section-copilot",
                        "dashboard-section-ai-config",
                        "dashboard-section-webhook",
                    ),
                ),
                (
                    "report",
                    (
                        "dashboard-section-stats",
                        "dashboard-section-briefing",
                        "dashboard-section-report",
                    ),
                ),
            ]

            for route_key, section_ids in checks:
                await _click_desktop_route(page, route_key)
                for section_id in section_ids:
                    await _expect_section(page, section_id)
                diag["routes"].append(route_key)

            visible_text = await _collect_visible_text(page)
            forbidden = _contains_forbidden(visible_text)
            diag["forbidden"] = forbidden
            assert forbidden is None, (
                f"Dashboard route sections 出现禁止外泄内容(命中模式: {forbidden})。"
                f"前 200 字: {visible_text[:200]!r}"
            )

            print(f"\\n[E2E 诊断] {diag}")
        finally:
            await context.close()
            await browser.close()
```

- [ ] **Step 2: 运行 RED**

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_dashboard_route_sections_e2e.py -q --tb=short --run-e2e -s
```

预期 RED：

- 当前 `SystemStatusBar.tsx` 没有 `dashboard-route-desktop-incidents`。
- 当前多个 section 没有 `dashboard-section-*` wrapper。
- 失败必须来自上述缺口，不应来自登录 helper、dev server 不可达或 Playwright 缺失。

- [ ] **Step 3: 提交 RED**

只在 RED 原因正确时提交：

```powershell
git --literal-pathspecs add -- server/tests/test_dashboard_route_sections_e2e.py docs/runs/2026-06-19-m3-10-dashboard-route-composition.md
git diff --cached --check
git commit -m "test(e2e): 复现 dashboard 路由区块可达性缺口"
```

---

### Task 2: GREEN - 单一路由元数据与导航

**Files:**

- Create: `web-next/constants/dashboardRoutes.ts`
- Modify: `web-next/components/dashboard/SystemStatusBar.tsx`
- Modify: `web-next/app/dashboard/dashboard-client.tsx`

- [ ] **Step 1: 新增路由元数据文件**

新增：

```typescript
import type { RouteKey } from "@/types/route";

export type DashboardRouteMeta = {
  key: RouteKey;
  label: string;
  index: string;
  description: string;
};

export const DASHBOARD_NAV_ITEMS: DashboardRouteMeta[] = [
  {
    key: "overview",
    label: "概览",
    index: "01",
    description: "全局安全态势、实时告警、AI 助手、配置与日报的综合视图。",
  },
  {
    key: "monitor",
    label: "监测",
    index: "02",
    description: "聚焦告警流、趋势图、终端输出与安全运营时间线。",
  },
  {
    key: "incidents",
    label: "案件",
    index: "03",
    description: "把分散告警归并为可追踪案件，推进处置状态并导出证据报告。",
  },
  {
    key: "waf",
    label: "WAF 管理",
    index: "04",
    description: "配置受保护站点、测试代理链路并确认威胁入库。",
  },
  {
    key: "ai",
    label: "AI 配置",
    index: "05",
    description: "管理 Copilot 会话、模型路由、Webhook 与通知渠道。",
  },
  {
    key: "report",
    label: "安全日报",
    index: "06",
    description: "查看由真实告警派生的安全日报与态势摘要。",
  },
];

export const DASHBOARD_ROUTE_META: Record<RouteKey, DashboardRouteMeta> =
  DASHBOARD_NAV_ITEMS.reduce(
    (acc, item) => {
      acc[item.key] = item;
      return acc;
    },
    {} as Record<RouteKey, DashboardRouteMeta>
  );

export function getDashboardRouteMeta(route: RouteKey): DashboardRouteMeta {
  return DASHBOARD_ROUTE_META[route];
}
```

- [ ] **Step 2: 更新 `SystemStatusBar.tsx`**

改动要求：

- 删除文件内本地 `NAV_ITEMS`。
- import `DASHBOARD_NAV_ITEMS`。
- 桌面按钮添加 `data-testid={`dashboard-route-desktop-${item.key}`}`。
- 移动端按钮添加 `data-testid={`dashboard-route-mobile-${item.key}`}`。
- 两类按钮都添加 `data-dashboard-route={item.key}`。
- active 按钮添加 `aria-current="page"`，非 active 为 `undefined`。
- 不改 `signOut`、主题、通知、WS 状态、status bar 语义。

关键片段：

```tsx
import { DASHBOARD_NAV_ITEMS } from "@/constants/dashboardRoutes";
```

桌面 nav 内按钮应变成：

```tsx
<button
  key={item.key}
  data-testid={`dashboard-route-desktop-${item.key}`}
  data-dashboard-route={item.key}
  aria-current={active ? "page" : undefined}
  onClick={() => onChangeRoute(item.key)}
  className={`text-xs font-mono uppercase tracking-[0.1em] transition-colors flex items-center gap-1.5 ${
    active ? "text-accent" : "text-ink-secondary hover:text-ink"
  }`}
>
  <span className="opacity-50">{item.index}</span>
  {item.label}
</button>
```

移动 nav 内按钮应使用同样逻辑，但 test id 为 `dashboard-route-mobile-${item.key}`。

- [ ] **Step 3: 更新 `dashboard-client.tsx` route meta**

改动要求：

- 删除本地 `NAV_ITEMS`。
- import `getDashboardRouteMeta`。
- `const currentRoute = getDashboardRouteMeta(route);`
- 继续把 `routeIndex`、`routeLabel`、`routeDescription` 传给 `SystemStatusBar`。
- 如果仍使用 `routeDescription(route)`，必须删除该依赖并用单一路由元数据替代，避免三处漂移。

片段：

```tsx
import { getDashboardRouteMeta } from "@/constants/dashboardRoutes";
```

```tsx
const currentRoute = getDashboardRouteMeta(route);
```

```tsx
<SystemStatusBar
  userEmail={userEmail}
  wsConnected={alertsCtx.wsConnected}
  route={route}
  onChangeRoute={setRoute}
  statusMessage={configCtx.status}
  routeIndex={currentRoute.index}
  routeLabel={currentRoute.label}
  routeDescription={currentRoute.description}
  pageFocus={isOverviewRoute ? "ALL SYSTEMS" : "FOCUSED VIEW"}
/>
```

- [ ] **Step 4: 最小验证**

```powershell
cd web-next
npm run typecheck
```

预期：0 TypeScript 错误。

---

### Task 3: GREEN - 抽出共享 UI 原子组件

**Files:**

- Create: `web-next/components/dashboard/SectionHeading.tsx`
- Create: `web-next/components/dashboard/DashboardFields.tsx`
- Create: `web-next/components/dashboard/DashboardRows.tsx`
- Modify: `web-next/app/dashboard/dashboard-client.tsx`

- [ ] **Step 1: 新增 `SectionHeading.tsx`**

```tsx
"use client";

import type { ReactNode } from "react";

export interface SectionHeadingProps {
  index: string;
  title: string;
  description?: string;
  action?: ReactNode;
}

export default function SectionHeading({
  index,
  title,
  description,
  action,
}: SectionHeadingProps) {
  return (
    <div className="flex items-baseline justify-between mb-6 pb-3 border-b border-line">
      <div>
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-accent mb-1.5">
          {index}
        </div>
        <h2 className="font-display text-2xl text-ink tracking-tight">{title}</h2>
        {description ? (
          <p className="text-xs text-ink-secondary mt-1">{description}</p>
        ) : null}
      </div>
      {action}
    </div>
  );
}
```

- [ ] **Step 2: 新增 `DashboardFields.tsx`**

```tsx
"use client";

import type { ReactNode } from "react";

export function FieldLabel({ children }: { children: ReactNode }) {
  return (
    <label className="block text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary mb-1.5">
      {children}
    </label>
  );
}

export function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className="w-full bg-transparent text-ink text-sm py-2 px-0 border-0 border-b border-line focus:outline-none focus:border-accent transition-colors placeholder:text-ink-tertiary"
    />
  );
}

export function SelectInput(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className="w-full bg-transparent text-ink text-sm py-2 px-0 border-0 border-b border-line focus:outline-none focus:border-accent transition-colors cursor-pointer"
    />
  );
}
```

- [ ] **Step 3: 新增 `DashboardRows.tsx`**

```tsx
"use client";

export function SessionRow({
  label,
  value,
  tone,
  mono,
}: {
  label: string;
  value: string;
  tone?: "ok" | "error";
  mono?: boolean;
}) {
  return (
    <div className="py-3 flex items-baseline justify-between gap-4">
      <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary shrink-0">
        {label}
      </span>
      <span
        className={`text-sm text-right ${
          tone === "ok" ? "text-success" : tone === "error" ? "text-danger" : "text-ink"
        } ${mono ? "font-mono tabular-nums" : ""}`}
      >
        {value}
      </span>
    </div>
  );
}

export function ChannelRow({
  label,
  enabled,
  customText,
}: {
  label: string;
  enabled: boolean;
  customText?: string;
}) {
  return (
    <div className="py-3 flex items-baseline justify-between">
      <div className="flex items-center gap-2">
        <span className={`w-1 h-1 rounded-full ${enabled ? "bg-accent" : "bg-ink-tertiary"}`} />
        <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary">
          {label}
        </span>
      </div>
      <span className={`text-sm ${enabled ? "text-ink" : "text-ink-tertiary"}`}>
        {customText || (enabled ? "已开启" : "已关闭")}
      </span>
    </div>
  );
}
```

- [ ] **Step 4: 从 `dashboard-client.tsx` 删除本地重复组件**

删除本地：

- `SectionHeading`
- `FieldLabel`
- `TextInput`
- `SelectInput`
- `SessionRow`
- `ChannelRow`

改用 import：

```tsx
import SectionHeading from "@/components/dashboard/SectionHeading";
import { FieldLabel, SelectInput, TextInput } from "@/components/dashboard/DashboardFields";
import { ChannelRow, SessionRow } from "@/components/dashboard/DashboardRows";
```

- [ ] **Step 5: 验证**

```powershell
cd web-next
npm run typecheck
```

预期：0 TypeScript 错误。

---

### Task 4: GREEN - 抽出 route section 组件

**Files:**

- Create: `web-next/components/dashboard/sections/DashboardBriefingSection.tsx`
- Create: `web-next/components/dashboard/sections/DashboardTrendsSection.tsx`
- Create: `web-next/components/dashboard/sections/DashboardAlertWorkspaceSection.tsx`
- Create: `web-next/components/dashboard/sections/DashboardTerminalReportSection.tsx`
- Create: `web-next/components/dashboard/sections/DashboardSecurityTimelineSection.tsx`
- Create: `web-next/components/dashboard/sections/DashboardIncidentWorkspaceSection.tsx`
- Create: `web-next/components/dashboard/sections/DashboardSystemStatusRouteSection.tsx`
- Create: `web-next/components/dashboard/sections/DashboardCopilotRouteSection.tsx`
- Create: `web-next/components/dashboard/sections/DashboardAiConfigSection.tsx`
- Create: `web-next/components/dashboard/sections/DashboardWebhookSection.tsx`
- Create: `web-next/components/dashboard/sections/DashboardReportSection.tsx`
- Modify: `web-next/app/dashboard/dashboard-client.tsx`

#### 4.1 基本规则

每个 section 组件必须：

- `"use client";`
- 顶层 wrapper 使用 `className="mt-14"`，除非当前页面已有更合适的 wrapper。
- 顶层 wrapper 加对应 `data-testid`。
- 使用 `SectionHeading`。
- 接收 props，不创建业务 hook。
- 保留原有子组件 props 与 data-testid。

#### 4.2 必须新增的 section wrapper test id

| 文件 | test id |
|---|---|
| `DashboardBriefingSection.tsx` | `dashboard-section-briefing` |
| `DashboardTrendsSection.tsx` | `dashboard-section-trends` |
| `DashboardAlertWorkspaceSection.tsx` | `dashboard-section-alerts` |
| `DashboardTerminalReportSection.tsx` | `dashboard-section-terminal-report` |
| `DashboardSecurityTimelineSection.tsx` | `dashboard-section-security-timeline` |
| `DashboardIncidentWorkspaceSection.tsx` | `dashboard-section-incidents` |
| `DashboardSystemStatusRouteSection.tsx` | `dashboard-section-system-status` |
| `DashboardCopilotRouteSection.tsx` | `dashboard-section-copilot` |
| `DashboardAiConfigSection.tsx` | `dashboard-section-ai-config` |
| `DashboardWebhookSection.tsx` | `dashboard-section-webhook` |
| `DashboardReportSection.tsx` | `dashboard-section-report` |

`StatsCards` 外层在 `dashboard-client.tsx` 加：

```tsx
<div data-testid="dashboard-section-stats">
  <StatsCards stats={counters} />
</div>
```

#### 4.3 `DashboardBriefingSection.tsx`

```tsx
"use client";

import BriefingSection from "@/components/dashboard/BriefingSection";
import SectionHeading from "@/components/dashboard/SectionHeading";
import type { AlertLogItem } from "@/types/alert";

export interface DashboardBriefingSectionProps {
  alerts: AlertLogItem[];
}

export default function DashboardBriefingSection({
  alerts,
}: DashboardBriefingSectionProps) {
  return (
    <div className="mt-14" data-testid="dashboard-section-briefing">
      <SectionHeading
        index="§ 00"
        title="日 / 周安全简报"
        description="基于当前告警流自动派生的态势指标。所有数据均来自真实告警记录,严禁伪造。"
      />
      <div className="p-6 bg-bg-raised border-l border-accent rounded-md">
        <BriefingSection alerts={alerts} />
      </div>
    </div>
  );
}
```

如果当前类型名不是 `AlertLogItem`，从 `web-next/types/alert.ts` 读取真实导出后使用实际类型；不得使用 `any`。

#### 4.4 `DashboardTrendsSection.tsx`

把 `AttackTrendChart` 和 `SourcePieChart` 的 dynamic import 从 `dashboard-client.tsx` 移入本组件：

```tsx
"use client";

import dynamic from "next/dynamic";
import SectionHeading from "@/components/dashboard/SectionHeading";
import type { AlertLogItem } from "@/types/alert";

const AttackTrendChart = dynamic(
  () => import("@/components/dashboard/AttackTrendChart"),
  { ssr: false, loading: () => <div className="h-full bg-bg-raised/40 animate-pulse" /> }
);

const SourcePieChart = dynamic(
  () => import("@/components/dashboard/SourcePieChart"),
  { ssr: false, loading: () => <div className="h-full bg-bg-raised/40 animate-pulse" /> }
);

export interface DashboardTrendsSectionProps {
  alerts: AlertLogItem[];
}

export default function DashboardTrendsSection({
  alerts,
}: DashboardTrendsSectionProps) {
  return (
    <div className="mt-14" data-testid="dashboard-section-trends">
      <SectionHeading
        index="§ 01"
        title="攻击趋势与分布"
        description="近 24 时段攻击曲线 + 风险级别与来源 TOP 6"
      />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="h-[300px]">
          <AttackTrendChart alerts={alerts} />
        </div>
        <div className="h-[300px]">
          <SourcePieChart alerts={alerts} />
        </div>
      </div>
    </div>
  );
}
```

#### 4.5 `DashboardAlertWorkspaceSection.tsx`

该组件接收 slots，避免把 `AttackLogTable`、`AlertDetailPanel` 的业务拼装强行搬太深：

```tsx
"use client";

import type { ReactNode } from "react";
import AlertSection from "@/components/dashboard/AlertSection";
import SectionHeading from "@/components/dashboard/SectionHeading";
import DemoFlowControls from "@/components/dashboard/DemoFlowControls";
import type { DemoAttackState } from "@/hooks/useAlerts";

export interface DashboardAlertWorkspaceSectionProps {
  loadState: "loading" | "ready" | "empty" | "error";
  wsConnected: boolean;
  totalAlerts: number;
  totalPages: number;
  page: number;
  selectedCountLabel: string;
  demoState: DemoAttackState;
  demoMessage: string | null;
  listSlot: ReactNode;
  detailSlot: ReactNode;
  onPrevPage: () => void;
  onNextPage: () => void;
  onRefresh: () => void;
  onRetry: () => void;
  onTriggerDemo: () => void;
  onExportCsv: () => void;
}

export default function DashboardAlertWorkspaceSection({
  loadState,
  wsConnected,
  totalAlerts,
  totalPages,
  page,
  selectedCountLabel,
  demoState,
  demoMessage,
  listSlot,
  detailSlot,
  onPrevPage,
  onNextPage,
  onRefresh,
  onRetry,
  onTriggerDemo,
  onExportCsv,
}: DashboardAlertWorkspaceSectionProps) {
  return (
    <div className="mt-14" data-testid="dashboard-section-alerts">
      <SectionHeading
        index="§ 02"
        title="实时告警、详情与 AI 助手"
        description={selectedCountLabel}
      />
      <AlertSection
        loadState={loadState}
        wsConnected={wsConnected}
        totalAlerts={totalAlerts}
        totalPages={totalPages}
        page={page}
        listSlot={listSlot}
        detailSlot={detailSlot}
        onPrevPage={onPrevPage}
        onNextPage={onNextPage}
        onRefresh={onRefresh}
        onRetry={onRetry}
        toolbarSlot={
          <DemoFlowControls
            demoState={demoState}
            demoMessage={demoMessage}
            onTriggerDemo={onTriggerDemo}
            onExportCsv={onExportCsv}
            onRefreshAlerts={onRefresh}
          />
        }
      />
    </div>
  );
}
```

如果 `DemoAttackState` 没有从 hook 导出，不要用 `any`；在 `useAlerts.ts` 中导出对应类型，或用 `React.ComponentProps<typeof DemoFlowControls>["demoState"]` 派生。

#### 4.6 其他 section

按同一规则抽出：

- `DashboardTerminalReportSection.tsx`：渲染原 “终端与安全日报” 区块，保留 `RefreshCw` 动画按钮、`HackerTerminal`、`reportCtx.markdown`。
- `DashboardSecurityTimelineSection.tsx`：渲染原安全运营时间线区块，透传 `SecurityTimelinePanel` props。
- `DashboardIncidentWorkspaceSection.tsx`：渲染原案件工作台区块，接收 `incidents` controller，内部只写 `<IncidentSection incidents={incidents} />`。
- `DashboardSystemStatusRouteSection.tsx`：渲染原站点监测与威胁确认区块，透传 `SystemStatusSection` props。
- `DashboardCopilotRouteSection.tsx`：渲染原 AI 助手上下文区块，透传 `CopilotSection` props。
- `DashboardAiConfigSection.tsx`：渲染原 AI 路由配置 + 当前会话区块，使用 `FieldLabel`、`TextInput`、`SelectInput`、`SessionRow`。
- `DashboardWebhookSection.tsx`：渲染原 Webhook 通知与渠道状态区块，使用 `FieldLabel`、`TextInput`、`SelectInput`、`ChannelRow`。
- `DashboardReportSection.tsx`：渲染原日报摘要区块。

每个组件必须从现有 JSX 平移，不能改文案语义、按钮禁用条件、callback 触发条件、test id、下载/复制行为。

- [ ] **Step 2: 更新 `dashboard-client.tsx` 组合逻辑**

`dashboard-client.tsx` 应保留 route boolean：

```tsx
const isOverviewRoute = route === "overview";
const isMonitorRoute = route === "monitor";
const isIncidentsRoute = route === "incidents";
const isWafRoute = route === "waf";
const isAiRoute = route === "ai";
const isReportRoute = route === "report";
```

并把 JSX 变成清晰组合：

```tsx
<div data-testid="dashboard-section-stats">
  <StatsCards stats={counters} />
</div>

<DashboardBriefingSection alerts={alertsCtx.alerts} />

{(isOverviewRoute || isMonitorRoute) && (
  <DashboardTrendsSection alerts={alertsCtx.alerts} />
)}

{(isOverviewRoute || isMonitorRoute) && (
  <DashboardAlertWorkspaceSection
    loadState={alertsCtx.loadState}
    wsConnected={alertsCtx.wsConnected}
    totalAlerts={alertsCtx.alerts.length}
    totalPages={alertsCtx.totalPages}
    page={alertsCtx.page}
    selectedCountLabel={`共 ${alertsCtx.alerts.length} 条告警 · ${
      alertsCtx.wsConnected ? "WebSocket 实时" : "轮询刷新"
    }`}
    demoState={alertsCtx.demoState}
    demoMessage={alertsCtx.demoMessage}
    listSlot={...}
    detailSlot={...}
    onPrevPage={() => alertsCtx.setPage(Math.max(0, alertsCtx.page - 1))}
    onNextPage={() => alertsCtx.setPage(Math.min(alertsCtx.totalPages - 1, alertsCtx.page + 1))}
    onRefresh={handleRefreshAlerts}
    onRetry={() => void alertsCtx.loadAlerts({ showLoading: true })}
    onTriggerDemo={() => void handleTriggerDemoAttack()}
    onExportCsv={handleExportCsv}
  />
)}
```

`listSlot` 与 `detailSlot` 仍在父层创建，确保 triage、incident、selected alert 关系不丢。

- [ ] **Step 3: 验证 `dashboard-client.tsx` 收窄**

记录：

```powershell
(Get-Content -LiteralPath web-next\app\dashboard\dashboard-client.tsx).Count
```

目标：从约 836 行下降到 420 行以内。若略高于 420，但已完成 section 抽离且 typecheck/build/E2E 通过，可继续；若仍高于 520 行，必须停止并说明哪里未拆。

- [ ] **Step 4: 类型检查**

```powershell
cd web-next
npm run typecheck
```

预期：0 错误。

---

### Task 5: GREEN - 跑通新增 E2E 与现有关键 E2E

**Files:**

- Modify: `docs/runs/2026-06-19-m3-10-dashboard-route-composition.md`

- [ ] **Step 1: 新增 E2E 应从 RED 变 GREEN**

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_dashboard_route_sections_e2e.py -q --tb=short --run-e2e -s
```

预期：

- 1 passed。
- 诊断输出 `routes` 包含 `overview / monitor / incidents / waf / ai / report`。

- [ ] **Step 2: M3-09 关键回归 E2E**

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_auth_session_e2e.py server\tests\test_demo_flow_e2e.py server\tests\test_incident_report_e2e.py server\tests\test_dashboard_route_sections_e2e.py -q --tb=short --run-e2e -s
```

预期：

- 4 passed。
- 不需要重启 dev server。
- Incident Report E2E 仍直接等待 `incident-detail-panel`，不能恢复点击 list item workaround。

- [ ] **Step 3: 默认后端全量**

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

预期：

- 默认跳过 E2E。
- 不出现新失败。

- [ ] **Step 4: Guardrails 专项**

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

预期：

- 与 M3-09 baseline 一致，无回归。

- [ ] **Step 5: 前端 typecheck/build，必须顺序执行**

```powershell
cd web-next
npm run typecheck
npm run build
```

注意：不得并行运行 `npm run typecheck` 与 `npm run build`。

---

### Task 6: IMPROVE - De-sloppify 与审查

**Files:**

- All touched files

- [ ] **Step 1: 搜索禁止模式**

```powershell
rg -n "TODO|FIXME|console\\.log|localStorage|sessionStorage|useIncidents\\(" web-next\app\dashboard web-next\components\dashboard web-next\constants server\tests\test_dashboard_route_sections_e2e.py
```

要求：

- `useIncidents(` 只允许出现在 `dashboard-client.tsx` 或 `useIncidents.ts`，不得出现在新的 route section 内。
- 不得新增 `localStorage` / `sessionStorage`。
- 不得留下 `console.log`。
- 如存在旧注释命中，必须判断是否本任务新增；本任务不得新增无意义 TODO。

- [ ] **Step 2: 检查 diff 范围**

```powershell
git diff --stat
git diff -- web-next\app\dashboard\dashboard-client.tsx web-next\components\dashboard\SystemStatusBar.tsx
```

确认：

- 没有认证/后端/security/schema 代码改动。
- 没有 `.coverage`。
- 没有真实 env。
- 没有 token/password/cookie 输出。

- [ ] **Step 3: 做前端安全自审**

在运行日志写下结论：

- 本任务不触碰后端 auth。
- 本任务不触碰 Guardrails。
- 本任务不触碰 SSRF。
- 本任务不触碰 DB schema。
- E2E helper 仍走 httpOnly cookie path。
- 新 section 不读写 storage。
- 新 section 不拼接危险 HTML。

---

### Task 7: 文档同步

**Files:**

- Modify: `docs/runs/2026-06-19-m3-10-dashboard-route-composition.md`
- Modify: `docs/agent/UNATTENDED_LONG_TASKS.md`
- Modify: `PRODUCT.md`
- Modify: `docs/plans/M2_PRODUCT_ROADMAP.md`

- [ ] **Step 1: 更新 run log 最终状态**

必须包含：

- 改动摘要。
- `dashboard-client.tsx` 拆分前/后行数。
- 新增 route metadata 文件说明。
- 新增 section 文件列表。
- 新增 E2E 验证结果。
- 现有 E2E 回归结果。
- 后端全量 / Guardrails / 前端 typecheck/build 结果。
- 安全边界说明。
- 下一条建议工单。

- [ ] **Step 2: 更新 `UNATTENDED_LONG_TASKS.md`**

必须：

- 把 `M3_10_DASHBOARD_ROUTE_COMPOSITION_TASK.md` 加入可用超长任务列表。
- 把推荐启动口令更新为下一条建议，不再指向 M3-10。
- 记录 M3-10 已交付内容。

- [ ] **Step 3: 更新 `PRODUCT.md` 与路线图**

必须记录：

- M3-10 已完成 Dashboard route composition 拆分。
- `incidents` 顶部导航恢复为一等入口。
- Dashboard section E2E 已覆盖 route 可达性。
- `dashboard-client.tsx` 保持 controller 编排，不再直接承载大段 route JSX。

---

## 5. 提交策略

禁止使用 `git add .`。

提交前必须运行：

```powershell
git status --short
git diff --cached --check
git diff --cached --name-only
```

不得 stage：

- `.coverage`
- `.claude/settings.local.json`
- `.env`
- 数据库文件
- 密钥 / 证书 / token

建议 commit 拆分：

1. `test(e2e): 复现 dashboard 路由区块可达性缺口`
   - `server/tests/test_dashboard_route_sections_e2e.py`
   - run log RED 阶段

2. `refactor(dashboard): 统一路由元数据与导航入口`
   - `web-next/constants/dashboardRoutes.ts`
   - `web-next/components/dashboard/SystemStatusBar.tsx`
   - `web-next/app/dashboard/dashboard-client.tsx`

3. `refactor(dashboard): 拆分 route section 渲染组件`
   - `web-next/components/dashboard/SectionHeading.tsx`
   - `web-next/components/dashboard/DashboardFields.tsx`
   - `web-next/components/dashboard/DashboardRows.tsx`
   - `web-next/components/dashboard/sections/*.tsx`
   - `web-next/app/dashboard/dashboard-client.tsx`

4. `test(e2e): 覆盖 dashboard 路由区块回归`
   - 如果 commit 1 的测试此时从 RED 变 GREEN 且需要补诊断/selector，放在此提交。

5. `docs(dashboard): 记录 route composition 收口`
   - run log
   - `docs/agent/UNATTENDED_LONG_TASKS.md`
   - `PRODUCT.md`
   - `docs/plans/M2_PRODUCT_ROADMAP.md`

通过全部质量门后可 push：

```powershell
git push origin main
```

---

## 6. 停止条件

满足任一条件必须停止并写清楚阻塞：

1. 新增 E2E 失败 3 轮仍无法确认是实现缺口还是环境问题。
2. 为完成拆分需要修改认证/授权/后端 security/DB schema。
3. 新 section 拆分导致 `useIncidents()`、`useAlerts()` 等 controller 在多个子组件里重复创建。
4. `dashboard-client.tsx` 拆分后 M3-09 Incident Report E2E 回退，或重新需要点击 `incident-list-item` 才能出现 detail。
5. 前端 typecheck/build 出现与本任务无关的大面积错误，且无法在 3 轮内定位。
6. diff 超过约 900 行且主要不是平移 JSX / 新 section 文件。
7. 发现真实 secret / token / env 被改动或出现在 diff 中。

停止时必须交付：

- 已完成内容。
- 未完成内容。
- 阻塞证据。
- 建议下一条最小工单。

---

## 7. 最终报告模板

完成后按这个格式输出：

```markdown
完成状态：完成 / 部分完成 / 阻塞

改动摘要：
- ...

关键文件：
- ...

验证：
- `pytest server/tests/test_dashboard_route_sections_e2e.py --run-e2e` -> ...
- `pytest server/tests/test_auth_session_e2e.py server/tests/test_demo_flow_e2e.py server/tests/test_incident_report_e2e.py server/tests/test_dashboard_route_sections_e2e.py --run-e2e` -> ...
- `pytest server/tests` -> ...
- `pytest server/tests/security/llm_guardrails` -> ...
- `npm run typecheck` -> ...
- `npm run build` -> ...

安全边界：
- 未改认证/授权/Guardrails/SSRF/DB schema。
- 未写 localStorage/sessionStorage/DOM token。
- 未提交 `.coverage` / env / 数据库 / 密钥。

运行日志：
- `docs/runs/2026-06-19-m3-10-dashboard-route-composition.md`

Commit / Push：
- ...

下一条建议工单：
- ...
```
