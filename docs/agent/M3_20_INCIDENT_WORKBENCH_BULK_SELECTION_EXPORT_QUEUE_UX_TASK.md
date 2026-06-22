# M3-20 Incident Workbench Bulk Selection / Export Queue UX 收口任务

> **给无人值守 Agent 的任务文档。** 本任务是 L5 超长任务：先读上下文，创建运行日志，按 TDD/E2E 红绿推进，阶段性记录证据，最后通过完整验证矩阵后精确 commit / push。不要把 skipped 当 passed。
>
> **执行要求**：实现时必须使用 `superpowers:executing-plans` 或 `superpowers:subagent-driven-development`，并使用 `superpowers:test-driven-development` 与 `superpowers:verification-before-completion`。如果当前环境没有子智能体工具，降级为 inline 执行，但仍要按阶段写运行日志。

## 0. 任务一句话

在 M3-19 案件列表筛选/归档能力之上，新增 **Bulk Selection / Export Queue** 体验：让 owner 能在当前筛选列表中多选案件、批量复制一份只含安全字段的案件摘要、把选中案件加入一个前端内存级“导出队列”提示区，并用真实浏览器 E2E 证明多选、批量复制、队列提示、筛选切换清理选择、桌面/移动布局和 forbidden sentinel 都可靠；不新增后端导出格式，不调用 LLM，不持久化队列。

## 1. 背景

已交付能力：

- M3-04 已交付案件工作台与案件状态流转。
- M3-07 / M3-14 已交付单案件报告导出与预览。
- M3-17 已交付 Evidence Pack Checklist。
- M3-18 已交付 Closure Review Checklist。
- M3-19 已交付案件列表状态筛选、关闭态归档视图和 `closed_at` 可见性。

当前体验缺口：

- owner 可以按状态筛选案件，但不能在列表层选中多个案件做批量复盘准备。
- 当前报告导出仍是单案件动作；演示或复盘时，经常需要先整理多个案件的安全摘要，再决定是否逐个打开详情导出报告。
- 现在没有批量复制的安全摘要格式，也没有“导出队列”提示区告诉用户当前选择了哪些案件、哪些能进一步单独导出报告。
- 还没有真实浏览器 E2E 覆盖列表多选、全选当前筛选、清空选择、筛选切换后选择清理、批量复制安全摘要、导出队列提示、桌面/移动截图和 forbidden sentinel。

本任务默认不改后端 API，不新增导出格式，不新增数据库字段，不改变权限模型。Bulk selection 和 export queue 只在当前 React 内存中存在，刷新页面后清空。

## 2. 必读上下文

