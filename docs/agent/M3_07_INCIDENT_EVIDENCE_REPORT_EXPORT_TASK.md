# M3-07 案件证据报告导出 L5 超长任务

> 任务级别：L5，跨后端契约 + 前端工作台 + 安全脱敏 + 验证矩阵的产品能力战役。  
> 目标读者：接手本仓库的开发 agent。  
> 核心目标：把 M3-04/M3-05 已建立的“案件 + 告警 + 时间线 + Copilot 上下文”能力，收束成可复制、可下载、可审计、可脱敏的 SOC 案件证据报告。

---

## 0. 背景

当前项目已经具备：

- M3-03：告警研判持久化和历史记录。
- M3-04：安全事件 / 案件工作台，含 incident、linked alerts、events。
- M3-05：案件感知 Copilot 合约，前端只发 `incident_id`，后端 owner 隔离构造受控上下文。
- M3-06：默认测试与安全质量门清零，后端 `318 passed, 2 skipped`，Guardrails 专项 `139 passed`。

现在的问题不是“没有数据”，而是**安全分析员不能把一个案件沉淀成一份可交付的证据报告**：

- 告警有单条“复制报告”，但案件级别没有。
- 案件时间线、关联告警、研判状态、处置备注分散在多个面板里。
- 现有 `/export/alerts` 是全量 CSV，不适合作为单个 incident 的复盘材料。
- 如果直接导出完整 payload / note / stack trace / system prompt，会有安全泄漏风险。

本任务要新增一个明确的产品能力：

```text
安全分析员打开案件详情
  -> 点击“复制报告”或“下载报告”
  -> 后端按 owner 隔离读取案件事实
  -> 构造脱敏 Markdown 证据报告
  -> 前端可复制到剪贴板或下载 .md 文件
  -> 审计 Log 记录导出动作，但不记录报告正文
```

---

## 1. 产品能力定义

完成后，用户应该能做到：

1. 在 Dashboard 的“安全事件 / 案件工作台”中选择一个案件。
2. 点击“复制报告”，把该案件的 Markdown 证据报告复制到剪贴板。
3. 点击“下载报告”，获得 `incident-<incident_id>-report.md` 文件。
4. 报告包含：
   - incident 基础信息：ID、标题、严重度、状态、创建/更新时间、关闭时间、告警数。
   - 案件摘要：截断且脱敏。
   - 关联告警摘要：最多 20 条，包含 alert_id、来源/目标、风险级别、拦截状态、研判状态、模型摘要、payload 长度与脱敏预览。
   - 案件时间线：最多 50 条，newest-first，包含 event_type、状态变化、detail、note 长度与脱敏预览。
   - 安全声明：报告已做脱敏和截断，完整原始数据只在系统内通过 owner API 查看。
5. 非 owner / 不存在 incident 统一 404，不泄露存在性。
6. 审计日志记录导出动作，但不写完整 title / summary / payload / note / API key / stack trace。

一句话能力声明：

> 安全分析员可以把一个案件一键整理成可分享的脱敏 Markdown 证据报告，用于复盘、交接或提交给上级，而不泄露系统密钥、完整 payload 或私有备注全文。

---

## 2. 非目标

本任务明确不做：

- 不做 PDF / DOCX / HTML 渲染。
- 不引入新依赖、浏览器插件、外部文件生成器或云存储。
- 不持久化导出文件，不新增数据库表或 Alembic migration。
- 不调用 LLM 生成报告，不依赖真实 API key。
- 不做批量案件导出。
- 不做跨用户共享、签名审批、SLA、工单系统、Jira/Slack 集成。
- 不把完整 raw payload、完整 note、完整 system prompt、regex、stack trace、API key 放进报告。

---

## 3. 启动前必读

