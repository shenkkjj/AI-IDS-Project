# M3-18 Incident Closure / Post-Incident Review Checklist UX 收口任务

> **给无人值守 Agent 的任务文档。** 本任务是 L5 超长任务：先读上下文，创建运行日志，按 TDD/E2E 红绿推进，阶段性记录证据，最后通过完整验证矩阵后精确 commit / push。不要把 skipped 当 passed。
>
> **执行要求**：实现时必须使用 `superpowers:executing-plans` 或 `superpowers:subagent-driven-development`，并使用 `superpowers:test-driven-development` 与 `superpowers:verification-before-completion`。如果当前环境没有子智能体工具，降级为 inline 执行，但仍要按阶段写运行日志。

## 0. 任务一句话

在案件详情里新增一个只读 **Closure Review Checklist**，把当前案件是否适合进入 `resolved / false_positive` 的复盘条件集中展示出来：案件状态是否接近关闭、证据包是否检查、报告元信息是否可用、关联告警是否存在、告警研判是否覆盖、时间线是否完整、是否有复盘备注、还缺什么，并允许复制一份不含敏感内容的关闭前复盘摘要。

## 1. 背景

已交付能力：

- M3-04 已交付案件工作台，后端支持 5 个案件状态：`open / investigating / contained / resolved / false_positive`；进入 `resolved / false_positive` 时自动设置 `closed_at`，从关闭态改回打开态时清空 `closed_at`。
- M3-07 已交付 `GET /incidents/{incident_id}/report?format=json|markdown`，报告服务负责脱敏、截断和 meta 计数。
- M3-14 已交付 `IncidentReportPreview`，可预览报告 meta、脱敏 markdown 片段、复制和下载报告。
- M3-15 已交付 SOC 时间线筛选、展开和复制摘要。
- M3-17 已交付 `IncidentEvidencePackChecklist`，在案件详情中展示只读证据包清单，并能复制安全证据包摘要。

当前体验缺口：

- 案件现在可以被手动改成 `resolved / false_positive`，但 owner 没有一个关闭前检查面板来判断证据、研判、时间线和复盘备注是否齐备。
- Evidence pack checklist 面向“证据包完整度”，还没有把 `contained / resolved / false_positive`、`closed_at`、复盘备注和关闭建议汇总在一起。
- 复盘或演示时，owner 需要一份可复制的关闭前摘要，说明当前案件能否关闭、还缺哪些动作、报告是否检查过、研判覆盖率是多少。
- 还没有真实浏览器 E2E 覆盖 closure review checklist、报告 meta 刷新、复制复盘摘要、桌面/移动截图和 forbidden sentinel。

本任务默认不改后端 API，不新增数据库字段，不新增状态，不改变 `closed_at` 语义，不自动关闭案件。Closure review checklist 只聚合现有前端数据、已有 incident detail、已有 report JSON meta 和已有状态保存控件。

## 2. 必读上下文

