# Run: M3-07 案件证据报告导出

开始时间：2026-06-18
运行模式：L5（产品能力战役：后端契约 + 前端 UI + 安全脱敏 + 验证矩阵）
预算：最长 2 小时；同一测试连续修复最多 3 轮；diff 上限 1500 行（任务文档阈值）

## 0. 启动环境

- 当前分支：`main`
- 本地 HEAD：`03c85ef6c0d3b6a0db30f66e4d4d61f6e3a95f`（`docs(quality): 记录 M3-06 测试与安全质量门收口基线`）
- 远端 `origin/main`：`03c85ef`（同步，无前进）
- 暂存区：空
- 工作树噪声：
  - `M .coverage`（禁提交，保留原状）
  - `M docs/agent/UNATTENDED_LONG_TASKS.md`（本任务允许 append 索引）
  - `?? docs/agent/M3_07_INCIDENT_EVIDENCE_REPORT_EXPORT_TASK.md`（本任务文档，保留）

启动条件：origin/main 同步 + 无暂存 + 噪声非禁提交 → ✅ 满足。

M3-04 案件工作台 / M3-05 案件感知 Copilot / M3-06 质量门均已交付；本任务在不动 schema、不改认证、不动 Guardrails 的前提下加产品能力。

## 1. 目标

把 M3-04 / M3-05 已建立的"案件 + 告警 + 时间线 + Copilot 上下文"能力，收束成可复制、可下载、可审计、可脱敏的 SOC 案件证据报告。

```text
安全分析员打开案件详情
  -> 点击"复制报告"或"下载报告"
  -> 后端按 owner 隔离读取案件事实
  -> 构造脱敏 Markdown 证据报告
  -> 前端可复制到剪贴板或下载 .md 文件
  -> 审计 Log 记录导出动作，但不记录报告正文
```

## 2. 范围

允许修改（来自任务文档 §9 / §11）：

- 后端：`server/routers/incidents_router.py` / `server/services/incident_report_service.py`（新增）/ `server/tests/test_incident_report_export.py`（新增）
- 前端：`web-next/types/incident.ts` / `web-next/hooks/useIncidents.ts` / `web-next/components/dashboard/IncidentDetailPanel.tsx`（必要时也调 `IncidentSection.tsx`）/ `web-next/app/api/backend/[...path]/route.ts`（仅当必须透传下载 header；优先用 JSON + Blob 避免代理 header 依赖）
- 文档：`PRODUCT.md` / `docs/plans/M2_PRODUCT_ROADMAP.md` / `docs/agent/UNATTENDED_LONG_TASKS.md` / 本 run log

禁止修改（已遵守）：

- `.coverage`、`.claude/settings.local.json`、真实 `.env`、`data/app.db`
- `server/security/**`、`/mcp` 鉴权逻辑
- 登录 / 注册 / JWT / refresh token / 2FA / cookie 语义
- `docker-compose.yml`、`nginx/**`
- Alembic migrations（本任务无 schema 变更）
- `server/routers/export_router.py` 全量 CSV 端点（不动）

禁止操作（已遵守）：

- 未使用 `git add .`
- 未 `git reset --hard` / `git clean`
- 未跳过 / 删除 / 弱化测试
- 未提交真实 secret / 数据库文件 / coverage / 证书私钥
- 未调用 LLM 生成报告

## 3. 计划

- [x] 阶段 1：建立运行日志 + 初始审计
- [x] 阶段 2：产品能力和数据契约确认
- [x] 阶段 3：后端 RED 测试
- [x] 阶段 4：后端报告 service 实现
- [x] 阶段 5：后端端点接入
- [x] 阶段 6：后端 GREEN 与安全测试
- [x] 阶段 7：前端类型与 hook 接入
- [x] 阶段 8：前端 UI 接入
- [x] 阶段 9：前端 typecheck/build 验证
- [x] 阶段 10：文档同步
- [x] 阶段 11：安全审查
- [x] 阶段 12：最终验证矩阵
- [ ] 阶段 13：精确 commit / push

