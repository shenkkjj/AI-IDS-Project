# Run: M3-05 案件感知 Copilot 合约

开始时间：2026-06-18
运行模式：L5（高风险 LLM 上下文 + 安全审查 + 前后端契约战役）
预算：最长 2 小时；同一测试连续修复最多 3 轮；diff 上限 1600 行（任务文档阈值；非测试/文档为 800 行）

## 0. 启动环境

- 当前分支：`main`
- 本地 HEAD：`1c2f45bb82e987c51d8dee29e10190c212505d91`
- 远端 `origin/main`：`1c2f45bb82e987c51d8dee29e10190c212505d91`（同步，无前进）
- 暂存区：空
- 工作树噪声：
  - `M .claude/settings.local.json`（禁提交，保留原状）
  - `M .coverage`（禁提交，保留原状）
  - `M docs/agent/UNATTENDED_LONG_TASKS.md`（本任务允许 append 索引；已包含 M3-05 占位）
  - `?? docs/agent/M3_05_INCIDENT_AWARE_COPILOT_CONTRACT_TASK.md`（本任务文档，保留）

启动条件：`origin/main` 未前进 + 无暂存 + 噪声文件均非禁提交 → ✅ 满足。

M3-04 已交付（`docs/runs/2026-06-18-m3-04-incident-case-workbench.md`），incident 三表 + API + 前端工作台 + 前端拼接 Copilot 提示词已落地。

## 1. 目标

把 M3-04 的"前端拼接案件摘要"升级为"后端受控、可测试、owner 隔离、Guardrails 不绕过"的 incident-aware Copilot contract。

目标闭环：

```text
案件工作台"用 AI 分析案件"按钮
  -> 前端只发 incident_id + 短意图
  -> 后端 owner 隔离加载案件上下文
  -> 构造受控 context_block
  -> Guardrails 输入检查不绕过
  -> SSE 错误净化（不暴露 reason/regex/stack）
  -> Provider 流式输出
  -> audit log 记录 incident_id 维度
```

## 2. 范围

允许修改（来自任务文档 §7）：

- 后端：`server/models/schemas.py` / `server/routers/copilot_router.py`（仅必要时）/ `server/services/copilot_service.py` / `server/services/incident_service.py`（仅导出 / helper 必要小改）/ `server/tests/test_copilot_contract.py` / `server/tests/test_copilot_incident_contract.py`（新增）
- 前端：`web-next/hooks/useCopilot.ts` / `web-next/components/dashboard/IncidentDetailPanel.tsx` / `web-next/app/dashboard/dashboard-client.tsx` / `web-next/types/copilot.ts` / `web-next/components/dashboard/CopilotSection.tsx`（必要时）
- 文档：`PRODUCT.md` / `docs/plans/M2_PRODUCT_ROADMAP.md` / `docs/agent/UNATTENDED_LONG_TASKS.md` / `docs/runs/2026-06-18-m3-05-incident-aware-copilot-contract.md`

禁止修改（已遵守）：

- `.coverage`、`.claude/settings.local.json`、真实 `.env`、`.env.compose.local`、`data/app.db`
- `server/security/**`（原则不触碰）、`/mcp` 鉴权逻辑
- 登录 / 注册 / JWT / refresh token / 2FA / cookie 语义
- `docker-compose.yml`、`nginx/**`
- Alembic migrations（本任务无 schema 变更）

禁止操作（已遵守）：

- 未使用 `git add .`
- 未 `git reset --hard` / `git clean`
- 未跳过 / 删除 / 弱化测试
- 未提交真实 secret / 数据库文件 / coverage / 证书私钥

## 3. 计划

- [ ] 阶段 1：建立运行日志 + 初始审计
- [ ] 阶段 2：产品能力和数据契约确认
- [ ] 阶段 3：RED 测试覆盖
- [ ] 阶段 4：后端 schema + context builder 实现
- [ ] 阶段 5：后端 router + Guardrails 顺序 + SSE 净化
- [ ] 阶段 6：后端 GREEN 验证
- [ ] 阶段 7：前端 useCopilot + IncidentDetailPanel 改造
- [ ] 阶段 8：前端 typecheck/build 验证
- [ ] 阶段 9：文档同步
- [ ] 阶段 10：安全审查
- [ ] 阶段 11：质量门
- [ ] 阶段 12：精确 commit / push

## 4. 阶段记录

### 阶段 2：产品能力和数据契约确认 ✅

事实来源分工：

