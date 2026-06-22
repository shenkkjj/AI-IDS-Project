# Run: M3-21 Incident Workspace Keyboard Navigation / Accessibility QA UX 收口

开始时间：2026-06-22
运行模式：L5
预算：90-180 分钟；同一失败最多修复 3 轮；diff 超过约 900 行时停止总结，除非主要是测试/文档

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
 M docs/runs/artifacts/m3-19-closed-incident-archive-status-filter/status-filter-desktop.png
 M docs/runs/artifacts/m3-19-closed-incident-archive-status-filter/status-filter-mobile.png
?? .tmp/
?? docs/agent/M3_21_INCIDENT_WORKSPACE_KEYBOARD_NAVIGATION_ACCESSIBILITY_QA_UX_TASK.md
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

当前 `git log --oneline --decorate -5`：

```text
67a520d (HEAD -> main, origin/main) docs(incidents): 记录案件批量操作 UX 收口
f91a270 feat(incidents): 增加案件批量选择与导出队列
42d3434 test(e2e): 覆盖案件批量选择导出队列
78abe5a docs(incidents): 记录案件归档筛选 UX 收口
c16014b feat(incidents): 增加案件状态筛选归档视图
```

启动观察：

- 本地 `main` 与 `origin/main` 对齐。
- 工作区已有跨任务截图刷新、旧 dev server 日志、`.tmp` 与 pytest cache 权限噪声；本任务只允许精确 stage M3-21 文件，禁止 `git add .`。
- `docs/agent/M3_21_INCIDENT_WORKSPACE_KEYBOARD_NAVIGATION_ACCESSIBILITY_QA_UX_TASK.md` 启动时未跟踪，但属于本任务文档入库范围。
- `docs/agent/UNATTENDED_LONG_TASKS.md` 启动时已有修改，本任务只在最终文档同步阶段复核并精确提交 M3-21 要求的部分。

## 必读上下文清单

- [x] `AGENTS.md`
- [x] `CLAUDE.md`
- [x] `PRODUCT.md`
- [x] `docs/agent/UNATTENDED_LONG_TASKS.md`
- [x] `docs/agent/M3_17_INCIDENT_ALERT_EVIDENCE_PACK_CHECKLIST_UX_TASK.md`
- [x] `docs/agent/M3_18_INCIDENT_CLOSURE_POST_INCIDENT_REVIEW_CHECKLIST_UX_TASK.md`
- [x] `docs/agent/M3_19_CLOSED_INCIDENT_ARCHIVE_STATUS_FILTER_UX_TASK.md`
- [x] `docs/agent/M3_20_INCIDENT_WORKBENCH_BULK_SELECTION_EXPORT_QUEUE_UX_TASK.md`
- [x] `docs/agent/M3_21_INCIDENT_WORKSPACE_KEYBOARD_NAVIGATION_ACCESSIBILITY_QA_UX_TASK.md`
- [x] `docs/runs/2026-06-21-m3-17-incident-alert-evidence-pack-checklist-ux.md`
- [x] `docs/runs/2026-06-21-m3-18-incident-closure-post-incident-review-checklist-ux.md`
- [x] `docs/runs/2026-06-21-m3-19-closed-incident-archive-status-filter-ux.md`
- [x] `docs/runs/2026-06-22-m3-20-incident-workbench-bulk-selection-export-queue-ux.md`
- [x] `docs/plans/M2_PRODUCT_ROADMAP.md` 中 M3-17 / M3-18 / M3-19 / M3-20 段落
- [x] `web-next/components/dashboard/IncidentSection.tsx`
- [x] `web-next/components/dashboard/IncidentList.tsx`
- [x] `web-next/components/dashboard/IncidentStatusFilterBar.tsx`
- [x] `web-next/components/dashboard/IncidentBulkActionBar.tsx`
- [x] `web-next/components/dashboard/IncidentExportQueuePanel.tsx`
- [x] `web-next/components/dashboard/IncidentDetailPanel.tsx`
- [x] `web-next/components/dashboard/IncidentReportPreview.tsx`
- [x] `web-next/components/dashboard/IncidentEvidencePackChecklist.tsx`
- [x] `web-next/components/dashboard/IncidentClosureReviewChecklist.tsx`
- [ ] `web-next/types/incidentBulkActions.ts`
- [x] `server/tests/e2e_helpers.py`
- [x] `server/tests/test_incident_bulk_selection_export_queue_e2e.py`
- [ ] `server/tests/test_incident_status_filter_archive_e2e.py`
- [ ] `server/tests/test_incident_closure_review_checklist_e2e.py`
- [ ] `server/tests/test_incident_evidence_pack_checklist_e2e.py`
- [ ] `server/tests/test_incident_report_preview_e2e.py`
- [ ] `server/tests/test_dashboard_responsive_e2e.py`

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