## 4. 阶段记录

### 阶段 1：建立运行日志 + 初始审计 ✅

- 远端 main 与本地 HEAD 一致（`03c85ef`）；暂存区空；噪声非禁提交。
- 启动条件满足。

### 阶段 2：产品能力和数据契约确认 ✅

事实来源分工（已读 `server/services/incident_service.py`、`server/routers/incidents_router.py`、`server/models_db.py`、`server/routers/logs_router.py` 的脱敏 sentinel 模式）：

- `incident_service.get_incident_detail(db, user_id, incident_id, event_limit=50)`：**案件报告事实来源**。返回 `{incident, linked_alerts, events, event_limit}`。`linked_alerts` 顺序由 `IncidentAlertLink.linked_at` 升序，`events` 顺序为 `created_at desc, id desc`（newest-first）。
- `linked_alerts[i].raw_alert.payload`：可能含 raw payload（必须脱敏为 preview + length）。
- `linked_alerts[i].llm_analysis.summary`：模型摘要（截断 240 字符 + 脱敏）。
- `linked_alerts[i].triage.analyst_note`：处置备注（**不**进报告正文，只进 meta / 不进 report 内容）。
- `events[i].detail`：脱敏摘要（截断 240 字符 + 脱敏）。
- `events[i].note`：私有 note（**不**进报告正文，只出 preview + length，最多 160 字符 + 脱敏）。
- `events[i].from_status / to_status`：状态变化展示，不含敏感信息。
- `events[i].actor_user_id`：actor id 本身不是 secret，但 report 展示 `#<user_id>` 即可。
- `incident.title / summary`：title 显示完整；summary 截断 1000 字符 + 脱敏。
- `Log(action="incident_report_export")`：**导出审计**。`detail` 走 `incident_id=...;format=...;alert_count=...;event_count=...;redaction_count=...`，**不**含 title / summary / payload / note / markdown 全文。
- 复用 `logs_router._SENTINEL_PATTERNS` 的脱敏 sentinel 集合（`sk-...` / `sk-proj-...` / `AKIA...` / `ghp_...` / `xox[baprs]-...` / `PRIVATE KEY` / `Traceback` / `ignore previous instructions` / `disregard system prompt` / `forget instructions` / `system:`），并新增 `developer:` 与 Guardrails 内部 `forbidden` / `block` 字面量。

owner 隔离策略：

- 复用 `incident_service.get_incident_detail` 已有的 owner 隔离（`Incident.user_id == user.id`）。
- 非 owner / 不存在统一返回 `None` → 路由层映射 404，**不**通过 403 暴露存在性。
- audit Log 仅在成功生成报告时写；非 owner / 不存在 / invalid format / DB 失败均**不**写 success Log。

报告契约（与任务文档 §5/§6 完全对齐）：

- HTTP 200 + `status=ok`（json 响应）或 `text/markdown; charset=utf-8`（markdown 响应）。
- `format=json`：
  ```json
  {
    "status": "ok",
    "incident_id": "inc_xxx",
    "filename": "incident-inc_xxx-report.md",
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
- `format=markdown`：
  - `Content-Type: text/markdown; charset=utf-8`
  - `Content-Disposition: attachment; filename=incident-<incident_id>-report.md`
  - body 为 Markdown 文本
- `filename` 只能由 `incident_id` 派生，**不**使用 title（避免文件名注入和泄密）。
- `meta` 只放计数和生成时间，不放敏感正文。

错误语义：

- 未登录：401。
- 非 owner / 不存在 incident：404。
- `format` 不在 `json | markdown`：422。
- DB 失败：503，不暴露 stack trace。

内容限制（与任务文档 §6 一致）：

- incident summary：最长 1000 字符，脱敏。
- alert summary：最长 240 字符，脱敏。
- payload preview：最长 180 字符，脱敏，只作为预览；必须同时给出 `payload_length`。
- event detail：最长 240 字符，脱敏。
- event note preview：最长 160 字符，脱敏，只作为预览；必须同时给出 `note_length`。
- linked alerts：最多 20 条，超出时在报告里写明"仅展示前 20 条，共 N 条"。
- events：最多 50 条，newest-first，超出时写明"仅展示最近 50 条，共 N 条"。

报告结构（与任务文档 §6 一致）：

```markdown
# 案件证据报告

