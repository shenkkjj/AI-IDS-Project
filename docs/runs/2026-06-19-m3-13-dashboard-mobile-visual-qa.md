# Run: M3-13 Dashboard 移动视觉 QA 收口

开始时间：2026-06-19
运行模式：L5
预算：最长 4 小时；同一失败最多修复 3 轮；只允许轻量 Tailwind/layout class 修复

## 目标

- 基于 M3-11 `mobile-overview.png` / `mobile-incidents.png` 截图证据，新增 Dashboard 移动视觉 E2E。
- 覆盖 390x844 与 430x932 下 `overview` / `incidents` 的 stats 卡片密度、section 间距、移动 nav active tab 可见性、整页横向溢出、forbidden sentinel、`N` 浮层 DOM 来源判断。
- 保存新的移动截图证据。
- 只做必要的轻量布局 class 修复，不重做视觉设计。

## 范围

允许修改：

- `server/tests/test_dashboard_mobile_visual_e2e.py`
- `web-next/components/dashboard/StatsCards.tsx`
- `web-next/components/dashboard/SystemStatusBar.tsx`
- `web-next/components/dashboard/sections/*.tsx`
- `docs/runs/2026-06-19-m3-13-dashboard-mobile-visual-qa.md`
- `docs/runs/artifacts/m3-13-dashboard-mobile-visual/**`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

禁止修改：

- 认证 / 授权
- `server/security/**` / Guardrails
- SSRF
- DB schema / Alembic migration
- 后端 API contract
- npm 依赖
- rate limit 常量
- `.env` / `.coverage` / 数据库 / 密钥

## 计划

- [x] Task 1 RED：新增移动视觉 E2E，覆盖目标断言与截图落盘。
- [x] Task 2 GREEN：按失败点做轻量 stats / section / nav class 修复。
- [x] Task 3：重跑移动视觉 E2E，保存 4 张新截图。
- [x] Task 4：回归 M3-11 responsive E2E、M3-12 Demo stability E2E、七组关键 E2E。
- [x] Task 5：后端全量、Guardrails、前端 typecheck/build。
- [x] Task 6：截图文件、扫描与文档同步。
- [x] Task 7：精确拆分 commit 并 push `origin/main`。

## 阶段记录

### 阶段 0：启动与上下文

