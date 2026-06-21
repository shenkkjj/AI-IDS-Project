# Run: M3-15 SOC 时间线筛选与详情展开 UX 收口

开始时间：2026-06-20
运行模式：L5
预算：最长 4 小时；同一失败最多修复 3 轮；diff 超过约 900 行时停止总结，除非主要是测试/文档

## 启动快照

当前 `git status --short --branch`：

```text
## main...origin/main
 M docs/agent/UNATTENDED_LONG_TASKS.md
 M docs/runs/artifacts/m3-11-dashboard-responsive/desktop-incidents.png
 M docs/runs/artifacts/m3-11-dashboard-responsive/desktop-overview.png
 M docs/runs/artifacts/m3-11-dashboard-responsive/mobile-incidents.png
 M docs/runs/artifacts/m3-11-dashboard-responsive/mobile-overview.png
 M docs/runs/artifacts/m3-13-dashboard-mobile-visual/mobile-390-incidents.png
 M docs/runs/artifacts/m3-13-dashboard-mobile-visual/mobile-390-overview.png
 M docs/runs/artifacts/m3-13-dashboard-mobile-visual/mobile-430-incidents.png
 M docs/runs/artifacts/m3-13-dashboard-mobile-visual/mobile-430-overview.png
?? docs/agent/M3_15_SOC_TIMELINE_DRILLDOWN_FILTER_UX_TASK.md
?? docs/runs/artifacts/m3-12-demo-flow-stability/
?? docs/runs/m3-13-demo-probe.json
?? docs/runs/m3-13-next-dev-3100.err.log
?? docs/runs/m3-13-next-dev-3100.out.log
?? docs/runs/m3-14-uvicorn-8100.err.log
?? docs/runs/m3-14-uvicorn-8100.out.log
?? docs/runs/m3-14-uvicorn-8110.err.log
?? docs/runs/m3-14-uvicorn-8110.out.log
warning: could not open directory '.tmp/pytest/pytest-of-276291/': Permission denied
```

当前 `git log -1 --oneline`：

```text
cf3ecdb docs(incidents): 记录报告预览 UX 收口
```

启动观察：

- 本地 `main` 与 `origin/main` 对齐。
- 工作区已有 M3-11/M3-12/M3-13/M3-14 artifact、日志和 M3-15 任务文档未提交项；本任务只允许精确 stage M3-15 相关文件，禁止 `git add .`。
- `.coverage`、`.env`、数据库、密钥和真实本地 env 文件均为禁止提交对象。

## 必读上下文清单

- [x] `AGENTS.md`
- [x] `CLAUDE.md`
- [x] `PRODUCT.md`
- [x] `docs/agent/UNATTENDED_LONG_TASKS.md`
- [x] `docs/runs/2026-06-19-m3-14-incident-report-preview-ux.md`
- [x] `docs/runs/2026-06-19-m3-13-dashboard-mobile-visual-qa.md`
- [x] `docs/plans/M2_PRODUCT_ROADMAP.md` 中 M2-03 审计时间线段落
- [x] `server/routers/logs_router.py`
- [x] `server/tests/test_security_timeline.py`
- [x] `web-next/components/dashboard/SecurityTimelinePanel.tsx`
- [x] `web-next/components/dashboard/sections/DashboardSecurityTimelineSection.tsx`
- [x] `web-next/hooks/useSecurityTimeline.ts`
- [x] `web-next/types/securityTimeline.ts`
- [x] `server/tests/e2e_helpers.py`
- [x] `server/tests/test_dashboard_responsive_e2e.py`

已使用 / 参考 skill：

- `superpowers:executing-plans`
- `superpowers:test-driven-development`
- `superpowers:verification-before-completion`
- `superpowers:finishing-a-development-branch`
- `frontend-patterns`
- `frontend-design`
- `e2e-testing`
- `precise-commit-hygiene`

## 目标

把 Dashboard 的 SOC 安全时间线从只读列表升级为可筛选、可展开、可复制脱敏摘要的运营证据面板，并用真实浏览器 E2E 覆盖桌面/移动截图和 forbidden sentinel。

## 范围

允许修改：

