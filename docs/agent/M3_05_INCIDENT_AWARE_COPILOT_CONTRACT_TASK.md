# M3-05 案件感知 Copilot 合约 L5 超长任务

> 任务级别：L5，高风险 LLM 上下文 + 安全审查 + 前后端契约战役。  
> 目标读者：接手本仓库的开发 agent。  
> 核心目标：把 M3-04 的“前端拼接案件摘要”升级为“后端受控、可测试、owner 隔离、Guardrails 不绕过”的 incident-aware Copilot contract。

---

## 0. 背景

当前 M3-04 已交付：

- `incidents` / `incident_alert_links` / `incident_events` 三张表。
- `GET /incidents/{id}` 返回 incident + linked_alerts + newest-first events。
- Dashboard 新增案件工作台。
- `IncidentDetailPanel` 里已有“用 AI 分析案件”按钮。
- 但 Copilot 案件上下文现在由前端 `buildCopilotPrompt(detail)` 拼成普通用户消息，再走现有 `/copilot/stream`。

这个方案能用，但产品和安全边界还不够硬：

- 前端拼接不是后端事实源，测试只能覆盖 UI 字符串，不能保护 API contract。
- 后端 `copilot_service` 只认识 `alert_id`，不认识 `incident_id`。
- fake provider contract 测试只覆盖单条 alert 上下文。
- owner 隔离依赖前端先拿到 detail，不够可审计。
- Copilot audit log 里没有 incident 维度，不利于 SOC 复盘。

本任务要把 Copilot 扩展为：

```text
POST /copilot/stream
{
  "message": "...",
  "alert_id": "...?",
  "incident_id": "...?",
  "history": [...]
}
```

后端根据 `incident_id` 读取 owner 的案件上下文，构造受控 `context_block`，再走原有 Guardrails、provider、SSE、audit 路径。

---

## 1. 产品能力定义

完成后，用户应该能做到：

1. 在案件详情中点击“用 AI 分析案件”。
2. 前端只发送 `incident_id` 和简短用户意图，不再把完整案件摘要塞进 `message`。
3. 后端验证 incident owner 后，构造案件上下文：
   - incident id / title / severity / status / alert_count
   - summary（截断）
   - 最多 5 条关联告警摘要
   - 最多 5 条案件事件摘要
4. Copilot 输出仍是原 SSE 流，仍受 Guardrails 输入检查保护。
5. 非 owner / 不存在 incident 不泄露存在性，不把别人的案件上下文发给 LLM。
6. fake provider contract 测试能证明 incident context 真正注入。
7. audit log 能记录 `incident_id` 维度，但不泄露完整 note / payload / secret。

一句话能力声明：

> 安全分析员可以让 Copilot 基于后端认证过的案件上下文进行分析，而不是依赖前端拼接文本。

---

## 2. 启动前必读

