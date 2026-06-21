# Run: M3-18 Incident Closure / Post-Incident Review Checklist UX 收口

开始时间：2026-06-21 16:58:29 +08:00
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
?? docs/agent/M3_18_INCIDENT_CLOSURE_POST_INCIDENT_REVIEW_CHECKLIST_UX_TASK.md
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
warning: could not open directory '.tmp/pytest/pytest-of-276291/': Permission denied
```

当前 `git log -1 --oneline`：

```text
1e0c74b docs(evidence): 记录案件证据包 UX 收口
```

启动观察：

- 本地 `main` 与 `origin/main` 对齐。
- `docs/agent/UNATTENDED_LONG_TASKS.md` 启动时已有 M3-18 固化 diff，本任务会在最终文档同步时继续把 M3-18 更新为已交付并推荐 M3-19。
- `docs/agent/M3_18_INCIDENT_CLOSURE_POST_INCIDENT_REVIEW_CHECKLIST_UX_TASK.md` 启动时未跟踪，但属于本任务要求的任务文档入库范围。
- 工作区已有跨任务截图、旧 dev server 日志和 `.tmp/pytest` 权限噪声；本任务只允许精确 stage M3-18 文件，禁止 `git add .`。

## 必读上下文清单

- [x] `AGENTS.md`
- [x] `CLAUDE.md`
- [x] `PRODUCT.md`
- [x] `docs/agent/UNATTENDED_LONG_TASKS.md`
- [x] `docs/agent/M3_18_INCIDENT_CLOSURE_POST_INCIDENT_REVIEW_CHECKLIST_UX_TASK.md`
- [x] `docs/runs/2026-06-21-m3-17-incident-alert-evidence-pack-checklist-ux.md`
- [x] `docs/runs/2026-06-21-m3-16-dashboard-operational-runbook-health-checklist-ux.md`
- [x] `docs/runs/2026-06-20-m3-15-soc-timeline-drilldown-filter-ux.md`
- [x] `docs/runs/2026-06-19-m3-14-incident-report-preview-ux.md`
- [x] `docs/runs/2026-06-18-m3-07-incident-evidence-report-export.md`
- [x] `docs/plans/M2_PRODUCT_ROADMAP.md` 中 M3-04 / M3-07 / M3-14 / M3-15 / M3-17 段落
- [x] `web-next/components/dashboard/IncidentDetailPanel.tsx`
- [x] `web-next/components/dashboard/IncidentEvidencePackChecklist.tsx`
- [x] `web-next/components/dashboard/IncidentReportPreview.tsx`
- [x] `web-next/components/dashboard/IncidentLinkedAlerts.tsx`
- [x] `web-next/components/dashboard/IncidentTimeline.tsx`
- [x] `web-next/hooks/useIncidents.ts`
- [x] `web-next/types/incident.ts`
- [x] `server/tests/e2e_helpers.py`
- [x] `server/tests/test_incident_evidence_pack_checklist_e2e.py`
- [x] `server/tests/test_incident_report_e2e.py`
- [x] `server/tests/test_incident_report_preview_e2e.py`
- [x] `server/tests/test_security_timeline_drilldown_e2e.py`
- [x] `server/tests/test_dashboard_responsive_e2e.py`
- [x] `server/tests/test_incidents.py` 中 `closed_at` 行为相关测试

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

在 Dashboard 案件详情中新增只读 Closure Review Checklist，集中展示案件是否适合进入 `resolved / false_positive` 的关闭前复盘条件，并支持复制不含敏感正文的复盘摘要。

## 范围

允许修改：

- `web-next/components/dashboard/IncidentDetailPanel.tsx`
- 新增 `web-next/components/dashboard/IncidentClosureReviewChecklist.tsx`
- 可新增 `web-next/types/closureReview.ts`（当前计划不新增）
- 必要时轻量更新 `web-next/components/dashboard/IncidentEvidencePackChecklist.tsx`（当前计划不改）
- 新增 `server/tests/test_incident_closure_review_checklist_e2e.py`
- 必要时轻量更新既有 incident report / preview / evidence pack E2E（当前计划不改）
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

## 阶段计划

- [x] 阶段 1 RED：新增 `server/tests/test_incident_closure_review_checklist_e2e.py`，确认缺少 `incident-closure-review-checklist` selector 时失败。
- [x] 阶段 2 GREEN：新增 `IncidentClosureReviewChecklist.tsx` 并接入 `IncidentDetailPanel.tsx`。
- [x] 阶段 3 IMPROVE：de-sloppify、安全扫描、移动端横向溢出检查。
- [x] 阶段 4：运行新增 closure E2E、M3-17 evidence pack E2E、既有 incident report / preview / timeline / responsive E2E。
- [x] 阶段 5：运行关键 E2E 串跑、后端全量、Guardrails、前端 typecheck/build。
- [x] 阶段 6：同步 `PRODUCT.md`、`docs/plans/M2_PRODUCT_ROADMAP.md`、`docs/agent/UNATTENDED_LONG_TASKS.md` 和本日志。
- [ ] 阶段 7：精确拆分 commit 并 push `origin/main`。

## 停止条件

- Playwright 浏览器无法启动，且无法用 `PLAYWRIGHT_CHROMIUM_EXECUTABLE` 指到系统 Chrome 解决。
- dev server 无法稳定返回 `/api/backend/health`。
- 需要修改认证、Guardrails、SSRF、DB schema、后端 incident/report API、依赖或 rate limit 常量。
- 需要新增后端导出格式、ZIP/PDF/DOCX 或 LLM 复盘生成才能完成 UX。
- E2E 只能 skipped，无法获得真实浏览器 pass。
- DOM、复制摘要、下载 markdown 或截图说明中出现 forbidden sentinel。
- 当前工作区存在 unrelated dirty files 时，不允许 broad stage；只能精确 stage 本任务文件。

## 阶段记录

### 阶段 0：启动与上下文

已完成任务文档、项目规则、相邻运行日志、现有 incident/report/evidence/timeline 前端组件、E2E helper 与 `closed_at` 后端行为测试阅读。

关键决策：

- Closure checklist 只读；只从 `detail.incident`、`detail.linked_alerts`、`detail.events` 和已有 `onLoadReport(incidentId)` 的 report meta 推导。
- `onLoadReport` 结果只保存 `filename` 和 `meta`；不保存完整 markdown。
- 复制摘要只含安全计数字段、关闭状态、建议和缺失项标签，不含 payload、note、markdown、system prompt、stack trace、API key。
- 新 checklist 放在 Evidence Pack Checklist 之后、事件时间线之前。
- E2E 保存 `contained` + 备注只验证既有状态控件仍工作；新 checklist 不自动关闭案件。

### 阶段 1：RED E2E

新增 `server/tests/test_incident_closure_review_checklist_e2e.py`，覆盖：

- 登录 Dashboard。
- 触发 Demo 告警并创建案件。
- 确认 M3-17 `incident-evidence-pack-checklist` 仍可见。
- 等待新 `incident-closure-review-checklist`。
- 检查八个 closure checklist row。
- 刷新报告 meta、复制 Closure Review 摘要、保存 `contained` + 复盘备注、下载既有 markdown 报告、桌面/移动截图、DOM/clipboard/markdown forbidden sentinel。

RED 过程：

1. 首轮失败在 Demo 告警前置，Next middleware 因 `ALLOWED_ORIGINS` 未包含 `http://localhost:3124` 返回 403；这是本地 E2E 启动环境问题，不改安全代码。
2. 用正确 `ALLOWED_ORIGINS=http://localhost:3124,http://127.0.0.1:3124` 重启前端后，RED 命中目标：