- `CopilotStreamIn(incident_id=...)`：新加可选字段，与 `alert_id` 可独立；二者同时给定时 **incident 优先**，`alert_id` 只作为 `selected_alert_id` 写入 context，不额外读 alert payload。
- `incident_service.get_incident_detail(db, user_id, incident_id, event_limit=5)`：**案件上下文事实来源**。复用 M3-04 owner 隔离（按 `user_id` 过滤）+ `event_limit=5`。
- `_load_incident_context(db, user, incident_id)`：薄壳，调用 `incident_service.get_incident_detail`；非 owner / 不存在 → `None`，路由层映射 SSE error。**不区分不存在 / 非 owner**。
- `_build_context_from_incident(detail, selected_alert_id=None)`：构造受控 context_block。最多 5 条 linked_alerts / 5 条 events；event note **不**进 context，只进 `note_length`；payload **不**进 context，只进 `payload_length`；summary 截断 500 字符，alert summary 截断 160 字符。
- `Log(action="copilot_stream")` **detail 扩展**：在原 `provider=...;model=...;alert_id=...` 之后追加 `;incident_id=...`。**不**写 title / summary / note / payload / secret。
- `server/security/llm_guardrails/**`：**不触碰**；Guardrails 仍在 provider 前执行；block 后 provider 不调用。
- SSE error **净化**：不暴露 reason / regex / stack trace，只暴露 category 摘要。incident 不存在错误走独立中文消息 "案件上下文不可用或不存在"，**不**与 Guardrails block 错误混用。

owner 隔离策略：

- `_load_incident_context` 走 `incident_service.get_incident_detail(db, user.id, incident_id, event_limit=5)`，service 层按 `user_id` 过滤。
- 非 owner / 不存在统一返回 `None` → SSE error + provider 不调用。
- 不通过 403 暴露 incident_id 是否存在。

Guardrails 顺序（推荐顺序，与 M2 SOC 运营基线一致）：

```text
rate limit -> user config -> context lookup -> Guardrails input -> create Log -> provider stream
```

要求：

- incident path 不能绕过 Guardrails。
- Guardrails block 后 provider 不调用。
- SSE error 不能暴露 full reason / regex / stack trace。
- incident 不存在 / 非 owner 时**不**走 Guardrails（context lookup 失败先于 Guardrails 返回）。

事件 timeline 返回顺序：`newest-first`（与 M3-04 / M3-03 一致）。

### 阶段 4：后端 schema + context builder 实现 ✅

`server/models/schemas.py::CopilotStreamIn` 新增:

```python
incident_id: str | None = Field(default=None, max_length=64)
```

`server/services/copilot_service.py` 新增:

- 常量: `_INCIDENT_SUMMARY_MAX=500` / `_ALERT_SUMMARY_MAX=160` /
  `_INCIDENT_CONTEXT_ALERT_LIMIT=5` / `_INCIDENT_CONTEXT_EVENT_LIMIT=5` /
  `_INCIDENT_NOT_FOUND_SSE_ERROR="案件上下文不可用或不存在"`。
- `_truncate_context_value(value, max_chars)` 通用截断。
- `_build_context_from_incident(detail, *, selected_alert_id=None)` 构造受控
  context_block,最多 5 条 linked_alerts + 5 条 events;event note **不**进 context
  (只放 `note_length`);alert payload **不**进 context(只放 `payload_length`);
  event detail 走 160 字符截断。
- `_load_incident_context(db, user, incident_id)` 走
  `incident_service.get_incident_detail(db, user.id, incident_id, event_limit=5)`,
  非 owner / 不存在统一 `None`。
- `copilot_stream` 重构 context lookup 顺序: rate limit -> user config ->
  context lookup -> Guardrails input -> create_log -> provider stream。
  - `data.incident_id` 优先;lookup 失败 → SSE error "案件上下文不可用或不存在" + return。
  - `data.alert_id` 仅作 `selected_alert_id` 写入,不再额外读 alert payload。
  - 仅有 `alert_id` 时仍走 `_build_context_from_alert`(M2 基线保留)。
- audit log `detail` 扩展: `provider=...;model=...;alert_id=...;incident_id=...`
  (incident_id 仅在提供时出现);不写 title / summary / note / payload / fake key。
- 新 import `from server.services import incident_service`(放在模块顶部,
  让 `_load_incident_context` 可被 monkeypatch `server.services.copilot_service.incident_service`)。

### 阶段 5：后端 router + Guardrails 顺序 + SSE 净化 ✅

- `server/routers/copilot_router.py` **不需要修改**:`CopilotStreamIn` 已在
  Pydantic 层接受 `incident_id`;`copilot_stream` 内部已处理。
- Guardrails 顺序: 仍 `context lookup -> Guardrails input -> provider stream`,
  incident 存在时 Guardrails 正常拦截,block 后 provider 不调用;
  incident 不存在时早于 Guardrails 返回 SSE error(不区分 owner / 不存在)。