- `web-next/components/dashboard/SecurityTimelinePanel.tsx`
- 可新增 `web-next/components/dashboard/SecurityTimelineDetail.tsx`
- 可新增 `web-next/components/dashboard/SecurityTimelineFilters.tsx`
- `web-next/types/securityTimeline.ts`（仅限前端展示辅助类型）
- `web-next/hooks/useSecurityTimeline.ts`（仅限必要小型 helper，不改 API path）
- 新增 `server/tests/test_security_timeline_drilldown_e2e.py`
- 必要时轻量更新 `server/tests/test_dashboard_responsive_e2e.py`
- `docs/runs/2026-06-20-m3-15-soc-timeline-drilldown-filter-ux.md`
- `docs/runs/artifacts/m3-15-soc-timeline-drilldown/**`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

禁止修改：

- 认证 / 授权
- `server/security/**` / Guardrails
- SSRF
- DB schema / Alembic migration
- `server/routers/logs_router.py` 和 timeline API contract
- `server/models_db.py`
- npm 依赖
- rate limit 常量
- `.env`、`.coverage`、数据库、真实密钥
- 用 `localStorage` / `sessionStorage` 存 timeline 内容
- 使用 `dangerouslySetInnerHTML` 或 `innerHTML`
- 把 regex、stack trace、system prompt、API key、raw guardrail reason 写入 DOM、截图说明、运行日志或测试输出

## 阶段计划

- [x] 阶段 0：完整阅读任务文档和必读上下文，创建运行日志。
- [x] 阶段 1 RED：新增 `server/tests/test_security_timeline_drilldown_e2e.py`，真实浏览器覆盖筛选、展开、复制、截图、sentinel，并确认缺失 selector 时失败。
- [x] 阶段 2 GREEN：实现 `SecurityTimelinePanel` 最小筛选、详情、Escape 收起、复制摘要和筛选空态。
- [x] 阶段 3 IMPROVE：de-sloppify、安全扫描、移动端横向溢出检查。
- [x] 阶段 4：运行新增 timeline drilldown E2E、后端 timeline 测试、Dashboard responsive E2E、九组关键 E2E。
- [ ] 阶段 5：运行后端全量、Guardrails、前端 typecheck/build。
- [ ] 阶段 6：同步 `PRODUCT.md`、`docs/plans/M2_PRODUCT_ROADMAP.md`、`docs/agent/UNATTENDED_LONG_TASKS.md` 和运行日志证据。
- [ ] 阶段 7：精确拆分 commit 并 push `origin/main`。

## 停止条件

- Playwright 浏览器无法启动，且无法用 `PLAYWRIGHT_CHROMIUM_EXECUTABLE` 指到系统 Chrome 解决。
- dev server 无法稳定返回 `/api/backend/health`。
- 需要修改认证、Guardrails、SSRF、DB schema、后端 timeline API、依赖或 rate limit 常量。
- E2E 只能 skipped，无法获得真实浏览器 pass。
- 时间线 DOM 或复制文本中出现 forbidden sentinel。
- 筛选 UX 需要后端新增 query 参数才能完成。
- 同一失败连续修复 3 轮仍失败。

## 阶段记录

### 阶段 0：启动与上下文

已完成任务文档和必读上下文读取。关键决策：

- 分类完全在前端基于已加载 `items` 计算，不新增后端 query 参数。
- 展开详情只显示 `ts/source/category/status/summary` 等已脱敏字段和固定安全说明，不展示 raw detail/reason。
- 复制摘要只由当前脱敏字段组成，格式为 `[SOC] <time> <source>/<categoryLabel> <status> - <summary>`。
- 运行日志和截图只记录路径、命令、计数和结果，不写入敏感 DOM 文本。

### 阶段 1：RED - 新增浏览器 E2E

新增 `server/tests/test_security_timeline_drilldown_e2e.py`：

- 复用 `assert_dev_server_reachable`、`register_or_login_for_e2e`、`skip_without_playwright`。
- 真实浏览器路径：登录 Dashboard -> 查看 `security-timeline` -> 触发 Demo 攻击 -> 刷新时间线 -> 验证筛选按钮 -> Demo/全部筛选 -> 展开详情 -> 复制摘要 -> Escape 收起 -> 桌面/移动截图 -> DOM/剪贴板 forbidden sentinel。
- 目标截图路径：
  - `docs/runs/artifacts/m3-15-soc-timeline-drilldown/security-timeline-desktop.png`
  - `docs/runs/artifacts/m3-15-soc-timeline-drilldown/security-timeline-mobile.png`