在 M3-20 Incident Workbench Bulk Selection / Export Queue UX 之上，新增案件工作台键盘导航与可访问性 QA 收口。owner 应能只用键盘完成状态筛选、列表多选、打开详情、状态 / 严重度切换、保存、报告预览焦点进入与关闭恢复、Evidence Pack / Closure Review 刷新与复制、批量复制、加入并清空前端导出队列。

## 范围

允许修改：

- `web-next/components/dashboard/IncidentSection.tsx`
- `web-next/components/dashboard/IncidentList.tsx`
- `web-next/components/dashboard/IncidentStatusFilterBar.tsx`
- `web-next/components/dashboard/IncidentBulkActionBar.tsx`
- `web-next/components/dashboard/IncidentExportQueuePanel.tsx`
- `web-next/components/dashboard/IncidentDetailPanel.tsx`
- `web-next/components/dashboard/IncidentReportPreview.tsx`
- `web-next/components/dashboard/IncidentEvidencePackChecklist.tsx`
- `web-next/components/dashboard/IncidentClosureReviewChecklist.tsx`
- 可新增 `web-next/components/dashboard/IncidentA11yUtils.ts`
- 新增 `server/tests/test_incident_workspace_accessibility_e2e.py`
- `docs/runs/2026-06-22-m3-21-incident-workspace-keyboard-navigation-accessibility-qa-ux.md`
- `docs/runs/artifacts/m3-21-incident-workspace-accessibility/**`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`
- `docs/agent/M3_21_INCIDENT_WORKSPACE_KEYBOARD_NAVIGATION_ACCESSIBILITY_QA_UX_TASK.md`

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
- 案件状态语义、`closed_at` 语义、报告导出格式、Evidence Pack / Closure Review 业务判定标准
- 自动关闭、删除或批量修改案件
- 调用 LLM
- 使用 `localStorage` / `sessionStorage`
- 使用 `dangerouslySetInnerHTML` / `innerHTML`

## 阶段计划

- [x] 阶段 0：基线与上下文读取。
- [ ] 阶段 1 RED：新增 keyboard/a11y E2E 并确认失败。
- [ ] 阶段 2 GREEN：补最小键盘导航、ARIA 和焦点恢复。
- [ ] 阶段 3 IMPROVE：de-sloppify、DOM audit、截图。
- [ ] 阶段 4：验证矩阵。
- [ ] 阶段 5：文档同步。
- [ ] 阶段 6：精确 commit / push。

## 停止条件

- Playwright / Chrome 无法启动，且无法用 `PLAYWRIGHT_CHROMIUM_EXECUTABLE` 指到系统 Chrome 解决。
- dev server 无法稳定返回 `/api/backend/health`。
- 需要修改认证、后端 API、DB schema、Guardrails、SSRF、npm 依赖或 rate limit 才能通过。
- 登录 / 注册 rate limit 阻塞且无法通过临时本地 backend 或预置独立本地测试账号解决。
- 新增 E2E 只能 skipped，无法获得真实浏览器 pass。
- DOM、clipboard 或截图说明命中 forbidden sentinel。
- 当前 dirty tree 中存在 unrelated 文件时，不允许 broad stage；只能精确 stage 本任务文件。

## 阶段记录

### 阶段 0：启动与上下文

已完成任务文档、项目规则、相邻运行日志、现有 incident workbench 前端组件和 M3-20 E2E helper 阅读。

关键事实：

- M3-20 已在 `IncidentSection` 中用 React state 保存 `selectedIncidentIds` 和 `exportQueue`，没有浏览器 storage 持久化。
- `IncidentList` 的 checkbox 已经是列表项按钮的 sibling，但 checkbox aria-label 当前包含完整 title，需要改为安全字段。
- `IncidentDetailPanel` 的 status / severity 已使用 `role="radiogroup"` 和 `role="radio"`，但尚未实现方向键导航。
- `IncidentReportPreview` 当前没有 `tabIndex` / `role`，打开后也没有焦点进入与关闭恢复。
- Evidence Pack / Closure Review 已有刷新、复制和 `aria-live` 状态，但 check item 语义仍可加强。

关键决策：

- 新增 E2E 复用 M3-20 测试里的真实 UI 创建案件路径，避免新增后端能力或测试专用 API。
- 键盘增强只绑定局部 radiogroup 和 report preview；不引入全局快捷键或可见键盘教程。
- `aria-label` 只使用 incident id、状态、严重度、告警数等安全字段，不新增完整 title / summary / payload / note / report markdown。
- 焦点状态只用 Tailwind `focus-visible` 类，不写 storage，不改全局 CSS。

## 验证证据

### 阶段 1：RED E2E

新增 `server/tests/test_incident_workspace_accessibility_e2e.py`，真实浏览器覆盖：

- 登录 Dashboard。
- 通过现有 UI 创建 contained 案件样本。
- keyboard 操作 `incident-filter-contained`、`incident-select-checkbox`、`incident-list-item`。
- status / severity radiogroup 方向键、保存、报告预览焦点进入和 Escape 焦点恢复。
- Evidence Pack / Closure Review 刷新与复制。
- 批量复制、加入导出队列、清空队列。
- accessible name audit、重复 id audit、storage key audit、DOM / clipboard forbidden sentinel。
- 桌面 / 移动截图路径。

静态检查：

```text
py_compile server\tests\test_incident_workspace_accessibility_e2e.py
passed
```

本地 dev server 前置：

```text
http://127.0.0.1:8140/health -> 200 {"status":"ok"}
http://localhost:3140/api/backend/health -> 200 {"status":"ok"}
```

首轮 RED 命令：

```powershell
$env:E2E_BASE_URL='http://localhost:3140'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_incident_workspace_accessibility_e2e.py -q --tb=short --run-e2e -s -rs
```

目标 RED 结果：

```text
1 failed in 14.10s
AssertionError: checkbox aria-label 应包含 incident_id, 实际 '选择案件 M3-21 contained cd4bfe'
```

失败点符合预期：当前 `IncidentList` checkbox accessible name 使用 title 片段，违反 M3-21 “不得新增完整 title 正文；允许 incident_id / 状态 / 严重度 / 告警数”的安全 aria-label 要求。

### 阶段 2：GREEN 实现与新增 E2E 通过

前端最小 UX 已落地：

- `IncidentSection.tsx`：为案件工作台整体和左右区域补 `region` / `aria-label`，刷新按钮补 `focus-visible`。
- `IncidentStatusFilterBar.tsx`：筛选按钮补稳定 `focus-visible`，保留 `aria-pressed`。
- `IncidentList.tsx`：checkbox accessible name 改为 incident id、状态、严重度、告警数；列表项补 `aria-current` / `aria-selected` 和 focus 样式。
- `IncidentBulkActionBar.tsx` / `IncidentExportQueuePanel.tsx`：按钮补 focus 样式，队列补 `role=list/listitem`。
- `IncidentDetailPanel.tsx`：status / severity radiogroup 支持 `ArrowRight/ArrowDown/ArrowLeft/ArrowUp/Home/End` 局部导航；报告预览打开后 focus 进入 preview region，Escape / close 恢复到 `incident-preview-report`；主要输入和按钮补 aria/focus。
- `IncidentReportPreview.tsx`：root 补 `role="region"`、`tabIndex={-1}`、focus 样式，close icon 明确隐藏。
- `IncidentEvidencePackChecklist.tsx` / `IncidentClosureReviewChecklist.tsx`：操作按钮补 focus 样式，checklist 补 list/listitem 语义，closure recommendation 补 status 语义。

新增 E2E GREEN：

```powershell
$env:E2E_BASE_URL='http://localhost:3140'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_incident_workspace_accessibility_e2e.py -q --tb=short --run-e2e -s -rs
```

结果：

```text
1 passed in 11.53s
诊断：registered=True；incident_id='inc_641d1670679e4c1c'；
checkbox_aria='选择案件 inc_641d1670679e4c1c，状态 已遏制，严重度 严重，1 条关联告警'；
preview_focus='incident-report-preview'；restore_focus='incident-preview-report'；
evidence_copy_status='已复制'；closure_copy_status='已复制'；bulk_copy_status='已复制'；
screenshots=[
  docs\runs\artifacts\m3-21-incident-workspace-accessibility\accessibility-desktop.png,
  docs\runs\artifacts\m3-21-incident-workspace-accessibility\accessibility-mobile.png
]
forbidden=None；clipboard_forbidden=None；storage={'local': [], 'session': []}
```

静态扫描：

```powershell
rg -n "console\.log|localStorage|sessionStorage|dangerouslySetInnerHTML|innerHTML|sk-|AKIA|ghp_|PRIVATE KEY|Traceback|system\s*:|developer\s*:" web-next\components\dashboard server\tests\test_incident_workspace_accessibility_e2e.py
```

结果仅命中新 E2E 的 forbidden sentinel 与 storage audit；产品代码无命中。

前端 typecheck 早期验证：

```text
npm run typecheck
passed
```

## 截图证据

待回填：

- `docs/runs/artifacts/m3-21-incident-workspace-accessibility/accessibility-desktop.png`
- `docs/runs/artifacts/m3-21-incident-workspace-accessibility/accessibility-mobile.png`

## 未解决问题

### 阶段 4：相邻案件 UX 回归

相邻回归首轮：

```powershell
$env:E2E_BASE_URL='http://localhost:3140'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_incident_bulk_selection_export_queue_e2e.py server\tests\test_incident_status_filter_archive_e2e.py server\tests\test_incident_closure_review_checklist_e2e.py server\tests\test_incident_evidence_pack_checklist_e2e.py server\tests\test_incident_report_preview_e2e.py server\tests\test_dashboard_responsive_e2e.py -q --tb=short --run-e2e -s -rs
```

结果：

```text
3 passed, 4 failed in 51.02s
```

通过项：

- `test_incident_bulk_selection_export_queue_e2e.py`：passed，forbidden=None，clipboard_forbidden=None，storage/local+session empty。
- `test_incident_status_filter_archive_e2e.py`：passed，forbidden=None。
- `test_incident_closure_review_checklist_e2e.py`：passed，forbidden=None，clipboard_forbidden=None。

失败项均为 E2E 注册 rate limit 前置，未进入产品 selector 或断言：

- `test_incident_evidence_pack_checklist_e2e.py`
- `test_incident_report_preview_e2e.py`
- `test_dashboard_responsive_e2e.py` desktop/mobile

处理：按既有 M3-20 run log 策略重启临时本地 backend，使用 `.tmp/m3-21-e2e-matrix.db` 清空本地内存限流；未修改生产 rate limit。

复跑失败项：

```powershell
$env:E2E_BASE_URL='http://localhost:3140'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_incident_evidence_pack_checklist_e2e.py server\tests\test_incident_report_preview_e2e.py server\tests\test_dashboard_responsive_e2e.py -q --tb=short --run-e2e -s -rs
```

结果：

```text
4 passed in 34.32s
```

相邻案件 UX 回归最终覆盖 7 个真实浏览器测试，全部通过；首轮失败仅为本地注册限流前置。

### 阶段 4：关键 E2E 串跑

关键 E2E 串跑首轮：

```powershell
$env:E2E_BASE_URL='http://localhost:3140'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_auth_session_e2e.py server\tests\test_demo_flow_e2e.py server\tests\test_incident_report_e2e.py server\tests\test_dashboard_route_sections_e2e.py server\tests\test_dashboard_responsive_e2e.py server\tests\test_demo_flow_stability_e2e.py server\tests\test_dashboard_mobile_visual_e2e.py server\tests\test_incident_report_preview_e2e.py server\tests\test_security_timeline_drilldown_e2e.py server\tests\test_dashboard_operational_runbook_e2e.py server\tests\test_incident_evidence_pack_checklist_e2e.py server\tests\test_incident_closure_review_checklist_e2e.py server\tests\test_incident_status_filter_archive_e2e.py server\tests\test_incident_bulk_selection_export_queue_e2e.py server\tests\test_incident_workspace_accessibility_e2e.py -q --tb=short --run-e2e -s -rs
```

首次结果：

```text
15 failed, 1 passed in 22.07s
```

失败均为本地 backend 注册 rate limit 前置，未进入产品断言。处理方式：在 `.tmp/m3-21-e2e-matrix.db` 预置关键 E2E stable 测试账号，重启临时 backend 清空内存限流；未修改认证/授权或 rate limit。

预置账号后复跑完整串跑：

```text
14 passed, 2 failed in 147.74s
```

其中 14 个真实浏览器测试已通过；2 个失败：

- `test_security_timeline_drilldown_e2e.py`：stable prefix 识别错误，仍为注册 rate limit 前置。
- `test_dashboard_operational_runbook_e2e.py`：stable prefix 识别错误，仍为注册 rate limit 前置。

补充实际 prefix 后再次重启临时 backend，并只复跑两项：

```powershell
$env:E2E_BASE_URL='http://localhost:3140'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_security_timeline_drilldown_e2e.py server\tests\test_dashboard_operational_runbook_e2e.py -q --tb=short --run-e2e -s -rs
```

结果：

```text
1 passed, 1 failed in 20.99s
```

- Security Timeline Drilldown：passed，forbidden=None，clipboard_forbidden=None。
- Operational Runbook：失败在既有测试 `_click_copy_and_assert_status` 对 `runbook-copy-status` visible 的等待；未命中 forbidden / 布局 / 本任务 selector。随后单独复跑该既有 E2E：

```powershell
$env:E2E_BASE_URL='http://localhost:3140'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_dashboard_operational_runbook_e2e.py -q --tb=short --run-e2e -s -rs
```

结果：

```text
1 passed in 7.50s
copy_status='已复制'；clipboard_checked=True；forbidden=None
```

关键 E2E 最终：15 个文件 / 16 个真实浏览器测试全部有通过证据；中间失败均为本地注册限流前置或既有 runbook 复制状态等待偶发，未修改 rate limit、认证、后端 API 或 runbook 代码。

### 阶段 4：后端 / Guardrails / 前端验证

后端 incident / report 契约：

任务文档中的 `server/tests/test_incident_api.py` 与 `server/tests/test_incident_report_api.py` 在当前仓库不存在；对应契约文件为 `server/tests/test_incidents.py` 与 `server/tests/test_incident_report_export.py`。

首轮因 Windows 默认 Temp 目录权限失败：

```text
PermissionError: [WinError 5] 拒绝访问。: 'C:\Users\27629\AppData\Local\Temp\pytest-of-276291'
```

指定本仓库 `.tmp` 后复跑：

```powershell
New-Item -ItemType Directory -Force -Path '.tmp\pytest-m3-21-incident' | Out-Null
$env:TMP=(Resolve-Path '.tmp\pytest-m3-21-incident').Path
$env:TEMP=$env:TMP
.\.venv\Scripts\python.exe -m pytest server\tests\test_incidents.py server\tests\test_incident_report_export.py -q --tb=short
```

结果：

```text
31 passed in 7.06s
```

Guardrails 专项：

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

结果：

```text
139 passed, 17 warnings in 19.60s
```

后端全量：

```powershell
New-Item -ItemType Directory -Force -Path '.tmp\pytest-m3-21-full' | Out-Null
$env:TMP=(Resolve-Path '.tmp\pytest-m3-21-full').Path
$env:TEMP=$env:TMP
$env:APP_SECRET='test-local-secret-key-for-m3-21-full-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-m3-21-full-32chars'
.\.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

