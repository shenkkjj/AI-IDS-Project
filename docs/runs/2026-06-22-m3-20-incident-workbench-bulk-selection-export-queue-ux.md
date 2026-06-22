# Run: M3-20 Incident Workbench Bulk Selection / Export Queue UX 收口

开始时间：2026-06-22
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
 M docs/runs/artifacts/m3-18-incident-closure-post-incident-review-checklist/closure-review-desktop.png
 M docs/runs/artifacts/m3-18-incident-closure-post-incident-review-checklist/closure-review-mobile.png
?? .tmp/
?? docs/agent/M3_20_INCIDENT_WORKBENCH_BULK_SELECTION_EXPORT_QUEUE_UX_TASK.md
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
warning: could not open directory 'server/.pytest_cache/': Permission denied
```

当前 `git log -1 --oneline`：

```text
78abe5a docs(incidents): 记录案件归档筛选 UX 收口
```

启动观察：

- 本地 `main` 与 `origin/main` 对齐。
- 工作区已有跨任务截图、旧 dev server 日志、`.tmp` 和 pytest cache 权限噪声；本任务只允许精确 stage M3-20 文件，禁止 `git add .`。
- `docs/agent/M3_20_INCIDENT_WORKBENCH_BULK_SELECTION_EXPORT_QUEUE_UX_TASK.md` 启动时未跟踪，但属于本任务文档入库范围。
- `docs/agent/UNATTENDED_LONG_TASKS.md` 启动时已有修改，本任务只在最终文档同步阶段复核并精确提交 M3-20 要求的部分。

## 必读上下文清单

- [x] `AGENTS.md`
- [x] `CLAUDE.md`
- [x] `PRODUCT.md`
- [x] `docs/agent/UNATTENDED_LONG_TASKS.md`
- [x] `docs/agent/M3_20_INCIDENT_WORKBENCH_BULK_SELECTION_EXPORT_QUEUE_UX_TASK.md`
- [x] `docs/runs/2026-06-21-m3-19-closed-incident-archive-status-filter-ux.md`
- [x] `docs/runs/2026-06-21-m3-18-incident-closure-post-incident-review-checklist-ux.md`
- [x] `docs/runs/2026-06-21-m3-17-incident-alert-evidence-pack-checklist-ux.md`
- [x] `docs/runs/2026-06-18-m3-07-incident-evidence-report-export.md`
- [x] `docs/plans/M2_PRODUCT_ROADMAP.md` 中 M3-04 / M3-07 / M3-17 / M3-18 / M3-19 段落
- [x] `web-next/components/dashboard/IncidentSection.tsx`
- [x] `web-next/components/dashboard/IncidentList.tsx`
- [x] `web-next/components/dashboard/IncidentStatusFilterBar.tsx`
- [x] `web-next/components/dashboard/IncidentDetailPanel.tsx`
- [x] `web-next/hooks/useIncidents.ts`
- [x] `web-next/types/incident.ts`
- [x] `server/tests/e2e_helpers.py`
- [x] `server/tests/test_incident_status_filter_archive_e2e.py`
- [x] `server/tests/test_incident_closure_review_checklist_e2e.py`
- [x] `server/tests/test_incident_evidence_pack_checklist_e2e.py`
- [x] `server/tests/test_incident_report_e2e.py`
- [x] `server/tests/test_incident_report_preview_e2e.py`
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

在 M3-19 案件列表状态筛选和关闭态归档之上，新增列表多选、全选当前筛选、批量复制安全摘要和前端内存级导出队列提示区；筛选切换时清理不可见选择，刷新页面后选择和队列清空。

## 范围

允许修改：

- `web-next/components/dashboard/IncidentSection.tsx`
- `web-next/components/dashboard/IncidentList.tsx`
- 新增 `web-next/components/dashboard/IncidentBulkActionBar.tsx`
- 新增 `web-next/components/dashboard/IncidentExportQueuePanel.tsx`
- 可新增 `web-next/types/incidentBulkActions.ts`
- 必要时轻量更新 `web-next/hooks/useIncidents.ts`，仅限前端列表状态 helper，不改变 API contract
- 新增 `server/tests/test_incident_bulk_selection_export_queue_e2e.py`
- 必要时轻量更新 `server/tests/test_incident_status_filter_archive_e2e.py`
- `docs/runs/2026-06-22-m3-20-incident-workbench-bulk-selection-export-queue-ux.md`
- `docs/runs/artifacts/m3-20-incident-workbench-bulk-selection-export-queue/**`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`
- `docs/agent/M3_20_INCIDENT_WORKBENCH_BULK_SELECTION_EXPORT_QUEUE_UX_TASK.md`

禁止修改：

- 认证 / 授权
- `server/security/**` / Guardrails
- SSRF
- DB schema / Alembic migration
- 后端 incident / report API contract
- `server/routers/incidents_router.py`
- `server/services/incident_service.py`
- `server/services/incident_report_service.py`
- `server/models_db.py`
- npm 依赖
- rate limit 常量
- `.env`、`.coverage`、数据库、真实密钥
- 新增案件状态或改变 `closed_at` 语义
- 自动关闭、删除或批量修改案件
- 新增 PDF / DOCX / ZIP / CSV / 后端批量导出格式
- 调用 LLM 生成批量摘要
- 把完整 raw payload、完整 analyst note、完整 timeline note、完整报告 markdown、system prompt、stack trace、API key 写入 DOM、复制文本、截图说明、运行日志或测试输出
- 使用 `localStorage` / `sessionStorage` 持久化选择或导出队列
- 使用 `dangerouslySetInnerHTML` 或 `innerHTML`

## 阶段计划

- [x] 阶段 0：读取任务文档、项目规则、相邻 run log、前端组件、hook 与 E2E helper。
- [x] 阶段 1 RED：新增 `server/tests/test_incident_bulk_selection_export_queue_e2e.py`，确认缺少 `incident-bulk-action-bar` selector 时失败。
- [x] 阶段 2 GREEN：新增批量操作栏、前端导出队列提示区，接入 `IncidentSection` 与 `IncidentList` 多选。
- [x] 阶段 3 IMPROVE：de-sloppify、安全扫描、移动端横向溢出检查、筛选切换清理选择检查。
- [ ] 阶段 4：运行新增 bulk selection E2E、M3-19 / M3-18 / M3-17 / report / preview / responsive 回归。
- [ ] 阶段 5：运行后端 incident 契约、关键 E2E 串跑、后端全量、Guardrails、前端 typecheck/build。
- [ ] 阶段 6：同步 `PRODUCT.md`、`docs/plans/M2_PRODUCT_ROADMAP.md`、`docs/agent/UNATTENDED_LONG_TASKS.md` 和本日志。
- [ ] 阶段 7：精确拆分 commit 并 push `origin/main`。

## 停止条件

- Playwright 浏览器无法启动，且无法用 `PLAYWRIGHT_CHROMIUM_EXECUTABLE` 指到系统 Chrome 解决。
- dev server 无法稳定返回 `/api/backend/health`。
- 需要新增后端批量导出 API、ZIP/PDF/CSV 或数据库队列表才能完成。
- 需要修改认证、Guardrails、SSRF、DB schema、后端 incident/report API、依赖或 rate limit 常量。
- E2E 只能 skipped，无法获得真实浏览器 pass。
- DOM、复制文本、下载 markdown 或截图说明中出现 forbidden sentinel。
- 当前工作区存在 unrelated dirty files 时，不允许 broad stage；只能精确 stage 本任务文件。

## 阶段记录

### 阶段 0：启动与上下文

已完成任务文档、项目规则、相邻运行日志、现有 incident list/status filter/detail 前端组件、hook 和 E2E helper 阅读。

关键决策：

- 选择和导出队列只保存在 `IncidentSection` React state 中，刷新页面自然清空。
- 批量复制摘要只包含安全字段：incident id、title length、status、severity、alert_count、updated_at、closed_at 是否存在。
- 导出队列只是前端准备队列提示，不触发后端请求、不下载文件、不新增导出格式。
- `incident-select-checkbox` 作为列表项主按钮的 sibling 渲染，checkbox 点击不触发详情选择；点击列表主体继续打开详情。
- 切换 M3-19 筛选后，`selectedIncidentIds` 与当前可见 `incidentItems` 求交集，避免隐藏项继续计数。

### 阶段 1：RED E2E 编写与环境前置

新增 `server/tests/test_incident_bulk_selection_export_queue_e2e.py`，覆盖登录、创建 open / contained / resolved 三个案件样本、批量选择、复制安全摘要、导出队列提示、筛选切换清理 selection、checkbox 不打开详情、列表主体打开详情、刷新不持久化、桌面/移动截图和 DOM/clipboard/storage forbidden sentinel。

静态检查：

```text
py_compile server\tests\test_incident_bulk_selection_export_queue_e2e.py
passed
```

本地 dev server 前置：

```text
http://127.0.0.1:8140/health -> 200 {"status":"ok"}
http://localhost:3140/api/backend/health -> 200 {"status":"ok"}
http://127.0.0.1:3140/api/backend/health -> 200 {"status":"ok"}
```

RED 首轮未到目标 selector：

```text
1 failed in 18.20s
AssertionError: Demo 攻击接口返回 HTTP 403: '{"error":"forbidden"}'
```

定位结果：

- 直接请求后端 `http://127.0.0.1:8140/alerts/demo` 带 `Origin: http://localhost:3140` 返回 401，说明后端 origin gate 已通过，缺少登录是预期。
- 通过前端代理 `http://localhost:3140/api/backend/alerts/demo` 返回 `{"error":"forbidden"}`。
- `web-next/middleware.ts` 对 `/api/backend/**` 检查的是 `ALLOWED_ORIGINS`，不是 `ALLOWED_HOSTS`；当前前端进程需要用 `ALLOWED_ORIGINS=http://localhost:3140,http://127.0.0.1:3140` 重启。

owner 重启前端并补 `ALLOWED_ORIGINS` 后，代理前置恢复：

```text
http://localhost:3140/api/backend/health -> 200 {"status":"ok"}
POST /api/backend/alerts/demo with Origin http://localhost:3140 -> 401 {"detail":"UNAUTHORIZED"}
```

目标 RED 命令：

```powershell
$env:E2E_BASE_URL='http://localhost:3140'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_incident_bulk_selection_export_queue_e2e.py -q --tb=short --run-e2e -s -rs
```

目标 RED 结果：

```text
1 failed in 33.16s
TimeoutError: waiting for get_by_test_id("incident-bulk-action-bar").first to be visible
```

失败点符合预期：真实浏览器已完成登录、Demo 告警、创建 open / contained / resolved 样本并进入案件列表；当前 UI 尚无批量操作栏，测试未 skip。

### 阶段 2：GREEN 实现

前端最小 UX 已落地：

- 新增 `IncidentBulkActionBar.tsx`，显示当前筛选下选中数、全选当前列表、清空选择、复制安全摘要、加入导出队列。
- 新增 `IncidentExportQueuePanel.tsx`，展示前端准备队列数量、最近加入 id、每项状态 / 严重度 / 告警数 / title length / closed_at 是否存在，并提供清空队列。
- 新增 `incidentBulkActions.ts`，集中生成安全字段队列项和 clipboard 摘要；摘要不包含 title 正文、summary、payload、note、report markdown、secret、stack trace。
- `IncidentList.tsx` 为每个列表项增加 sibling checkbox：`data-testid="incident-select-checkbox"`，checkbox 点击只切换选择，不触发行详情打开。
- `IncidentSection.tsx` 用 React state 保存 `selectedIncidentIds` 与 `exportQueue`；切换筛选或列表刷新时把 selection 与当前可见列表求交集；队列去重并限制最多 25 项。
- 没有新增后端 API、DB schema、npm 依赖或导出格式；没有调用 LLM；没有使用 `localStorage` / `sessionStorage` / `dangerouslySetInnerHTML`。

### 阶段 3：IMPROVE 与新增 E2E GREEN

新增 E2E 初次 GREEN 前暴露两个环境 / 测试稳定性问题：

- 当前本地 backend 长时运行后触发注册限流，owner 按本任务临时 SQLite DB 重启 backend 后恢复；未改生产 rate limit。
- 新开 `/dashboard` 页面后 Dashboard route click 偶发未触发 hydration handler。测试最终改为在同一 hydrated 真实浏览器页面内 `overview -> incidents` 重新挂载验证 React 内存状态清空，并随后执行真实 `page.reload()` 验证本功能没有 storage 持久化。业务验证仍覆盖刷新后不可从 storage 恢复 selection / queue。

新增 E2E GREEN：

```powershell
$env:E2E_BASE_URL='http://localhost:3140'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_incident_bulk_selection_export_queue_e2e.py -q --tb=short --run-e2e -s -rs
```

结果：

```text
1 passed in 19.56s
诊断：registered=True；open / contained / resolved 三个样本创建成功；
copy_status='已复制'；clipboard_checked=True；
screenshots=[
  docs\runs\artifacts\m3-20-incident-workbench-bulk-selection-export-queue\bulk-selection-desktop.png,
  docs\runs\artifacts\m3-20-incident-workbench-bulk-selection-export-queue\bulk-selection-mobile.png
]
forbidden=None；clipboard_forbidden=None；
storage_before_reload={'local': [], 'session': []}；
storage={'local': [], 'session': []}
```

禁用项扫描：

```powershell
rg -n "console\.log|localStorage|sessionStorage|dangerouslySetInnerHTML|innerHTML|sk-|AKIA|ghp_|PRIVATE KEY|Traceback|system\s*:|developer\s*:" web-next\components\dashboard web-next\types\incidentBulkActions.ts server\tests\test_incident_bulk_selection_export_queue_e2e.py
```

结果仅命中新 E2E 的 forbidden sentinel 与 storage 断言；产品代码无命中。

## 验证证据

- 新增 bulk selection/export queue E2E：`1 passed in 19.56s`。
- 相邻案件 UX 回归 E2E（incident report / preview / evidence pack / closure / status filter / Dashboard responsive）：`7 passed in 74.98s`。
- Demo flow stability 复跑：`1 passed in 10.14s`。
- 关键 E2E 串跑（auth / demo / report / route / responsive / stability / mobile visual / preview / timeline / runbook / evidence / closure / status filter / bulk selection）：`15 passed in 145.85s`。
- 后端 incident 契约：`17 passed in 3.12s`。
- 后端全量：`344 passed, 16 skipped, 17 warnings in 85.66s`。
- Guardrails 专项：`139 passed, 17 warnings in 18.92s`。
- 前端 `npm run typecheck`：通过。
- 前端 `npm run build`：通过（`/dashboard` 57.1 kB / First Load JS 204 kB）。

关键 E2E 串跑的本地环境说明：

- 首轮完整串跑在长时运行 backend 上遇到注册限流 setup 失败；未修改生产 `REGISTER_RATE_LIMIT_*`。
- 第二轮把多个用例指向同一稳定账号后触发登录限流 setup 失败；未修改生产 `LOGIN_RATE_LIMIT_*`。
- 最终在临时 `.tmp/m3-20-e2e-green.db` 中为每个 E2E prefix 预置独立本地测试账号后完成真实浏览器完整串跑；该数据库不纳入提交，不改变 DB schema 或后端 API。

## 截图证据

- 桌面：`docs/runs/artifacts/m3-20-incident-workbench-bulk-selection-export-queue/bulk-selection-desktop.png`
- 移动：`docs/runs/artifacts/m3-20-incident-workbench-bulk-selection-export-queue/bulk-selection-mobile.png`

## 未解决问题

无本任务阻塞。

环境噪声：关键 E2E 初始失败均发生在登录/注册前置阶段，来自本地 dev backend 长时运行后的 rate-limit 内存状态；最终通过独立本地测试账号完成完整串跑，未修改认证/授权、后端 rate limit、Guardrails 或后端 API。

## 最终状态

已完成。准备按测试 / 前端 UX / 文档与截图三组精确拆分 commit，并 push 到 `origin/main`。