```text
Locator.wait_for: Timeout 15000ms exceeded.
waiting for get_by_test_id("incident-closure-review-checklist").first to be visible
```

### 阶段 2：GREEN 前端实现

新增 `web-next/components/dashboard/IncidentClosureReviewChecklist.tsx` 并在 `IncidentDetailPanel.tsx` 中接入。

实现摘要：

- 八项只读检查：状态可复核、证据包基础材料、报告元信息、关联告警、研判覆盖、时间线事件、复盘备注、关闭缺失项。
- 关闭建议只从当前状态、缺失项和既有数据推导，不自动把案件改为 `resolved` / `false_positive`。
- `closure-refresh-report` 只保存 `filename/meta`，不保存完整 markdown。
- `closure-copy-summary` 只复制安全计数字段、`closed_at` 是否适用、复盘备注是否存在、建议和缺失项；不复制 payload、note 正文、报告正文或 secret。
- 复盘备注检查只显示是否存在，不渲染备注正文。

GREEN 验证：

```text
pytest server\tests\test_incident_closure_review_checklist_e2e.py -q --tb=short --run-e2e -s -rs
1 passed in 10.30s
```

### 阶段 3：IMPROVE / 安全扫描 / 截图检查

快速类型与安全边界检查：

```text
npx tsc --noEmit --pretty false --incremental false
exit 0

py_compile server\tests\test_incident_closure_review_checklist_e2e.py
exit 0

rg -n "localStorage|sessionStorage|dangerouslySetInnerHTML|innerHTML|sk-|AKIA|ghp_|PRIVATE KEY|Traceback|system\s*:|developer\s*:" ...
仅命中新 E2E forbidden sentinel 常量。
```

截图人工检查：