结果：

```text
344 passed, 17 skipped, 17 warnings in 89.00s
```

前端 typecheck：

```text
npm run typecheck
passed
```

前端 build：

```text
npm run build
passed
/dashboard 57.8 kB / First Load JS 205 kB
```

## 未解决问题

暂无。

## 阶段 5：文档同步

已同步：

- `PRODUCT.md` §2.2 新增 M3-21 交付说明、截图路径、验证矩阵和安全边界。
- `docs/plans/M2_PRODUCT_ROADMAP.md` 新增 M3-21 收口段，记录 RED、GREEN、关键 E2E 中间失败原因、最终通过证据、精确 stage 文件清单和不做范围。
- `docs/agent/UNATTENDED_LONG_TASKS.md` 将 M3-21 条目更新为已交付，并把推荐启动口令推进到 M3-22 Incident Workspace Guided Review Session / Operator Handoff UX 候选。
- `docs/agent/M3_21_INCIDENT_WORKSPACE_KEYBOARD_NAVIGATION_ACCESSIBILITY_QA_UX_TASK.md` 作为本次 L5 任务文档入库。

截图证据：

- `docs/runs/artifacts/m3-21-incident-workspace-accessibility/accessibility-desktop.png`
- `docs/runs/artifacts/m3-21-incident-workspace-accessibility/accessibility-mobile.png`

