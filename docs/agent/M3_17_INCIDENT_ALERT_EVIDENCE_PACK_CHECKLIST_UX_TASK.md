# M3-17 Incident / Alert Evidence Pack Checklist UX 收口任务

> **给无人值守 Agent 的任务文档。** 本任务是 L5 超长任务：先读上下文，创建运行日志，按 TDD/E2E 红绿推进，阶段性记录证据，最后通过完整验证矩阵后精确 commit / push。不要把 skipped 当 passed。
>
> **执行要求**：实现时必须使用 `superpowers:executing-plans` 或 `superpowers:subagent-driven-development`，并使用 `superpowers:test-driven-development` 与 `superpowers:verification-before-completion`。如果当前环境没有子智能体工具，降级为 inline 执行，但仍要按阶段写运行日志。

## 0. 任务一句话

在案件详情里新增一个只读 **Evidence Pack Checklist**，把当前案件可用于交付和复盘的证据状态集中展示出来：报告是否可生成、关联告警是否存在、案件时间线是否完整、告警研判是否覆盖、报告是否脱敏/截断、当前还缺什么，并允许复制一份不含敏感内容的证据包摘要。

## 1. 背景

已交付能力：

- M3-04 已交付案件工作台，案件详情里有 `IncidentDetailPanel`、`IncidentLinkedAlerts` 和 `IncidentTimeline`。
- M3-07 已交付 `GET /incidents/{incident_id}/report?format=json|markdown`，前端通过 `useIncidents.loadIncidentReport()` 拉取后端脱敏后的 markdown 和 `IncidentReportMeta`。
- M3-14 已交付 `IncidentReportPreview`，可预览报告 meta、脱敏 markdown 片段、复制和下载报告。
- M3-15 已交付 SOC 时间线筛选、展开和复制摘要。
- M3-16 已交付 Dashboard operational runbook / health checklist，证明“只读检查清单 + 复制安全摘要 + E2E 截图”这类 UX 可以在不碰后端安全边界的前提下稳定落地。

当前体验缺口：

- 案件详情里有报告按钮、关联告警和事件时间线，但 owner 不能一眼判断“这个案件证据包是否够完整”。
- 当前报告 meta 只有预览时才看到，不能和关联告警、研判状态、时间线事件放到一个清单里对照。
- 演示或复盘时，需要一个只读面板告诉用户缺少哪些材料，例如没有关联告警、没有研判状态、没有时间线事件、报告元信息未检查。
- 还没有真实浏览器 E2E 覆盖 evidence pack checklist、报告 meta 检查、缺失项提示、复制证据包摘要、桌面/移动截图和 forbidden sentinel。

本任务默认不改后端 API，不新增数据库字段，不新增导出格式，不改变报告生成策略。Evidence pack checklist 只聚合现有前端数据和已有 report JSON meta。

## 2. 必读上下文