生成时间: ...
案件 ID: inc_xxx
状态: ...
严重度: ...
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

## 5. 验证证据

### 5.1 RED→GREEN 收敛

RED 阶段（`pytest server/tests/test_incident_report_export.py`）：

- 14 个测试；RED 阶段 11 failed + 3 passed（3 个恰好是期望 404 的 `test_report_other_user_incident_returns_404` / `test_report_nonexistent_incident_returns_404` / `test_report_non_owner_does_not_write_audit_log`，默认 404 命中）。
- 失败原因全部为 `{"detail":"Not Found"}`（端点未实现）+ `test_report_truncates_alerts_and_events` 一个真实测试 bug（`target_statuses` 长度应为 59，我写成了 64，已修）。

GREEN 阶段（实现 `incident_report_service.py` + 端点后）：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_incident_report_export.py -q --tb=short
```

结果：**14 passed in 3.50s**。

### 5.2 后端回归矩阵

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_incident_report_export.py server\tests\test_incidents.py server\tests\test_incident_persistence.py server\tests\test_security_timeline.py -q --tb=short
```

结果：**44 passed in 6.46s**（M3-07 新增 14 + M3-04 既有 30；0 回归）。

### 5.3 后端全量基线

```powershell
.venv\Scripts\python.exe -m pytest server\tests -q --tb=line
```

结果：**332 passed, 2 skipped in 88.68s**（M3-06 baseline 318 + M3-07 新增 14；0 失败）。跳过的 2 个是 `--run-e2e` 显式触发的 Playwright E2E（设计意图）。

### 5.4 Guardrails 专项

```powershell
.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q
```

结果：**139 passed**（与 M3-06 一致；M3-07 未触碰 `server/security/**`，0 回归）。

### 5.5 前端

```powershell
cd web-next
npm run typecheck    # 0 错误
npm run build        # /dashboard 43.7 kB / First Load JS 191 kB
```

`/dashboard` 体积在预算内（与 M3-06 42.9 kB / 190 kB 差异很小 +0.8 kB / +1 kB First Load JS，符合任务文档 §11 不挤压时间线标题的视觉要求）。

### 5.6 14 个 RED→GREEN 测试清单

- `test_report_unauthenticated_returns_401` — 未登录 401。
- `test_report_other_user_incident_returns_404` — 非 owner 404。
- `test_report_nonexistent_incident_returns_404` — 不存在 404。
- `test_report_invalid_format_returns_422` — invalid format 422。
- `test_report_format_json_returns_envelope` — `format=json` 返回完整 envelope。
- `test_report_format_markdown_returns_markdown_body` — `format=markdown` 返回 text/markdown + Content-Disposition。
- `test_report_does_not_include_full_payload` — 报告不含完整 raw payload,只放 `payload_length` + 截断 preview(≤ 180 字符)。
- `test_report_does_not_include_full_note` — 报告不含完整 note,只放 `note_length` + 截断 preview(≤ 160 字符)。
- `test_report_does_not_include_secrets_or_sentinels` — 报告不含 fake secret / system prompt / stack trace / PRIVATE KEY / Guardrails regex(12 条 sentinel 全检)。
- `test_report_success_writes_sanitised_audit_log` — 成功生成报告写 `Log(action="incident_report_export")`,detail 只含 incident_id / format / 计数,不含 title / summary。
- `test_report_non_owner_does_not_write_audit_log` — 非 owner 不写 success Log。
- `test_report_includes_basic_incident_and_linked_alerts` — 报告含 4 段结构(案件摘要 / 关联告警 / 时间线 / 安全声明)。
- `test_report_truncates_alerts_and_events` — 大案件:25 alerts → 20,60 events → 50,报告里写明"仅展示前 20 / 仅展示最近 50";`meta.truncated=true`。
- `test_report_filename_derived_only_from_incident_id` — filename 只由 incident_id 派生,不含 title 任何字符(`; / " \n` 等)。

