# M3-19 Closed Incident Archive / Status Filter UX 收口任务

> **给无人值守 Agent 的任务文档。** 本任务是 L5 超长任务：先读上下文，创建运行日志，按 TDD/E2E 红绿推进，阶段性记录证据，最后通过完整验证矩阵后精确 commit / push。不要把 skipped 当 passed。
>
> **执行要求**：实现时必须使用 `superpowers:executing-plans` 或 `superpowers:subagent-driven-development`，并使用 `superpowers:test-driven-development` 与 `superpowers:verification-before-completion`。如果当前环境没有子智能体工具，降级为 inline 执行，但仍要按阶段写运行日志。

## 0. 任务一句话

在案件列表里新增 **Closed Incident Archive / Status Filter** 体验：基于现有 `GET /incidents?status=` 和 `useIncidents.loadIncidents({ status })`，让 owner 能按 `全部 / 活跃 / 已开启 / 调查中 / 已遏制 / 已解决 / 误报 / 已关闭归档` 筛选案件，并在关闭态列表中清楚看到 `closed_at`、关闭状态和关联告警数；不新增后端字段，不改权限模型，不改变案件状态流转。

## 1. 背景

已交付能力：

- M3-04 已交付案件工作台，后端支持 5 个案件状态：`open / investigating / contained / resolved / false_positive`；进入 `resolved / false_positive` 时自动设置 `closed_at`，从关闭态改回打开态时清空 `closed_at`。
- M3-07 / M3-14 已交付案件报告导出与预览。
- M3-17 已交付 Evidence Pack Checklist。
- M3-18 已交付 Closure Review Checklist，帮助 owner 判断案件是否适合关闭。
- 当前后端 `GET /incidents?status=<status>&limit=50` 已支持单状态白名单过滤；前端 `useIncidents.loadIncidents({ status })` 已支持透传状态参数。

当前体验缺口：

- `IncidentSection` 进入时始终加载全部案件，列表无法按状态查看。
- 已关闭案件和活跃案件混在同一个列表里，owner 难以快速回看 `resolved / false_positive` 的归档案件。
- `IncidentList` 只在底部显示 `已关闭`，没有明确展示 `closed_at` 时间，也没有按关闭态筛选的空态文案。
- 还没有真实浏览器 E2E 覆盖案件列表状态筛选、关闭态归档视图、`closed_at` 可见性、筛选切换后 detail 同步、桌面/移动截图和 forbidden sentinel。

本任务默认不改后端 API，不新增数据库字段，不新增状态，不改变 `closed_at` 语义，不自动关闭案件。M3-19 只把现有列表查询能力做成可见、可验证、可复盘的前端体验。

## 2. 必读上下文

