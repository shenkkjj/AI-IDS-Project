# Run: M3-19 Closed Incident Archive / Status Filter UX 收口

开始时间：2026-06-21 17:51:13 +08:00
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
 M docs/runs/artifacts/m3-14-incident-report-preview/incident-report-preview-desktop.png
 M docs/runs/artifacts/m3-14-incident-report-preview/incident-report-preview-mobile.png
 M docs/runs/artifacts/m3-15-soc-timeline-drilldown/security-timeline-desktop.png
 M docs/runs/artifacts/m3-15-soc-timeline-drilldown/security-timeline-mobile.png
 M docs/runs/artifacts/m3-16-dashboard-operational-runbook/operational-runbook-desktop.png
 M docs/runs/artifacts/m3-16-dashboard-operational-runbook/operational-runbook-mobile.png
 M docs/runs/artifacts/m3-17-incident-alert-evidence-pack-checklist/evidence-pack-desktop.png
 M docs/runs/artifacts/m3-17-incident-alert-evidence-pack-checklist/evidence-pack-mobile.png
?? docs/agent/M3_19_CLOSED_INCIDENT_ARCHIVE_STATUS_FILTER_UX_TASK.md
?? docs/runs/artifacts/m3-12-demo-flow-stability/
?? docs/runs/m3-13-demo-probe.json
?? docs/runs/m3-13-next-dev-3100.err.log
?? docs/runs/m3-13-next-dev-3100.out.log
?? docs/runs/m3-14-uvicorn-8100.err.log
?? docs/runs/m3-14-uvicorn-8100.out.log
?? docs/runs/m3-14-uvicorn-8110.err.log
?? docs/runs/m3-14-uvicorn-8110.out.log
?? docs/runs/m3-15-*.log
?? docs/runs/m3-16-*.log
?? docs/runs/m3-17-*.log
?? docs/runs/m3-18-*.log
warning: unable to access 'C:\Users\27629/.config/git/ignore': Permission denied
warning: could not open directory '.tmp/pytest-m3-15-full-20260621001241/pytest-of-276291/': Permission denied
warning: could not open directory '.tmp/pytest-m3-16-full/pytest-of-276291/': Permission denied
warning: could not open directory '.tmp/pytest-m3-17-full-20260621162641/pytest-of-276291/': Permission denied
warning: could not open directory '.tmp/pytest-m3-18-full-20260621172509/pytest-of-276291/': Permission denied
warning: could not open directory 'server/.pytest_cache/': Permission denied
```

当前 `git log -1 --oneline`：

```text
cf7ead5 docs(closure): 记录案件关闭检查 UX 收口
```

启动观察：

- 本地 `main` 与 `origin/main` 对齐。
- 工作区已有跨任务截图、旧 dev server 日志、`.tmp` / pytest cache 权限噪声；本任务只允许精确 stage M3-19 文件，禁止 `git add .`。
- `docs/agent/M3_19_CLOSED_INCIDENT_ARCHIVE_STATUS_FILTER_UX_TASK.md` 启动时未跟踪，但属于本任务文档入库范围。
- `docs/agent/UNATTENDED_LONG_TASKS.md` 启动时已有修改，本任务只在最终文档同步阶段复核并精确提交本任务要求的部分。

## 必读上下文清单

- [x] `AGENTS.md`
- [x] `CLAUDE.md`
- [x] `PRODUCT.md`
- [x] `docs/agent/UNATTENDED_LONG_TASKS.md`
- [x] `docs/runs/2026-06-21-m3-18-incident-closure-post-incident-review-checklist-ux.md`
- [x] `docs/runs/2026-06-21-m3-17-incident-alert-evidence-pack-checklist-ux.md`
- [x] `docs/runs/2026-06-19-m3-14-incident-report-preview-ux.md`
- [x] `docs/runs/2026-06-18-m3-04-incident-case-workbench.md`
- [x] `docs/plans/M2_PRODUCT_ROADMAP.md` 中 M3-04 / M3-14 / M3-17 / M3-18 段落
- [x] `web-next/components/dashboard/IncidentSection.tsx`
- [x] `web-next/components/dashboard/IncidentList.tsx`
- [x] `web-next/components/dashboard/IncidentDetailPanel.tsx`
- [x] `web-next/hooks/useIncidents.ts`
- [x] `web-next/types/incident.ts`
- [x] `server/routers/incidents_router.py` 中 `list_incidents_endpoint`
- [x] `server/services/incident_service.py` 中 `list_incidents` 与 `closed_at` 状态逻辑
- [x] `server/tests/test_incidents.py` 中 `GET /incidents` 与 `closed_at` 测试
- [x] `server/tests/e2e_helpers.py`
- [x] `server/tests/test_incident_closure_review_checklist_e2e.py`
- [x] `server/tests/test_incident_evidence_pack_checklist_e2e.py`
- [x] `server/tests/test_incident_report_e2e.py`
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

在 Dashboard 案件列表中新增状态筛选与关闭态归档视图，让 owner 能按全部、活跃、单状态和已关闭归档查看案件；关闭态列表必须展示 `closed_at`、状态 badge 和关联告警数，并避免筛选切换后详情区显示 stale incident。

## 范围

允许修改：

- `web-next/components/dashboard/IncidentSection.tsx`
- `web-next/components/dashboard/IncidentList.tsx`
- 新增 `web-next/components/dashboard/IncidentStatusFilterBar.tsx`
- 可新增前端筛选辅助类型文件
- 必要时轻量更新 `web-next/hooks/useIncidents.ts`，仅限清空 stale selection / 避免筛选 race，不改变后端 API contract
- 新增 `server/tests/test_incident_status_filter_archive_e2e.py`
- `docs/runs/2026-06-21-m3-19-closed-incident-archive-status-filter-ux.md`
- `docs/runs/artifacts/m3-19-closed-incident-archive-status-filter/**`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`
- `docs/agent/M3_19_CLOSED_INCIDENT_ARCHIVE_STATUS_FILTER_UX_TASK.md`

禁止修改：

- 认证 / 授权
- `server/security/**` / Guardrails
- SSRF
- DB schema / Alembic migration
- 后端 incident / report API contract
- `server/routers/incidents_router.py`
- `server/services/incident_service.py`
- `server/models_db.py`
- npm 依赖
- rate limit 常量
- `.env`、`.coverage`、数据库、真实密钥
- 新增案件状态
- 改变 `closed_at` 自动设置 / 清空语义
- 自动把案件状态改为 `resolved` 或 `false_positive`
- 调用 LLM
- 把 raw payload、完整 analyst note、完整 timeline note、完整报告 markdown、system prompt、stack trace、API key 写入 DOM、复制文本、截图说明、运行日志或测试输出
- 使用 `localStorage` / `sessionStorage`
- 使用 `dangerouslySetInnerHTML` 或 `innerHTML`

## 阶段计划

- [x] 阶段 0：读取任务文档、项目规则、相邻 run log、前端组件、hook、后端契约与 E2E helper。
- [x] 阶段 1 RED：新增 `server/tests/test_incident_status_filter_archive_e2e.py`，确认缺少 `incident-status-filter-bar` selector 时失败。
- [x] 阶段 2 GREEN：新增 `IncidentStatusFilterBar.tsx`，接入 `IncidentSection.tsx`，扩展 `IncidentList.tsx` 关闭态展示和筛选空态。
- [x] 阶段 3 IMPROVE：de-sloppify、安全扫描、移动端横向溢出检查、筛选 race/stale detail 检查。
- [x] 阶段 4：运行新增 status filter E2E、M3-18 closure / M3-17 evidence pack E2E、既有 report / preview / responsive E2E。
- [x] 阶段 5：运行后端 incident 契约、关键 E2E 串跑、后端全量、Guardrails、前端 typecheck/build。
- [x] 阶段 6：同步 `PRODUCT.md`、`docs/plans/M2_PRODUCT_ROADMAP.md`、`docs/agent/UNATTENDED_LONG_TASKS.md` 和本日志。
- [x] 阶段 7：精确拆分 commit 并 push `origin/main`。

## 停止条件

- Playwright 浏览器无法启动，且无法用 `PLAYWRIGHT_CHROMIUM_EXECUTABLE` 指到系统 Chrome 解决。
- dev server 无法稳定返回 `/api/backend/health`。
- 发现后端 `GET /incidents?status=` 实际不可用，且必须修改后端 API 才能完成筛选。
- 需要修改认证、Guardrails、SSRF、DB schema、后端 incident/report API、依赖或 rate limit 常量。
- 需要新增 DB 字段、后端复合状态 API 或 LLM 归档摘要才能完成 UX。
- E2E 只能 skipped，无法获得真实浏览器 pass。
- DOM、复制文本、下载 markdown 或截图说明中出现 forbidden sentinel。
- 当前工作区存在 unrelated dirty files 时，不允许 broad stage；只能精确 stage 本任务文件。

## 阶段记录

### 阶段 0：启动与上下文

已完成任务文档、项目规则、相邻运行日志、现有 incident 前端组件、hook、后端 `status`/`closed_at` 契约与 E2E helper 阅读。

关键事实：

- 后端 `GET /incidents?limit=50&status=<status>` 已存在，`incidents_router.list_incidents_endpoint` 只接受单一合法状态。
- `incident_service.list_incidents` 支持可选单状态过滤，默认按 `updated_at desc, id desc` 返回。
- `closed_at` 语义由 M3-04 锁定：进入 `resolved / false_positive` 自动设置，改回打开态清空。
- `useIncidents.loadIncidents({ status, signal })` 已支持透传单状态参数。
- 当前 `IncidentSection` 进入时仅调用 `loadIncidents({ limit: 50 })`，暂无筛选控件；切换列表数据后也没有显式清空 stale detail。
- 当前 `IncidentList` 只显示 `更新 ... · 已关闭`，没有 `incident-closed-at` 结构化展示和筛选空态文案。

关键决策：

- 复合筛选 `active` / `closed` 只在前端按单状态接口聚合，不新增后端参数。
- 单状态筛选调用既有 `incidents.loadIncidents({ limit: 50, status })`。
- 筛选切换后如当前 `selectedIncident` 不在新列表中，清空 selected/detail 并显示“未选择案件”，避免 stale detail。
- 筛选状态仅存在 React state 中，不写浏览器 storage。

### 阶段 1：RED E2E 编写与环境阻塞

新增 `server/tests/test_incident_status_filter_archive_e2e.py`，覆盖：

- 登录 Dashboard。
- 通过现有 UI 创建 4 个案件样本：`open`、`contained`、`resolved`、`false_positive`。
- 断言 `incident-status-filter-bar` 与 8 个筛选按钮可见。
- 断言 `已关闭归档` 只显示 `resolved / false_positive`，且每个关闭态列表项展示 `incident-closed-at`。
- 点击关闭态案件后确认 `incident-detail-panel` 与 M3-18 `incident-closure-review-checklist` 仍可见。
- 断言 `活跃` 只显示 `open / contained` 样本，且不展示 `incident-closed-at`。
- 断言 `contained`、`resolved`、`false_positive` 单状态筛选。
- 刷新页面后筛选回到默认 `全部`，证明未写 storage。
- 扫描 DOM forbidden sentinel，保存桌面 / 移动截图，检查移动横向溢出。

静态检查：

```text
py_compile server\tests\test_incident_status_filter_archive_e2e.py
passed
```

```text
rg -n "incident-status-filter-bar|incident-filter-closed|incident-closed-at|localStorage|sessionStorage|dangerouslySetInnerHTML|innerHTML" server\tests\test_incident_status_filter_archive_e2e.py web-next\components\dashboard
仅命中新 E2E 的目标 selector；生产组件尚无筛选 selector，符合 RED 预期。
```

真实浏览器 RED 首轮环境问题：

- `http://localhost:3000/api/backend/health`、`http://localhost:3126/api/backend/health`、`http://localhost:3123/api/backend/health`、`http://localhost:3100/api/backend/health` 均超时。
- `http://127.0.0.1:8000/health` 无法连接。
- 尝试启动本任务隔离 dev server（后端 `8130`、前端 `3130`、临时 SQLite `.tmp/m3-19-e2e-red.db`）时，当前审批服务两次拒绝 `Start-Process` 后台启动命令；按安全规则不能绕过。
- owner 手动启动后端 `8130` / 前端 `3130` 后，首轮 RED 因前端 `ALLOWED_HOSTS` 未含 `localhost:3130`，`POST /api/backend/alerts/demo` 返回 `403 INVALID_ORIGIN`，这是 E2E 环境配置问题，未改认证/授权代码。
- owner 重启前端并设置 `ALLOWED_HOSTS=localhost:3130,127.0.0.1:3130` 后，健康检查通过：

```text
http://127.0.0.1:8130/health -> 200 {"status":"ok"}
http://localhost:3130/api/backend/health -> 200 {"status":"ok"}
POST /api/backend/alerts/demo with Origin http://localhost:3130 -> 401 unauthenticated, origin gate passed
```

目标 RED 命令：

```powershell
$env:E2E_BASE_URL='http://localhost:3130'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_incident_status_filter_archive_e2e.py -q --tb=short --run-e2e -s -rs
```

目标 RED 结果：

```text
1 failed in 36.98s
TimeoutError: waiting for get_by_test_id("incident-status-filter-bar").first to be visible
```

失败点符合预期：真实浏览器已完成登录、Demo 告警、创建 open / contained / resolved / false_positive 样本并进入案件列表；当前 UI 尚无状态筛选栏，测试未 skip。

### 阶段 2：GREEN 前端实现

新增 / 修改：

- 新增 `web-next/components/dashboard/IncidentStatusFilterBar.tsx`：
  - 8 个筛选按钮：`全部 / 活跃 / 已开启 / 调查中 / 已遏制 / 已解决 / 误报 / 已关闭归档`。
  - 暴露 `incident-status-filter-bar`、8 个筛选按钮 test id 和 `incident-filter-summary`。
  - 当前筛选按钮使用 `aria-pressed`，按钮可换行。
- 修改 `web-next/components/dashboard/IncidentSection.tsx`：
  - 默认筛选为 `all`。
  - 单状态筛选调用既有 `loadIncidents({ limit: 50, status })`。
  - `active` 顺序调用 `open / investigating / contained` 后前端聚合并按 `updated_at` 排序。
  - `closed` 顺序调用 `resolved / false_positive` 后前端聚合并按 `closed_at` fallback `updated_at` 排序。
  - 使用 `AbortController` + request sequence 避免旧筛选请求覆盖新筛选。
  - 当前 selected 不在新列表时清空 selected/detail，避免 stale detail。
- 修改 `web-next/hooks/useIncidents.ts`：
  - 新增 `replaceIncidentItems(items)` 用于复合筛选聚合结果替换列表。
  - 新增 `clearSelectedIncident()` 用于筛选切换后清空 stale detail。
  - `AbortError` 不进入 error 态。
- 修改 `web-next/components/dashboard/IncidentList.tsx`：
  - 新增 `filterLabel` 与 `mode="archive"`。
  - 筛选空态使用 `incident-list-empty-filtered` 与针对性文案。
  - 关闭态展示结构化 `incident-closed-at`；活跃态保留 `incident-list-updated-at`。

GREEN 验证：

```text
py_compile server\tests\test_incident_status_filter_archive_e2e.py
passed

npm run typecheck
passed

rg -n "console\.log|localStorage|sessionStorage|dangerouslySetInnerHTML|innerHTML|sk-|AKIA|ghp_|PRIVATE KEY|Traceback|system\s*:|developer\s*:" web-next\components\dashboard server\tests\test_incident_status_filter_archive_e2e.py
仅命中新 E2E forbidden sentinel 常量。
```

新增 E2E GREEN：

```powershell
$env:E2E_BASE_URL='http://localhost:3130'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
$env:E2E_E2E_INCIDENT_STATUS_FILTER_EMAIL='e2e-incident-status-filter-local-1782047454979@example.com'
.\.venv\Scripts\python.exe -m pytest server\tests\test_incident_status_filter_archive_e2e.py -q --tb=short --run-e2e -s -rs
```

结果：

```text
1 passed in 19.95s
[Incident Status Filter Archive E2E 诊断] {'registered': True, 'samples': {'open': 'inc_a9f6db5e3af54fc8', 'contained': 'inc_df8c0dec3ad04529', 'resolved': 'inc_1c49028dae5341f6', 'false_positive': 'inc_88ad96173d2d4d5d'}, 'screenshots': ['docs\\runs\\artifacts\\m3-19-closed-incident-archive-status-filter\\status-filter-desktop.png', 'docs\\runs\\artifacts\\m3-19-closed-incident-archive-status-filter\\status-filter-mobile.png'], 'forbidden': None}
```

截图已生成：

- `docs/runs/artifacts/m3-19-closed-incident-archive-status-filter/status-filter-desktop.png`
- `docs/runs/artifacts/m3-19-closed-incident-archive-status-filter/status-filter-mobile.png`

### 阶段 3：IMPROVE 与安全复查

复查结论：

- 复合筛选只消费既有单状态 `GET /incidents?status=` 能力；没有新增后端 API、DB schema、状态枚举或导出格式。
- 筛选 state 只保存在 React 组件内；刷新页面后回到默认 `全部`，E2E 同步断言没有 incident filter key 写入 `localStorage` / `sessionStorage`。
- `IncidentList` 在 `mode="archive"` 时只展示关闭态 `closed_at` 与更新信息；活跃筛选不展示 `incident-closed-at`。
- `IncidentSection` 使用 request sequence 与 `AbortController` 防止快速切换筛选时旧请求覆盖新列表。
- 当前 selected 不在新筛选列表中时调用 `clearSelectedIncident()`，详情区回到“未选择案件”，避免 stale incident。

安全扫描：

```text
rg -n "console\.log|localStorage|sessionStorage|dangerouslySetInnerHTML|innerHTML|sk-|AKIA|ghp_|PRIVATE KEY|Traceback|system\s*:|developer\s*:" web-next\components\dashboard server\tests\test_incident_status_filter_archive_e2e.py
仅命中新 E2E forbidden sentinel 常量。
```

截图人工复核：

- `status-filter-desktop.png` 展示状态筛选条、已关闭归档列表、关闭态 `incident-closed-at` 与 M3-18 closure checklist。
- `status-filter-mobile.png` 展示移动筛选按钮与列表，无阻塞性横向溢出或关键控件重叠。

### 阶段 4：浏览器 E2E 回归

新增 status filter E2E：

```text
1 passed in 19.95s
forbidden=None
```

相邻 M3-18 / M3-17 回归：

```powershell
$env:E2E_BASE_URL='http://localhost:3130'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
$env:E2E_E2E_CLOSURE_REVIEW_EMAIL='e2e-incident-status-filter-local-1782047394310@example.com'
$env:E2E_E2E_EVIDENCE_PACK_EMAIL='e2e-incident-status-filter-local-1782047330797@example.com'
.\.venv\Scripts\python.exe -m pytest server\tests\test_incident_closure_review_checklist_e2e.py server\tests\test_incident_evidence_pack_checklist_e2e.py -q --tb=short --run-e2e -s -rs
```

```text
2 passed in 10.63s
```

既有 report / preview / responsive 回归：

```powershell
$env:E2E_BASE_URL='http://localhost:3130'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
$env:E2E_E2E_REPORT_EMAIL='e2e-incident-status-filter-local-1782046848541@example.com'
$env:E2E_E2E_REPORT_PREVIEW_EMAIL='e2e-incident-status-filter-local-1782046647839@example.com'
$env:E2E_E2E_AUTH_EMAIL='e2e-incident-status-filter-local-1782047454979@example.com'
.\.venv\Scripts\python.exe -m pytest server\tests\test_incident_report_e2e.py server\tests\test_incident_report_preview_e2e.py server\tests\test_dashboard_responsive_e2e.py -q --tb=short --run-e2e -s -rs
```

```text
4 passed in 26.91s
```

### 阶段 5：完整验证矩阵

后端 incident 契约：

```powershell
New-Item -ItemType Directory -Force -Path '.tmp\pytest-m3-19-incident' | Out-Null
$env:TMP=(Resolve-Path '.tmp\pytest-m3-19-incident').Path
$env:TEMP=$env:TMP
.\.venv\Scripts\python.exe -m pytest server\tests\test_incidents.py -q --tb=short
```

```text
17 passed in 3.10s
```

关键 E2E 串跑：

```text
Auth / Demo / Incident report / Dashboard route / Responsive desktop+mobile / Demo stability / Mobile visual / Incident report preview / Security timeline drilldown / Dashboard operational runbook / Incident evidence pack checklist / Incident closure review checklist / Incident status filter archive
```

首轮串跑在本地 backend 长时运行后触发注册/登录限流，结果为 `10 passed, 4 failed in 153.15s`；失败项均在测试 setup 登录阶段，非本任务 selector 或断言失败。owner 重启后端/前端清空本地限流状态后，复跑失败项：

```powershell
$env:E2E_BASE_URL='http://localhost:3130'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_dashboard_responsive_e2e.py server\tests\test_demo_flow_stability_e2e.py server\tests\test_dashboard_mobile_visual_e2e.py -q --tb=short --run-e2e -s -rs
```

```text
4 passed in 36.88s
```

本次关键 E2E 覆盖总计 14 个真实浏览器测试，最终失败项复跑全部通过；未修改生产 rate limit。

后端全量：

```powershell
New-Item -ItemType Directory -Force -Path '.tmp\pytest-m3-19-full' | Out-Null
$env:TMP=(Resolve-Path '.tmp\pytest-m3-19-full').Path
$env:TEMP=$env:TMP
$env:APP_SECRET='test-local-secret-key-for-m3-19-full-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-m3-19-full-32chars'
.\.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

```text
344 passed, 15 skipped, 17 warnings in 83.76s
```

Guardrails 专项：

```powershell
New-Item -ItemType Directory -Force -Path '.tmp\pytest-m3-19-guardrails' | Out-Null
$env:TMP=(Resolve-Path '.tmp\pytest-m3-19-guardrails').Path
$env:TEMP=$env:TMP
$env:APP_SECRET='test-local-secret-key-for-m3-19-guardrails-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-m3-19-guardrails-32chars'
.\.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

```text
139 passed, 17 warnings in 18.30s
```

前端：

```text
npm run typecheck
passed

npm run build
passed
/dashboard 55 kB / First Load JS 202 kB
```

### 阶段 6：文档同步

- `PRODUCT.md` §2.2 新增 M3-19 已交付摘要。
- `docs/plans/M2_PRODUCT_ROADMAP.md` 新增 M3-19 收口章节、验证矩阵和边界说明。
- `docs/agent/UNATTENDED_LONG_TASKS.md` 将 M3-19 从“已固化，等待执行”更新为“已交付”，下一条建议切到 M3-20。
- 本运行日志补齐 RED → GREEN → IMPROVE、截图、验证矩阵和提交计划。

### 阶段 7：提交计划与边界确认

计划精确拆分 3 个 commit：

1. `test(e2e): 覆盖案件归档筛选`
2. `feat(incidents): 增加案件状态筛选归档视图`
3. `docs(incidents): 记录案件归档筛选 UX 收口`

精确 stage 范围：

- E2E：`server/tests/test_incident_status_filter_archive_e2e.py`
- 前端 UX：`web-next/components/dashboard/IncidentStatusFilterBar.tsx`、`IncidentSection.tsx`、`IncidentList.tsx`、`web-next/hooks/useIncidents.ts`
- 文档 / 截图：本运行日志、M3-19 任务文档、M3-19 截图目录、`PRODUCT.md`、`docs/plans/M2_PRODUCT_ROADMAP.md`、`docs/agent/UNATTENDED_LONG_TASKS.md`

不纳入提交：

- 旧任务截图刷新：`docs/runs/artifacts/m3-11`、`m3-13`、`m3-14`、`m3-15`、`m3-16`、`m3-17`、`m3-18`
- 旧 dev server 日志和 probe 文件
- `.tmp`、pytest cache、`.coverage`、真实 env、数据库或密钥

最终边界确认：

- 未改认证 / 授权 / Guardrails / SSRF / DB schema / Alembic migration / 后端 incident/report API / npm 依赖 / rate limit。
- 未新增后端导出格式；未自动关闭案件；未调用 LLM。
- 未使用 `localStorage` / `sessionStorage` 持久化筛选；未使用 `dangerouslySetInnerHTML` / `innerHTML`。
- 未把 raw payload、完整 analyst note、完整 timeline note、报告 markdown、system prompt、stack trace、API key 写入 UI、截图说明、运行日志或复制文本。