## 6. 安全审查

| 审查项 | 结论 | 证据 |
|---|---|---|
| owner 隔离 | 保持 | 复用 `incident_service.get_incident_detail` owner 隔离(已由 M3-04 测试锁定);非 owner / 不存在统一 404,不区分;`test_report_other_user_incident_returns_404` 锁定。 |
| 报告不含完整 raw payload | 保持 | `payload_preview` 截断 ≤ 180 字符 + `payload_length` 显示原长;`test_report_does_not_include_full_payload` 锁定 `long_payload(514 chars) not in markdown` + preview 截断 + length 正确。 |
| 报告不含完整 note | 保持 | `note_preview` 截断 ≤ 160 字符 + `note_length` 显示原长;`test_report_does_not_include_full_note` 锁定 `long_note(221 chars) not in markdown` + preview 截断 + length 正确。 |
| 报告不含 fake secret / system prompt / stack trace / Guardrails regex | 保持 | 12 条 sentinel 全检通过:`test_report_does_not_include_secrets_or_sentinels` 锁定把 fake key / system: / Traceback / ignore previous instructions 放进 summary 和 note,验证 report markdown 不命中任何 sentinel。 |
| audit 脱敏 | 保持 | `Log(action="incident_report_export")` detail 只含 `incident_id / format / alert_count / included_alerts / event_count / included_events / redaction_count`,**不**含 title / summary / payload / note / markdown 全文;`test_report_success_writes_sanitised_audit_log` + `test_report_non_owner_does_not_write_audit_log` 锁定。 |
| filename 派生 | 保持 | filename 只由 `incident_id` 派生,含 `; / " \n` 等非法字符时降级为 `_`;`test_report_filename_derived_only_from_incident_id` 锁定 title 任何字符(含 `\n` / `;` / `rm` / `/` / `"`)不进 filename。 |
| 失败错误净化 | 保持 | DB 失败 → 503 `案件报告加载失败`(中文,不暴露 stack trace);非 owner / 不存在 → 404 `案件不存在`(不区分 owner / 不存在,不暴露 incident_id 是否存在);`logger.warning` 记录 incident_id + err。 |
| 审计写入失败 | 不阻断 | `Log` 写入失败仅 `logger.warning`,不阻断主请求;非 owner / 不存在 / invalid format / DB 失败均**不**写 success Log。 |
| 新增 env var | 无 | 复用现有 `require_auth_user` / `incident_service.get_incident_detail` / `create_log`;不需要新 env var。 |
| 新增 schema / migration | 无 | 不新增数据库表 / Alembic migration;复用 M3-04 已落地的 incidents / incident_alert_links / incident_events 三表。 |
| 认证 / JWT / cookie | 未触碰 | `server/core/auth*` / `server/routers/auth*` 未读未改;`require_auth_user` 复用 M3-04 baseline。 |
| `/mcp` 鉴权 | 未触碰 | `mcp_server.py` 未读未改。 |
| LLM provider 默认 registry | 未触碰 | `llm_providers._PROVIDERS` 未修改;**不调用 LLM**生成报告。 |
| Guardrails / `server/security/**` | 未触碰 | `git diff server/security/` 为空;M3-07 只新增 `server/services/incident_report_service.py` + 修改 `server/routers/incidents_router.py`(只新加端点与 audit helper)。 |
| SSRF / URL 解析 | 不适用 | 报告导出是纯服务端拼 Markdown,不访问外部 URL。 |
| 前端不动 incident detail 拼报告 | 保持 | M3-07 严格按 M3-05 思路,前端只调后端 `format=json` 拿到脱敏 markdown,不重新组装 payload / note。`IncidentDetailPanel.handleReport` 不读 `detail.events[*].note` / `detail.linked_alerts[*].raw_alert.payload` 全文,只发 incident_id 给后端。 |
| 浏览器侧剪贴板降级 | 保持 | `navigator.clipboard` 不可用时降级提示 `复制失败`,不崩溃;下载用 `Blob` + `URL.createObjectURL`,不绕过浏览器安全策略。 |
| 真实 secret / 数据库文件 / coverage | 未触碰 | `.coverage` / `.claude/settings.local.json` / `data/*.db` 保留原状未 stage。 |