本地 E2E 服务：

```text
backend:  http://127.0.0.1:8100/health -> 200 {"status":"ok"}
frontend: http://localhost:3100/api/backend/health -> 200 {"status":"ok"}
```

前端 3100 由本轮隔离启动：

```powershell
$env:BACKEND_BASE_URL='http://127.0.0.1:8100'
$env:ALLOWED_ORIGINS='http://localhost:3100,http://127.0.0.1:3100,http://localhost:3000,http://127.0.0.1:3000'
$env:ALLOWED_HOSTS='localhost:3100,127.0.0.1:3100,localhost:3000,127.0.0.1:3000,localhost:3001,127.0.0.1:3001,localhost:3002,127.0.0.1:3002,localhost:3003,127.0.0.1:3003'
$env:AUTH_TRUST_HOST='true'
$env:AUTH_SECRET='dev-secret-for-local-development-only-change-in-production'
.\node_modules\.bin\next.cmd dev -p 3100
```

RED 命令：

```powershell
$env:E2E_BASE_URL='http://localhost:3100'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_security_timeline_drilldown_e2e.py -q --tb=short --run-e2e -s -rs
```

第一次运行在 Next dev 首次编译 `/` 时超出 15s 登录页导航前置，不计为目标 RED。预热后重跑结果：

```text
1 failed in 29.00s
TimeoutError: waiting for get_by_test_id("security-timeline-filter-all").first to be visible
```

失败点符合预期：当前 UI 没有时间线筛选控件，测试没有因 selector 缺失而 skip。

### 阶段 2：GREEN - 最小 Timeline UX

修改 `web-next/components/dashboard/SecurityTimelinePanel.tsx`：

- 增加前端内存筛选状态：`全部 / Demo / Copilot / 护栏 / 系统`。
- 计数基于当前已加载 `items` 计算，不向后端发新请求。
- 时间线条目由只读行升级为可展开按钮，保留 `data-testid="security-timeline-item"` 和 `data-category`。
- 展开详情只显示 `时间 / 来源 / 类别 / 状态 / 脱敏摘要 / 安全说明`，不展示 raw detail/reason。
- 复制摘要只由已脱敏字段组成：`[SOC] <time> <source>/<categoryLabel> <status> - <summary>`。
- Escape 收起详情；切换筛选后若当前展开项不可见则自动收起。
- 不新增 fetch、不使用 storage、不使用 `dangerouslySetInnerHTML` 或 `innerHTML`。

GREEN 命令：

```powershell
$env:E2E_BASE_URL='http://localhost:3100'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_security_timeline_drilldown_e2e.py -q --tb=short --run-e2e -s -rs
```

GREEN 结果：

```text
1 passed in 18.51s
[Security Timeline Drilldown E2E 诊断] {'registered': True, 'demo_items': 1, 'copy_status': '已复制', 'screenshots': ['docs\\runs\\artifacts\\m3-15-soc-timeline-drilldown\\security-timeline-desktop.png', 'docs\\runs\\artifacts\\m3-15-soc-timeline-drilldown\\security-timeline-mobile.png'], 'forbidden': None, 'clipboard_forbidden': None}
```

### 阶段 3：IMPROVE / de-sloppify

扫描命令：

```powershell
rg -n "console\.log|localStorage|sessionStorage|dangerouslySetInnerHTML|innerHTML|sk-|AKIA|ghp_|PRIVATE KEY|Traceback|system:|developer:" web-next\components\dashboard server\tests\test_security_timeline_drilldown_e2e.py
```

结果：

- 仅命中新 E2E 的 forbidden sentinel 正则常量。
- 生产组件未命中 `console.log`、`localStorage`、`sessionStorage`、`dangerouslySetInnerHTML`、`innerHTML` 或敏感字面量。
- 初次扫描曾命中 `SecurityTimelinePanel.tsx` 里的对象键 `system: 0`；已改为从 `FILTER_OPTIONS` 初始化计数，避免任务指定扫描命令出现生产组件误报。

前端 typecheck 早期检查：