## 最终验证矩阵

| 类别 | 命令 / 范围 | 结果 |
|---|---|---|
| RED E2E | `server/tests/test_incident_workspace_accessibility_e2e.py --run-e2e`（旧 UI） | 预期失败：checkbox aria-label 使用 title 片段 |
| 新增 E2E | `server/tests/test_incident_workspace_accessibility_e2e.py --run-e2e` | 1 passed in 11.53s |
| 相邻案件 UX | bulk selection、status filter、closure、evidence、report preview、dashboard responsive | 最终 7 个真实浏览器测试均有通过证据 |
| 关键 E2E | 15 个 E2E 文件 / 16 个真实浏览器测试 | 全部有通过证据；中间失败为本地注册限流或既有 runbook 等待偶发 |
| 后端 incident/report 契约 | `test_incidents.py` + `test_incident_report_export.py` | 31 passed in 7.06s |
| 后端全量 | `server/tests` | 344 passed, 17 skipped, 17 warnings in 89.00s |
| Guardrails | `server/tests/security/llm_guardrails` | 139 passed, 17 warnings in 19.60s |
| 前端 typecheck | `npm run typecheck` | passed |
| 前端 build | `npm run build` | passed；`/dashboard` 57.8 kB / First Load JS 205 kB |

## 提交计划

精确拆分 3 个 commit：

1. `test(e2e): 覆盖案件工作台键盘可访问性`
2. `feat(a11y): 完善案件工作台键盘导航`
3. `docs(a11y): 记录案件工作台可访问性收口`

禁止 stage：

- 旧任务截图刷新：`docs/runs/artifacts/m3-11` 到 `m3-20` 下的截图变更。
- 旧 dev server 日志、`.tmp`、pytest cache、真实 env、数据库、密钥、`.coverage`。

## 最终状态

实现、E2E、截图、验证矩阵和文档同步已完成；等待精确 commit 与 push。