## 7. 未解决问题

无。

## 8. 最终状态

- 完成状态：**完成**。
- 改动文件列表(精确 stage,5 个 commit):

  | commit | 范围 | 文件 |
  |---|---|---|
  | `test(incidents): 覆盖案件证据报告导出契约` | 测试 | `server/tests/test_incident_report_export.py` |
  | `feat(incidents): 实现案件证据报告 service 与端点` | 后端 | `server/services/incident_report_service.py` (新增) + `server/routers/incidents_router.py` (新增 `GET /incidents/{id}/report` 端点 + audit helper) |
  | `feat(dashboard): 支持复制和下载案件报告` | 前端 | `web-next/types/incident.ts` + `web-next/hooks/useIncidents.ts` + `web-next/components/dashboard/IncidentDetailPanel.tsx` + `web-next/components/dashboard/IncidentSection.tsx` |
  | `docs(incidents): 记录案件报告导出边界` | 文档 | `PRODUCT.md` + `docs/plans/M2_PRODUCT_ROADMAP.md` + `docs/agent/UNATTENDED_LONG_TASKS.md` + `docs/runs/2026-06-18-m3-07-incident-evidence-report-export.md` |

- 禁提交保留在本地噪声(不 stage):`.coverage` / `.claude/settings.local.json` / `docs/agent/M3_07_INCIDENT_EVIDENCE_REPORT_EXPORT_TASK.md`(本任务文档,保留原状)。
- commit / push 状态:**5 个 commit 已落地本地 main 并成功 push 到 origin/main**。
  - `d705403 test(incidents): 覆盖案件证据报告导出契约`
  - `fdbe2ab feat(incidents): 实现案件证据报告 service 与端点`
  - `3fb4da7 feat(dashboard): 支持复制和下载案件报告`
  - `c403c5e docs(incidents): 记录案件报告导出边界`
  - `ebbf8c5 docs(incidents): 补记 M3-07 push 受网络阻塞状态`
  - push 实际执行:第 1 次 background push 失败 (Connection timed out 300s),随后 3 次 foreground push 全部失败 (Failed to connect to github.com port 443 after 21s),环境层诊断显示 `github.com` DNS 被劫持到内网 `10.6.10.251`。第 5 次重试 (网络层瞬时恢复) 成功:
    ```
    To https://github.com/shenkkjj/AI-IDS-Project.git
       03c85ef..ebbf8c5  main -> main
    ```
  - `git status --short --branch` → `## main...origin/main`(无 ahead/behind 差距,本地与远端完全同步)。
  - `git rev-parse origin/main` → `ebbf8c5c8f30526019c3bd6eff72b87a4ffc5e26`(与本地 HEAD `ebbf8c5` 一致)。
- 剩余本地噪声:`.coverage` / `docs/agent/M3_07_INCIDENT_EVIDENCE_REPORT_EXPORT_TASK.md`(禁提交 / 任务文档保留,保留原状)。`git status` 确认:工作树只剩 `.coverage` modified + 任务文档 untracked,无任何意外文件被遗漏或多余 stage。