- `closure-review-desktop.png`：桌面全页可见 Evidence Pack 与 Closure Review，布局紧凑，时间线仍在下方。
- `closure-review-mobile.png`：移动 viewport 可见 checklist，E2E 断言整页横向溢出 `<= 4px`。

### 阶段 4：相关 E2E

为避免 RED 轮账号和临时数据影响正式矩阵，使用 fresh 后端/前端：

- 后端：`127.0.0.1:8126`
- 前端：`http://localhost:3126`
- DB：`.tmp/m3-18-e2e-matrix.db`
- 预创建 5 个稳定测试账号，用环境变量映射 E2E prefix，避免触发 5/小时注册限流；未修改后端 rate limit。

结果：

```text
pytest server\tests\test_incident_closure_review_checklist_e2e.py -q --tb=short --run-e2e -s -rs
1 passed in 12.07s

pytest server\tests\test_incident_evidence_pack_checklist_e2e.py `
  server\tests\test_incident_report_e2e.py `
  server\tests\test_incident_report_preview_e2e.py `
  server\tests\test_security_timeline_drilldown_e2e.py `
  server\tests\test_dashboard_responsive_e2e.py `
  -q --tb=short --run-e2e -s -rs
6 passed in 52.10s
```

注：相邻 E2E 首轮在第 6 次注册时触发本地 `REGISTER_RATE_LIMIT_MAX=5/小时`，已按任务文档允许方式改用 fresh backend + 预置稳定账号；未改生产限流常量。

### 阶段 5：完整验证矩阵

关键 E2E 串跑：

```text
pytest server\tests\test_auth_session_e2e.py `
  server\tests\test_demo_flow_e2e.py `
  server\tests\test_incident_report_e2e.py `
  server\tests\test_dashboard_route_sections_e2e.py `
  server\tests\test_dashboard_responsive_e2e.py `
  server\tests\test_demo_flow_stability_e2e.py `
  server\tests\test_dashboard_mobile_visual_e2e.py `
  server\tests\test_incident_report_preview_e2e.py `
  server\tests\test_security_timeline_drilldown_e2e.py `
  server\tests\test_dashboard_operational_runbook_e2e.py `
  server\tests\test_incident_evidence_pack_checklist_e2e.py `
  server\tests\test_incident_closure_review_checklist_e2e.py `
  -q --tb=short --run-e2e -s -rs
13 passed in 99.18s
```

后端与前端：

```text
pytest server\tests\test_security_timeline.py -q --tb=short
12 passed in 1.13s

pytest server\tests\security\llm_guardrails -q --tb=short
139 passed, 17 warnings in 19.05s

pytest server\tests -q --tb=short
344 passed, 14 skipped, 17 warnings in 83.26s

npm run typecheck
passed

npm run build
passed (/dashboard 53.4 kB / First Load JS 201 kB)
```

### 阶段 6：文档同步

已同步：

- `PRODUCT.md` 新增第 27 项 M3-18 已交付说明。
- `docs/plans/M2_PRODUCT_ROADMAP.md` 新增 M3-18 完整交付段。
- `docs/agent/UNATTENDED_LONG_TASKS.md` 把 M3-18 改为已交付，并把推荐口令更新为 M3-19 先固化再执行。
- 本运行日志补齐 RED/GREEN/IMPROVE、验证矩阵、截图路径和最终边界。

## 验证证据

- RED：`incident-closure-review-checklist` 缺失导致 Playwright selector 15s timeout。
- 新增 closure E2E：`1 passed in 12.07s`。
- M3-17 evidence pack + incident report + incident report preview + security timeline drilldown + Dashboard responsive E2E：`6 passed in 52.10s`。
- 关键 E2E 串跑：`13 passed in 99.18s`。
- 后端 timeline 专项：`12 passed in 1.13s`。
- Guardrails：`139 passed, 17 warnings in 19.05s`。
- 后端全量：`344 passed, 14 skipped, 17 warnings in 83.26s`。
- 前端 `npm run typecheck`：通过。
- 前端 `npm run build`：通过。
- 禁止项扫描：生产改动未命中 `localStorage` / `sessionStorage` / `dangerouslySetInnerHTML` / `innerHTML`；E2E sentinel 常量命中属预期。

## 截图证据

- `docs/runs/artifacts/m3-18-incident-closure-post-incident-review-checklist/closure-review-desktop.png`
- `docs/runs/artifacts/m3-18-incident-closure-post-incident-review-checklist/closure-review-mobile.png`

## 未解决问题

- 无本任务阻塞。
- 工作区仍有启动前已存在或相邻 E2E 刷新的历史截图 / dev server log / `.tmp` 噪声；提交时只精确 stage M3-18 文件。
- M3-19 任务文档尚未存在，本次只在无人值守索引中把下一条推荐改为“先固化 M3-19 再执行”。

## 最终状态

待精确 commit / push。