执行前完整阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`
- `docs/runs/2026-06-18-m3-04-incident-case-workbench.md`
- `docs/runs/2026-06-18-m3-05-incident-aware-copilot-contract.md`
- `docs/runs/2026-06-18-m3-06-test-and-security-quality-gate-closure.md`

必须阅读当前实现：

- `server/routers/incidents_router.py`
- `server/services/incident_service.py`
- `server/routers/export_router.py`
- `server/routers/logs_router.py`
- `server/core/database.py`
- `server/models_db.py`
- `server/tests/test_incidents.py`
- `server/tests/test_incident_persistence.py`
- `server/tests/test_security_timeline.py`
- `web-next/hooks/useIncidents.ts`
- `web-next/types/incident.ts`
- `web-next/components/dashboard/IncidentSection.tsx`
- `web-next/components/dashboard/IncidentDetailPanel.tsx`
- `web-next/components/dashboard/IncidentTimeline.tsx`
- `web-next/components/dashboard/IncidentLinkedAlerts.tsx`
- `web-next/app/api/backend/[...path]/route.ts`

必须遵守：

- TDD：先写后端 contract 测试，确认 RED，再实现。
- API Design：新增端点必须有清晰资源语义、HTTP 状态码、输入校验。
- Security Review：报告导出涉及用户数据、payload、note、审计、下载，必须做安全审查。
- Frontend Patterns：UI 必须贴合现有工作台风格，保持紧凑、可扫描、可操作。
- Verification Loop：完成前必须跑后端相关矩阵、全量后端基线、前端 typecheck/build。

---

## 4. 初始仓库审计

开始改文件前必须创建运行日志：

```text
docs/runs/2026-06-18-m3-07-incident-evidence-report-export.md
```

在运行日志记录：

- 当前分支。
- 当前 `HEAD`。
- `origin/main`。
- `git status --short --branch`。
- 暂存区是否为空。
- 已知本地噪声：
  - `.coverage`
  - `.claude/settings.local.json`
  - `data/*.db`
  - `.env*` 中真实密钥文件
  - 证书 / 私钥 / token / browser profile

停止条件：

- 本地分支落后远端且无法判断 fast-forward。
- 暂存区已有用户改动。
- 工作树出现大量与本任务无关业务改动。
- 发现真实 secret、真实数据库、证书私钥即将被提交。

---

## 5. API 契约

新增案件报告端点，优先放在 `server/routers/incidents_router.py`，作为 incident 子资源，而不是放进全局 `/export`：

```http
GET /incidents/{incident_id}/report?format=json
GET /incidents/{incident_id}/report?format=markdown
```

### 5.1 `format=json`

默认格式建议为 `json`，便于前端拿到 Markdown 字符串后复制 / 下载。

响应示例：

```json
{
  "status": "ok",
  "incident_id": "inc_abc123",
  "filename": "incident-inc_abc123-report.md",
  "markdown": "# 案件证据报告 ...",
  "meta": {
    "generated_at": 1718700000.0,
    "alert_count": 3,
    "included_alerts": 3,
    "event_count": 8,
    "included_events": 8,
    "redaction_count": 2,
    "truncated": false
  }
}
```

要求：

- HTTP 200。
- `status="ok"`。
- `filename` 只能由 `incident_id` 派生，不使用 title，避免文件名注入和泄密。
- `markdown` 是最终报告全文。
- `meta` 只放计数和生成时间，不放敏感正文。

### 5.2 `format=markdown`

可选但建议实现，用于直接下载或命令行调用。

响应要求：

- HTTP 200。
- `Content-Type: text/markdown; charset=utf-8`。
- `Content-Disposition: attachment; filename=incident-<incident_id>-report.md`。
- body 为 Markdown 文本。

如果 Next.js 代理层没有透传 `Content-Disposition`，前端仍应使用 `format=json` 自己创建 Blob 下载；代理层是否透传该 header 由实现阶段判断，必要时可小改 `web-next/app/api/backend/[...path]/route.ts`。

### 5.3 错误语义

- 未登录：401。
- 非 owner / 不存在 incident：404，`detail="案件不存在"` 或沿用现有文案，不区分原因。
- `format` 不在 `json | markdown`：422。
- DB 失败：503，用户可见中文，不暴露 stack trace。

---

## 6. 报告内容规范

报告必须是 Markdown，结构固定，便于复制到飞书、GitHub Issue、工单系统或邮件中。

建议结构：

```markdown
# 案件证据报告

生成时间: 2026-06-18 12:00:00 UTC
案件 ID: inc_xxx
状态: investigating
严重度: high
关联告警: 3

## 1. 案件摘要

...

## 2. 关联告警

| alert_id | source | target | risk | blocked | triage | summary |
|---|---|---|---|---|---|---|

### 告警证据摘录

- alert_id: ...
  - payload_length: 123
  - payload_preview: ...

## 3. 案件时间线

- 2026-06-18 11:59:00 UTC · status_changed · investigating -> contained
  - detail: ...
  - note_length: 42
  - note_preview: ...

## 4. 安全与脱敏说明

本报告由 AI-CyberSentinel 自动生成。报告已对密钥、系统提示词、堆栈、完整 payload 和完整处置备注做脱敏或截断。
```

内容限制：

- incident summary：最长 1000 字符，脱敏。
- alert summary：最长 240 字符，脱敏。
- payload preview：最长 180 字符，脱敏，只作为预览；必须同时给出 `payload_length`。
- event detail：最长 240 字符，脱敏。
- event note preview：最长 160 字符，脱敏，只作为预览；必须同时给出 `note_length`。
- linked alerts：最多 20 条，超出时在报告里写明“仅展示前 20 条，共 N 条”。
- events：最多 50 条，newest-first，超出时写明“仅展示最近 50 条，共 N 条或至少 N 条”。

---

## 7. 脱敏规则

报告正文、JSON `markdown` 字段、Markdown 响应 body 都不得包含：

- `sk-...` / `sk-proj-...`
- `AKIA...`
- `ghp_...`
- `xoxb-...` / `xoxp-...`
- `PRIVATE KEY`
- `Traceback (most recent call last)`
- `system:` / `developer:` / `ignore previous instructions` / `disregard system prompt`
- 完整 raw payload（只允许 preview + length）
- 完整 `IncidentEvent.note`（只允许 preview + length）
- regex 原文、Guardrails 内部 pattern、stack trace

建议实现：

- 新建 `server/services/incident_report_service.py`，集中放报告构造和脱敏 helper。
- 使用纯函数：
  - `sanitize_report_text(text: str, max_chars: int) -> tuple[str, int]`
  - `build_incident_report(detail: dict[str, Any], *, generated_at: datetime | None = None) -> dict[str, Any]`
- `redaction_count` 记录脱敏命中次数。
- 不要在前端重复实现后端脱敏规则；前端只消费后端报告。

---

## 8. 审计要求

每次成功生成报告都写一条 `Log`：

```text
action="incident_report_export"
level="info"
detail="incident_id=inc_xxx;format=json;alert_count=3;event_count=8;redaction_count=2"
```

要求：

- `detail` 不写 title、summary、payload、note、markdown、filename 中 title 派生值。
- 审计写入失败不能让报告生成失败，但必须 `logger.warning`。
- 非 owner / 不存在 incident 不写成功导出 Log。

---

## 9. 后端实施范围

允许修改：

- `server/routers/incidents_router.py`
- `server/services/incident_service.py`（仅必要的小 helper；优先不改）
- `server/services/incident_report_service.py`（建议新增）
- `server/tests/test_incident_report_export.py`（建议新增）
- `server/tests/test_incidents.py`（仅必要时扩展共享 fixture；优先新增独立测试）
- `server/tests/test_security_timeline.py`（仅必要时扩展导出 Log 可见性；非必须）
- `server/routers/export_router.py`（仅当复用导出 helper 必要；优先不改）

不允许修改：

- Alembic migration / 数据库 schema。
- 认证 / JWT / cookie / refresh token。
- `server/security/**`。
- LLM provider registry。
- `/mcp` 鉴权。
- WAF / sniffer 规则。

---

## 10. 后端测试计划

先写 `server/tests/test_incident_report_export.py`，至少覆盖：

1. 未登录请求 `/incidents/{id}/report` 返回 401。
2. owner 请求 `format=json` 返回 `status=ok`、`incident_id`、`filename`、`markdown`、`meta`。
3. owner 请求 `format=markdown` 返回 `text/markdown` 和 Markdown body。
4. 非 owner 请求别人 incident report 返回 404，不区分存在性。
5. 不存在 incident 返回 404。
6. invalid `format=xml` 返回 422。
7. 报告包含 incident 基础信息、关联告警摘要、事件时间线。
8. 报告不包含完整 payload，只包含 `payload_length` 和脱敏 / 截断 preview。
9. 报告不包含完整 note，只包含 `note_length` 和脱敏 / 截断 preview。
10. 报告不包含 fake secret、system prompt、Traceback、PRIVATE KEY、Guardrails regex。
11. 导出成功写 `Log(action="incident_report_export")`，detail 只含安全计数和 id。
12. 大案件截断：25 条 linked alerts 只展示前 20 条，60 条 events 只展示最近 50 条，并在报告中说明。

RED 阶段要求：

- 新测试必须先运行并失败，失败原因应是端点 / service 尚未实现，而不是语法错误或 fixture 坏。

目标验证命令：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_incident_report_export.py -q --tb=short
```

---

## 11. 前端实施范围

允许修改：

- `web-next/types/incident.ts`
- `web-next/hooks/useIncidents.ts`
- `web-next/components/dashboard/IncidentDetailPanel.tsx`
- `web-next/components/dashboard/IncidentSection.tsx`
- `web-next/app/api/backend/[...path]/route.ts`（仅当必须透传下载 header；优先用 JSON + Blob 避免代理 header 依赖）

建议 UI：

- 在 `IncidentDetailPanel` 的“事件时间线”工具区旁边增加两个紧凑按钮：
  - `复制报告`
  - `下载报告`
- 使用 lucide icon：
  - `Clipboard` / `ClipboardCheck`
  - `Download`
  - `Loader2`
- data-testid：
  - `incident-copy-report`
  - `incident-download-report`
  - `incident-report-status`
- 状态文案短小：
  - `生成中`
  - `已复制`
  - `已下载`
  - `报告生成失败`

交互要求：

- 点击复制 / 下载时调用后端 `GET /api/backend/incidents/{incident_id}/report?format=json`。
- 复制使用后端返回的 `markdown`。
- 下载使用 `Blob([markdown], { type: "text/markdown;charset=utf-8" })` + `URL.createObjectURL`，文件名使用后端 `filename`。
- 如果 `navigator.clipboard` 不可用，复制按钮失败但不崩溃；可以提示“复制失败”。
- 不在前端拼报告正文，不在前端读取完整 payload / note 重新组装。

视觉要求：

- 保持当前工作台密度和克制风格，不新增大卡片，不做营销式介绍。
- 不让按钮挤压事件时间线标题；移动端允许换行。
- 按钮内文字不能溢出。

---

## 12. 前端验证计划

必须运行：

```powershell
cd web-next
npm run typecheck
npm run build
```

如果实现触碰 `web-next/app/api/backend/[...path]/route.ts`：

- 必须确认现有 `/api/backend/export/alerts?limit=1000` 不回归。
- 必须确认 `Content-Type`、`Cache-Control`、`X-Content-Type-Options` 仍保留。
- 不允许把 backend 的任意危险 header 原样透传；如需透传，只允许 `Content-Disposition` 这类下载必要 header，并写清安全理由。

---

## 13. 文档同步

必须同步：

- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/runs/2026-06-18-m3-07-incident-evidence-report-export.md`

文档必须说明：

- 新端点。
- 报告内容。
- 脱敏边界。
- owner 隔离。
- 不做 PDF、不调用 LLM、不持久化导出文件。
- 验证命令和结果。

---

## 14. 阶段计划

### 阶段 1：启动审计与运行日志

- 创建 run log。
- 记录 git 状态和远端状态。
- 记录使用的 skill。
- 确认 `.coverage` 等噪声不 stage。

### 阶段 2：产品契约和数据边界确认

- 复核 `incident_service.get_incident_detail` 返回结构。
- 复核 `IncidentEvent.note` / `raw_alert.payload` 的存储和展示边界。
- 复核现有 alert 单条复制报告逻辑。
- 在 run log 写明本任务报告字段 contract。

### 阶段 3：后端 RED 测试

- 新增 `test_incident_report_export.py`。
- 跑单测确认 RED。
- RED 必须来自端点 / service 缺失。

### 阶段 4：后端报告 service 实现

- 新增 `incident_report_service.py`。
- 实现脱敏、截断、Markdown 构造、meta 计数。
- 保持纯函数可测。

### 阶段 5：后端端点接入

- `GET /incidents/{incident_id}/report`。
- owner 隔离复用 `incident_service.get_incident_detail(db, user.id, incident_id, event_limit=50)`。
- format 校验。
- audit Log。
- 错误净化。

### 阶段 6：后端 GREEN 与安全测试

运行：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_incident_report_export.py -q --tb=short
```

再运行：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_incidents.py server\tests\test_incident_persistence.py server\tests\test_security_timeline.py -q --tb=short
```

### 阶段 7：前端类型与 hook 接入

- 扩展 `IncidentReportResponse` 类型。
- `useIncidents` 新增 `buildIncidentReport` / `loadIncidentReport` helper。
- 不把报告正文保存进全局长期 state，避免大字符串滞留；按按钮请求即可。

### 阶段 8：前端 UI 接入

- `IncidentDetailPanel` 增加复制 / 下载报告按钮。
- 状态提示短小、可重试。
- 失败不影响保存、关联告警、AI 分析。

### 阶段 9：文档同步

- 更新 PRODUCT / roadmap / UNATTENDED / run log。

### 阶段 10：安全审查

重点检查：

- 报告正文不含 fake secret / system prompt / stack trace / regex / 完整 note / 完整 payload。
- 审计 Log 不含报告正文。
- 非 owner 404。
- 失败错误不暴露 stack。
- 前端不绕过后端脱敏自行拼报告。
- 无真实 secret、无新 env var、无 schema migration。

### 阶段 11：最终验证矩阵

至少运行：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_incident_report_export.py server\tests\test_incidents.py server\tests\test_incident_persistence.py server\tests\test_copilot_incident_contract.py server\tests\test_demo_flow.py server\tests\security\llm_guardrails -q --tb=short
```

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

```powershell
cd web-next
npm run typecheck
npm run build
```

### 阶段 12：精确 commit / push

只有满足以下条件才允许 commit / push：

- run log 完整。
- 禁提交文件未 stage。
- 后端目标测试通过。
- 后端全量基线通过。
- 前端 typecheck/build 通过。
- 安全审查已写入 run log。

禁止 `git add .`。

建议 commit：

```text
test(incidents): 覆盖案件证据报告导出契约
feat(incidents): 增加案件证据报告导出
feat(dashboard): 支持复制和下载案件报告
docs(incidents): 记录案件报告导出边界
```

push：

```powershell
git status --short --branch
git log --oneline --decorate -8
git push origin main
```

---

## 15. 验收标准

最低验收：

- `GET /incidents/{incident_id}/report?format=json` 可用。
- owner 可生成报告；非 owner / 不存在 404。
- 报告不泄露完整 payload / note / fake secret / system prompt / stack trace。
- 导出成功写脱敏 audit Log。
- 前端案件详情可复制 / 下载报告。
- 后端相关测试 + 前端 typecheck/build 通过。

目标验收：

- `format=markdown` 也可用。
- 大案件截断行为有测试。
- 后端 `server/tests` 全绿。
- Guardrails 专项无回归。
- 文档同步完整。
- 精确 commit / push 到 `origin/main`。

---

## 16. 停止条件

满足任一条件必须停止并写清楚：

1. 同一个失败连续修复 3 轮仍失败。
2. 需要新增数据库表 / migration 才能继续。
3. 需要引入 PDF / DOCX / 外部渲染依赖。
4. 为满足报告内容必须导出完整 raw payload 或完整 private note。
5. 需要修改认证 / JWT / cookie。
6. 需要改 `server/security/**` 核心护栏。
7. diff 超过约 1500 行且不是测试 / 文档为主。
8. 后端全量测试出现大量无关失败。
9. 远端 main 前进，无法安全 fast-forward。

停止时必须交付：

- 已完成内容。
- 未完成内容。
- 阻塞原因。
- 下一条最小工单。

---

## 17. 完成时输出

最终报告必须包含：

- 完成状态：完成 / 部分完成 / 阻塞。
- 新增端点与前端入口。
- 改动文件列表。
- 运行过的验证命令和结果。
- 安全审查结论。
- run log 路径。
- commit 列表和 push 状态。
- 剩余问题与下一条建议工单。

---

## 18. 给 agent 的短启动口令

```text
请执行 `docs/agent/M3_07_INCIDENT_EVIDENCE_REPORT_EXPORT_TASK.md` 中定义的 L5 超长任务。先完整阅读该文件和其中列出的必读上下文，创建运行日志，按 TDD 先写后端报告导出契约测试并确认 RED，再实现后端报告 service、incident report 端点、前端复制/下载入口和文档同步；不要问我小问题，不要新增数据库迁移，不要引入 PDF/DOCX/外部渲染依赖，不要调用 LLM 生成报告，不要导出完整 payload/note/secret/system prompt/stack trace，不要使用 git add .，不要提交 `.coverage`、`.claude/settings.local.json`、真实 env、数据库或密钥。满足质量门后可以按文档精确 commit 并 push 到 `origin/main`，完成后按任务文档输出最终报告。
```