开始前必须完整阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/runs/2026-06-21-m3-18-incident-closure-post-incident-review-checklist-ux.md`
- `docs/runs/2026-06-21-m3-17-incident-alert-evidence-pack-checklist-ux.md`
- `docs/runs/2026-06-19-m3-14-incident-report-preview-ux.md`
- `docs/runs/2026-06-18-m3-04-incident-case-workbench.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md` 中 M3-04 / M3-14 / M3-17 / M3-18 段落
- `web-next/components/dashboard/IncidentSection.tsx`
- `web-next/components/dashboard/IncidentList.tsx`
- `web-next/components/dashboard/IncidentDetailPanel.tsx`
- `web-next/hooks/useIncidents.ts`
- `web-next/types/incident.ts`
- `server/routers/incidents_router.py` 中 `list_incidents_endpoint`
- `server/services/incident_service.py` 中 `list_incidents` 与 `closed_at` 状态逻辑
- `server/tests/test_incidents.py` 中 `GET /incidents` 与 `closed_at` 测试
- `server/tests/e2e_helpers.py`
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
- 可新增 `web-next/components/dashboard/IncidentStatusFilterBar.tsx`
- 可新增 `web-next/types/incidentFilters.ts`，但只放前端筛选辅助类型，不改变后端字段语义
- 必要时轻量更新 `web-next/hooks/useIncidents.ts`，仅限暴露当前筛选状态或避免并发 race，不得改变 API contract
- 新增 `server/tests/test_incident_status_filter_archive_e2e.py`
- 必要时轻量更新 `server/tests/test_incident_closure_review_checklist_e2e.py`
- `docs/runs/2026-06-21-m3-19-closed-incident-archive-status-filter-ux.md`
- `docs/runs/artifacts/m3-19-closed-incident-archive-status-filter/**`
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
- `server/models_db.py`
- npm 依赖
- rate limit 常量
- `.env`、`.coverage`、数据库、真实密钥
- 新增案件状态
- 改变 `closed_at` 自动设置 / 清空语义
- 自动把案件状态改为 `resolved` 或 `false_positive`
- 调用 LLM 生成筛选或归档摘要
- 把完整 raw payload、完整 analyst note、完整 timeline note、完整报告 markdown、system prompt、stack trace、API key 写入 DOM、复制文本、截图说明、运行日志或测试输出
- 用 `localStorage` / `sessionStorage` 保存筛选状态
- 使用 `dangerouslySetInnerHTML` 或 `innerHTML`

当前工作区长期存在跨任务截图和 dev server log 脏文件。提交时必须精确 stage 本任务文件，禁止 `git add .`。

## 4. 运行预算与停止条件

预算：

- 最长运行 4 小时。
- 同一失败最多修复 3 轮。
- diff 超过约 900 行时停止总结，除非主要是测试/文档。

必须停止并写清楚阻塞：

- Playwright 浏览器无法启动，且无法用 `PLAYWRIGHT_CHROMIUM_EXECUTABLE` 指到系统 Chrome 解决。
- dev server 无法稳定返回 `/api/backend/health`。
- 发现后端 `GET /incidents?status=` 实际不可用，且必须修改后端 API 才能完成筛选。
- 需要修改认证、Guardrails、SSRF、DB schema、后端 incident/report API、依赖或 rate limit 常量。
- 需要新增 DB 字段、后端复合状态 API 或 LLM 归档摘要才能完成 UX。
- E2E 只能 skipped，无法获得真实浏览器 pass。
- DOM、复制文本、下载 markdown 或截图说明中出现 forbidden sentinel。
- 当前工作区存在 unrelated dirty files 时，不允许 broad stage；只能精确 stage 本任务文件。

## 5. 产品验收标准

完成后用户应该能在 Dashboard 的案件列表里完成：

1. 在案件列表顶部看到状态筛选控件。
2. 筛选项至少包含：
   - `全部`
   - `活跃`，聚合 `open / investigating / contained`
   - `已开启`
   - `调查中`
   - `已遏制`
   - `已解决`
   - `误报`
   - `已关闭归档`，聚合 `resolved / false_positive`
3. 每个筛选项使用按钮或 segmented control，不使用下拉菜单隐藏主路径。
4. 点击单状态筛选时调用现有 `incidents.loadIncidents({ limit: 50, status })`。
5. 点击 `活跃` 或 `已关闭归档` 时可以并行或顺序调用现有单状态接口后在前端聚合；不得新增后端复合状态参数。
6. 筛选切换期间显示加载态，失败时显示明确错误态，并保留刷新按钮可重试。
7. 当前筛选条件下无案件时显示针对性空态：
   - `已关闭归档` 空态：提示“暂无已关闭案件”。
   - `活跃` 空态：提示“暂无活跃案件”。
   - 单状态空态：提示当前状态暂无案件。
8. 关闭态案件列表项必须展示：
   - `closed_at` 格式化时间，`data-testid="incident-closed-at"`。
   - 当前状态 badge，仍用现有状态文案。
   - `alert_count`。
9. 活跃案件列表项仍展示 updated time，不因新增筛选丢失原有信息。
10. 筛选后如果当前选中的案件不在新列表里，详情区应进入“未选择案件”或自动选择新列表第一条；不得显示已经不在当前筛选结果中的 stale detail。
11. 筛选状态不写入 `localStorage` / `sessionStorage`，刷新页面后回到默认 `全部`。
12. 桌面和移动端不产生整页横向溢出，长 incident id / title 能换行。
13. DOM、复制文本、下载 markdown、截图说明均不包含 forbidden sentinel。

## 6. 推荐设计

### 6.1 UI 形态

建议新增组件：

```text
web-next/components/dashboard/IncidentStatusFilterBar.tsx
```

放在 `IncidentSection` 左栏标题与刷新按钮下方、创建入口上方：

```text
CASES / 案件列表
刷新
IncidentStatusFilterBar
创建入口
IncidentList
```

建议测试 ID：

```text
incident-status-filter-bar
incident-filter-all
incident-filter-active
incident-filter-open
incident-filter-investigating
incident-filter-contained
incident-filter-resolved
incident-filter-false-positive
incident-filter-closed
incident-filter-summary
incident-list-empty-filtered
incident-closed-at
incident-list-updated-at
```

视觉要求：

- 保持 Dashboard 工具型、紧凑、低噪声风格。
- 筛选按钮可换行，不撑破移动端。
- 当前筛选按钮有明确 active 样式和 `aria-pressed`。
- 不使用 modal，不新增 route，不做大型营销式卡片。
- 可以使用 lucide `Archive`, `Filter`, `RefreshCw`, `CheckCircle2`，但按钮必须有清晰文本或 `aria-label`。

### 6.2 状态模型

建议前端类型：

```ts
type IncidentListFilter =
  | "all"
  | "active"
  | "open"
  | "investigating"
  | "contained"
  | "resolved"
  | "false_positive"
  | "closed";
```

映射：

```text
all:
  loadIncidents({ limit: 50 })

open / investigating / contained / resolved / false_positive:
  loadIncidents({ limit: 50, status })

active:
  load open + investigating + contained, merge by incident_id,
  sort by updated_at desc then incident_id desc

closed:
  load resolved + false_positive, merge by incident_id,
  sort by closed_at desc fallback updated_at desc
```

注意：

- 聚合请求可以顺序执行，避免并发 race；也可以 `Promise.all`，但必须处理 abort / stale result。
- 不要把筛选状态写进 storage。
- 切换筛选后，如果 `selectedIncident` 不在新列表中，清空 selected/detail 或选择列表第一条。推荐清空 selected/detail 并显示“未选择案件”，行为最可控。
- 如果 `useIncidents` 目前没有清空 detail 的方法，可以在最小范围内增加 `clearSelectedIncident()`，但不得改变后端契约。

### 6.3 列表项展示

`IncidentList` 建议新增 props：

```ts
type IncidentListMode = "default" | "archive";

interface IncidentListProps {
  items: IncidentSummary[];
  loadState: "idle" | "loading" | "ready" | "empty" | "error";
  selectedId: string | null;
  onSelect: (incident: IncidentSummary) => void;
  filterLabel?: string;
  mode?: IncidentListMode;
}
```

关闭态展示：

```text
关闭时间: <formatted closed_at or "未记录">
更新: <formatted updated_at>
<incident_id> · <alert_count> 关联告警
```

活跃态展示保留：

```text
更新 <formatted updated_at>
```

## 7. TDD / E2E 计划

### Task 1：创建运行日志

创建：

```text
docs/runs/2026-06-21-m3-19-closed-incident-archive-status-filter-ux.md
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
server/tests/test_incident_status_filter_archive_e2e.py
```

必须复用：

- `server.tests.e2e_helpers.assert_dev_server_reachable`
- `server.tests.e2e_helpers.register_or_login_for_e2e`
- `server.tests.e2e_helpers.skip_without_playwright`

测试流程：

1. 启动 Playwright chromium，支持 `PLAYWRIGHT_CHROMIUM_EXECUTABLE`。
2. `accept_downloads=True`，必要时授予 clipboard 权限。
3. 登录 Dashboard。
4. 通过现有 UI 创建至少 3 个案件样本：
   - 1 个保持 `open` 或 `investigating`。
   - 1 个保存为 `contained`。
   - 1 个保存为 `resolved`。
   - 可选第 4 个保存为 `false_positive`，如果时间充足。
5. 等待 `incident-list`。
6. 断言 `incident-status-filter-bar` 可见。
7. 断言 8 个筛选按钮可见：
   - `incident-filter-all`
   - `incident-filter-active`
   - `incident-filter-open`
   - `incident-filter-investigating`
   - `incident-filter-contained`
   - `incident-filter-resolved`
   - `incident-filter-false-positive`
   - `incident-filter-closed`
8. 点击 `incident-filter-closed`，等待列表只显示 `resolved / false_positive` 案件。
9. 断言关闭态列表项含 `incident-closed-at`，且文本不是空。
10. 点击关闭态案件，断言 `incident-detail-panel` 能加载，且 M3-18 `incident-closure-review-checklist` 仍可见。
11. 点击 `incident-filter-active`，等待列表只显示 `open / investigating / contained` 案件，并断言 `incident-closed-at` 不出现在活跃案件项中。
12. 点击 `incident-filter-contained`，断言只显示 contained 样本。
13. 点击 `incident-filter-resolved`，断言只显示 resolved 样本。
14. 如果 `false_positive` 样本存在，点击 `incident-filter-false-positive`，断言只显示 false_positive 样本；否则断言出现 `incident-list-empty-filtered`。
15. 扫描整页 DOM forbidden sentinel。
16. 保存桌面截图：

```text
docs/runs/artifacts/m3-19-closed-incident-archive-status-filter/status-filter-desktop.png
```

17. 设置移动 viewport 390x844，确认筛选栏可换行、列表可读、无横向溢出，保存：

```text
docs/runs/artifacts/m3-19-closed-incident-archive-status-filter/status-filter-mobile.png
```

RED 预期：

- 当前 UI 没有 `incident-status-filter-bar`，测试应 fail 在该 selector。
- 不允许因为 selector 不存在而 skip。

### Task 3：GREEN - 实现最小 UX

实现：

- `IncidentStatusFilterBar.tsx`
- `IncidentSection.tsx` 接入筛选状态和加载逻辑
- `IncidentList.tsx` 支持筛选空态和关闭态时间展示

要求：

- 默认筛选为 `all`。
- 单状态筛选复用 `incidents.loadIncidents({ limit: 50, status })`。
- `active / closed` 复合筛选只在前端聚合现有单状态接口结果。
- 切换筛选时不要刷新页面，不新增 route。
- 切换筛选后避免 stale detail：如果当前 selected 不在新结果中，清空 selected/detail 或选择第一条；实现必须稳定并被 E2E 覆盖。
- 不使用 storage 保存筛选。
- 不影响从告警创建案件、M3-17 Evidence Pack、M3-18 Closure Review、报告复制/下载/预览。

### Task 4：IMPROVE - de-sloppify

检查并修复：

- 是否留下 `console.log`。
- 是否用了 `localStorage` / `sessionStorage`。
- 是否用了 `dangerouslySetInnerHTML` / `innerHTML`。
- 是否把 raw payload、完整 note、完整 markdown 写进列表或筛选摘要。
- 是否把 system prompt、stack trace、API key、regex、cookie、token 写进 DOM 或复制文本。
- 按钮是否有清晰文本或 `aria-label`。
- 移动端是否横向溢出。
- 筛选切换是否可能把过期请求结果覆盖新筛选结果。
- 是否为了实现筛选而修改后端。若有，回退该方向，改用现有单状态接口。

扫描命令：

```powershell
rg -n "console\.log|localStorage|sessionStorage|dangerouslySetInnerHTML|innerHTML|sk-|AKIA|ghp_|PRIVATE KEY|Traceback|system\s*:|developer\s*:" web-next\components\dashboard server\tests\test_incident_status_filter_archive_e2e.py
```

命中测试 sentinel 常量允许；生产组件命中敏感字面量必须修。

### Task 5：验证矩阵

如果本机 Chromium `spawn EPERM`，优先使用系统 Chrome：

```powershell
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
```

如需隔离 dev server，可沿用 M3-18 的 fresh backend/frontend 方案，但必须写进运行日志。

必须运行：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_incident_status_filter_archive_e2e.py -q --tb=short --run-e2e -s -rs
```

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_incident_closure_review_checklist_e2e.py server\tests\test_incident_evidence_pack_checklist_e2e.py -q --tb=short --run-e2e -s -rs
```

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_incident_report_e2e.py server\tests\test_incident_report_preview_e2e.py server\tests\test_dashboard_responsive_e2e.py -q --tb=short --run-e2e -s -rs
```

后端 incident 契约，确认未破坏现有 status 参数：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_incidents.py -q --tb=short
```

关键 E2E 串跑，实际总数以 pytest 输出为准：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_auth_session_e2e.py server\tests\test_demo_flow_e2e.py server\tests\test_incident_report_e2e.py server\tests\test_dashboard_route_sections_e2e.py server\tests\test_dashboard_responsive_e2e.py server\tests\test_demo_flow_stability_e2e.py server\tests\test_dashboard_mobile_visual_e2e.py server\tests\test_incident_report_preview_e2e.py server\tests\test_security_timeline_drilldown_e2e.py server\tests\test_dashboard_operational_runbook_e2e.py server\tests\test_incident_evidence_pack_checklist_e2e.py server\tests\test_incident_closure_review_checklist_e2e.py server\tests\test_incident_status_filter_archive_e2e.py -q --tb=short --run-e2e -s -rs
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

- `PRODUCT.md`：在 M3 实施状态中新增 M3-19 已交付说明，包含真实验证结果、截图路径和安全边界。
- `docs/plans/M2_PRODUCT_ROADMAP.md`：新增 M3-19 章节，记录目标、已交付、验证、边界、改动文件、未解决问题。
- `docs/agent/UNATTENDED_LONG_TASKS.md`：把 M3-19 加入可复用超长任务列表；推荐下一条默认工单改为 **M3-20 Incident Workbench Bulk Selection / Export Queue UX**。
- `docs/runs/2026-06-21-m3-19-closed-incident-archive-status-filter-ux.md`：补齐最终验证证据和最终状态。

M3-20 候选方向：

```text
Incident Workbench Bulk Selection / Export Queue UX：在不新增后端导出格式和不改权限模型的前提下，为案件列表增加多选、批量复制安全摘要、导出队列提示和 E2E 证据。
```

## 8. 安全与隐私检查

必须确认：

- 状态筛选不调用 LLM。
- 状态筛选不保存到 `localStorage` / `sessionStorage`。
- 列表不展示 raw payload。
- 列表不展示完整 timeline note / analyst note。
- 列表不保存完整报告 markdown。
- 未使用 `dangerouslySetInnerHTML` / `innerHTML`。
- DOM 不含 secret / token / stack trace / system prompt / developer prompt / Guardrails regex。
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

1. `test(e2e): 覆盖案件归档筛选`
   - `server/tests/test_incident_status_filter_archive_e2e.py`
2. `feat(incidents): 增加案件状态筛选归档视图`
   - `web-next/components/dashboard/IncidentStatusFilterBar.tsx`
   - `web-next/components/dashboard/IncidentSection.tsx`
   - `web-next/components/dashboard/IncidentList.tsx`
   - 如有必要，精确加入轻量前端类型/helper 文件
3. `docs(incidents): 记录案件归档筛选 UX 收口`
   - `docs/runs/2026-06-21-m3-19-closed-incident-archive-status-filter-ux.md`
   - `docs/runs/artifacts/m3-19-closed-incident-archive-status-filter/*.png`
   - `docs/agent/M3_19_CLOSED_INCIDENT_ARCHIVE_STATUS_FILTER_UX_TASK.md`
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
- 下一条建议工单：`M3-20 Incident Workbench Bulk Selection / Export Queue UX`。

如果阻塞：

- 写清楚阻塞发生在哪个阶段。
- 写清楚已经完成的文件和验证。
- 写清楚下一步最小可执行动作。
- 不要 push 半成品。