- SSE 错误净化: incident 不存在 → `案件上下文不可用或不存在`,**不**暴露
  reason / regex / stack trace;Guardrails block → `请求被安全护栏拦截(类别: <category>)`。
  这两条独立,互不混用。

### 阶段 6：后端 GREEN 验证 ✅

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_copilot_contract.py server\tests\test_copilot_incident_contract.py server\tests\test_incidents.py server\tests\test_incident_persistence.py server\tests\test_alert_triage.py server\tests\test_alert_triage_persistence.py server\tests\test_demo_flow.py -q --tb=short
```

结果: **58 passed, 1 failed, 17 warnings in 11.11s**。

唯一失败: `test_demo_alert_can_drive_copilot_fallback` 在 NeMo Guardrails
`moderation_unavailable` 错误上;**经 `git stash` + 同测试在 M3-04 baseline
(1c2f45b) 复跑确认是预存失败**,与 M3-05 改动无关。M3-04 run log
`docs/runs/2026-06-18-m3-04-incident-case-workbench.md` 已记录 "12 个预存失败
(LLM Colang flows 9 个 + SSRF 3 个)"。本任务不触碰 `server/security/**`,不引入新失败。

新测试 9/9 通过,既有测试无回归。

### 阶段 3：RED 测试覆盖 ✅

新增 `server/tests/test_copilot_incident_contract.py`（9 个测试）:

- schema: `CopilotStreamIn` 接受 / 拒长 / 可选 `incident_id`。
- happy path: fake provider 收到受控 context_block,包含 `[当前安全案件上下文]` / `incident_id:` / `severity:` / `status:` / 关联告警段 / 案件事件段。
- incident 缺失: SSE error 含 `案件上下文不可用或不存在`,fake provider call_count == 0。
- Guardrails block with valid incident: fake provider call_count == 0,SSE 不暴露 reason / regex。
- audit log: detail 含 `incident_id=inc-test`,不写 title / summary / note / fake key / stack trace。
- 截断: 10 alerts + 10 events → context 只含前 5 条;长 summary 截断;note / payload 全文不进 context。
- alert_id + incident_id: incident 优先,`selected_alert_id: alert-marker-99` 行出现,`alert_id: alert-marker-99` 不出现。

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_copilot_incident_contract.py -q --tb=short
```

结果: **9 failed in 1.05s**。失败原因:

- schema 缺 `incident_id` 字段 (3 个 schema 测试) → 后续需在 `CopilotStreamIn` 加字段。
- 其余 6 个测试在 `_stub_incident` 处 `monkeypatch.setattr("server.services.copilot_service.incident_service.get_incident_detail", ...)` ImportError → 后续需在 `copilot_service.py` `from server.services import incident_service`,并加 `_load_incident_context` / `_build_context_from_incident` 内部函数。

确认: RED 失败原因与设计目标一致,不是语法错误或环境问题。

### 阶段 7：前端 useCopilot + IncidentDetailPanel 改造 ✅

- `web-next/hooks/useCopilot.ts`:
  - 新增导出 `SendMessageOptions = { incidentId?: string | null; alertId?: string | null }`。
  - `sendMessage(messageText, options?)` 接受 options,显式 `incidentId` 时 hint 锁定为 `案件上下文: inc_xxx`,body 注入 `incident_id`。
  - `alertId` 显式覆盖优先级高于 `selected?.alertId` 回退。
  - 新增 `activeIncidentId` state,useEffect 优先显示 incident 上下文 hint。
- `web-next/components/dashboard/IncidentDetailPanel.tsx`:
  - 删 `buildCopilotPrompt(detail)` 函数及 `export`,删 `sessionStorage` 中间态写入。
  - `handleCopilot` 改为派发 `{ prompt: "请分析当前安全案件,给出风险、证据、影响和下一步处置。", incidentId: detail.incident.incident_id }`。
  - 依赖收窄为 `detail.incident.incident_id`(去掉无关的 `detail` 全对象)。
- `web-next/app/dashboard/dashboard-client.tsx`:
  - 监听 `incident:copilot` 事件,提取 `incidentId` 后调 `copilotCtx.sendMessage(prompt, { incidentId })`;无 incidentId 时回退到旧路径。
  - 注释从"M3-04 监听拼好的 prompt"更新为"M3-04 / M3-05 短意图 + incidentId"。

### 阶段 8：前端 typecheck/build 验证 ✅

```powershell
cd web-next
npm run typecheck
npm run build
```

结果:

- typecheck 0 错误(`next typegen && tsc --noEmit` 成功,路由类型生成 OK)。
- build 成功(3.2s,`/dashboard` 42.9 kB / First Load JS 190 kB,在预算内)。
- 浏览器 E2E 缺本地 Chrome,未跑;与 M3-04 状态一致。

### 阶段 9：文档同步 ✅

- `PRODUCT.md` §2.2 第 12 项 + §2.2 段末未变;新条目完整记录 M3-05 边界。
- `docs/plans/M2_PRODUCT_ROADMAP.md` §8 新增"M3-05 案件感知 Copilot 合约(2026-06-18 已交付)"段,含 schema / context builder / Guardrails 顺序 / SSE 净化 / audit 脱敏 / 9 个 fake provider 测试 / 前端 3 文件改动 / 不做项 / 运行日志路径。
- `docs/agent/UNATTENDED_LONG_TASKS.md` M3-05 索引更新为"已交付 + 2026-06-18 落点"完整说明。
- run log:本文件全阶段证据。

### 阶段 10：安全审查 ✅

见下方"安全审查"小节。

### 阶段 11：质量门 ✅

见下方"验证证据"小节。

### 阶段 12：精确 commit / push ✅

见下方"最终状态"小节。

### 阶段 1：建立运行日志 + 初始审计 ✅

- 远端 main 与本地 HEAD 一致（`1c2f45b`）；暂存区空；本地噪声仅 `.claude/settings.local.json` / `.coverage`（禁提交）、`docs/agent/UNATTENDED_LONG_TASKS.md`（本任务允许 append 索引）、未追踪的 `docs/agent/M3_05_*.md` 任务文档。
- 启动条件满足。
- M3-04 交付已通过历史 run log 复核。

## 5. 验证证据

### 5.1 后端 pytest

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_copilot_contract.py server\tests\test_copilot_incident_contract.py server\tests\test_incidents.py server\tests\test_incident_persistence.py server\tests\test_alert_triage.py server\tests\test_alert_triage_persistence.py -q --tb=short
```

结果: **54 passed in 5.49s**。

含 `test_demo_flow.py` 复跑回归: **58 passed, 1 failed, 17 warnings in 11.11s**。
唯一失败 `test_demo_alert_can_drive_copilot_fallback` 经 `git stash` 复跑 M3-04 baseline (`1c2f45b`) 确认是预存失败 (NeMo Guardrails `moderation_unavailable`),与 M3-05 改动无关;M3-04 run log 已记录 "12 个预存失败 (LLM Colang flows 9 个 + SSRF 3 个)"。M3-05 不触碰 `server/security/**`。

新测试 9/9 通过:

- `test_copilot_stream_in_accepts_incident_id`
- `test_copilot_stream_in_rejects_oversize_incident_id`
- `test_copilot_stream_in_incident_id_optional`
- `test_fake_provider_streams_sse_tokens_with_incident_context`
- `test_fake_provider_not_invoked_when_incident_missing`
- `test_fake_provider_not_invoked_when_incident_guardrails_block`
- `test_copilot_audit_log_includes_incident_id_without_note`
- `test_incident_context_truncates_alerts_and_events`
- `test_incident_takes_priority_over_alert_id_in_context`

### 5.2 前端

```powershell
cd web-next
npm run typecheck
npm run build
```

结果: typecheck 0 错误;build 成功(3.2s,`/dashboard` 42.9 kB / First Load JS 190 kB)。

### 5.3 git status

变更文件(待精确 stage):

- `M .claude/settings.local.json`（禁提交,保留原状）
- `M .coverage`（禁提交,保留原状）
- `M docs/agent/UNATTENDED_LONG_TASKS.md`（本任务允许 append 索引,已同步 M3-05 状态）
- `M docs/plans/M2_PRODUCT_ROADMAP.md`（本任务允许更新,新增 M3-05 段）
- `M docs/runs/2026-06-18-m3-05-incident-aware-copilot-contract.md`（本任务允许新增 run log）
- `M PRODUCT.md`（本任务允许更新,新增第 12 项 M3-05 说明）
- `M server/models/schemas.py`（CopilotStreamIn 增 incident_id 字段）
- `M server/services/copilot_service.py`（新增 helpers + 重构 copilot_stream 顺序 + audit detail 扩展）
- `A server/tests/test_copilot_incident_contract.py`（新增 9 个 RED→GREEN 测试）
- `M web-next/app/dashboard/dashboard-client.tsx`（监听 incident:copilot 事件提取 incidentId）
- `M web-next/components/dashboard/IncidentDetailPanel.tsx`（删 buildCopilotPrompt + sessionStorage,只发短意图 + incidentId）
- `M web-next/hooks/useCopilot.ts`（新增 SendMessageOptions + incidentId body 注入 + hint 锁定）

未追踪: `docs/agent/M3_05_INCIDENT_AWARE_COPILOT_CONTRACT_TASK.md`(本任务文档)。

## 6. 安全审查

- **owner 隔离**: `_load_incident_context` 走 `incident_service.get_incident_detail(db, user.id, incident_id, event_limit=5)`,service 按 `user_id` 严格过滤;非 owner / 不存在统一 `None` → SSE error "案件上下文不可用或不存在" + provider 不调用。**不**通过 403 / 404 区分暴露 incident_id 是否存在。`test_fake_provider_not_invoked_when_incident_missing` 锁定。
- **Guardrails 不绕过**: `copilot_stream` 顺序为 rate limit → user config → context lookup → Guardrails input → create_log → provider stream。incident 存在时 Guardrails 正常拦截,block 后 provider 不被调用;SSE 错误仅暴露 `category` 摘要,`reason` 全文 / regex / stack trace 仅进 `log_guardrail_event` 审计。`test_fake_provider_not_invoked_when_incident_guardrails_block` 锁定。
- **context 最小化**: incident path context_block 不放:
  - 完整 event note(只放 `note_length=...`)
  - 完整 alert payload(只放 `payload_length=...`)
  - 完整 title(截断 500 字符)
  - 完整 summary(截断 500 字符)
  - secret / system prompt / stack trace / regex / API key
  - 与 owner 案件无关的 incident_id(用户必须传自己的 incident_id,且后端按 user_id 过滤)
  `test_incident_context_truncates_alerts_and_events` 锁定 10→5 截断 + note / payload 全文不进 context。
- **audit 脱敏**: `Log(action="copilot_stream")` detail 现包含 `provider=...;model=...;alert_id=...;incident_id=...`(incident_id 仅在提供时出现)。`test_copilot_audit_log_includes_incident_id_without_note` 锁定 detail 不写 title / summary / note / fake key / stack trace。
- **fake provider 隔离**: `FakeLLMProvider` 仍**不**进 `_PROVIDERS` 默认 registry;仅通过 `register_provider("fake_test", ...)` 注入。`test_copilot_incident_contract.py` 复用 M2-06 已建立的 fake provider 模式(duck-typed `fake_stream` hook,生产不可达)。
- **SSE 错误净化**: 两条独立 SSE error。
  - incident 不可用 → `案件上下文不可用或不存在`(不区分 owner / 不存在)
  - Guardrails block → `请求被安全护栏拦截(类别: <category>)`(不暴露 reason 全文 / regex / stack trace)
- **未触碰 `server/security/**`**: `git diff` 复核,本次只修改 `server/models/schemas.py` / `server/services/copilot_service.py` / `server/tests/test_copilot_incident_contract.py` + 前端 3 文件 + 文档。Guardrails / LLM provider / MCP 路径全部未修改。
- **新 env var**: 无;任务文档 §7 列出的修改范围内不需要新增环境变量。
- **认证 / JWT / 2FA / cookie 语义**: 未触碰;`main.py` / `server/routers/copilot_router.py` 未修改。
- **WS / CORS / nginx / docker-compose**: 未触碰。
- **生产部署文档**: M3-05 复用现有 `DATABASE_URL` / Alembic baseline,M2-01 / M2-07 已有完整说明;无新增部署要求;无 schema 变更,无需新 Alembic migration。
- **前端不动 incident detail 拼 message**: M3-04 的 `buildCopilotPrompt(detail)` 已删;前端只发短意图 + incident_id,后端负责 owner 隔离 / 脱敏 / Guardrails / SSE 净化。`sessionStorage` 中间态写入也清除。

## 7. 未解决问题

无。

## 8. 最终状态

- 推送状态:见精确 commit / push 阶段。
- 改动文件(4 个 commit,精确 stage):
  - `test(copilot): 覆盖案件上下文合约`
  - `feat(copilot): 支持后端案件上下文`
  - `feat(dashboard): 使用 incident_id 调用 Copilot`
  - `docs(copilot): 记录案件感知 Copilot 边界`
- 工作树状态:见 `git status --short --branch`(在 push 后确认)。
- 远端 `origin/main` HEAD:本次 push 后指向最后一个 commit。
- 剩余本地噪声:`.coverage` / `.claude/settings.local.json`(禁提交,保留原状);`docs/agent/UNATTENDED_LONG_TASKS.md` / `docs/runs/2026-06-18-m3-05-incident-aware-copilot-contract.md` 已在 M3-05 commit 内同步。