开始前必须完整阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/runs/2026-06-21-m3-16-dashboard-operational-runbook-health-checklist-ux.md`
- `docs/runs/2026-06-20-m3-15-soc-timeline-drilldown-filter-ux.md`
- `docs/runs/2026-06-19-m3-14-incident-report-preview-ux.md`
- `docs/runs/2026-06-18-m3-07-incident-evidence-report-export.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md` 中 M3-04 / M3-07 / M3-14 / M3-16 段落
- `web-next/components/dashboard/IncidentDetailPanel.tsx`
- `web-next/components/dashboard/IncidentSection.tsx`
- `web-next/components/dashboard/IncidentLinkedAlerts.tsx`
- `web-next/components/dashboard/IncidentTimeline.tsx`
- `web-next/components/dashboard/IncidentReportPreview.tsx`
- `web-next/hooks/useIncidents.ts`
- `web-next/types/incident.ts`
- `server/tests/e2e_helpers.py`
- `server/tests/test_incident_report_e2e.py`
- `server/tests/test_incident_report_preview_e2e.py`
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

- `web-next/components/dashboard/IncidentDetailPanel.tsx`
- 可新增 `web-next/components/dashboard/IncidentEvidencePackChecklist.tsx`
- 可新增 `web-next/types/evidencePack.ts`，但只放前端展示辅助类型，不改变后端字段语义
- `web-next/hooks/useIncidents.ts`（仅限小型类型导出或不改变 API contract 的 helper）
- 新增 `server/tests/test_incident_evidence_pack_checklist_e2e.py`
- 必要时轻量更新 `server/tests/test_incident_report_e2e.py`
- 必要时轻量更新 `server/tests/test_incident_report_preview_e2e.py`
- `docs/runs/2026-06-21-m3-17-incident-alert-evidence-pack-checklist-ux.md`
- `docs/runs/artifacts/m3-17-incident-alert-evidence-pack-checklist/**`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

禁止修改：

- 认证 / 授权
- `server/security/**` / Guardrails
- SSRF
- DB schema / Alembic migration
- 后端 incident / report API contract
- `server/services/incident_report_service.py`，除非发现现有测试失败且必须先停下汇报
- `server/routers/incidents_router.py`，除非发现现有测试失败且必须先停下汇报
- npm 依赖
- rate limit 常量
- `.env`、`.coverage`、数据库、真实密钥
- 新增 PDF / DOCX / ZIP / 外部导出格式
- 调用 LLM 生成证据包
- 把完整 raw payload、完整 analyst note、system prompt、stack trace、API key 写入 DOM、复制文本、截图说明、运行日志或测试输出
- 用 `localStorage` / `sessionStorage` 保存 checklist 或报告 markdown
- 使用 `dangerouslySetInnerHTML` 或 `innerHTML`

## 4. 运行预算与停止条件

预算：

- 最长运行 4 小时。
- 同一失败最多修复 3 轮。
- diff 超过约 900 行时停止总结，除非主要是测试/文档。

必须停止并写清楚阻塞：

- Playwright 浏览器无法启动，且无法用 `PLAYWRIGHT_CHROMIUM_EXECUTABLE` 指到系统 Chrome 解决。
- dev server 无法稳定返回 `/api/backend/health`。
- 需要修改认证、Guardrails、SSRF、DB schema、后端 incident/report API、依赖或 rate limit 常量。
- 需要新增后端导出格式、ZIP/PDF/DOCX 或 LLM 报告生成才能完成 UX。
- E2E 只能 skipped，无法获得真实浏览器 pass。
- DOM、复制摘要、下载 markdown 或截图说明中出现 forbidden sentinel。
- 当前工作区存在 unrelated dirty files 时，不允许 broad stage；只能精确 stage 本任务文件。

## 5. 产品验收标准

完成后用户应该能在 Dashboard 的案件详情里完成：

1. 打开某个案件详情后看到 `Evidence Pack Checklist` 面板。
2. 面板至少包含 6 行检查项：
   - 报告可生成：基于现有 `loadIncidentReport()` 拉取 `IncidentReportMeta` 后显示 `ok`。
   - 关联告警：基于 `detail.linked_alerts.length`，有告警为 `ok`，没有告警为 `missing`。
   - 案件时间线：基于 `detail.events.length`，有事件为 `ok`，没有事件为 `missing`。
   - 告警研判覆盖：统计 linked alerts 中 `triage.status` 不为空且不是 `new` 的数量。
   - 脱敏状态：基于 report meta 的 `redaction_count` 和 `truncated` 展示 `ok / warn / manual`。
   - 缺失项：列出当前缺失的证据项，例如 `缺少关联告警`、`报告元信息未检查`、`存在未研判告警`。
3. 面板提供 `检查报告元信息` 按钮：
   - `data-testid="evidence-pack-refresh-report"`
   - 点击后只调用已有 `onLoadReport(incidentId)`。
   - 只保存 `filename` 和 `meta` 到短期 React state，不保存完整 markdown。
4. 面板提供 `复制证据包摘要` 按钮：
   - `data-testid="evidence-pack-copy-summary"`
   - 状态 `data-testid="evidence-pack-copy-status"`
   - 复制内容只包含安全字段：incident_id、status、severity、linked alert count、timeline event count、triage coverage、report meta 计数、missing items。
5. 面板不改变案件状态，不新增/移除告警，不保存备注，不调用 Copilot。
6. 桌面和移动端不产生整页横向溢出，长 id / 命令 / missing item 文案能换行。
7. DOM、复制文本、下载 markdown、截图说明均不包含 forbidden sentinel。

## 6. 推荐设计

### 6.1 UI 形态

在 `IncidentDetailPanel` 的 `关联告警` 区和 `事件时间线` 区之间加入只读面板，建议新增组件：

```text
web-next/components/dashboard/IncidentEvidencePackChecklist.tsx
```

建议测试 ID：

```text
incident-evidence-pack-checklist
evidence-pack-check-report
evidence-pack-check-linked-alerts
evidence-pack-check-timeline
evidence-pack-check-triage
evidence-pack-check-redaction
evidence-pack-check-missing
evidence-pack-refresh-report
evidence-pack-copy-summary
evidence-pack-copy-status
evidence-pack-report-filename
evidence-pack-report-meta
```

视觉要求：

- 保持当前案件详情的工具型、紧凑、低噪声风格。
- 不使用 modal，不新增 route，不做大卡片堆叠。
- 每行检查项用短标题、状态标签、计数、短说明表达。
- 可以使用 lucide `PackageCheck`、`Clipboard`、`RefreshCw`、`ShieldCheck`，但按钮必须有清楚文本或 `aria-label`。
- 移动端优先可读性，长 id 使用 `break-all`。

### 6.2 状态推导

前端只从 `IncidentDetailResponse` 和已有 report JSON meta 推导：

```text
report:
  未检查 -> manual
  report meta 加载成功 -> ok
  report meta 加载失败 -> warn

linked alerts:
  linked_alerts.length > 0 -> ok
  linked_alerts.length === 0 -> missing

timeline:
  events.length > 0 -> ok
  events.length === 0 -> missing

triage coverage:
  reviewed = linked_alerts where triage.status exists and triage.status !== "new"
  reviewed === linked_alerts.length and linked_alerts.length > 0 -> ok
  reviewed > 0 -> warn
  reviewed === 0 -> manual or missing

redaction:
  report meta 未加载 -> manual
  meta.redaction_count > 0 or meta.truncated -> ok
  meta.redaction_count === 0 and not truncated -> warn with "未触发脱敏,仍由后端报告服务生成"

missing:
  derive from report unchecked/failed, no linked alerts, no timeline events, unreviewed alerts
```

不要把 `raw_alert.payload`、`triage.analyst_note`、`IncidentEvent.note` 全量写进 checklist 或复制文本。可以展示计数和状态，不展示原文。

### 6.3 建议 props

```ts
type IncidentEvidencePackChecklistProps = {
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
[AI-CyberSentinel Evidence Pack]
incident_id=<id>
status=<status>
severity=<severity>
linked_alerts=<count>
timeline_events=<count>
triage_reviewed=<reviewed>/<total>
report_checked=<yes/no>
report_alerts=<included>/<total>
report_events=<included>/<total>
redactions=<count>
truncated=<yes/no>
missing=<comma separated safe labels>
```

剪贴板不可用时显示 `复制失败`，不能抛出未处理异常。

## 7. TDD / E2E 计划

### Task 1：创建运行日志

创建：

```text
docs/runs/2026-06-21-m3-17-incident-alert-evidence-pack-checklist-ux.md
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
server/tests/test_incident_evidence_pack_checklist_e2e.py
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
7. 断言 `incident-evidence-pack-checklist` 可见。
8. 断言 6 行检查项可见：
   - `evidence-pack-check-report`
   - `evidence-pack-check-linked-alerts`
   - `evidence-pack-check-timeline`
   - `evidence-pack-check-triage`
   - `evidence-pack-check-redaction`
   - `evidence-pack-check-missing`
9. 点击 `evidence-pack-refresh-report`，等待 `evidence-pack-report-meta`。
10. 断言 report meta 包含告警、事件、脱敏、截断计数。
11. 点击 `evidence-pack-copy-summary`，断言状态为 `已复制` 或 `复制失败`。
12. 如果 clipboard 可读，断言复制文本包含 `AI-CyberSentinel Evidence Pack`、`incident_id`、`linked_alerts`、`triage_reviewed`、`redactions`，且不含 forbidden sentinel。
13. 点击 `incident-download-report`，读取真实 markdown，复用报告结构和 forbidden sentinel 断言，确认 checklist 没破坏既有报告下载。
14. 扫描整页 DOM forbidden sentinel。
15. 保存桌面截图：

```text
docs/runs/artifacts/m3-17-incident-alert-evidence-pack-checklist/evidence-pack-desktop.png
```

16. 设置移动 viewport 390x844，确认 checklist 仍可见且无横向溢出，保存：

```text
docs/runs/artifacts/m3-17-incident-alert-evidence-pack-checklist/evidence-pack-mobile.png
```

RED 预期：

- 当前 UI 没有 `incident-evidence-pack-checklist`，测试应 fail 在该 selector。
- 不允许因为 selector 不存在而 skip。

### Task 3：GREEN - 实现最小 UX

实现：

- `IncidentEvidencePackChecklist.tsx`
- `IncidentDetailPanel.tsx` 接入 checklist，传入 `detail.incident`、`detail.linked_alerts`、`detail.events` 和 `onLoadReport`。

要求：

- 只保存 `reportMeta`、`reportFilename`、`reportStatus`、`copyStatus` 等小状态。
- 调用 `onLoadReport()` 后不要保存完整 markdown。
- 不影响已有 `预览报告 / 复制报告 / 下载报告 / 用 AI 分析案件` 按钮。
- 切换 incident 时 checklist state 要随组件重新计算或清空。

### Task 4：IMPROVE - de-sloppify

检查并修复：

- 是否留下 `console.log`。
- 是否用了 `localStorage` / `sessionStorage`。
- 是否用了 `dangerouslySetInnerHTML` / `innerHTML`。
- 是否把 raw payload、完整 note、完整 markdown 长期保存到 checklist state。
- 是否把 system prompt、stack trace、API key、regex、cookie、token 写进 DOM 或复制文本。
- 按钮是否有清晰文本或 `aria-label`。
- 移动端是否横向溢出。
- 是否把检查清单做成可修改业务状态的控件。如果有，必须改回只读。

扫描命令：

```powershell
rg -n "console\.log|localStorage|sessionStorage|dangerouslySetInnerHTML|innerHTML|sk-|AKIA|ghp_|PRIVATE KEY|Traceback|system:|developer:" web-next\components\dashboard server\tests\test_incident_evidence_pack_checklist_e2e.py
```

命中测试 sentinel 常量允许；生产组件命中敏感字面量必须修。

### Task 5：验证矩阵

如果本机 Chromium `spawn EPERM`，优先使用系统 Chrome：

```powershell
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
```

如需隔离 dev server，可沿用 M3-16 的 fresh backend/frontend 方案，但必须写进运行日志。

必须运行：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_incident_evidence_pack_checklist_e2e.py -q --tb=short --run-e2e -s -rs
```

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_incident_report_e2e.py -q --tb=short --run-e2e -s -rs
```

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_incident_report_preview_e2e.py -q --tb=short --run-e2e -s -rs
```

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_security_timeline_drilldown_e2e.py -q --tb=short --run-e2e -s -rs
```

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_dashboard_responsive_e2e.py -q --tb=short --run-e2e -s -rs
```

关键 E2E 串跑，加入 M3-17 新用例，实际总数以 pytest 输出为准：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_auth_session_e2e.py server\tests\test_demo_flow_e2e.py server\tests\test_incident_report_e2e.py server\tests\test_dashboard_route_sections_e2e.py server\tests\test_dashboard_responsive_e2e.py server\tests\test_demo_flow_stability_e2e.py server\tests\test_dashboard_mobile_visual_e2e.py server\tests\test_incident_report_preview_e2e.py server\tests\test_security_timeline_drilldown_e2e.py server\tests\test_dashboard_operational_runbook_e2e.py server\tests\test_incident_evidence_pack_checklist_e2e.py -q --tb=short --run-e2e -s -rs
```

默认后端：

```powershell
$tmpRoot = ".tmp\pytest-m3-17-full-$(Get-Date -Format 'yyyyMMddHHmmss')"
New-Item -ItemType Directory -Force -Path $tmpRoot | Out-Null
$env:TMP=(Resolve-Path $tmpRoot).Path
$env:TEMP=$env:TMP
.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

Guardrails：

```powershell
$tmpRoot = ".tmp\pytest-m3-17-guardrails-$(Get-Date -Format 'yyyyMMddHHmmss')"
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

- `PRODUCT.md`：在 M3 当前状态中补 M3-17 已交付摘要。
- `docs/plans/M2_PRODUCT_ROADMAP.md`：补 M3-17 摘要。
- `docs/agent/UNATTENDED_LONG_TASKS.md`：新增 M3-17 已交付条目，推荐口令改为下一条候选。
- `docs/runs/2026-06-21-m3-17-incident-alert-evidence-pack-checklist-ux.md`：记录真实命令、结果、截图路径、commit hash、push 状态。

下一条候选建议：

- `M3-18 Incident closure / post-incident review checklist UX`：在案件状态、证据包和报告能力之上，补一个关闭前检查清单，帮助 owner 确认案件是否可进入 `resolved / false_positive`。
- `Guardrails moderation httpx pool 健康监控`：需要 owner 单独授权，因为会触碰 `server/security/llm_guardrails/**`。

默认推荐继续产品体验，除非 owner 明确授权动 Guardrails。

### Task 7：精确 commit / push

禁止 `git add .`。

建议拆分：

1. `test(e2e): 覆盖案件证据包清单`
2. `feat(incidents): 增加案件证据包检查面板`
3. `docs(evidence): 记录案件证据包 UX 收口`

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
- 与本任务无关的旧 artifact 或缓存

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
- 未改 auth / Guardrails / SSRF / DB schema / 后端 incident/report API / npm 依赖 / rate limit
- 未提交 .coverage / env / DB / 密钥
- DOM / copy text / markdown forbidden sentinel 扫描结果

运行日志：
- docs/runs/2026-06-21-m3-17-incident-alert-evidence-pack-checklist-ux.md

下一条建议：
- <建议>
```

## 9. 启动口令

```text
请执行 `docs/agent/M3_17_INCIDENT_ALERT_EVIDENCE_PACK_CHECKLIST_UX_TASK.md` 中定义的 L5 超长任务。先完整阅读任务文档和必读上下文，创建运行日志，新增真实浏览器 E2E 覆盖 Incident / Alert evidence pack checklist，再实现最小前端 UX。只允许前端 evidence checklist UX、E2E、截图和文档同步，不新增后端导出格式，不修改认证/授权/Guardrails/SSRF/DB schema/后端 incident/report API/npm 依赖/rate limit，不调用 LLM，不使用 localStorage/sessionStorage 或 `dangerouslySetInnerHTML`，不要提交 `.coverage`、真实 env、数据库或密钥。通过新增 evidence pack E2E、既有 incident report E2E、incident report preview E2E、security timeline E2E、Dashboard responsive E2E、关键 E2E 串跑、后端全量、Guardrails、前端 typecheck/build 后，精确拆分 commit 并 push 到 `origin/main`，完成后输出最终报告。
```