执行前完整阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`
- `docs/agent/M3_04_INCIDENT_CASE_WORKBENCH_TASK.md`
- `docs/runs/2026-06-18-m3-04-incident-case-workbench.md`

必须阅读当前实现：

- `server/models/schemas.py`
- `server/routers/copilot_router.py`
- `server/services/copilot_service.py`
- `server/services/llm_providers.py`
- `server/services/alert_service.py`
- `server/services/incident_service.py`
- `server/routers/incidents_router.py`
- `server/security/llm_guardrails/core.py`
- `server/security/llm_guardrails/exceptions.py`
- `server/tests/test_copilot_contract.py`
- `server/tests/test_incidents.py`
- `server/tests/test_incident_persistence.py`
- `web-next/hooks/useCopilot.ts`
- `web-next/components/dashboard/IncidentDetailPanel.tsx`
- `web-next/components/dashboard/CopilotSection.tsx`
- `web-next/components/dashboard/CopilotPanel.tsx`
- `web-next/types/copilot.ts`
- `web-next/types/incident.ts`

必须遵守：

- TDD：先补 RED contract 测试，再改 production。
- Security review：本任务碰 LLM 上下文、用户输入、API 请求体和 audit。
- 不新增 LLM provider。
- 不弱化或绕过 Guardrails。

---

## 3. 初始仓库审计

开始改文件前必须：

1. 创建运行日志：

   ```text
   docs/runs/2026-06-18-m3-05-incident-aware-copilot-contract.md
   ```

2. 记录：
   - 当前分支。
   - `HEAD`。
   - `origin/main`。
   - `git status --short --branch`。
   - `git log --oneline origin/main..HEAD`。
   - 暂存区是否为空。
   - 本地噪声文件。

3. 如果出现以下情况，立即停止：
   - `origin/main` 比本地新，且无法安全 fast-forward。
   - 暂存区非空。
   - 发现 `.coverage`、`.claude/settings.local.json`、真实 `.env`、数据库文件、密钥文件被暂存。
   - M3-04 的 incident 相关测试当前无法运行，且不是环境问题。

允许存在但不得提交：

- `.coverage`
- `.claude/settings.local.json`
- `.env`
- `.env.compose.local`
- `data/app.db`
- `server/.pytest_cache/**`
- `**/__pycache__/**`

---

## 4. 后端契约

### 4.1 请求 schema

修改 `server/models/schemas.py::CopilotStreamIn`：

```python
incident_id: str | None = Field(default=None, max_length=64)
```

规则：

- `alert_id` 和 `incident_id` 可以都为空：通用咨询。
- 可以只有 `alert_id`：沿用现有单告警上下文。
- 可以只有 `incident_id`：案件上下文。
- 如果二者都提供：**incident 优先**。后端用 incident 作为主要上下文；`alert_id` 只作为轻量 `selected_alert_id` 行，不额外读 alert payload。

### 4.2 后端 context builder

在 `server/services/copilot_service.py` 新增：

- `_truncate_context_value(value, max_chars)`
- `_build_context_from_incident(detail, selected_alert_id=None)`
- `_load_incident_context(db, user_id, incident_id)`

建议上下文格式：

```text
[当前安全案件上下文]
incident_id: inc_xxx
title: ...
severity: high
status: investigating
alert_count: 3
selected_alert_id: ...
summary: ...

[关联告警摘要]
- alert_id=... source=... destination=... risk=... blocked=... summary=...

[案件事件摘要]
- event_type=status_changed from=open to=investigating note_length=... created_at=...

请基于该安全案件给出专业安全分析和可执行防御建议，优先给出立即动作。
```

硬限制：

- 最多 5 条 linked alerts。
- 最多 5 条 incident events。
- incident summary 最多 500 字符。
- 每条 alert summary 最多 160 字符。
- event note 不放全文，只放 `note_length`。
- 不放完整 raw payload；如需 payload 信息，只放 `payload_length`。
- 不放 secret、system prompt、stack trace、regex。
- 不改变 `history` 合并逻辑。

### 4.3 owner 隔离

`_load_incident_context` 必须通过 `incident_service.get_incident_detail(db, user_id, incident_id, event_limit=5)` 或等价 owner 过滤路径读取。

如果返回 None：

- 返回 SSE error：

  ```text
  案件上下文不可用或不存在
  ```

- provider 不应被调用。
- 错误不区分不存在和非 owner。

### 4.4 Guardrails 顺序

推荐顺序：

```text
rate limit -> user config -> context lookup -> Guardrails input -> create Log -> provider stream
```

要求：

- incident path 不能绕过 Guardrails。
- Guardrails block 后 provider 不调用。
- SSE error 不能暴露 full reason / regex / stack trace。

### 4.5 audit log

`create_log(action="copilot_stream")` detail 扩展为：

```text
provider=...;model=...;alert_id=...;incident_id=...
```

要求：

- incident_id 可以写。
- 不写 incident title / summary / note / payload。
- Guardrails audit 仍照旧。

---

## 5. 前端契约

当前 `IncidentDetailPanel.buildCopilotPrompt(detail)` 会拼完整消息并通过 `incident:copilot` 自定义事件传给 Dashboard。

本任务要改成：

- `IncidentDetailPanel` 触发事件时只传：

  ```ts
  {
    incidentId: detail.incident.incident_id,
    prompt: "请分析当前安全案件，给出风险、证据、影响和下一步处置。"
  }
  ```

- 不再把 linked alerts / events 拼进 `prompt`。
- `useCopilot.sendMessage` 支持可选第二参数：

  ```ts
  sendMessage(messageText: string, options?: { incidentId?: string | null; alertId?: string | null })
  ```

- 请求 body 新增 `incident_id`。
- 如果 `options.incidentId` 存在，hint 可以显示：

  ```text
  案件上下文: inc_xxx
  ```

最小可接受：

- 不重写 CopilotPanel。
- 不新增 UI 大组件。
- 不改消息流式解析。
- 不把 incident detail 继续塞到用户消息里。

---

## 6. RED 测试要求

先写失败测试。

### 6.1 后端 contract 测试

扩展 `server/tests/test_copilot_contract.py`，建议新增：

1. `test_fake_provider_streams_sse_tokens_with_incident_context`
   - 构造 fake incident detail。
   - `CopilotStreamIn(message="请分析当前案件", incident_id="inc-test")`。
   - fake provider 被调用 1 次。
   - `recorded["context_block"]` 包含 `[当前安全案件上下文]`、`incident_id: inc-test`、`severity:`、`status:`、`关联告警摘要`。
   - `recorded["user_message"]` 只含用户短消息，不含完整 alert summary。

2. `test_fake_provider_not_invoked_when_incident_missing`
   - incident lookup 返回 None。
   - SSE error 含 `案件上下文不可用或不存在`。
   - fake provider call_count == 0。

3. `test_fake_provider_not_invoked_when_incident_guardrails_block`
   - incident 存在。
   - Guardrails block。
   - fake provider call_count == 0。
   - SSE 不含 full reason / regex。

4. `test_copilot_audit_log_includes_incident_id_without_note`
   - stub `create_log` 捕获 detail。
   - detail 包含 `incident_id=inc-test`。
   - detail 不含 title / summary / note / fake key / stack trace。

5. `test_incident_context_truncates_alerts_and_events`
   - 构造 10 条 linked alerts 和 10 条 events。
   - context 只包含前 5 条摘要。
   - 不含第 6 条特征字符串。
   - 长 summary 截断。

如果直接 mock `incident_service.get_incident_detail` 更快，可以使用 monkeypatch；不要为了 contract 测试启动完整 FastAPI。

### 6.2 schema 测试

至少验证：

- `CopilotStreamIn(incident_id="x")` 可创建。
- 超长 `incident_id` 在 route/Pydantic 层返回 422 或构造失败。
- `history` 规则不变。

### 6.3 前端验证

当前项目没有前端单测基线，至少必须：

- `npm run typecheck`
- `npm run build`

不要为了本任务引入新的前端测试框架。

---

## 7. 允许修改范围

后端：

- `server/models/schemas.py`
- `server/routers/copilot_router.py`（仅必要时）
- `server/services/copilot_service.py`
- `server/services/incident_service.py`（仅导出 / helper 必要小改）
- `server/tests/test_copilot_contract.py`
- 可新增 `server/tests/test_copilot_incident_contract.py`

前端：

- `web-next/hooks/useCopilot.ts`
- `web-next/components/dashboard/IncidentDetailPanel.tsx`
- `web-next/app/dashboard/dashboard-client.tsx`
- `web-next/types/copilot.ts`
- 必要时 `web-next/components/dashboard/CopilotSection.tsx`

文档：

- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/runs/2026-06-18-m3-05-incident-aware-copilot-contract.md`

---

## 8. 禁止修改范围

禁止：

- `.coverage`
- `.claude/settings.local.json`
- `.env`
- `.env.compose.local`
- `data/app.db`
- 真实 secret / token / key / 证书私钥
- `docker-compose.yml`
- `nginx/**`
- Alembic migrations（本任务不需要 schema 变更）
- `server/security/**`，原则上不触碰
- 登录、注册、JWT、refresh token、2FA、cookie 语义

不要：

- 新增 LLM provider。
- 把 fake provider 放进默认 `_PROVIDERS`。
- 用真实 API key 测试。
- 把 incident note / alert payload 全文发给 LLM。
- 把 incident detail 拼进前端 message。
- skip / 删除 / 弱化 guardrails、copilot、incident 既有测试。

---

## 9. 分阶段执行计划

### 阶段 1：运行日志和基线审计

- 建 run log。
- 记录 git 状态。
- 记录 M3-04 当前 HEAD。
- 跑最小 baseline：

  ```powershell
  $env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
  $env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
  .venv\Scripts\python.exe -m pytest server\tests\test_copilot_contract.py server\tests\test_incidents.py -q --tb=short
  ```

### 阶段 2：契约选择写入 run log

明确：

- `alert_id + incident_id` 同时存在时 incident 优先。
- incident 不存在 / 非 owner 时 SSE error + provider 不调用。
- context 最多 5 alerts + 5 events。
- event note 不进 context，只进 note_length。
- audit log detail 只写 incident_id，不写 note/title/summary。

### 阶段 3：RED 测试

- 先写后端 contract tests。
- 执行新测试，确认失败原因是缺 `incident_id` contract 或 context builder，不是语法错误。
- 记录 RED 输出摘要到 run log。

### 阶段 4：后端实现

- 扩展 `CopilotStreamIn`。
- 实现 `_load_incident_context` 和 `_build_context_from_incident`。
- 修改 `copilot_stream`：
  - 读取 incident context。
  - incident 不存在返回 SSE error。
  - context_block 使用 incident / alert 规则。
  - create_log detail 加 `incident_id`。
- 保持 Guardrails block 不调用 provider。

### 阶段 5：后端 GREEN

运行：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_copilot_contract.py -q --tb=short
.venv\Scripts\python.exe -m pytest server\tests\test_incidents.py server\tests\test_incident_persistence.py -q --tb=short
```

### 阶段 6：前端改造

- `useCopilot.sendMessage` 增加 options。
- `IncidentDetailPanel` 不再调用 `buildCopilotPrompt(detail)` 拼完整上下文。
- 保留一个短 prompt helper，如：

  ```text
  请分析当前安全案件，给出风险、证据、影响和下一步处置。
  ```

- Dashboard `incident:copilot` handler 调用：

  ```ts
  copilotCtx.sendMessage(prompt, { incidentId })
  ```

### 阶段 7：前端验证

```powershell
cd web-next
npm run typecheck
npm run build
```

如能启动 dev server，可手动或浏览器验证：

- Dashboard 打开。
- 案件详情点击“用 AI 分析案件”。
- Network 请求 body 含 `incident_id`。
- message 是短意图，不含 linked alert 摘要。

### 阶段 8：安全审查

run log 必须写：

- owner 隔离：incident lookup 走 user_id。
- non-owner / missing：SSE error，provider 不调用。
- Guardrails：仍在 provider 前执行；block 后 provider 不调用。
- context 最小化：不放完整 note / payload / secret。
- audit：只写 incident_id，不写 note/title/summary。
- fake provider：仍不进默认 registry。
- `server/security/**` 未触碰或触碰原因。

### 阶段 9：文档同步

更新：

- `PRODUCT.md`：M3-05 当前实现边界和验收。
- `docs/plans/M2_PRODUCT_ROADMAP.md`：M3-05 状态。
- `docs/agent/UNATTENDED_LONG_TASKS.md`：本任务索引，完成后标已交付。
- run log：全阶段证据。

### 阶段 10：质量门

至少运行：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_copilot_contract.py server\tests\test_incidents.py server\tests\test_incident_persistence.py server\tests\test_alert_triage.py server\tests\test_alert_triage_persistence.py server\tests\test_demo_flow.py -q --tb=short
```

如果触碰 `server/security/**`，还必须跑：

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

最终：

```powershell
git diff --check
git status --short --branch
```

---

## 10. 提交与推送

只有全部质量门通过后，才允许精确 commit / push。

禁止 `git add .`。

建议 commit 拆分：

1. `test(copilot): 覆盖案件上下文合约`
2. `feat(copilot): 支持后端案件上下文`
3. `feat(dashboard): 使用 incident_id 调用 Copilot`
4. `docs(copilot): 记录案件感知 Copilot 边界`

提交前必须：

```powershell
git diff --cached --name-status
```

不得 staged：

- `.coverage`
- `.claude/settings.local.json`
- `.env*` 真实配置
- `data/app.db`
- `*.pem`
- `*.key`
- `server/.pytest_cache/**`
- `**/__pycache__/**`

push 前：

```powershell
git status --short --branch
git log --oneline origin/main..HEAD
```

如果 `origin/main` 前进，停止并报告，不要强推。

---

## 11. 停止条件

遇到以下任一情况必须停止并写 run log：

1. 同一测试失败连续修复 3 轮。
2. 为实现 incident-aware Copilot 必须修改 `server/security/**` 策略。
3. 需要真实 LLM API key。
4. fake provider 必须进入默认 registry 才能测试。
5. owner 隔离无法保证。
6. 只能靠把完整 incident detail 塞进用户 message 才能实现。
7. 需要 schema migration。
8. 前端 build 失败且无法在 3 轮内修复。
9. 发现 M3-04 incident API 与文档不一致，且会影响本任务核心契约。

---

## 12. 完成报告模板

完成后输出：

```text
完成状态：完成 / 部分完成 / 阻塞

本次新增能力：
- ...

关键文件：
- ...

验证命令：
- ... -> 结果

安全审查：
- owner 隔离：...
- Guardrails：...
- context 最小化：...
- audit 脱敏：...

提交：
- commit 列表
- push 状态

剩余风险：
- ...
```

---

## 13. 给 owner 的短启动口令

```text
请执行 docs/agent/M3_05_INCIDENT_AWARE_COPILOT_CONTRACT_TASK.md 里的 L5 超长任务。先完整阅读任务文档和其中列出的必读文件，创建并持续更新 run log；按 RED→GREEN→IMPROVE 推进，完成后端 incident_id Copilot contract、owner 隔离、fake provider 合约测试、Guardrails 不绕过、SSE 错误净化、前端用 incident_id 调用 Copilot、文档同步、质量门、精确 commit/push。不要 git add .，不要提交 .coverage、.claude/settings.local.json、真实 env、数据库文件或密钥。遇到远端前进、认证/安全护栏策略变更、真实 LLM key 需求或质量门无法通过时停止并报告。
```