开始前必须完整阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/runs/2026-06-21-m3-19-closed-incident-archive-status-filter-ux.md`
- `docs/runs/2026-06-21-m3-18-incident-closure-post-incident-review-checklist-ux.md`
- `docs/runs/2026-06-21-m3-17-incident-alert-evidence-pack-checklist-ux.md`
- `docs/runs/2026-06-18-m3-07-incident-evidence-report-export.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md` 中 M3-04 / M3-07 / M3-17 / M3-18 / M3-19 段落
- `web-next/components/dashboard/IncidentSection.tsx`
- `web-next/components/dashboard/IncidentList.tsx`
- `web-next/components/dashboard/IncidentStatusFilterBar.tsx`
- `web-next/components/dashboard/IncidentDetailPanel.tsx`
- `web-next/hooks/useIncidents.ts`
- `web-next/types/incident.ts`
- `server/tests/e2e_helpers.py`
- `server/tests/test_incident_status_filter_archive_e2e.py`
- `server/tests/test_incident_closure_review_checklist_e2e.py`
- `server/tests/test_incident_evidence_pack_checklist_e2e.py`
- `server/tests/test_incident_report_e2e.py`
- `server/tests/test_dashboard_responsive_e2e.py`

必须使用或参考的 skill：

- `superpowers:executing-plans` 或 `superpowers:subagent-driven-development`
- `superpowers:test-driven-development`
- `superpowers:verification-before-completion`
- `frontend-patterns`
- `frontend-design`
- `e2e-testing`

## 3. 硬边界

允许修改：

- `web-next/components/dashboard/IncidentSection.tsx`
- `web-next/components/dashboard/IncidentList.tsx`
- 可新增 `web-next/components/dashboard/IncidentBulkActionBar.tsx`
- 可新增 `web-next/components/dashboard/IncidentExportQueuePanel.tsx`
- 可新增 `web-next/types/incidentBulkActions.ts`，但只放前端展示辅助类型，不改变后端字段语义
- 必要时轻量更新 `web-next/hooks/useIncidents.ts`，仅限前端列表状态 helper，不改变 API contract
- 新增 `server/tests/test_incident_bulk_selection_export_queue_e2e.py`
- 必要时轻量更新 `server/tests/test_incident_status_filter_archive_e2e.py`
- `docs/runs/2026-06-22-m3-20-incident-workbench-bulk-selection-export-queue-ux.md`
- `docs/runs/artifacts/m3-20-incident-workbench-bulk-selection-export-queue/**`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

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
- 新增案件状态
- 改变 `closed_at` 自动设置 / 清空语义
- 自动关闭、删除或批量修改案件
- 新增 PDF / DOCX / ZIP / CSV / 后端批量导出格式
- 调用 LLM 生成批量摘要
- 把完整 raw payload、完整 analyst note、完整 timeline note、完整报告 markdown、system prompt、stack trace、API key 写入 DOM、复制文本、截图说明、运行日志或测试输出
- 用 `localStorage` / `sessionStorage` 持久化选中项或导出队列
- 使用 `dangerouslySetInnerHTML` 或 `innerHTML`

当前工作区长期存在跨任务截图、dev server log、`.tmp` 脏文件。提交时必须精确 stage 本任务文件，禁止 `git add .`。

## 4. 运行预算与停止条件

预算：

- 最长运行 4 小时。
- 同一失败最多修复 3 轮。
- diff 超过约 900 行时停止总结，除非主要是测试/文档。

必须停止并写清楚阻塞：

- Playwright 浏览器无法启动，且无法用 `PLAYWRIGHT_CHROMIUM_EXECUTABLE` 指到系统 Chrome 解决。
- dev server 无法稳定返回 `/api/backend/health`。
- 需要新增后端批量导出 API、ZIP/PDF/CSV 或数据库队列表才能完成。
- 需要修改认证、Guardrails、SSRF、DB schema、后端 incident/report API、依赖或 rate limit 常量。
- E2E 只能 skipped，无法获得真实浏览器 pass。
- DOM、复制文本、下载 markdown 或截图说明中出现 forbidden sentinel。
- 当前工作区存在 unrelated dirty files 时，不允许 broad stage；只能精确 stage 本任务文件。

## 5. 产品验收标准

完成后用户应该能在 Dashboard 的案件列表里完成：

1. 每条案件列表项左侧有可访问的多选控件：
   - `data-testid="incident-select-checkbox"`
   - `aria-label` 包含案件标题或 id。
2. 列表顶部或筛选条下方出现批量操作区：
   - `data-testid="incident-bulk-action-bar"`
   - 显示当前选中数量。
   - 提供 `全选当前列表`、`清空选择`、`复制安全摘要`、`加入导出队列`。
3. 全选只选择当前筛选结果里的案件，不跨筛选隐藏选择。
4. 切换 M3-19 状态筛选后，如果已选案件不在新筛选结果中，必须自动清理这些选择，并在批量操作区显示当前筛选内的真实选中数。
5. `复制安全摘要`：
   - `data-testid="incident-bulk-copy-summary"`
   - 状态 `data-testid="incident-bulk-copy-status"`
   - 复制内容只包含安全字段：incident id、title length、status、severity、alert_count、updated_at、closed_at 是否存在。
   - 不包含 summary 原文、payload、note、报告 markdown、secret、token。
6. `加入导出队列`：
   - `data-testid="incident-add-export-queue"`
   - 只把选中案件的安全字段加入 React 内存队列。
   - 不调用后端，不下载文件，不新增导出格式。
7. 队列提示区：
   - `data-testid="incident-export-queue-panel"`
   - 显示队列数量、最近加入的案件 id、每项状态和安全说明。
   - 提供 `清空队列`，`data-testid="incident-export-queue-clear"`。
   - 文案应明确这是“待逐案导出的准备队列”，不是后台任务。
8. 刷新页面后选择和队列清空；不得写 storage。
9. 单击列表项仍能打开案件详情；点击 checkbox 不应误触发行选择。
10. 现有 M3-19 状态筛选、M3-18 Closure Review、M3-17 Evidence Pack、单案件报告复制/下载/预览都不被破坏。
11. 桌面和移动端不产生整页横向溢出，批量操作按钮能换行。
12. DOM、复制文本、下载 markdown、截图说明均不包含 forbidden sentinel。

## 6. 推荐设计

### 6.1 UI 形态

建议新增：

```text
web-next/components/dashboard/IncidentBulkActionBar.tsx
web-next/components/dashboard/IncidentExportQueuePanel.tsx
```

放置顺序：

```text
CASES / 案件列表
刷新
IncidentStatusFilterBar
IncidentBulkActionBar
IncidentExportQueuePanel
创建入口
IncidentList
```

建议测试 ID：

```text
incident-select-checkbox
incident-bulk-action-bar
incident-bulk-selected-count
incident-bulk-select-page
incident-bulk-clear-selection
incident-bulk-copy-summary
incident-bulk-copy-status
incident-add-export-queue
incident-export-queue-panel
incident-export-queue-count
incident-export-queue-item
incident-export-queue-clear
```

视觉要求：

- 保持 Dashboard 工具型、紧凑、低噪声风格。
- 批量操作区不要做成 modal；应该是列表上方的内联工具条。
- 队列提示区可以是轻量 panel，但不要套卡片内卡片。
- 当前筛选无案件时，批量操作按钮 disabled。
- 多选 checkbox 有稳定尺寸，避免 hover / checked 状态导致列表布局跳动。
- 移动端按钮可换行，长 id 用 `break-all`。

### 6.2 状态模型

建议在 `IncidentSection` 内维护：

```ts
const [selectedIncidentIds, setSelectedIncidentIds] = useState<Set<string>>(new Set());
const [exportQueue, setExportQueue] = useState<IncidentSummary[]>([]);
const [bulkCopyStatus, setBulkCopyStatus] = useState<"idle" | "copied" | "failed">("idle");
```

筛选列表变化后：

```text
visibleIds = new Set(incidents.incidentItems.map(item => item.incident_id))
selectedIncidentIds = selectedIncidentIds ∩ visibleIds
```

队列加入规则：

```text
selected items by current list order
dedupe by incident_id
queue max 25 items
if selection empty, do nothing and show disabled state
```

不要把 selection 或 queue 写入 `localStorage` / `sessionStorage`。

### 6.3 安全摘要格式

建议复制格式：

```text
[AI-CyberSentinel Incident Bulk Summary]
count=<n>
filter=<current filter label>

- incident_id=<id>
  title_length=<number>
  status=<status>
  severity=<severity>
  alert_count=<number>
  updated_at=<epoch>
  closed_at=<present/absent>
```

不得复制：

- `incident.summary` 原文。
- alert payload。
- analyst note / timeline note。
- report markdown。
- secret / token / stack trace / prompt。

## 7. TDD / E2E 计划

### Task 1：创建运行日志

创建：

```text
docs/runs/2026-06-22-m3-20-incident-workbench-bulk-selection-export-queue-ux.md
```

初始内容必须包含：

- 开始时间。
- 当前 `git status --short --branch`。
- 当前 `git log -1 --oneline`。
- 必读上下文清单。
- 允许/禁止范围。
- 阶段计划。
- 停止条件。
- 当前工作区已有跨任务 artifact / dev server log / `.tmp` 脏文件，不允许 broad stage。

### Task 2：RED - 新增真实浏览器 E2E

新增：

```text
server/tests/test_incident_bulk_selection_export_queue_e2e.py
```

必须复用：

- `server.tests.e2e_helpers.assert_dev_server_reachable`
- `server.tests.e2e_helpers.register_or_login_for_e2e`
- `server.tests.e2e_helpers.skip_without_playwright`

测试流程：

1. 启动 Playwright chromium，支持 `PLAYWRIGHT_CHROMIUM_EXECUTABLE`。
2. `accept_downloads=True`，授予 clipboard 权限。
3. 登录 Dashboard。
4. 通过现有 UI 创建至少 3 个案件样本：
   - 1 个 open。
   - 1 个 contained。
   - 1 个 resolved。
5. 进入案件列表，等待 `incident-status-filter-bar`。
6. 断言 `incident-bulk-action-bar` 可见。
7. 断言每个 `incident-list-item` 内有 `incident-select-checkbox`。
8. 勾选两条案件，断言 `incident-bulk-selected-count` 显示 `2`。
9. 点击 `incident-bulk-copy-summary`，断言 `incident-bulk-copy-status` 为 `已复制` 或 `复制失败`。
10. 如果 clipboard 可读，断言复制文本包含 `AI-CyberSentinel Incident Bulk Summary`、`count=2`、`incident_id=`、`status=`、`severity=`，且不包含 forbidden sentinel、summary 原文、payload、note。
11. 点击 `incident-add-export-queue`，断言 `incident-export-queue-panel` 可见，`incident-export-queue-count` 显示 `2`。
12. 点击 `incident-filter-closed`，等待列表切换到关闭态，断言不在关闭态列表内的选择被清理，选中数不再错误显示为 `2`。
13. 点击 `incident-bulk-select-page`，断言当前关闭态列表被选中。
14. 点击 `incident-export-queue-clear`，断言队列清空。
15. 点击某个非 checkbox 的列表主体，断言仍能打开 `incident-detail-panel`，且 M3-18 `incident-closure-review-checklist` 仍可见。
16. 刷新页面，断言 `incident-bulk-selected-count` 回到 `0`，队列不持久化。
17. 扫描整页 DOM forbidden sentinel 和 storage：
   - `localStorage.length` 不因本功能增加。
   - `sessionStorage.length` 不因本功能增加。
18. 保存桌面截图：

```text
docs/runs/artifacts/m3-20-incident-workbench-bulk-selection-export-queue/bulk-selection-desktop.png
```

19. 设置移动 viewport 390x844，确认批量操作栏可换行、队列提示区可读、无横向溢出，保存：

```text
docs/runs/artifacts/m3-20-incident-workbench-bulk-selection-export-queue/bulk-selection-mobile.png
```

RED 预期：

- 当前 UI 没有 `incident-bulk-action-bar`，测试应 fail 在该 selector。
- 不允许因为 selector 不存在而 skip。

### Task 3：GREEN - 实现最小 UX

实现：

- `IncidentBulkActionBar.tsx`
- `IncidentExportQueuePanel.tsx`
- `IncidentList.tsx` 接入 checkbox、多选状态、checkbox 点击阻止行选择
- `IncidentSection.tsx` 维护 selection / export queue / bulk copy state

要求：

- 单击 checkbox 只切换选择，不打开 detail。
- 单击列表主体仍打开 detail。
- `全选当前列表` 只选择 `incidents.incidentItems` 当前可见项。
- 切换筛选时清理不在当前列表中的 selection。
- 队列只在内存中，刷新即清空。
- 队列去重，最多 25 条。
- 不调用后端导出接口。
- 不影响 M3-19 status filter、M3-18 closure review、M3-17 evidence pack。

### Task 4：IMPROVE - de-sloppify

检查并修复：

- 是否留下 `console.log`。
- 是否用了 `localStorage` / `sessionStorage`。
- 是否用了 `dangerouslySetInnerHTML` / `innerHTML`。
- 是否把 raw payload、完整 note、完整 markdown 写进列表、复制摘要或队列。
- 是否把 system prompt、stack trace、API key、regex、cookie、token 写进 DOM 或复制文本。
- 按钮是否有清晰文本或 `aria-label`。
- checkbox 是否有固定尺寸，移动端是否横向溢出。
- 筛选切换是否会保留隐藏项选择。
- 队列是否被误描述为真实后台导出任务。必须明确只是前端准备队列。

扫描命令：

```powershell
rg -n "console\.log|localStorage|sessionStorage|dangerouslySetInnerHTML|innerHTML|sk-|AKIA|ghp_|PRIVATE KEY|Traceback|system\s*:|developer\s*:" web-next\components\dashboard server\tests\test_incident_bulk_selection_export_queue_e2e.py
```

命中测试 sentinel 常量允许；生产组件命中敏感字面量必须修。

### Task 5：验证矩阵

如果本机 Chromium `spawn EPERM`，优先使用系统 Chrome：

```powershell
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
```

如需隔离 dev server，可沿用 M3-19 的 fresh backend/frontend 方案，但必须写进运行日志。

必须运行：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_incident_bulk_selection_export_queue_e2e.py -q --tb=short --run-e2e -s -rs
```

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_incident_status_filter_archive_e2e.py server\tests\test_incident_closure_review_checklist_e2e.py server\tests\test_incident_evidence_pack_checklist_e2e.py -q --tb=short --run-e2e -s -rs
```

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_incident_report_e2e.py server\tests\test_incident_report_preview_e2e.py server\tests\test_dashboard_responsive_e2e.py -q --tb=short --run-e2e -s -rs
```

后端 incident 契约：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_incidents.py -q --tb=short
```

关键 E2E 串跑，实际总数以 pytest 输出为准：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_auth_session_e2e.py server\tests\test_demo_flow_e2e.py server\tests\test_incident_report_e2e.py server\tests\test_dashboard_route_sections_e2e.py server\tests\test_dashboard_responsive_e2e.py server\tests\test_demo_flow_stability_e2e.py server\tests\test_dashboard_mobile_visual_e2e.py server\tests\test_incident_report_preview_e2e.py server\tests\test_security_timeline_drilldown_e2e.py server\tests\test_dashboard_operational_runbook_e2e.py server\tests\test_incident_evidence_pack_checklist_e2e.py server\tests\test_incident_closure_review_checklist_e2e.py server\tests\test_incident_status_filter_archive_e2e.py server\tests\test_incident_bulk_selection_export_queue_e2e.py -q --tb=short --run-e2e -s -rs
```

后端全量：

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

注意：

- 不要把 skipped 算成 passed。
- `npm run typecheck` 和 `npm run build` 不要并行运行，避免 `.next/types` 竞争导致假失败。
- 如果 E2E 因本地注册/登录限流失败，可以用 fresh backend/frontend 或多个稳定测试账号分摊，但不能改生产 rate limit。

### Task 6：文档同步

验证通过后更新：

- `PRODUCT.md`：在 M3 实施状态中新增 M3-20 已交付说明，包含真实验证结果、截图路径和安全边界。
- `docs/plans/M2_PRODUCT_ROADMAP.md`：新增 M3-20 章节，记录目标、已交付、验证、边界、改动文件、未解决问题。
- `docs/agent/UNATTENDED_LONG_TASKS.md`：把 M3-20 加入可复用超长任务列表；推荐下一条默认工单改为 **M3-21 Incident Workspace Keyboard Navigation / Accessibility QA UX**。
- `docs/runs/2026-06-22-m3-20-incident-workbench-bulk-selection-export-queue-ux.md`：补齐最终验证证据和最终状态。

M3-21 候选方向：

```text
Incident Workspace Keyboard Navigation / Accessibility QA UX：在不改后端和权限模型的前提下，为案件列表、筛选、多选、详情面板补键盘导航、焦点状态、aria 语义和真实浏览器可访问性 E2E。
```

## 8. 安全与隐私检查

必须确认：

- 批量选择不调用 LLM。
- 批量摘要不保存到 `localStorage` / `sessionStorage`。
- 队列只在 React state 中，不持久化。
- 列表和队列不展示 raw payload。
- 列表和队列不展示完整 timeline note / analyst note。
- 不保存完整报告 markdown。
- 未使用 `dangerouslySetInnerHTML` / `innerHTML`。
- DOM / clipboard 不含 secret / token / stack trace / system prompt / developer prompt / Guardrails regex。
- E2E 截图路径不包含真实用户 secret。
- 提交不包含 `.coverage`、真实 `.env`、数据库、临时 dev server log。

## 9. 提交计划

通过验证后拆成 3 个精确 commit。提交前必须运行：

```powershell
git status --short
git diff --cached --check
```

禁止：

```powershell
git add .
```

建议 commit：

1. `test(e2e): 覆盖案件批量选择导出队列`
   - `server/tests/test_incident_bulk_selection_export_queue_e2e.py`
2. `feat(incidents): 增加案件批量选择与导出队列`
   - `web-next/components/dashboard/IncidentBulkActionBar.tsx`
   - `web-next/components/dashboard/IncidentExportQueuePanel.tsx`
   - `web-next/components/dashboard/IncidentList.tsx`
   - `web-next/components/dashboard/IncidentSection.tsx`
   - 如有必要，精确加入轻量前端类型/helper 文件
3. `docs(incidents): 记录案件批量操作 UX 收口`
   - `docs/runs/2026-06-22-m3-20-incident-workbench-bulk-selection-export-queue-ux.md`
   - `docs/runs/artifacts/m3-20-incident-workbench-bulk-selection-export-queue/*.png`
   - `docs/agent/M3_20_INCIDENT_WORKBENCH_BULK_SELECTION_EXPORT_QUEUE_UX_TASK.md`
   - `docs/agent/UNATTENDED_LONG_TASKS.md`
   - `PRODUCT.md`
   - `docs/plans/M2_PRODUCT_ROADMAP.md`

如果工作区有 unrelated dirty files，只精确 stage 上述本任务文件，不要清理或回滚别人的改动。

## 10. 最终报告格式

完成后用中文输出：

- 完成状态：完成 / 部分完成 / 阻塞。
- 本任务改动文件列表。
- 三个 commit hash 与 commit message。
- 运行日志路径。
- 截图路径。
- 运行过的验证命令与结果，必须列出真实 passed / skipped / failed 数字。
- 安全边界确认。
- 未解决问题。
- 下一条建议工单：`M3-21 Incident Workspace Keyboard Navigation / Accessibility QA UX`。

如果阻塞：

- 写清楚阻塞发生在哪个阶段。
- 写清楚已经完成的文件和验证。
- 写清楚下一步最小可执行动作。
- 不要 push 半成品。
