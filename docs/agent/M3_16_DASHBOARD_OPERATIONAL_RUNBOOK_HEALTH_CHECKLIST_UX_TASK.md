# M3-16 Dashboard Operational Runbook / Health Checklist UX 收口任务

> **给无人值守 Agent 的任务文档。** 本任务是 L5 超长任务：先读上下文，创建运行日志，按 TDD/E2E 红绿推进，阶段性记录证据，最后通过完整验证矩阵后精确 commit / push。不要把 skipped 当 passed。
>
> **执行要求**：实现时必须使用 `superpowers:executing-plans` 或 `superpowers:subagent-driven-development`，并使用 `superpowers:test-driven-development` 与 `superpowers:verification-before-completion`。如果当前环境没有子智能体工具，降级为 inline 执行，但仍要按阶段写运行日志。

## 0. 任务一句话

把 Dashboard 的 WAF / 系统状态区升级成一个 owner 可自助排障的 **Operational Runbook / Health Checklist**：用户能在一个紧凑面板里看到后端健康、Next API 代理健康、登录会话、Demo readiness、E2E readiness、env security check 指引，并复制一份不含密钥的诊断摘要。

## 1. 背景

已交付能力：

- M3-10 已把 Dashboard route composition 收口，`waf` route 由 `DashboardSystemStatusRouteSection` 承载。
- `SystemStatusSection.tsx` 已有站点状态、代理 WAF 测试、威胁确认与语音开关。
- `useSiteHealth.ts` 已轮询 `/api/backend/site/health`，并把健康态映射为 `online / warning / offline`。
- `test_dashboard_route_sections_e2e.py` 和 `test_dashboard_responsive_e2e.py` 已覆盖 Dashboard route wrapper、桌面/移动响应式、横向溢出、icon-only 命名和 DOM forbidden sentinel。
- M3-15 已完成 SOC 时间线筛选、详情展开、复制摘要和真实浏览器截图验证。

当前体验缺口：

- owner 需要知道“现在该怎么判断系统能不能演示 / 能不能排障”，但这些信息分散在 README、运行日志、脚本和测试命令里。
- Dashboard 没有一个只读运维检查面板，把 `/health`、Next API 代理、登录会话、Demo 入口、E2E 命令、env security check 命令连成一个可复制的诊断摘要。
- 新用户遇到 “Copilot 不输出 / Demo 不动 / E2E 失败” 时，需要翻多份文档，不能直接在产品界面看到最小检查清单。
- 还没有真实浏览器 E2E 证明这个 runbook 面板在桌面和移动端可读、不泄露密钥、不依赖 storage、不触碰后端安全边界。

本任务默认不改后端 API、不新增数据库字段、不执行环境安全脚本、不读取真实 env、不修改认证/授权/Guardrails。它只把现有前端健康态和静态安全命令整理成一个 Dashboard UX。

## 2. 必读上下文