已完整阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/runs/2026-06-19-m3-11-dashboard-section-responsive-qa.md`
- `docs/runs/2026-06-19-m3-12-demo-flow-e2e-stability.md`
- `docs/agent/M3_13_DASHBOARD_MOBILE_VISUAL_QA_TASK.md`
- `server/tests/e2e_helpers.py`
- `server/tests/test_dashboard_responsive_e2e.py`
- 任务列出的 Dashboard 组件与 `sections/*.tsx`

已使用技能：

- `superpowers:subagent-driven-development`：已读；当前环境没有暴露可调度子智能体工具，降级为 `superpowers:executing-plans`。
- `superpowers:executing-plans`
- `superpowers:test-driven-development`
- `superpowers:verification-before-completion`
- `superpowers:finishing-a-development-branch`
- `e2e-testing`

### 阶段 1：移动视觉 E2E

新增 `server/tests/test_dashboard_mobile_visual_e2e.py`：

- 两个 viewport：390x844 与 430x932。
- 两个 route：`overview` 与 `incidents`。
- 断言 active mobile nav tab 位于横向滚动容器可见区域。
- 断言整页无横向溢出：`scrollWidth <= clientWidth + 4`。
- 断言 stats grid 高度不超过 viewport 高度 42%，单卡高度不超过 160px。
- 断言 stats section 到 briefing section 间距不超过 64px。
- 扫描 forbidden sentinel。
- 检测形似圆形 `N` 的应用 DOM 候选，要求 count 为 0。
- 成功时保存 4 张 full-page 截图到 `docs/runs/artifacts/m3-13-dashboard-mobile-visual/`。

本机 bundled Chromium 启动被系统权限拦截，表现为：

```text
BrowserType.launch: spawn EPERM
```

最终改用系统 Chrome：

```powershell
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
```

注册限流环境下，E2E 使用稳定测试账号环境变量规避同一 IP register 额度污染；七组关键 E2E 串跑时使用：

```powershell
$env:E2E_E2E_AUTH_EMAIL='e2e-route-sections-stable@example.com'
$env:E2E_E2E_DEMO_EMAIL='e2e-demo-stable@example.com'
$env:E2E_E2E_REPORT_EMAIL='e2e-incident-report-stable@example.com'
$env:E2E_E2E_DEMO_STABILITY_EMAIL='e2e-demo-stability-stable@example.com'
$env:E2E_E2E_MOBILE_VISUAL_EMAIL='e2e-report-stable@example.com'
```

### 阶段 2：轻量布局修复

修复只限 Tailwind/layout class：

- `StatsCards.tsx`
  - 为 grid 增加 `data-testid="stats-card-grid"`。
  - 移动端 padding 从 `p-6` 收口为 `p-4 sm:p-6 md:p-8`。
  - 增加稳定最小高度：`min-h-[118px] sm:min-h-[132px] md:min-h-0`。
  - 收紧 header 间距、label tracking 与 value 换行，降低移动端 stats 卡片空白和文字挤压。
- `SystemStatusBar.tsx`
  - 移动 nav wrapper 增加 `overflow-x-auto overscroll-x-contain`。
  - 收紧移动 nav gap 与 tracking，提升 active tab 可见性。
- `DashboardBriefingSection.tsx` / `DashboardIncidentWorkspaceSection.tsx`
  - section 顶部间距从 `mt-14` 调为 `mt-8 sm:mt-14`。

未改业务 hook、state、prompt、认证、后端 API、Guardrails、SSRF、DB schema、npm 依赖或 rate limit 常量。

### 阶段 3：截图与 `N` 浮层判定

移动视觉 E2E 最终输出诊断：

```text
{'viewports': ['mobile-390','mobile-430'],
 'routes': ['mobile-390:overview','mobile-390:incidents','mobile-430:overview','mobile-430:incidents'],
 'n_overlay': {'count': 0, 'candidates': []},
 'forbidden': None}
```

新截图文件：

| 文件 | 大小 |
|---|---:|
| `docs/runs/artifacts/m3-13-dashboard-mobile-visual/mobile-390-overview.png` | 363017 |
| `docs/runs/artifacts/m3-13-dashboard-mobile-visual/mobile-390-incidents.png` | 102898 |
| `docs/runs/artifacts/m3-13-dashboard-mobile-visual/mobile-430-overview.png` | 367295 |
| `docs/runs/artifacts/m3-13-dashboard-mobile-visual/mobile-430-incidents.png` | 102198 |

截图中仍可见左下圆形 `N` 浮层，但 DOM 来源检测 count 为 0；判定为浏览器/外部 overlay，不属于应用 DOM，因此未修改应用代码去“修”它。

### 阶段 4：环境 workaround

后端默认 pytest 曾因系统临时目录权限失败：

```text
PermissionError: C:\Users\27629\AppData\Local\Temp\pytest-of-276291
```

最终设置项目内临时目录：

```powershell
New-Item -ItemType Directory -Force -Path '.tmp\pytest' | Out-Null
$env:TMP=(Resolve-Path '.tmp\pytest').Path
$env:TEMP=$env:TMP
```

`npm run typecheck` 因用户目录 npm shim 损坏失败：

```text
Cannot find module 'C:\Users\27629\AppData\Roaming\npm\node_modules\npm\bin\npm-cli.js'
```

最终使用等价本地 binary：

```powershell
..\web-next\node_modules\.bin\next.cmd typegen
..\web-next\node_modules\.bin\tsc.cmd --noEmit
```

build 使用：

```powershell
..\web-next\node_modules\.bin\next.cmd build
```

E2E 回归阶段发现当前 `localhost:3000` 的 Next dev server 状态不可靠：`/api/backend/health` 曾返回 Next 内部 chunk 缺失错误（`Cannot find module './745.js'`），且长时运行 `localhost:8000` backend 会复现 M3-12 记录的 Guardrails moderation pool 退化，导致 demo / Copilot 请求 fail-closed。最终 E2E 验证使用临时、隔离的本地服务：

```powershell
# backend
.\.venv\Scripts\python.exe -m uvicorn server.main:app --host 127.0.0.1 --port 8100

# frontend
$env:BACKEND_BASE_URL='http://127.0.0.1:8100'
$env:ALLOWED_ORIGINS='http://localhost:3100,http://127.0.0.1:3100,http://localhost:3000,http://127.0.0.1:3000'
$env:ALLOWED_HOSTS='localhost:3100,127.0.0.1:3100,localhost:3000,127.0.0.1:3000,localhost:3001,127.0.0.1:3001,localhost:3002,127.0.0.1:3002,localhost:3003,127.0.0.1:3003'
$env:AUTH_TRUST_HOST='true'
$env:AUTH_SECRET='dev-secret-for-local-development-only-change-in-production'
.\node_modules\.bin\next.cmd dev -p 3100

# tests
$env:E2E_BASE_URL='http://localhost:3100'
```

补充证据：临时 3100 前端若只设置 `ALLOWED_HOSTS` 而遗漏 `ALLOWED_ORIGINS`，`middleware.ts` 会按默认 `3000` origin 白名单把同源 `POST /api/backend/alerts/demo` 拦成 `{"error":"forbidden"}`，fresh 8100 后端不会收到请求。最终矩阵已补齐 `ALLOWED_ORIGINS`，`POST /api/backend/alerts/demo` 与 `POST /api/backend/copilot/stream` 均返回 200。

### 阶段 5：de-sloppify 与安全扫描

扫描命令：

```powershell
rg -n "console\.log|localStorage|sessionStorage|innerHTML|dangerouslySetInnerHTML|useIncidents\(|useAlerts\(|REGISTER_RATE_LIMIT|COPILOT_RATE_LIMIT|pytest\.skip|xfail" server\tests\test_dashboard_mobile_visual_e2e.py web-next\components\dashboard web-next\app\dashboard web-next\constants server\core server\security
```

结论：

- 新测试中只有浏览器缺失前置 `pytest.skip`，未用 skip/xfail 绕过真实断言。
- 未新增 `console.log`、storage 写入、dangerous HTML。
- 未新增业务 hook 重复实例。
- rate limit 仅命中既有定义/引用，未修改常量。

## 验证证据

- 移动视觉 E2E：

```powershell
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.venv\Scripts\python.exe -m pytest server\tests\test_dashboard_mobile_visual_e2e.py -q --tb=short --run-e2e -s -rs
```

结果：`1 passed in 13.82s`。

- M3-11 responsive E2E：

```powershell
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.venv\Scripts\python.exe -m pytest server\tests\test_dashboard_responsive_e2e.py -q --tb=short --run-e2e -s -rs
```

结果：`2 passed in 20.08s`。

- M3-12 Demo stability E2E：

```powershell
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow_stability_e2e.py -q --tb=short --run-e2e -s -rs
```

结果：`1 passed in 6.32s`。

- 七组关键 E2E：

```powershell
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.venv\Scripts\python.exe -m pytest server\tests\test_auth_session_e2e.py server\tests\test_demo_flow_e2e.py server\tests\test_incident_report_e2e.py server\tests\test_dashboard_route_sections_e2e.py server\tests\test_dashboard_responsive_e2e.py server\tests\test_demo_flow_stability_e2e.py server\tests\test_dashboard_mobile_visual_e2e.py -q --tb=short --run-e2e -s -rs
```

结果：`8 passed in 69.21s`。

- 后端全量：

```powershell
New-Item -ItemType Directory -Force -Path '.tmp\pytest' | Out-Null
$env:TMP=(Resolve-Path '.tmp\pytest').Path
$env:TEMP=$env:TMP
.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

结果：`342 passed, 9 skipped, 17 warnings in 44.99s`。

- Guardrails：

```powershell
New-Item -ItemType Directory -Force -Path '.tmp\pytest' | Out-Null
$env:TMP=(Resolve-Path '.tmp\pytest').Path
$env:TEMP=$env:TMP
.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

结果：`139 passed, 17 warnings in 19.26s`。

- 前端 typecheck 等价命令：

```powershell
# cwd web-next
..\web-next\node_modules\.bin\next.cmd typegen
..\web-next\node_modules\.bin\tsc.cmd --noEmit
```

结果：通过，`Route types generated successfully`，TypeScript 0 错误。

- 前端 build：

```powershell
# cwd web-next
..\web-next\node_modules\.bin\next.cmd build
```

结果：通过，`/dashboard` 44.1 kB / First Load JS 191 kB。

## 未解决问题

- 无阻塞问题。
- 系统 Chrome、项目内 pytest 临时目录、本地 `next.cmd` / `tsc.cmd` workaround 仅用于本机环境，不改变项目代码语义。
- 截图中的圆形 `N` 浮层不是应用 DOM；本任务只记录和防回归，不处理外部 overlay。

## 最终状态

完成。