开始前必须完整阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/runs/2026-06-21-m3-17-incident-alert-evidence-pack-checklist-ux.md`
- `docs/runs/2026-06-21-m3-16-dashboard-operational-runbook-health-checklist-ux.md`
- `docs/runs/2026-06-20-m3-15-soc-timeline-drilldown-filter-ux.md`
- `docs/runs/2026-06-19-m3-14-incident-report-preview-ux.md`
- `docs/runs/2026-06-18-m3-07-incident-evidence-report-export.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md` 中 M3-04 / M3-07 / M3-14 / M3-15 / M3-17 段落
- `web-next/components/dashboard/IncidentDetailPanel.tsx`
- `web-next/components/dashboard/IncidentEvidencePackChecklist.tsx`
- `web-next/components/dashboard/IncidentReportPreview.tsx`
- `web-next/components/dashboard/IncidentLinkedAlerts.tsx`
- `web-next/components/dashboard/IncidentTimeline.tsx`
- `web-next/hooks/useIncidents.ts`
- `web-next/types/incident.ts`
- `server/tests/e2e_helpers.py`
- `server/tests/test_incident_evidence_pack_checklist_e2e.py`
- `server/tests/test_incident_report_e2e.py`
- `server/tests/test_incident_report_preview_e2e.py`
- `server/tests/test_security_timeline_drilldown_e2e.py`
- `server/tests/test_dashboard_responsive_e2e.py`
- `server/tests/test_incidents.py` 中 `closed_at` 行为相关测试

必须使用或参考的 skill：

- `superpowers:executing-plans` 或 `superpowers:subagent-driven-development`
- `superpowers:test-driven-development`
- `superpowers:verification-before-completion`
- `frontend-patterns`
- `frontend-design`
- `e2e-testing`

## 3. 硬边界

允许修改：

- `web-next/components/dashboard/IncidentDetailPanel.tsx`
- 可新增 `web-next/components/dashboard/IncidentClosureReviewChecklist.tsx`
- 可新增 `web-next/types/closureReview.ts`，但只放前端展示辅助类型，不改变后端字段语义
- 必要时轻量更新 `web-next/components/dashboard/IncidentEvidencePackChecklist.tsx`，仅限抽取可复用小 helper 或避免重复样式，不得改变 M3-17 已验收行为
- 新增 `server/tests/test_incident_closure_review_checklist_e2e.py`
- 必要时轻量更新 `server/tests/test_incident_evidence_pack_checklist_e2e.py`
- 必要时轻量更新 `server/tests/test_incident_report_e2e.py`
- 必要时轻量更新 `server/tests/test_incident_report_preview_e2e.py`
- `docs/runs/2026-06-21-m3-18-incident-closure-post-incident-review-checklist-ux.md`
- `docs/runs/artifacts/m3-18-incident-closure-post-incident-review-checklist/**`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

禁止修改：

- 认证 / 授权
- `server/security/**` / Guardrails
- SSRF
- DB schema / Alembic migration
- 后端 incident / report API contract
- `server/services/incident_service.py`
- `server/routers/incidents_router.py`
- `server/services/incident_report_service.py`
- npm 依赖
- rate limit 常量
- `.env`、`.coverage`、数据库、真实密钥
- 新增案件状态
- 改变 `closed_at` 自动设置 / 清空语义
- 自动把案件状态改为 `resolved` 或 `false_positive`
- 新增 PDF / DOCX / ZIP / 外部导出格式
- 调用 LLM 生成复盘建议
- 把完整 raw payload、完整 analyst note、完整 timeline note、完整报告 markdown、system prompt、stack trace、API key 写入 DOM、复制文本、截图说明、运行日志或测试输出
- 用 `localStorage` / `sessionStorage` 保存 checklist、报告 markdown 或复盘摘要
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
- 需要修改认证、Guardrails、SSRF、DB schema、后端 incident/report API、依赖或 rate limit 常量。
- 需要新增后端导出格式、ZIP/PDF/DOCX 或 LLM 复盘生成才能完成 UX。
- E2E 只能 skipped，无法获得真实浏览器 pass。
- DOM、复制摘要、下载 markdown 或截图说明中出现 forbidden sentinel。
- 当前工作区存在 unrelated dirty files 时，不允许 broad stage；只能精确 stage 本任务文件。

## 5. 产品验收标准

完成后用户应该能在 Dashboard 的案件详情里完成：

1. 打开某个案件详情后看到 `Closure Review Checklist` 面板。
2. 面板位置建议放在 `Evidence Pack Checklist` 之后、`事件时间线` 之前，形成“证据包检查 → 关闭前复盘 → 时间线”的阅读顺序。
3. 面板至少包含 8 行检查项：
   - 关闭状态准备度：基于当前 `incident.status`，`contained / resolved / false_positive` 为 `ready`，`investigating` 为 `review`，`open` 为 `missing`。
   - 证据包状态：基于当前 linked alerts、events、triage coverage 和 report meta 是否已检查推导。
   - 报告元信息：基于现有 `onLoadReport(incidentId)` 拉取 `IncidentReportMeta` 后显示 `ready`。
   - 关联告警：`detail.linked_alerts.length > 0` 为 `ready`，否则 `missing`。
   - 研判覆盖：统计 linked alerts 中 `triage.status` 存在且不为 `new` 的数量。
   - 时间线完整度：`detail.events.length > 0` 为 `ready`，否则 `missing`。
   - 复盘备注：`detail.events` 中存在 `note_added` 事件，或当前案件有可用 summary 时为 `review / ready`；没有时提示“建议保存一条复盘备注”。
   - 缺失项：列出当前还缺的动作，例如“先将状态推进到 contained”、“检查报告元信息”、“补充复盘备注”、“完成告警研判”。
4. 面板提供 `检查报告元信息` 按钮：
   - `data-testid="closure-refresh-report"`
   - 点击后只调用已有 `onLoadReport(incidentId)`。
   - 只保存 `filename` 和 `meta` 到短期 React state，不保存完整 markdown。
5. 面板提供 `复制复盘摘要` 按钮：
   - `data-testid="closure-copy-summary"`
   - 状态 `data-testid="closure-copy-status"`
   - 复制内容只包含安全字段：incident id、当前 status、severity、closed_at 是否存在、linked alert count、timeline event count、triage coverage、report checked、redaction/truncation count、final note seen、recommendation、missing items。
6. 面板只给关闭建议，不改变案件状态；用户仍然使用已有 `incident-status-*` radio 和 `incident-save` 保存状态。
7. 如果当前 status 已是 `resolved / false_positive`，面板显示“已进入关闭态”，并展示 `closed_at` 是否存在；如果 `closed_at` 缺失，只提示异常，不自行修复。
8. 桌面和移动端不产生整页横向溢出，长 id / 命令 / missing item 文案能换行。
9. DOM、复制文本、下载 markdown、截图说明均不包含 forbidden sentinel。

## 6. 推荐设计

### 6.1 UI 形态

新增组件：

```text
web-next/components/dashboard/IncidentClosureReviewChecklist.tsx
```

在 `IncidentDetailPanel` 中接入：

```text
关联告警
Evidence Pack Checklist
Closure Review Checklist
事件时间线
```

建议测试 ID：

```text
incident-closure-review-checklist
closure-check-status-ready
closure-check-evidence-pack
closure-check-report-meta
closure-check-linked-alerts
closure-check-triage-coverage
closure-check-timeline-events
closure-check-final-note
closure-check-missing
closure-refresh-report
closure-copy-summary
closure-copy-status
closure-report-filename
closure-report-meta
closure-recommendation
```

视觉要求：

- 保持当前案件详情的工具型、紧凑、低噪声风格。
- 不使用 modal，不新增 route，不做大卡片堆叠。
- 每行检查项用短标题、状态标签、计数、短说明表达。
- 可以使用 lucide `CheckCircle2`、`Clipboard`、`RefreshCw`、`ShieldCheck`、`FileCheck2`，但按钮必须有清晰文本或 `aria-label`。
- 移动端优先可读性，长 id 使用 `break-all` 或现有等效 class。

### 6.2 状态推导

前端只从 `IncidentDetailResponse` 和已有 report JSON meta 推导：

```text
status readiness:
  resolved / false_positive -> ready, label "已进入关闭态"
  contained -> ready, label "可进入关闭前复核"
  investigating -> review, label "仍在调查中"
  open -> missing, label "尚未进入处置流程"

report meta:
  未检查 -> review
  加载成功 -> ready
  加载失败 -> missing 或 review，显示安全错误摘要

linked alerts:
  linked_alerts.length > 0 -> ready
  linked_alerts.length === 0 -> missing

triage coverage:
  reviewed = linked_alerts where triage.status exists and triage.status !== "new"
  reviewed === linked_alerts.length and linked_alerts.length > 0 -> ready
  reviewed > 0 -> review
  reviewed === 0 -> missing 或 review

timeline:
  events.length > 0 -> ready
  events.length === 0 -> missing

final note:
  events contains event_type === "note_added" -> ready
  incident.summary exists -> review
  otherwise -> missing

closed_at:
  status in resolved/false_positive and closed_at exists -> ready
  status in resolved/false_positive and closed_at missing -> review
  status not closed -> manual/info

recommendation:
  no missing + status contained/resolved/false_positive -> ready
  no missing + status investigating -> review
  any missing -> not_ready
```

不要把 `raw_alert.payload`、`triage.analyst_note`、`IncidentEvent.note` 全量写进 checklist 或复制文本。可以展示计数和状态，不展示原文。

### 6.3 建议 props

```ts
type IncidentClosureReviewChecklistProps = {
  incident: IncidentSummary;
  linkedAlerts: IncidentLinkedAlert[];
  events: IncidentEvent[];
  onLoadReport: (incidentId: string) => Promise<{
    ok: boolean;
    filename?: string;
    meta?: IncidentReportMeta;
    error?: string;
  }>;
};
```

`onLoadReport` 可复用现有 `IncidentDetailPanel` 的 `onLoadReport`，组件内部忽略 markdown，仅保存 `filename` 和 `meta`。

### 6.4 复制摘要格式

建议格式：

```text
[AI-CyberSentinel Closure Review]
incident_id=<id>
status=<status>
severity=<severity>
closed_at=<present/absent/not_applicable>
linked_alerts=<count>
timeline_events=<count>
triage_reviewed=<reviewed>/<total>
report_checked=<yes/no>
report_redactions=<count or unknown>
report_truncated=<yes/no/unknown>
final_note_seen=<yes/no>
recommendation=<ready/review/not_ready>
missing=<comma separated safe labels>
```

剪贴板不可用时显示 `复制失败`，不能抛出未处理异常。

## 7. TDD / E2E 计划

### Task 1：创建运行日志

创建：

```text
docs/runs/2026-06-21-m3-18-incident-closure-post-incident-review-checklist-ux.md
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
server/tests/test_incident_closure_review_checklist_e2e.py
```

必须复用：

- `server.tests.e2e_helpers.assert_dev_server_reachable`
- `server.tests.e2e_helpers.register_or_login_for_e2e`
- `server.tests.e2e_helpers.skip_without_playwright`

测试流程：

1. 启动 Playwright chromium，支持 `PLAYWRIGHT_CHROMIUM_EXECUTABLE`。
2. `accept_downloads=True`，必要时授予 clipboard 权限。
3. 登录 Dashboard。
4. 触发 Demo 攻击。
5. 点击最新告警。
6. 从告警创建案件，等待 `incident-detail-panel`。
7. 断言 `incident-evidence-pack-checklist` 仍可见，避免破坏 M3-17。
8. 断言 `incident-closure-review-checklist` 可见。
9. 断言 8 行检查项可见：
   - `closure-check-status-ready`
   - `closure-check-evidence-pack`
   - `closure-check-report-meta`
   - `closure-check-linked-alerts`
   - `closure-check-triage-coverage`
   - `closure-check-timeline-events`
   - `closure-check-final-note`
   - `closure-check-missing`
10. 点击 `closure-refresh-report`，等待 `closure-report-meta`。
11. 断言 report meta 包含告警、事件、脱敏、截断计数。
12. 点击 `closure-copy-summary`，断言状态为 `已复制` 或 `复制失败`。
13. 如果 clipboard 可读，断言复制文本包含 `AI-CyberSentinel Closure Review`、`incident_id`、`status`、`triage_reviewed`、`recommendation`、`missing`，且不含 forbidden sentinel。
14. 点击已有 `incident-status-contained`，输入短复盘备注到 `incident-note-input`，点击 `incident-save`，等待保存完成；该动作只证明已有状态控件仍正常，不由新 checklist 自动关闭案件。
15. 重新断言 checklist 仍显示，且 `closure-recommendation` 更新为可复核或缺失项减少。
16. 点击 `incident-download-report`，读取真实 markdown，复用报告结构和 forbidden sentinel 断言，确认 closure checklist 没有破坏报告下载。
17. 扫描整页 DOM forbidden sentinel。
18. 保存桌面截图：

```text
docs/runs/artifacts/m3-18-incident-closure-post-incident-review-checklist/closure-review-desktop.png
```

19. 设置移动 viewport 390x844，确认 checklist 仍可见且无横向溢出，保存：

```text
docs/runs/artifacts/m3-18-incident-closure-post-incident-review-checklist/closure-review-mobile.png
```

RED 预期：

- 当前 UI 没有 `incident-closure-review-checklist`，测试应 fail 在该 selector。
- 不允许因为 selector 不存在而 skip。

### Task 3：GREEN - 实现最小 UX

实现：

- `IncidentClosureReviewChecklist.tsx`
- `IncidentDetailPanel.tsx` 接入 checklist，传入 `detail.incident`、`detail.linked_alerts`、`detail.events` 和 `onLoadReport`。

要求：

- 只保存 `reportMeta`、`reportFilename`、`reportStatus`、`copyStatus` 等小状态。
- 调用 `onLoadReport()` 后不要保存完整 markdown。
- 不影响已有 `预览报告 / 复制报告 / 下载报告 / 用 AI 分析案件 / Evidence Pack Checklist`。
- 不新增自动保存，不自动改 status。
- 切换 incident 时 checklist state 要随组件重新计算或清空。

### Task 4：IMPROVE - de-sloppify

检查并修复：

- 是否留下 `console.log`。
- 是否用了 `localStorage` / `sessionStorage`。
- 是否用了 `dangerouslySetInnerHTML` / `innerHTML`。
- 是否把 raw payload、完整 note、完整 markdown 保存到 checklist state。
- 是否把 system prompt、stack trace、API key、regex、cookie、token 写进 DOM 或复制文本。
- 按钮是否有清晰文本或 `aria-label`。
- 移动端是否横向溢出。
- 是否把 checklist 做成可自动修改业务状态的控件。如有，必须改回只读。

扫描命令：

```powershell
rg -n "console\.log|localStorage|sessionStorage|dangerouslySetInnerHTML|innerHTML|sk-|AKIA|ghp_|PRIVATE KEY|Traceback|system:|developer:" web-next\components\dashboard server\tests\test_incident_closure_review_checklist_e2e.py
```

命中测试 sentinel 常量允许；生产组件命中敏感字面量必须修。

### Task 5：验证矩阵

如果本机 Chromium `spawn EPERM`，优先使用系统 Chrome：

```powershell
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
```

如需隔离 dev server，可沿用 M3-17 的 fresh backend/frontend 方案，但必须写进运行日志。

必须运行：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_incident_closure_review_checklist_e2e.py -q --tb=short --run-e2e -s -rs
```

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_incident_evidence_pack_checklist_e2e.py -q --tb=short --run-e2e -s -rs
```

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_incident_report_e2e.py server\tests\test_incident_report_preview_e2e.py server\tests\test_security_timeline_drilldown_e2e.py server\tests\test_dashboard_responsive_e2e.py -q --tb=short --run-e2e -s -rs
```

关键 E2E 串跑，实际总数以 pytest 输出为准：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_auth_session_e2e.py server\tests\test_demo_flow_e2e.py server\tests\test_incident_report_e2e.py server\tests\test_dashboard_route_sections_e2e.py server\tests\test_dashboard_responsive_e2e.py server\tests\test_demo_flow_stability_e2e.py server\tests\test_dashboard_mobile_visual_e2e.py server\tests\test_incident_report_preview_e2e.py server\tests\test_security_timeline_drilldown_e2e.py server\tests\test_dashboard_operational_runbook_e2e.py server\tests\test_incident_evidence_pack_checklist_e2e.py server\tests\test_incident_closure_review_checklist_e2e.py -q --tb=short --run-e2e -s -rs
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

- `PRODUCT.md`：在 M3 实施状态中新增 M3-18 已交付说明，包含真实验证结果、截图路径和安全边界。
- `docs/plans/M2_PRODUCT_ROADMAP.md`：新增 M3-18 章节，记录目标、已交付、验证、边界、改动文件、未解决问题。
- `docs/agent/UNATTENDED_LONG_TASKS.md`：把 M3-18 加入可复用超长任务列表；推荐下一条默认工单改为 **M3-19 Closed Incident Archive / Status Filter UX**。
- `docs/runs/2026-06-21-m3-18-incident-closure-post-incident-review-checklist-ux.md`：补齐最终验证证据和最终状态。

M3-19 候选方向：

```text
Closed Incident Archive / Status Filter UX：在案件列表中补状态筛选、关闭态归档视图和 closed_at 可见性，基于现有 incidents 查询能力和状态字段，不新增 DB schema，不改后端权限模型。
```

## 8. 安全与隐私检查

必须确认：

- Closure checklist 不调用 LLM。
- Closure checklist 不保存完整报告 markdown。
- Closure checklist 不展示或复制 raw payload。
- Closure checklist 不展示或复制完整 timeline note / analyst note。
- Closure checklist 不写 `localStorage` / `sessionStorage`。
- Closure checklist 不使用 `dangerouslySetInnerHTML` / `innerHTML`。
- 复制摘要不含 secret / token / stack trace / system prompt / developer prompt / Guardrails regex。
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

1. `test(e2e): 覆盖案件关闭前复盘清单`
   - `server/tests/test_incident_closure_review_checklist_e2e.py`
2. `feat(incidents): 增加案件关闭前检查面板`
   - `web-next/components/dashboard/IncidentClosureReviewChecklist.tsx`
   - `web-next/components/dashboard/IncidentDetailPanel.tsx`
   - 如有必要，精确加入轻量 helper 文件
3. `docs(closure): 记录案件关闭检查 UX 收口`
   - `docs/runs/2026-06-21-m3-18-incident-closure-post-incident-review-checklist-ux.md`
   - `docs/runs/artifacts/m3-18-incident-closure-post-incident-review-checklist/*.png`
   - `docs/agent/M3_18_INCIDENT_CLOSURE_POST_INCIDENT_REVIEW_CHECKLIST_UX_TASK.md`
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
- 下一条建议工单：`M3-19 Closed Incident Archive / Status Filter UX`。

如果阻塞：

- 写清楚阻塞发生在哪个阶段。
- 写清楚已经完成的文件和验证。
- 写清楚下一步最小可执行动作。
- 不要 push 半成品。
