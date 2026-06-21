# Run: M3-17 Incident / Alert Evidence Pack Checklist UX 收口

开始时间：2026-06-21
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
?? docs/agent/M3_17_INCIDENT_ALERT_EVIDENCE_PACK_CHECKLIST_UX_TASK.md
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
warning: could not open directory '.tmp/pytest/pytest-of-276291/': Permission denied
```

当前 `git log -1 --oneline`：

```text
9029150 docs(runbook): 记录 Dashboard 运维检查 UX 收口
```

启动观察：

- 本地 `main` 与 `origin/main` 对齐。
- 工作区已有跨任务截图、旧 dev server 日志和 `.tmp/pytest` 权限噪声；本任务只允许精确 stage M3-17 文件，禁止 `git add .`。
- `docs/agent/UNATTENDED_LONG_TASKS.md` 启动时已有修改，后续只做本任务要求的 M3-17 文档同步，并在提交前复核 diff。

## 必读上下文清单

- [x] `AGENTS.md`
- [x] `CLAUDE.md`
- [x] `PRODUCT.md`
- [x] `docs/agent/UNATTENDED_LONG_TASKS.md`
- [x] `docs/agent/M3_17_INCIDENT_ALERT_EVIDENCE_PACK_CHECKLIST_UX_TASK.md`
- [x] `docs/runs/2026-06-21-m3-16-dashboard-operational-runbook-health-checklist-ux.md`
- [x] `docs/runs/2026-06-20-m3-15-soc-timeline-drilldown-filter-ux.md`
- [x] `docs/runs/2026-06-19-m3-14-incident-report-preview-ux.md`
- [x] `docs/runs/2026-06-18-m3-07-incident-evidence-report-export.md`
- [x] `docs/plans/M2_PRODUCT_ROADMAP.md`
- [x] `web-next/components/dashboard/IncidentDetailPanel.tsx`
- [x] `web-next/components/dashboard/IncidentSection.tsx`
- [x] `web-next/components/dashboard/IncidentLinkedAlerts.tsx`
- [x] `web-next/components/dashboard/IncidentTimeline.tsx`
- [x] `web-next/components/dashboard/IncidentReportPreview.tsx`
- [x] `web-next/hooks/useIncidents.ts`
- [x] `web-next/types/incident.ts`
- [x] `server/tests/e2e_helpers.py`
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

在 Dashboard 案件详情中新增只读 Evidence Pack Checklist，集中展示报告元信息、关联告警、案件时间线、研判覆盖、脱敏/截断状态和缺失项，并支持复制不含敏感正文的证据包摘要。

## 范围

允许修改：

- `web-next/components/dashboard/IncidentDetailPanel.tsx`
- 新增 `web-next/components/dashboard/IncidentEvidencePackChecklist.tsx`
- 可新增 `web-next/types/evidencePack.ts`
- `web-next/hooks/useIncidents.ts`（仅限小型 helper / 类型导出；当前计划不改）
- 新增 `server/tests/test_incident_evidence_pack_checklist_e2e.py`
- 必要时轻量更新既有 incident report / preview E2E
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
- `server/services/incident_report_service.py`
- `server/routers/incidents_router.py`
- npm 依赖
- rate limit 常量
- `.env`、`.coverage`、数据库、真实密钥
- 新增 PDF / DOCX / ZIP / 外部导出格式
- 调用 LLM 生成证据包
- 把完整 raw payload、完整 analyst note、system prompt、stack trace、API key 写入 DOM、复制文本、截图说明、运行日志或测试输出
- 用 `localStorage` / `sessionStorage` 保存 checklist 或报告 markdown
- 使用 `dangerouslySetInnerHTML` 或 `innerHTML`

## 阶段计划

- [x] 阶段 1 RED：新增 `server/tests/test_incident_evidence_pack_checklist_e2e.py`，确认缺少 `incident-evidence-pack-checklist` selector 时失败。
- [x] 阶段 2 GREEN：新增 `IncidentEvidencePackChecklist.tsx` 并接入 `IncidentDetailPanel.tsx`。
- [x] 阶段 3 IMPROVE：de-sloppify、安全扫描、移动端横向溢出检查。
- [x] 阶段 4：运行新增 evidence pack E2E、既有 incident report / preview / timeline / responsive E2E。
- [x] 阶段 5：运行关键 E2E 串跑、后端全量、Guardrails、前端 typecheck/build。
- [x] 阶段 6：同步 `PRODUCT.md`、`docs/plans/M2_PRODUCT_ROADMAP.md`、`docs/agent/UNATTENDED_LONG_TASKS.md` 和本日志。
- [ ] 阶段 7：精确拆分 commit 并 push `origin/main`。

## 停止条件

- Playwright 浏览器无法启动，且无法用 `PLAYWRIGHT_CHROMIUM_EXECUTABLE` 指到系统 Chrome 解决。
- dev server 无法稳定返回 `/api/backend/health`。
- 需要修改认证、Guardrails、SSRF、DB schema、后端 incident/report API、依赖或 rate limit 常量。
- 需要新增后端导出格式、ZIP/PDF/DOCX 或 LLM 报告生成才能完成 UX。
- E2E 只能 skipped，无法获得真实浏览器 pass。
- DOM、复制摘要、下载 markdown 或截图说明中出现 forbidden sentinel。
- 当前工作区存在 unrelated dirty files 时，不允许 broad stage；只能精确 stage 本任务文件。

## 阶段记录

### 阶段 0：启动与上下文

已完成任务文档、项目规则、相邻运行日志、现有 incident/report/timeline 前端组件与 E2E helper 阅读。

关键决策：

- Checklist 只读；只从 `detail.incident`、`detail.linked_alerts`、`detail.events` 和已有 `onLoadReport(incidentId)` 的 report meta 推导。
- `onLoadReport` 结果只保存 `filename` 和 `meta`；不保存完整 markdown。
- 复制摘要只含安全计数字段和缺失项标签，不含 payload、note、markdown、system prompt、stack trace、API key。
- E2E 复用现有登录、Demo、案件创建、下载报告路径；不新增 auth/setup 逻辑。

### 阶段 1：RED - 新增浏览器 E2E

新增 `server/tests/test_incident_evidence_pack_checklist_e2e.py`：

- 复用 `assert_dev_server_reachable`、`register_or_login_for_e2e`、`skip_without_playwright`。
- 真实浏览器路径：登录 Dashboard -> 触发 Demo 攻击 -> 从告警创建案件 -> 验证 evidence pack checklist -> 检查报告 meta -> 复制摘要 -> 下载 markdown -> DOM / clipboard / markdown forbidden sentinel -> 桌面 / 移动截图。
- 目标截图路径：
  - `docs/runs/artifacts/m3-17-incident-alert-evidence-pack-checklist/evidence-pack-desktop.png`
  - `docs/runs/artifacts/m3-17-incident-alert-evidence-pack-checklist/evidence-pack-mobile.png`

本轮隔离 dev server：

```text
backend:  http://127.0.0.1:8121/health -> 200 {"status":"ok"}
frontend: http://localhost:3121/api/backend/health -> 200 {"status":"ok"}
```

RED 命令：

```powershell
$env:E2E_BASE_URL='http://localhost:3121'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_incident_evidence_pack_checklist_e2e.py -q --tb=short --run-e2e -s -rs
```

RED 结果：

```text
1 failed in 25.78s
TimeoutError: waiting for get_by_test_id("incident-evidence-pack-checklist").first to be visible
```

失败点符合预期：当前 UI 没有 evidence pack checklist，测试没有因 selector 缺失而 skip。

### 阶段 2：GREEN - 最小 UX

新增 / 修改：

- 新增 `web-next/components/dashboard/IncidentEvidencePackChecklist.tsx`：
  - 六项检查：报告可生成、关联告警、案件时间线、告警研判覆盖、脱敏状态、缺失项。
  - 点击 `evidence-pack-refresh-report` 仅调用既有 `onLoadReport(incidentId)`，只保存 `filename` 与 `meta`，丢弃返回 markdown。
  - 点击 `evidence-pack-copy-summary` 复制安全摘要：incident id、状态、严重度、关联告警数、时间线事件数、研判覆盖、report meta 计数、缺失项。
  - 不写 `localStorage` / `sessionStorage`，不使用 `dangerouslySetInnerHTML` / `innerHTML`。
- 修改 `web-next/components/dashboard/IncidentDetailPanel.tsx`：
  - 在关联告警区和事件时间线区之间挂载 checklist。
  - 只传入 `detail.incident`、`detail.linked_alerts`、`detail.events` 和既有 `onLoadReport`。

GREEN 命令：

```powershell
$env:E2E_BASE_URL='http://localhost:3121'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_incident_evidence_pack_checklist_e2e.py -q --tb=short --run-e2e -s -rs
```

GREEN 结果：

```text
1 passed in 9.26s
[Incident Evidence Pack Checklist E2E 诊断] {'registered': True, 'report_meta': True, 'copy_status': '已复制', 'clipboard_checked': True, 'forbidden': None, 'clipboard_forbidden': None}
```

截图已生成：

- `docs/runs/artifacts/m3-17-incident-alert-evidence-pack-checklist/evidence-pack-desktop.png`
- `docs/runs/artifacts/m3-17-incident-alert-evidence-pack-checklist/evidence-pack-mobile.png`

### 阶段 3：IMPROVE / de-sloppify

扫描命令：

```powershell
rg -n "console\.log|localStorage|sessionStorage|dangerouslySetInnerHTML|innerHTML|sk-|AKIA|ghp_|PRIVATE KEY|Traceback|system:|developer:" web-next\components\dashboard server\tests\test_incident_evidence_pack_checklist_e2e.py
```

结果：

- 仅命中新 E2E 的 forbidden sentinel 常量。
- 生产组件未命中 `console.log`、`localStorage`、`sessionStorage`、`dangerouslySetInnerHTML`、`innerHTML` 或敏感字面量。

前端 typecheck 早期检查：

```powershell
# cwd web-next
npm run typecheck
```

结果：通过，`Route types generated successfully`。

### 阶段 4：E2E 回归矩阵

指定既有 E2E 回归命令：

```powershell
$env:E2E_BASE_URL='http://localhost:3121'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_incident_report_e2e.py server\tests\test_incident_report_preview_e2e.py server\tests\test_security_timeline_drilldown_e2e.py server\tests\test_dashboard_responsive_e2e.py -q --tb=short --run-e2e -s -rs
```

结果：

```text
5 passed in 37.49s
```

关键 E2E 首轮：

```text
12 failed in 8.79s
```

失败均发生在测试前置：本地 `REGISTER_RATE_LIMIT_MAX=5/hour` 已被当前隔离 backend 消耗，稳定账号尚未存在；未进入业务断言。

关键 E2E 第二轮：

```text
9 passed, 3 failed in 184.77s
```

已预置共享稳定账号后，最后 3 个失败在登录前置：同一邮箱短时间被多条 E2E 反复登录，触发本地 `LOGIN_RATE_LIMIT_MAX=10/5min` 限制或会话前置不稳定；未进入业务断言。

最终处理：

- 不修改认证/授权。
- 不修改 `REGISTER_RATE_LIMIT_*` 或 `LOGIN_RATE_LIMIT_*` 常量。
- 启动 fresh 本地 E2E backend/frontend：`8123/3123`。
- 复用历史已存在的 5 个稳定测试账号分摊登录次数。

最终关键 E2E 串跑命令：

```powershell
$env:E2E_BASE_URL='http://localhost:3123'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_auth_session_e2e.py server\tests\test_demo_flow_e2e.py server\tests\test_incident_report_e2e.py server\tests\test_dashboard_route_sections_e2e.py server\tests\test_dashboard_responsive_e2e.py server\tests\test_demo_flow_stability_e2e.py server\tests\test_dashboard_mobile_visual_e2e.py server\tests\test_incident_report_preview_e2e.py server\tests\test_security_timeline_drilldown_e2e.py server\tests\test_dashboard_operational_runbook_e2e.py server\tests\test_incident_evidence_pack_checklist_e2e.py -q --tb=short --run-e2e -s -rs
```

最终结果：

```text
12 passed in 104.30s
```

### 阶段 5：后端 / Guardrails / 前端最终质量门

后端全量命令：

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

结果：

```text
344 passed, 13 skipped, 17 warnings in 85.37s
```

Guardrails 专项命令：

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

结果：

```text
139 passed, 17 warnings in 19.29s
```

前端最终命令：

```powershell
# cwd web-next
npm run typecheck
npm run build
```

结果：

```text
typecheck passed
build passed
/dashboard 51.5 kB / First Load JS 199 kB
```

### 阶段 6：文档同步

已同步：

- `PRODUCT.md`：新增第 26 项 M3-17 已交付摘要。
- `docs/plans/M2_PRODUCT_ROADMAP.md`：新增 M3-17 收口段。
- `docs/agent/UNATTENDED_LONG_TASKS.md`：M3-17 更新为已交付，推荐启动口令推进到 M3-18 候选。
- 本运行日志：补齐验证矩阵、截图路径、精确 commit 计划。

### 阶段 7：精确 commit / push 计划

计划拆分：

1. `test(e2e): 覆盖案件证据包清单`
   - `server/tests/test_incident_evidence_pack_checklist_e2e.py`
   - `docs/runs/artifacts/m3-17-incident-alert-evidence-pack-checklist/evidence-pack-desktop.png`
   - `docs/runs/artifacts/m3-17-incident-alert-evidence-pack-checklist/evidence-pack-mobile.png`
2. `feat(incidents): 增加案件证据包检查面板`
   - `web-next/components/dashboard/IncidentEvidencePackChecklist.tsx`
   - `web-next/components/dashboard/IncidentDetailPanel.tsx`
3. `docs(evidence): 记录案件证据包 UX 收口`
   - `PRODUCT.md`
   - `docs/plans/M2_PRODUCT_ROADMAP.md`
   - `docs/agent/UNATTENDED_LONG_TASKS.md`
   - `docs/agent/M3_17_INCIDENT_ALERT_EVIDENCE_PACK_CHECKLIST_UX_TASK.md`
   - `docs/runs/2026-06-21-m3-17-incident-alert-evidence-pack-checklist-ux.md`

已提交：

- `9afcfa6` `test(e2e): 覆盖案件证据包清单`
- `093ac57` `feat(incidents): 增加案件证据包检查面板`

文档提交与 push 状态待回填。

## 验证证据

- RED evidence pack E2E：`1 failed in 25.78s`，失败点为缺少 `incident-evidence-pack-checklist`，符合预期。
- GREEN evidence pack E2E：`1 passed in 9.26s`。
- 既有 incident report / preview / security timeline / Dashboard responsive E2E：`5 passed in 37.49s`。
- 关键 E2E 串跑：`12 passed in 104.30s`。
- 后端全量：`344 passed, 13 skipped, 17 warnings in 85.37s`。
- Guardrails 专项：`139 passed, 17 warnings in 19.29s`。
- 前端 typecheck：通过。
- 前端 build：通过，`/dashboard 51.5 kB / First Load JS 199 kB`。
- de-sloppify 扫描：生产组件未命中 `console.log`、`localStorage`、`sessionStorage`、`dangerouslySetInnerHTML`、`innerHTML` 或敏感字面量；新 E2E 仅命中 forbidden sentinel 常量。

## 截图证据

- `docs/runs/artifacts/m3-17-incident-alert-evidence-pack-checklist/evidence-pack-desktop.png`
- `docs/runs/artifacts/m3-17-incident-alert-evidence-pack-checklist/evidence-pack-mobile.png`

## 未解决问题

无本任务阻塞。关键 E2E 首轮/二轮失败均为本地长串测试账号注册或登录限流前置问题；最终使用 fresh 本地 E2E backend/frontend 与多个稳定测试账号分摊登录次数完成真实浏览器验证，未修改认证/授权或 rate limit。

## 最终状态

实现、验证和文档同步已完成；前两组 commit 已完成，等待文档 commit / push 回填最终状态。