开始前必须完整阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/runs/2026-06-20-m3-15-soc-timeline-drilldown-filter-ux.md`
- `docs/runs/2026-06-19-m3-13-dashboard-mobile-visual-qa.md`
- `docs/runs/2026-06-19-m3-11-dashboard-section-responsive-qa.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md` 中 M3 Dashboard / operational readiness 相关段落
- `web-next/app/dashboard/dashboard-client.tsx`
- `web-next/components/dashboard/SystemStatusSection.tsx`
- `web-next/components/dashboard/sections/DashboardSystemStatusRouteSection.tsx`
- `web-next/hooks/useSiteHealth.ts`
- `web-next/constants/dashboardRoutes.ts`
- `server/tests/e2e_helpers.py`
- `server/tests/test_dashboard_route_sections_e2e.py`
- `server/tests/test_dashboard_responsive_e2e.py`
- `scripts/check_env_security.py`（只读理解命令和退出码，不在前端调用）

必须使用或参考的 skill：

- `superpowers:executing-plans` 或 `superpowers:subagent-driven-development`
- `superpowers:test-driven-development`
- `superpowers:verification-before-completion`
- `frontend-patterns`
- `frontend-design`
- `e2e-testing`

## 3. 硬边界

允许修改：

- `web-next/components/dashboard/sections/DashboardSystemStatusRouteSection.tsx`
- `web-next/components/dashboard/SystemStatusSection.tsx`
- 可新增 `web-next/components/dashboard/OperationalRunbookPanel.tsx`
- 可新增 `web-next/types/operationalRunbook.ts`
- `web-next/app/dashboard/dashboard-client.tsx`（仅限向 system status section 传递已有 `userEmail`、route 或健康态 props，不重排业务 hook）
- 新增 `server/tests/test_dashboard_operational_runbook_e2e.py`
- 必要时轻量更新 `server/tests/test_dashboard_route_sections_e2e.py`
- 必要时轻量更新 `server/tests/test_dashboard_responsive_e2e.py`
- `docs/runs/2026-06-21-m3-16-dashboard-operational-runbook-health-checklist-ux.md`
- `docs/runs/artifacts/m3-16-dashboard-operational-runbook/**`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

禁止修改：

- 认证 / 授权生产逻辑
- `server/security/**` / Guardrails
- SSRF
- DB schema / Alembic migration
- 后端 API contract，包括 `/health`、`/api/backend/health`、`/api/backend/site/health`
- `scripts/check_env_security.py` 的行为
- npm 依赖
- rate limit 常量
- `.env`、`.coverage`、数据库、真实密钥
- 在浏览器里执行 PowerShell / Python / env security check
- 在浏览器或后端读取真实 `.env`
- 用 `localStorage` / `sessionStorage` 保存 runbook 或诊断摘要
- 使用 `dangerouslySetInnerHTML` 或 `innerHTML`
- 把 token、cookie、API key、stack trace、system prompt、raw env、完整异常写入 DOM、截图说明、运行日志或复制摘要

## 4. 运行预算与停止条件

预算：

- 最长运行 4 小时。
- 同一失败最多修复 3 轮。
- diff 超过约 900 行时停止总结，除非主要是测试/文档。

必须停止并写清楚阻塞：

- Playwright 浏览器无法启动，且无法用 `PLAYWRIGHT_CHROMIUM_EXECUTABLE` 指到系统 Chrome 解决。
- dev server 无法稳定返回 `/api/backend/health`。
- 需要修改认证、Guardrails、SSRF、DB schema、后端 API、依赖或 rate limit 常量。
- 需要让前端执行本地脚本或读取真实环境变量才能完成 UX。
- E2E 只能 skipped，无法获得真实浏览器 pass。
- DOM、复制摘要或截图说明中出现 forbidden sentinel。
- 运行日志发现当前工作区存在 unrelated dirty files 时，不允许 broad stage；只能精确 stage 本任务文件。

## 5. 产品验收标准

完成后用户应该能在 Dashboard 的 `WAF 管理` route 和 `概览` route 中看到一个运维检查面板：

1. 面板标题表达清楚这是 Operational Runbook / Health Checklist。
2. 面板至少包含 6 行检查项：
   - 后端健康：来自现有 `siteState` / `useSiteHealth` 的健康文案和 tone。
   - Next API 代理：说明 `/api/backend/health` 是 E2E 前置探针，显示“可由 E2E 自动探测”。
   - 登录会话：显示当前用户邮箱的脱敏版本，例如 `a***@example.com`；不展示 token / cookie。
   - Demo readiness：说明 `trigger-demo-attack` 入口、告警列表和 Copilot fallback 是关键演示链路。
   - E2E readiness：展示可复制的关键命令，不自动执行。
   - Env security check：展示 `scripts/check_env_security.py` 的本地运行命令和生产阻塞语义，不自动执行。
3. 每行检查项有明确状态 tone：
   - `ok`
   - `warn`
   - `manual`
   - `blocked`
4. 面板提供 `复制诊断摘要` 按钮：
   - `data-testid="runbook-copy-summary"`
   - 成功或失败状态 `data-testid="runbook-copy-status"`
   - 复制内容只包含安全字段：时间戳、健康文案、代理探针说明、脱敏邮箱、检查项状态、推荐命令。
5. 面板展示 4 条安全命令，便于 owner 复制到终端：
   - `.venv\Scripts\python.exe -m pytest server\tests -q --tb=short`
   - `.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short`
   - `cd web-next && npm run typecheck`
   - `cd web-next && npm run build`
   - 另展示 env security 命令：`.venv\Scripts\python.exe scripts\check_env_security.py`
6. 桌面和移动端不产生整页横向溢出，命令文本可换行或在面板内部横向滚动，但不能撑破页面。
7. DOM、复制文本、截图说明均不包含 forbidden sentinel。

## 6. 推荐设计

### 6.1 UI 形态

在 `DashboardSystemStatusRouteSection` 的 `SystemStatusSection` 下方加入一个紧凑的 runbook 面板，建议新增组件：

```text
web-next/components/dashboard/OperationalRunbookPanel.tsx
```

建议测试 ID：

```text
operational-runbook-panel
runbook-check-backend-health
runbook-check-proxy-health
runbook-check-auth-session
runbook-check-demo-readiness
runbook-check-e2e-readiness
runbook-check-env-security
runbook-command-backend-pytest
runbook-command-guardrails
runbook-command-frontend-typecheck
runbook-command-frontend-build
runbook-command-env-security
runbook-copy-summary
runbook-copy-status
```

视觉要求：

- 保持当前 SOC 工具风格：紧凑、信息密集、低噪声。
- 不做 hero、不做营销卡片、不新增大面积装饰。
- 不把卡片套卡片；如果现有 section 已是页面区块，runbook 面板用轻量边框 / 分隔线 / 网格即可。
- 移动端优先可读性，命令文本允许 `break-all` 或面板内 `overflow-x-auto`。
- 用清楚的状态标签和短说明，不写冗长教程。

### 6.2 状态推导

前端只从已有 props 和静态命令推导，不新增 fetch：

```text
backend health:
  siteState.tone === "online" -> ok
  siteState.tone === "warning" -> warn
  siteState.tone === "offline" -> blocked

proxy health:
  manual，说明 E2E 会探测 /api/backend/health

auth session:
  userEmail 存在 -> ok，显示脱敏邮箱
  userEmail 为空 -> blocked

demo readiness:
  manual，说明需要触发 Demo 并观察告警 / Copilot fallback

e2e readiness:
  manual，展示命令

env security:
  manual，展示命令和生产模式阻塞语义
```

不要把 `siteHealthCtx.health` 全量 JSON 直接写进 DOM 或复制摘要；只展示 `siteState.text`、`siteState.tone` 和脱敏 URL。

### 6.3 邮箱与 URL 脱敏

建议实现小型 helper：

```ts
function maskEmail(email: string): string {
  const [name, domain] = email.split("@");
  if (!name || !domain) return "已登录";
  const visible = name.slice(0, 1);
  return `${visible}***@${domain}`;
}
```

URL 只展示 origin 或当前 `siteState.url` 的前 80 字符，避免长 URL 撑破布局。不要展示 querystring 中疑似 token 的内容；如果无法可靠清洗，使用 `已配置目标站点`。

### 6.4 复制摘要格式

建议格式：

```text
[AI-CyberSentinel Runbook]
generated_at=<ISO timestamp>
backend_health=<text>/<tone>
proxy_probe=/api/backend/health manual
session=<masked email>
demo_readiness=manual trigger-demo-attack
e2e_readiness=manual pytest/typecheck/build
env_security=manual scripts/check_env_security.py
commands:
- .venv\Scripts\python.exe -m pytest server\tests -q --tb=short
- .venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
- cd web-next && npm run typecheck
- cd web-next && npm run build
- .venv\Scripts\python.exe scripts\check_env_security.py
```

剪贴板不可用时显示 `复制失败`，不能抛出未处理异常。

## 7. TDD / E2E 计划

### Task 1：创建运行日志

创建：

```text
docs/runs/2026-06-21-m3-16-dashboard-operational-runbook-health-checklist-ux.md
```

初始内容必须包含：

- 开始时间。
- 当前 `git status --short --branch`。
- 当前 `git log -1 --oneline`。
- 必读上下文清单。
- 允许/禁止范围。
- 阶段计划。
- 停止条件。
- 当前工作区已有跨任务 artifact / dev server log 脏文件，不允许 broad stage。

### Task 2：RED - 新增真实浏览器 E2E

新增：

```text
server/tests/test_dashboard_operational_runbook_e2e.py
```

必须复用：

- `server.tests.e2e_helpers.assert_dev_server_reachable`
- `server.tests.e2e_helpers.register_or_login_for_e2e`
- `server.tests.e2e_helpers.skip_without_playwright`

测试流程：

1. 启动 Playwright chromium，支持 `PLAYWRIGHT_CHROMIUM_EXECUTABLE`。
2. 登录 Dashboard。
3. 点击桌面 `dashboard-route-desktop-waf`。
4. 等待 `dashboard-section-system-status`。
5. 断言 `operational-runbook-panel` 可见。
6. 断言 6 行检查项可见：
   - `runbook-check-backend-health`
   - `runbook-check-proxy-health`
   - `runbook-check-auth-session`
   - `runbook-check-demo-readiness`
   - `runbook-check-e2e-readiness`
   - `runbook-check-env-security`
7. 断言 5 条命令可见：
   - `runbook-command-backend-pytest`
   - `runbook-command-guardrails`
   - `runbook-command-frontend-typecheck`
   - `runbook-command-frontend-build`
   - `runbook-command-env-security`
8. 点击 `runbook-copy-summary`，断言 `runbook-copy-status` 命中 `已复制` 或 `复制失败`。
9. 如果 clipboard 可读，断言复制文本包含 `AI-CyberSentinel Runbook`、`backend_health`、`env_security` 和上述命令。
10. 断言复制文本不包含 forbidden sentinel。
11. 扫描整页 DOM forbidden sentinel。
12. 保存桌面截图：

```text
docs/runs/artifacts/m3-16-dashboard-operational-runbook/operational-runbook-desktop.png
```

13. 设置移动 viewport 390x844，点击移动 `dashboard-route-mobile-waf`，重复关键断言，保存：

```text
docs/runs/artifacts/m3-16-dashboard-operational-runbook/operational-runbook-mobile.png
```

RED 预期：

- 当前 UI 没有 `operational-runbook-panel`，测试应 fail 在该 selector。
- 不允许因为 selector 不存在而 skip。

### Task 3：GREEN - 实现最小 UX

实现：

- `OperationalRunbookPanel.tsx`
- `DashboardSystemStatusRouteSection.tsx` 接入面板。
- `dashboard-client.tsx` 只传入已有 `userEmail` 和 `siteState`；不新增业务 hook。
- 必要时 `SystemStatusSection.tsx` 只做布局间距配合，不改变现有按钮行为。

建议组件 props：

```ts
type OperationalRunbookPanelProps = {
  siteState: {
    text: string;
    tone: "online" | "warning" | "offline";
    url?: string;
  };
  userEmail: string;
};
```

组件内允许：

- 计算检查项数组。
- 计算复制摘要。
- `navigator.clipboard.writeText`，失败时设置降级文案。
- 对长命令使用 `<code>`。

组件内禁止：

- fetch。
- storage。
- 执行脚本。
- 读取 env。
- 渲染 HTML 字符串。

### Task 4：IMPROVE - de-sloppify

检查并修复：

- 是否留下 `console.log`。
- 是否用了 `localStorage` / `sessionStorage`。
- 是否用了 `dangerouslySetInnerHTML` / `innerHTML`。
- 是否展示了未脱敏邮箱、token、cookie、完整 URL query。
- 是否新增过度抽象。
- 按钮是否有 `aria-label` 或清晰文本。
- 移动端命令文本是否撑破页面。
- 与现有 `SystemStatusSection` 是否形成重复噪声。

扫描命令：

```powershell
rg -n "console\.log|localStorage|sessionStorage|dangerouslySetInnerHTML|innerHTML|sk-|AKIA|ghp_|PRIVATE KEY|Traceback|system:|developer:" web-next\components\dashboard server\tests\test_dashboard_operational_runbook_e2e.py
```

命中测试 sentinel 常量允许；生产组件命中敏感字面量必须修。

### Task 5：验证矩阵

如果本机 Chromium `spawn EPERM`，优先使用系统 Chrome：

```powershell
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
```

如需隔离 dev server，可沿用 M3-15 的 fresh backend/frontend 方案，但必须写进运行日志。

必须运行：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_dashboard_operational_runbook_e2e.py -q --tb=short --run-e2e -s -rs
```

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_dashboard_route_sections_e2e.py -q --tb=short --run-e2e -s -rs
```

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_dashboard_responsive_e2e.py -q --tb=short --run-e2e -s -rs
```

关键 E2E 串跑：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_auth_session_e2e.py server\tests\test_demo_flow_e2e.py server\tests\test_incident_report_e2e.py server\tests\test_dashboard_route_sections_e2e.py server\tests\test_dashboard_responsive_e2e.py server\tests\test_demo_flow_stability_e2e.py server\tests\test_dashboard_mobile_visual_e2e.py server\tests\test_incident_report_preview_e2e.py server\tests\test_security_timeline_drilldown_e2e.py server\tests\test_dashboard_operational_runbook_e2e.py -q --tb=short --run-e2e -s -rs
```

默认后端：

```powershell
$tmpRoot = ".tmp\pytest-m3-16-full-$(Get-Date -Format 'yyyyMMddHHmmss')"
New-Item -ItemType Directory -Force -Path $tmpRoot | Out-Null
$env:TMP=(Resolve-Path $tmpRoot).Path
$env:TEMP=$env:TMP
.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

Guardrails：

```powershell
$tmpRoot = ".tmp\pytest-m3-16-guardrails-$(Get-Date -Format 'yyyyMMddHHmmss')"
New-Item -ItemType Directory -Force -Path $tmpRoot | Out-Null
$env:TMP=(Resolve-Path $tmpRoot).Path
$env:TEMP=$env:TMP
.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

前端，必须顺序执行，不要和 build 并行：

```powershell
cd web-next
npm run typecheck
npm run build
```

如果 npm shim 损坏，可使用本地 binary 等价命令，但必须写进运行日志。

### Task 6：文档同步

更新：

- `PRODUCT.md`：在 M3 当前状态中补 M3-16 已交付摘要。
- `docs/plans/M2_PRODUCT_ROADMAP.md`：补 M3-16 摘要。
- `docs/agent/UNATTENDED_LONG_TASKS.md`：新增 M3-16 条目，推荐口令改为下一条候选。
- `docs/runs/2026-06-21-m3-16-dashboard-operational-runbook-health-checklist-ux.md`：记录真实命令、结果、截图路径、commit hash、push 状态。

下一条候选建议：

- `M3-17 Incident / alert evidence pack checklist UX`：在现有报告、案件、时间线能力之上，补一个只读证据包清单视图，列出可下载报告、关联告警、时间线事件、脱敏状态和缺失项，不新增后端导出格式。
- `Guardrails moderation httpx pool 健康监控`：需要 owner 单独授权，因为会触碰 `server/security/llm_guardrails/**`。

默认推荐继续产品体验，除非 owner 明确授权动 Guardrails。

### Task 7：精确 commit / push

禁止 `git add .`。

建议拆分：

1. `test(e2e): 覆盖 Dashboard 运维检查面板`
2. `feat(dashboard): 增加运维 runbook 检查面板`
3. `docs(runbook): 记录 Dashboard 运维检查 UX 收口`

提交前必须运行：

```powershell
git status --short
git diff --check
git diff --cached --check
git diff --cached --name-only
```

确认未 staged：

- `.coverage`
- `.env`
- 数据库文件
- 真实密钥
- 用户本地日志
- 与本任务无关的 M3-11/M3-12/M3-13/M3-14/M3-15 artifact 或缓存

push：

```powershell
git push origin main
```

push 失败则记录远端错误和下一步，不要反复盲推。

## 8. 完成报告格式

完成后输出：

```text
完成状态：完成 / 部分完成 / 阻塞
本次 commit：
- <hash> <message>

改动文件：
- <path>：<一句话说明>

真实验证：
- <command> -> <结果>

截图证据：
- <path>

安全边界：
- 未改 auth / Guardrails / SSRF / DB schema / 后端 API / npm 依赖 / rate limit
- 未提交 .coverage / env / DB / 密钥
- DOM / copy text forbidden sentinel 扫描结果

运行日志：
- docs/runs/2026-06-21-m3-16-dashboard-operational-runbook-health-checklist-ux.md

下一条建议：
- <建议>
```

## 9. 启动口令

```text
请执行 `docs/agent/M3_16_DASHBOARD_OPERATIONAL_RUNBOOK_HEALTH_CHECKLIST_UX_TASK.md` 中定义的 L5 超长任务。先完整阅读任务文档和必读上下文，创建运行日志，新增真实浏览器 E2E 覆盖 Dashboard operational runbook / health checklist 面板，再实现最小前端 UX。只允许前端 Dashboard runbook/health checklist UX、E2E、截图和文档同步，不要修改认证/授权/Guardrails/SSRF/DB schema/后端 API/npm 依赖/rate limit，不要在浏览器执行脚本或读取真实 env，不要使用 localStorage/sessionStorage 或 `dangerouslySetInnerHTML`，不要提交 `.coverage`、真实 env、数据库或密钥。通过新增 runbook E2E、Dashboard route E2E、Dashboard responsive E2E、关键 E2E 串跑、后端全量、Guardrails、前端 typecheck/build 后，精确拆分 commit 并 push 到 `origin/main`，完成后输出最终报告。
```