```powershell
# cwd web-next
.\node_modules\.bin\next.cmd typegen
.\node_modules\.bin\tsc.cmd --noEmit
```

结果：通过，`Route types generated successfully`，TypeScript 0 错误。

### 阶段 4：E2E / timeline 回归矩阵

后端 timeline 测试：

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\test_security_timeline.py -q --tb=short
```

结果：`12 passed in 2.88s`。

Dashboard responsive E2E：

```powershell
$env:E2E_BASE_URL='http://localhost:3100'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_dashboard_responsive_e2e.py -q --tb=short --run-e2e -s -rs
```

结果：`2 passed in 30.06s`，桌面 / 移动 DOM forbidden 均为 `None`。

九组关键 E2E 首轮：

```powershell
$env:E2E_BASE_URL='http://localhost:3100'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_auth_session_e2e.py server\tests\test_demo_flow_e2e.py server\tests\test_incident_report_e2e.py server\tests\test_dashboard_route_sections_e2e.py server\tests\test_dashboard_responsive_e2e.py server\tests\test_demo_flow_stability_e2e.py server\tests\test_dashboard_mobile_visual_e2e.py server\tests\test_incident_report_preview_e2e.py server\tests\test_security_timeline_drilldown_e2e.py -q --tb=short --run-e2e -s -rs
```

结果：`7 passed, 3 failed in 67.96s`。失败均为后段 E2E 登录前置被本地 dev backend 的 `REGISTER_RATE_LIMIT_MAX=5/小时` 阻塞，未进入业务断言。

处理方式：

- 不修改 rate limit，不修改认证/授权。
- 启动 fresh E2E backend 8110 / frontend 3110 清空进程内限流状态。
- backend 仅用进程环境设置本地测试值：`APP_SECRET` / `AUTH_SECRET` / `ALLOWED_ORIGINS` / `ALLOWED_HOSTS` / `OPENAI_API_KEY=test-local-nonsecret-placeholder` / `HTTPS_PROXY=http://10.255.255.1:3128`，沿用 M3-14 的 no-key Copilot fallback 验证方式，不改 Guardrails 代码。
- 预置 / 复用 stable E2E 账号，并设置 `E2E_*_EMAIL`，减少 register 消耗；仍走真实 NextAuth callback 和真实浏览器。

中间一次 fresh 8110/3110 九组串跑结果：`9 passed, 1 failed in 160.77s`。唯一失败为 `test_dashboard_responsive_e2e.py` 移动用例的登录前置中后端登录限流（5 分钟窗口），未进入业务断言。

最终九组关键 E2E 命令：

```powershell
$env:E2E_BASE_URL='http://localhost:3110'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
$env:E2E_E2E_AUTH_EMAIL='e2e-auth-stable@example.com'
$env:E2E_E2E_DEMO_EMAIL='e2e-demo-stable@example.com'
$env:E2E_E2E_REPORT_EMAIL='e2e-report-stable@example.com'
$env:E2E_E2E_DEMO_STABILITY_EMAIL='e2e-demo-stability-stable@example.com'
$env:E2E_E2E_MOBILE_VISUAL_EMAIL='e2e-mobile-visual-stable@example.com'
$env:E2E_E2E_REPORT_PREVIEW_EMAIL='e2e-report-stable@example.com'
$env:E2E_E2E_TIMELINE_DRILLDOWN_EMAIL='e2e-demo-stability-stable@example.com'
.\.venv\Scripts\python.exe -m pytest server\tests\test_auth_session_e2e.py server\tests\test_demo_flow_e2e.py server\tests\test_incident_report_e2e.py server\tests\test_dashboard_route_sections_e2e.py server\tests\test_dashboard_responsive_e2e.py server\tests\test_demo_flow_stability_e2e.py server\tests\test_dashboard_mobile_visual_e2e.py server\tests\test_incident_report_preview_e2e.py server\tests\test_security_timeline_drilldown_e2e.py -q --tb=short --run-e2e -s -rs
```

最终结果：

```text
10 passed in 144.89s
```

说明：九个 E2E 文件中 `test_dashboard_responsive_e2e.py` 参数化桌面 / 移动两个用例，因此总用例数为 10。

## 验证证据

- 新增 timeline drilldown E2E：

```powershell
$env:E2E_BASE_URL='http://localhost:3100'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_security_timeline_drilldown_e2e.py -q --tb=short --run-e2e -s -rs
```

结果：`1 passed in 18.51s`。

- 后端 timeline 契约：

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\test_security_timeline.py -q --tb=short
```

结果：`12 passed in 2.88s`。

- Dashboard responsive E2E：

```powershell
$env:E2E_BASE_URL='http://localhost:3100'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_dashboard_responsive_e2e.py -q --tb=short --run-e2e -s -rs
```

结果：`2 passed in 30.06s`。

- 九组关键 E2E（Auth / Demo / Incident report / Dashboard route / Responsive desktop+mobile / Demo stability / Mobile visual / Incident report preview / Security timeline drilldown）：

```powershell
$env:E2E_BASE_URL='http://localhost:3110'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_auth_session_e2e.py server\tests\test_demo_flow_e2e.py server\tests\test_incident_report_e2e.py server\tests\test_dashboard_route_sections_e2e.py server\tests\test_dashboard_responsive_e2e.py server\tests\test_demo_flow_stability_e2e.py server\tests\test_dashboard_mobile_visual_e2e.py server\tests\test_incident_report_preview_e2e.py server\tests\test_security_timeline_drilldown_e2e.py -q --tb=short --run-e2e -s -rs
```

结果：`10 passed in 144.89s`。

- 后端全量：

```powershell
$tmpRoot = ".tmp\pytest-m3-15-full-$(Get-Date -Format 'yyyyMMddHHmmss')"
New-Item -ItemType Directory -Force -Path $tmpRoot | Out-Null
$env:TMP=(Resolve-Path $tmpRoot).Path
$env:TEMP=$env:TMP
.\.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

首次使用固定 `.tmp\pytest` 目录时遇到 Windows `PermissionError: .tmp\pytest\pytest-of-276291`，导致 74 个 setup error；未改后端代码，改用本次专属临时目录后通过。

最终结果：`342 passed, 11 skipped, 17 warnings in 129.68s`。

- Guardrails 专项：

```powershell
$tmpRoot = ".tmp\pytest-m3-15-guardrails-$(Get-Date -Format 'yyyyMMddHHmmss')"
New-Item -ItemType Directory -Force -Path $tmpRoot | Out-Null
$env:TMP=(Resolve-Path $tmpRoot).Path
$env:TEMP=$env:TMP
.\.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

结果：`139 passed, 17 warnings in 21.84s`。

- 前端 typecheck：

```powershell
# cwd web-next
.\node_modules\.bin\next.cmd typegen
.\node_modules\.bin\tsc.cmd --noEmit
```

结果：通过，`FRONTEND_TYPECHECK_EXIT=0`。

- 前端 build：

```powershell
# cwd web-next
.\node_modules\.bin\next.cmd build
```

结果：通过，`FRONTEND_BUILD_EXIT=0`，`/dashboard` 47.1 kB，First Load JS 194 kB。

- forbidden / storage / HTML 注入扫描：

```powershell
rg -n "console\.log|localStorage|sessionStorage|dangerouslySetInnerHTML|innerHTML|sk-|AKIA|ghp_|PRIVATE KEY|Traceback|system:|developer:" web-next\components\dashboard server\tests\test_security_timeline_drilldown_e2e.py
```

结果：仅命中新 E2E 的 sentinel 常量；生产 timeline 组件无 forbidden 命中。

## 截图证据

- `docs/runs/artifacts/m3-15-soc-timeline-drilldown/security-timeline-desktop.png`
- `docs/runs/artifacts/m3-15-soc-timeline-drilldown/security-timeline-mobile.png`

## 未解决问题

- 无本任务阻塞。
- 九组关键 E2E 首轮在长时运行 dev backend 上触发 register/login rate limit，最终通过 fresh 本地 E2E backend/frontend 和稳定测试账号完成真实浏览器验证；未改 rate limit 常量或认证逻辑。
- 后端全量首次固定 `.tmp\pytest` 目录复跑遇到 Windows 权限拒绝；用本次专属临时目录复跑通过，未改测试代码或后端代码。

## 最终状态

代码、E2E、截图和文档同步已完成；等待精确 commit / push 收口。
