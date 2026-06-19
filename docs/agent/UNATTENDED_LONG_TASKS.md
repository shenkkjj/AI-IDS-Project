# 无人值守长任务手册

> 读者：项目 owner、AI Agent。
> 目的：允许 agent 连续工作较长时间，同时防止无限乱改、偷偷越权、重复失败和不可审查的大 diff。
> 使用方式：给 agent 下长任务前，把本文件和 `PRODUCT.md` 一起列为必读。

---

## 1. 核心原则

无人值守不等于完全放权。这个项目可以让 agent 长时间执行，但必须满足四个条件：

1. **边界清楚**：知道能改什么、不能改什么。
2. **预算清楚**：知道最多跑多久、最多尝试几轮。
3. **证据清楚**：每个阶段留下日志、diff、测试结果和未解决问题。
4. **停止清楚**：遇到高风险、重复失败、测试无法恢复时必须停下，而不是硬凑完成。

本项目默认采用 **Sequential Pipeline + De-sloppify + Verification** 模式：

```text
读取上下文 -> 制定小计划 -> 实现一小段 -> 清理 AI 赘余 -> 验证 -> 记录 -> 下一小段
```

只有当任务已经有完整 RFC、工作单元能互不重叠、并且有清晰合并策略时，才使用并行 agent 或 DAG 模式。

---

## 2. 长任务分级

### L1：低风险无人值守

适合直接跑 1-2 小时：

- 修复文档乱码。
- 改 README / docs / 注释。
- 补非核心测试。
- 拆小型前端组件，但不改业务语义。
- 清理明显 dead code，且有测试覆盖。

要求：

- 可以自动改文件。
- 可以自动运行测试。
- 不允许 commit / push / deploy，除非用户明确要求。

### L2：中风险无人值守

适合跑 1-3 小时，但必须有阶段检查点：

- 新增普通 UI 功能。
- 新增普通 API。
- 重构 service/router，但不改认证、安全、数据库 schema。
- 修复明确 bug。

要求：

- 每完成一个子任务就更新运行日志。
- 测试失败最多连续修复 3 轮。
- 如果 diff 超过约 800 行，必须停下并总结，不继续扩大范围。

### L3：高风险半自动

不适合完全无人值守，必须设置硬停止点：

- 认证、授权、session、cookie、JWT。
- `server/security/**`。
- LLM Guardrails / prompt injection / MCP。
- 数据库 schema / migration。
- `.env.example`、部署、nginx、CI 安全策略。
- 删除大量文件或跨模块重构。

要求：

- agent 可以研究和写计划。
- 如果要真正改代码，必须先写风险说明和回滚方案。
- 改完必须做安全审查。
- 不允许自动 commit / push / deploy。

---

## 3. 无人值守运行日志

每次长任务必须创建一个运行日志：

```text
docs/runs/YYYY-MM-DD-task-slug.md
```

日志模板：

```markdown
# Run: <任务名>

开始时间：
运行模式：L1 / L2 / L3
预算：最长 X 小时，最多 Y 轮修复

## 目标

-

## 范围

允许修改：
-

禁止修改：
-

## 计划

- [ ]

## 阶段记录

### 阶段 1

改动：
验证：
结果：
下一步：

## 验证证据

-

## 未解决问题

-

## 最终状态

完成 / 部分完成 / 阻塞
```

agent 每完成一个阶段都要更新这个文件。长任务结束后，你只看这个文件、`git diff --stat` 和测试结果，就能判断它干了什么。

---

## 4. 默认允许和禁止

### 默认允许

- 读取代码、文档、测试、配置样例。
- 修改任务范围内的代码和测试。
- 新增小型文档、运行日志、测试文件。
- 运行本地测试、typecheck、build。
- 用小步补丁修复验证失败。

### 默认禁止

- 不经用户明确要求就 commit、push、merge、deploy。
- 修改真实 `.env` 的 secret 值。
- 打印、复制、提交任何 secret。
- 删除数据库、清空数据、重置 git 历史。
- 为了通过测试而删除、跳过、弱化测试。
- 在 L3 高风险区域连续大改而不停止汇报。

---

## 5. 停止条件

满足任一条件时，agent 必须停下并写总结：

1. 同一个测试失败连续修复 3 轮仍失败。
2. 发现任务目标和现有产品边界冲突。
3. 需要修改认证、授权、密钥、数据库 schema、安全护栏，但原任务没有授权。
4. 需要外部登录、付费服务、真实生产 secret。
5. diff 明显失控，超过约 800 行且不是纯文档或生成文件。
6. 当前验证无法运行，且无法在本地修复环境问题。
7. 任务已经达到时间预算。

停止不是失败。停止时要交付：

- 已完成内容。
- 未完成内容。
- 阻塞原因。
- 推荐下一条最小工单。

---

## 6. 验证命令基线

### 后端普通任务

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

### 可选 Playwright E2E

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_e2e.py -q --tb=short --run-e2e
```

### LLM Guardrails / 安全护栏任务

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

### 前端任务

```powershell
npm run typecheck
npm run build
```

工作目录：

```powershell
cd web-next
```

### 注意

- `pytest server\tests` 是默认后端基线；Playwright E2E 默认跳过，必须用 `--run-e2e` 显式运行。
- 当前没有独立 ESLint 配置；不要在无人值守或 CI 中使用 `npx next lint`。前端默认使用 `npm run typecheck` 和 `npm run build`。

---

## 7. 无人值守任务提示词

把下面这段复制给 agent，然后替换尖括号内容。

```markdown
你是 AI-CyberSentinel 的长任务执行 agent。请用中文回复。

启动前必读：
- `PRODUCT.md`
- `AGENTS.md`
- `CLAUDE.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`

任务名称：
- <例如：M0-01 修复 README 与关键文档乱码>

运行模式：
- <L1 / L2 / L3>

时间与重试预算：
- 最长运行：<例如 2 小时>
- 同一失败最多修复：3 轮
- diff 超过约 800 行时停止总结，除非主要是文档

任务目标：
- <一句话说明完成后用户能做什么>

允许修改：
- <path>

禁止修改：
- 真实 `.env`
- git 历史
- 认证/授权/安全护栏/数据库 schema，除非本任务明确列入允许修改
- 部署、push、merge、生产配置

执行要求：
1. 先创建 `docs/runs/YYYY-MM-DD-<task-slug>.md` 运行日志。
2. 把任务拆成 15-30 分钟可验证的小阶段。
3. 每阶段结束更新运行日志。
4. 每轮实现后做一次 de-sloppify：删除无意义测试、重复防御、调试输出、注释掉的废代码。
5. 运行相关验证命令。
6. 遇到停止条件时立刻停下，写清楚阻塞和下一步。

验收标准：
- <用户可见行为>
- <测试或构建命令>
- <安全要求>

完成时输出：
- 完成状态：完成 / 部分完成 / 阻塞
- 改动文件列表
- 运行过的验证命令和结果
- 运行日志路径
- 下一条建议工单
```

---

## 8. 可复用超长任务文档

如果任务太长，不要在聊天框里复制完整提示词。把任务固化成 `docs/agent/*.md`，然后只发一个短启动口令。

当前可用的超长任务：

- `docs/agent/M2_SOC_OPERATIONS_BASELINE_TASK.md`：L5 级 M2 SOC 运营基线战役，覆盖 Demo Flow E2E、Copilot contract、审计时间线、生产安全配置检查、文档同步和提交准备。
- `docs/agent/M2_01_DATABASE_URL_ALEMBIC_BASELINE_TASK.md`：L5 级 M2-01 数据库 URL 与 Alembic 基线战役，覆盖 `DATABASE_URL` 事实来源、SQLite 默认回退、Alembic baseline（revision `d9af4388f20a_baseline_schema.py`）、迁移测试、文档同步和通过后推送。运行日志：`docs/runs/2026-06-17-m2-01-database-url-alembic-baseline.md`。
- `docs/agent/M2_07_DOCKER_COMPOSE_E2E_READINESS_TASK.md`：L5 级 M2-07 Docker Compose 端到端验收战役，覆盖 Compose 本地启动、数据库/迁移接线、`postgresql+psycopg` 驱动验证、nginx 入口和证书策略收口、前端回源/登录 smoke、健康检查、文档同步和通过后推送。运行日志：`docs/runs/2026-06-17-m2-07-docker-compose-e2e-readiness.md`。
- `docs/agent/M2_07_PUSH_AND_RUNLOG_FINALIZATION_TASK.md`：L5 级 M2-07 push 与运行日志最终收口战役，覆盖本地 M2-07 commit 复核、运行日志补交、禁止文件审查、Docker smoke 证据复核、远端状态检查和通过后推送 `origin/main`。
- `docs/agent/GITHUB_PUSH_CONNECTIVITY_AND_CREDENTIALS_RECOVERY_TASK.md`：L5 级 GitHub push 连通性与凭据恢复战役，覆盖 DNS/TCP/HTTPS 凭据/`gh auth`/SSH 现有凭据诊断、远端 fast-forward 审查、禁提交文件保护和安全 push；需要用户登录或新增密钥时必须停止。
- `docs/agent/M3_DEMO_READY_SOC_WORKBENCH_CLOSING_TASK.md`：L4 级 M3 Demo-Ready SOC 工作台收口战役，覆盖 M3 UI 改造审计、真实浏览器 E2E、验证矩阵、运行日志同步和精确拆分提交。
- `docs/agent/M3_AGENT_OPS_AND_PUSH_READINESS_TASK.md`：L5 级 M3 Agent Ops 与 push 前总审查战役，覆盖超长任务文档固化、提交栈复核、最终验证矩阵和通过后推送 `origin/main`。
- `docs/agent/M3_02_ALERT_TRIAGE_RESPONSE_WORKBENCH_TASK.md`：L5 级 M3-02 告警研判与处置工作台战役，覆盖 `PATCH /alerts/{alert_id}/triage` 接口、5 个稳定状态枚举（new / investigating / contained / false_positive / resolved）、`analyst_note` 800 字上限、所有权 404 规则、`Log(action="alert_triage_update")` 脱敏审计、`AlertTriagePanel` 紧凑控件、简报"待研判 / 已闭环"计数、E2E 覆盖与通过后推送。**重要边界**：triage 状态保存在当前进程告警 backlog payload 中，不做数据库 schema / 迁移；持久化、查询历史、跨副本共享留给后续数据库迁移任务。
- `docs/agent/M3_03_ALERT_TRIAGE_PERSISTENCE_AND_HISTORY_TASK.md`：L5 级 M3-03 告警研判持久化与历史记录战役，覆盖 `alert_records` / `alert_triage_events` 数据库表、Alembic migration `d33d40488e0f`、重启后 `GET /alerts` 恢复、`GET /alerts/{alert_id}/triage/history` 历史查询、owner 隔离、脱敏审计、Dashboard 历史展示、质量门和通过后推送。**已交付**（2026-06-18）：ORM + migration + service + 路由 + 前端 `AlertTriageHistory` 全部落地；11 个 RED→GREEN 持久化测试 + 3 个 migration 测试通过；运行日志 `docs/runs/2026-06-18-m3-03-alert-triage-persistence-and-history.md`。
- `docs/agent/M3_04_INCIDENT_CASE_WORKBENCH_TASK.md`：L5 级 M3-04 安全事件 / 案件工作台战役，覆盖 incident/case 数据库持久化、告警关联、事件状态流转、事件时间线、owner 隔离、脱敏审计、Dashboard 案件视图、Copilot 案件摘要、迁移验证、质量门和通过后推送。**已交付**（2026-06-18）：ORM 三表 `incidents` / `incident_alert_links` / `incident_events` + Alembic migration `4f3c9a1d8b7e`（基于 `d33d40488e0f`）落地；`GET / POST / PATCH /incidents` + `POST /incidents/{id}/alerts` + `DELETE /incidents/{id}/alerts/{alert_id}` 全套端点 + 5 状态白名单 + closed_at 关闭态自动设置 / 重开清空 + 重复 link 幂等 + owner 404 + Log 脱敏；前端 `useIncidents` + `IncidentSection / IncidentList / IncidentDetailPanel / IncidentTimeline / IncidentLinkedAlerts` 5 个新组件 + `RouteKey="incidents"` + 案件 Copilot 前端拼接；32 个 incident / migration 测试通过（24 个新 incident + 8 个新 / 扩展 migration）；运行日志 `docs/runs/2026-06-18-m3-04-incident-case-workbench.md`。
- `docs/agent/M3_05_INCIDENT_AWARE_COPILOT_CONTRACT_TASK.md`：L5 级 M3-05 案件感知 Copilot 合约战役，覆盖后端 `incident_id` Copilot contract、owner 隔离、fake provider 合约测试、Guardrails 不绕过、SSE 错误净化、audit 脱敏、前端从“拼完整案件摘要”改为“发送 incident_id + 短意图”、质量门和通过后推送。**已交付**（2026-06-18）：`CopilotStreamIn` 增 `incident_id` (max_length=64) 与 `alert_id` incident 优先语义；`copilot_service._load_incident_context` 走 M3-04 owner 隔离路径 + `event_limit=5`；`_build_context_from_incident` 构造受控 context_block (最多 5 alerts + 5 events;summary 500 / alert summary 160 / event detail 160 字符截断;note 只放 `note_length`;payload 只放 `payload_length`;不放 secret / system prompt / stack trace)。SSE 错误净化分两条:incident 不可用 `案件上下文不可用或不存在` (不区分 owner/不存在,不暴露 incident_id),Guardrails block `请求被安全护栏拦截(类别: <category>)` (不暴露 reason / regex)。Guardrails 仍在 provider 前执行,incident 路径不绕过。audit `Log(action="copilot_stream")` detail 增 `incident_id=...` 维度,不写 title / summary / note / fake key / stack trace。fake provider 合约测试 `test_copilot_incident_contract.py` 9 通过;既有 incident / copilot contract / alert triage / demo flow 0 回归(`test_demo_alert_can_drive_copilot_fallback` 仍为 M3-04 baseline 预存 NeMo Guardrails `moderation_unavailable` 失败)。前端 `useCopilot.sendMessage(text, { incidentId })` 透传;`IncidentDetailPanel` 不再 `buildCopilotPrompt`,只发短意图 + incidentId;`dashboard-client` 提取 `incidentId` 灌进 `sendMessage` options。`npm run typecheck` 0 错误;`npm run build` 通过 (`/dashboard` 42.9 kB / First Load JS 190 kB)。运行日志 `docs/runs/2026-06-18-m3-05-incident-aware-copilot-contract.md`。
- `docs/agent/M3_06_TEST_AND_SECURITY_QUALITY_GATE_CLOSURE_TASK.md`：L5 级 M3-06 测试与安全质量门收口战役，覆盖 M3-04 / M3-05 反复记录的预存失败复现与收口：Demo Flow fallback 的 `moderation_unavailable` 测试隔离、LLM Guardrails Colang corpus 确定性测试、SSRF 防护去真实 DNS 依赖、M3-03/M3-04/M3-05 回归矩阵、默认后端测试基线、前端 typecheck/build、文档同步、安全审查和通过后精确 push。**已交付**（2026-06-18）：3 大预存失败面**全部清零**且不靠 skip/xfail/删除断言 —— Demo Flow fallback 在 `test_demo_flow.py` 内 stub `GuardrailEngine.instance().check_input` 为 allow(模式与 `test_copilot_contract._stub_guardrails` 一致);Colang corpus 在 `conftest.py` 增加 `_safe_moderation_for_colang` autouse fixture 把 `OpenAIModerationClient.check` 改为 pass-through(用 `staticmethod` 包装规避 self 绑定 TypeError);SSRF 13/13 已稳定通过(M3-04 记录已过时);`mock_openai_moderation_*` 历史 fixtures 同步修 self-bug。后端基线 `318 passed, 2 skipped`(0 失败);Guardrails 专项 `139 passed`;Demo Flow `5 passed`;SSRF `13 passed`;Copilot/Incident 回归矩阵 `72 passed`;前端 `npm run typecheck` 0 错误 + `npm run build` 通过(`/dashboard` 42.9 kB / 190 kB)。**生产安全策略不降级**:`_run_rails` fail-closed / SSE error 净化 / SSRF 阻断 / audit 脱敏 全部保持原样;测试 stub 只存在于 `tests/` 目录。运行日志：`docs/runs/2026-06-18-m3-06-test-and-security-quality-gate-closure.md`。
- `docs/agent/M3_07_INCIDENT_EVIDENCE_REPORT_EXPORT_TASK.md`：L5 级 M3-07 案件证据报告导出战役，覆盖后端 `GET /incidents/{incident_id}/report?format=json|markdown` 契约、owner 隔离、Markdown 报告生成、payload/note/secret/system prompt/stack trace 脱敏与截断、导出审计 Log、前端案件详情“复制报告 / 下载报告”入口、类型和 hook 接入、质量门和通过后精确 push。**已交付**（2026-06-18）：`server/services/incident_report_service.py` 纯函数 service（`sanitize_report_text` / `build_incident_report`）落地，固定 4 段报告结构 + summary 1000 / alert summary 240 / payload preview 180 / event detail 240 / event note preview 160 / linked_alerts ≤ 20 / events ≤ 50 截断；`server/routers/incidents_router.py` 新增 `GET /incidents/{incident_id}/report?format=json|markdown`，复用 `incident_service.get_incident_detail` owner 隔离，非 owner / 不存在统一 404 不区分，invalid format 422，DB 失败 503；filename 只由 `incident_id` 派生，非法字符降级为 `_`；audit `Log(action="incident_report_export")` 仅在成功生成时写，detail 只含 `incident_id / format / alert_count / included_alerts / event_count / included_events / redaction_count`，**不**含 title / summary / payload / note / markdown 全文。脱敏复用 `logs_router._SENTINEL_PATTERNS` + 新增 `developer:` 触发。前端 `web-next/types/incident.ts` 新增 `IncidentReportMeta` / `IncidentReportResponse`；`web-next/hooks/useIncidents.ts` 新增 `loadIncidentReport` helper（不保存 markdown 到 React 长期 state，按按钮请求）；`web-next/components/dashboard/IncidentDetailPanel.tsx` 事件时间线工具区加 `复制报告` / `下载报告` 按钮（`Clipboard` / `ClipboardCheck` / `Download` / `Loader2` icon；`data-testid="incident-copy-report" / "incident-download-report" / "incident-report-status"`），状态文案 `生成中 / 已复制 / 已下载 / 报告生成失败`，复制走 `navigator.clipboard.writeText`（不可用降级 `复制失败`），下载走 `Blob` + `URL.createObjectURL` + `anchor.click()`；`web-next/components/dashboard/IncidentSection.tsx` 注入 `onLoadReport` 到 `IncidentDetailPanel`。**不调用 LLM / 不引入 PDF/DOCX/外部渲染 / 不新增 schema / 不引入 env var / 不触碰 `server/security/**`**。14 个 RED→GREEN 测试通过（含 401 / 404 / 422 / json envelope / markdown body / payload 截断 / note 截断 / 脱敏 sentinel / audit 脱敏 / 大案件截断 / filename 派生）；后端全量 `332 passed, 2 skipped`（M3-06 baseline 318 + M3-07 新增 14；0 失败）；Guardrails 专项 `139 passed` 0 回归；前端 `npm run typecheck` 0 错误 + `npm run build` 通过（`/dashboard` 43.7 kB / First Load JS 191 kB）。运行日志：`docs/runs/2026-06-18-m3-07-incident-evidence-report-export.md`。
- `docs/agent/M3_08_INCIDENT_REPORT_BROWSER_E2E_AND_AGENT_DOCS_CATCHUP_TASK.md`：L5 级 M3-08 案件报告浏览器验收与 Agent 文档归档战役，覆盖 M3-07 报告导出的真实浏览器路径：注册/登录 → 触发 Demo 告警 → 创建案件 → 打开案件详情 → 下载 Markdown 报告 → 验证报告结构与脱敏 sentinel → 点击复制报告 → 扫描页面 DOM 无 secret/stack/system prompt 泄漏；同时收口 `docs/agent/M3_07_INCIDENT_EVIDENCE_REPORT_EXPORT_TASK.md` 未入库问题、更新无人值守索引、记录运行日志、执行后端/Guardrails/前端质量门并通过后精确 commit/push。**重要边界**：不新增 API、不新增 schema、不改认证/授权/Guardrails、不引入 PDF/DOCX/LLM 报告生成；若 Playwright 或 dev server 环境阻塞，必须保留测试并把最终状态写成”部分完成 / E2E 环境阻塞”，不能假装浏览器验收通过。**已交付**（2026-06-18，部分完成 / E2E dev 环境阻塞）：M3-07 / M3-08 任务文档归档入库；`server/tests/test_incident_report_e2e.py` Playwright E2E 写好（`pytestmark = [pytest.mark.e2e]`，`@pytest.mark.e2e` + `@pytest.mark.asyncio`，`accept_downloads=True` + `clipboard-read` / `clipboard-write` grants，覆盖：唯一邮箱 → 后端 API 预 register → UI login → 触发 Demo 攻击 → 点击告警 → 创建案件 → 下载报告 → 验证 markdown 4 段结构 + payload_length / payload_preview + 12 条 forbidden sentinel + DOM 整页扫描），默认 `pytest server/tests` 跳过（1 skipped），`--run-e2e` 显式触发；后端契约 14 passed；后端全量 `332 passed, 3 skipped`（M3-07 14 + E2E 1 skip = 3 skipped）；Guardrails 专项 139 passed 0 回归；前端 `npm run typecheck` 0 错误 + `npm run build` 通过（`/dashboard` 43.7 kB / First Load JS 191 kB）。**E2E 阻塞摘要**（run log 阶段 4 详记）：next-auth 5.0.0-beta.30 + Next.js 15 dev mode 下 `useSession()` 在 dashboard 客户端 `status` 永为 `loading`，`SYSTEM · LOADING` 60s 不消失；`/api/auth/session` 客户端 fetch 200 OK + user，但 React 状态不同步；经调试确认非项目代码问题（dev mode RSC hydration 与 next-auth 5 beta SessionProvider 兼容性问题），与认证/授权/Guardrails 修改边界冲突，留给 owner 单独修复（升级 next-auth / 改 `providers.tsx` 配置 / 升级 Next.js dev mode）。最小后端修复 1 行：`server/main.py` 漏导 `incidents_router`（M3-04 引入时的回归，本任务首启 dev server 触发 NameError），已在 run log 阶段 3 记录并随本任务 commit 修复。运行日志：`docs/runs/2026-06-18-m3-08-incident-report-browser-e2e-and-agent-docs-catchup.md`。
- `docs/agent/NEXT_01_AUTH_SESSION_LOADING_E2E_RECOVERY_TASK.md`：L5 级 NEXT-01 认证会话 loading 阻塞收口战役，覆盖 M3-08 暴露的 next-auth 5 beta + Next.js 15 dev mode `useSession()` 永 `loading` 问题：先新增最小 auth E2E 复现 RED，再优先把 `/dashboard` 改成服务端 `auth()` 放行，必要时给 `SessionProvider` 注入服务端初始 session 或最小升级 `next-auth` / `next`，最后必须让 `test_auth_session_e2e.py --run-e2e` 与 M3-08 `test_incident_report_e2e.py --run-e2e` 真实通过，并跑后端全量、Guardrails、前端 typecheck/build。**重要边界**：认证高风险区，只允许修 Dashboard 会话放行与 E2E 验收阻塞；不允许绕过认证、不允许把 token 放进 localStorage/sessionStorage、不允许暴露 backend access token、不允许改后端 auth API/schema/Guardrails。**已交付**（2026-06-19）：路线 A + B 同时落地；`web-next/app/dashboard/page.tsx` 改为 Server Component, 用 `auth()` + `redirect("/")` 决定放行, 不再依赖客户端 `useSession()` 的 hydration; `web-next/app/layout.tsx` 在服务端调 `auth()` 把 session 透传给 `Providers`; `web-next/app/providers.tsx` 接受 `session?: Session | null` 并喂给 `<SessionProvider session=...>`. 不升级 next-auth / next, 不改后端 auth/security/Guardrails. 新增 `server/tests/test_auth_session_e2e.py` 最小 E2E (注册→UI 登录+`/api/auth/callback/credentials` 兜底→等 dashboard URL→断言 `trigger-demo-attack` 45s 内可见 / `SYSTEM · LOADING` 消失 / `/api/auth/session` 返回 user / DOM 无 sentinel)。M3-08 `test_incident_report_e2e.py` helper 同步加 callback 兜底 + 列表点击等待 (M3-04 双 useIncidents 实例 race 规避)。**真实验证**: `pytest server/tests/test_auth_session_e2e.py --run-e2e` 1 passed; `pytest server/tests/test_incident_report_e2e.py --run-e2e` 1 passed (registered/demo/create/download/copy_status='已复制'/forbidden=None); 后端契约 14 passed; Guardrails 139 passed; 后端排除 SSRF (受限 DNS 环境失败, M3-06 验证正常网络下 13/13 pass) 后 319 passed + 4 skipped 0 回归; 前端 `npm run typecheck` 0 错误 + `npm run build` 通过 (`/dashboard` 43.4 kB / First Load JS 191 kB)。运行日志: `docs/runs/2026-06-19-next-01-auth-session-loading-e2e-recovery.md`。
- `docs/agent/NEXT_02_E2E_AND_SSRF_QUALITY_GATE_HARDENING_TASK.md`：L5 级 NEXT-02 E2E 与 SSRF 质量门硬化战役，覆盖 NEXT-01 后残留的两个质量门缺口：修复旧 `test_demo_flow_e2e.py` 使用 `expect_navigation` 等待 Next.js App Router client-side route 的不稳定登录路径，改为复用已验证的后端 API register + NextAuth callback cookie seeding + `/dashboard` 显式验收；同时让 `server/tests/test_ssrf.py` 的公网域名 build-url 测试用 monkeypatch 隔离真实 DNS，避免受限网络把公网域名解析到 `198.18.*` 等保留地址后误红。**重要边界**：不改生产 `server/analyzer.py` / `server/core/utils.py` SSRF 防护，不改认证生产代码，不跳过 Demo Flow E2E，不删除 Copilot fallback / triage / DOM forbidden sentinel 断言，不使用 `git add .`，不提交 `.coverage` / 真实 env / 数据库 / 密钥。目标质量门：`test_demo_flow_e2e.py --run-e2e`、`test_auth_session_e2e.py --run-e2e`、`test_incident_report_e2e.py --run-e2e`、`test_ssrf.py`、后端全量、Guardrails、前端 typecheck/build 全部通过。**已交付**（2026-06-19）：`server/tests/test_demo_flow_e2e.py` 的 `_register_via_ui` 重写为 NEXT-01 已验证路径——后端 API `/api/backend/auth/register`（409/"已存在"/"exists" 视为已存在）→ 等 `login-email` hydration + `login-submit` 可点击 → `/api/auth/csrf` + `/api/auth/callback/credentials` 直接种 httpOnly cookie → 点击 `login-submit` 兜底 → URL polling `window.location.pathname === '/dashboard'`，失败 fallback 显式 `page.goto("/dashboard")` 让服务端 `auth()` 决定接受/redirect；`pytestmark` 改成 `[pytest.mark.e2e]` 列表；`_wait_for_demo_button` timeout 从 15s 提到 45s。`server/tests/test_ssrf.py` 抽出 module 级 `allow_public_dns` fixture（monkeypatch `_is_url_pointing_to_internal -> False`）只在 `test_public_domain_ok` / `test_build_url_with_ssrf_check` / `test_build_url_strips_trailing_slash` / `test_build_url_with_subpath` 4 个公网域名测试上启用；新增 `test_allow_public_dns_fixture_does_not_bypass_literal_internal_ip` 双保险，确认 fixture 启用时 literal IP 仍走生产阻断；保留 `test_loopback_blocked` / `test_private_ip_blocked` / `test_link_local_blocked` / `test_cloud_metadata_blocked` / `test_build_url_rejects_internal` / `test_multicast_blocked` / `test_reserved_blocked` / `test_build_url_rejects_empty` / `test_empty_hostname` 不加 fixture。**未改**生产 `server/analyzer.py` / `server/core/utils.py` SSRF 逻辑，未改 `web-next/app/{dashboard,layout,providers}` / 后端认证/Guardrails/数据库/部署。Copilot fallback `API Key`/`Base URL`、triage `data-triage-status="investigating"`、DOM forbidden sentinel 断言全部保留。**真实验证**：`pytest server/tests/test_demo_flow_e2e.py --run-e2e` 1 passed (`registered/demo/copilot/triage` 全部 True / `forbidden=None`)；`pytest server/tests/test_auth_session_e2e.py --run-e2e` 1 passed；`pytest server/tests/test_incident_report_e2e.py --run-e2e` 1 passed (`copy_status='已复制'`)；`pytest server/tests/test_ssrf.py` 14 passed（13 原 + 1 新增保护测试，正常解开本地 DNS 环境失败）；`pytest server/tests` 333 passed, 4 skipped（4 个 e2e 默认 skip，与 NEXT-01 基线一致）；Guardrails 139 passed；前端 `npm run typecheck` 0 错误 + `npm run build` 通过（`/dashboard` 43.4 kB / First Load JS 191 kB）。运行日志：`docs/runs/2026-06-19-next-02-e2e-and-ssrf-quality-gate-hardening.md`。
- `docs/agent/M3_09_INCIDENT_STATE_AND_E2E_RESILIENCE_TASK.md`：L5 级 M3-09 案件状态单一事实源与 E2E 韧性战役，覆盖 NEXT-02 run log 留下的两个后续问题：`IncidentSection` 与 `dashboard-client.tsx` 各自独立 `useIncidents()` 导致从告警创建案件后必须点击列表项才能加载详情；三条 Playwright E2E 连续运行时多次注册会触发 `REGISTER_RATE_LIMIT_MAX=5/小时`，目前靠重启 dev server 解锁。任务目标：把 `useIncidents()` 提升到 `dashboard-client.tsx` 父层并传给 `IncidentSection`，让案件列表 / selected / detail / report 共用单一 state；新增复用的 `server/tests/e2e_helpers.py`，减少三条 E2E 重复 register + NextAuth callback 代码，并让 409 / 已存在 / 可用稳定测试账号路径自动恢复。**重要边界**：不改生产注册限流、不改后端 auth/token/cookie 语义、不改 Guardrails / SSRF / 数据库 schema，不把 token 写进 storage / DOM，不跳过浏览器 E2E。**已交付**（2026-06-19）：`web-next/hooks/useIncidents.ts` 末尾导出 `IncidentsController = ReturnType<typeof useIncidents>` 类型；`web-next/components/dashboard/IncidentSection.tsx` 改成接收 `incidents: IncidentsController` props,内部不再创建第二个 `useIncidents()` 实例,detail effect 增加 ready 短路避免重复拉取闪烁；`web-next/app/dashboard/dashboard-client.tsx` 把已存在的 `incidentsCtx` 注入 `<IncidentSection incidents={incidentsCtx} />`,从告警创建案件后列表 / selectedIncident / detail / 复制下载报告共享同一份 state。`server/tests/test_incident_report_e2e.py` 移除 `incident-list-item` 点击 workaround 改成直接等待 `incident-detail-panel` + 强制断言 list-item 与 detail-panel 的 `data-incident-id` 相同。新增 `server/tests/e2e_helpers.py`(`skip_without_playwright` / `unique_e2e_user` / `stable_e2e_user` / `classify_register_response` / `ensure_registered_or_rate_limited` / `login_with_nextauth_callback` / `ensure_dashboard_url` / `assert_dev_server_reachable` / `register_or_login_for_e2e` + `_stable_account_can_login`),429 fallback 路径优先走后端 `/auth/login/password` 探测稳定账号(限流更宽松,默认 10/5min),已存在则直接走 NextAuth callback 种 cookie 不再消耗 register 名额;不存在则 best-effort 一次 register。新增 `server/tests/test_e2e_helpers.py` 9 个纯函数单测覆盖 `classify_register_response` 三种状态 + `unique_e2e_user` 唯一性 + `stable_e2e_user` 默认 / env 覆盖。三条 E2E (`test_auth_session_e2e.py` / `test_demo_flow_e2e.py` / `test_incident_report_e2e.py`) 删除本地 `_register_unique_user` / `_register_via_ui` / `_register_and_login` / `_ensure_dashboard_url` / `_skip_without_playwright` / `_assert_dev_server_reachable` 重复实现,统一 import `server.tests.e2e_helpers`。**严格安全约束**:helper 仅使用 `page.request.post /api/backend/auth/register` + `/api/auth/callback/credentials`(httpOnly cookie),不写 `localStorage` / `sessionStorage` / DOM,不打印 cookie / token / password。**未改**:`server/services/auth_service.py` / `server/core/state.py` / `server/core/config.py` / `server/core/auth*` / `server/routers/auth*` / `server/security/**` / Alembic migration / `REGISTER_RATE_LIMIT_MAX=5` / `REGISTER_RATE_LIMIT_WINDOW=3600`。**真实验证**:`pytest server/tests/test_e2e_helpers.py` 9 passed;`pytest server/tests/test_auth_session_e2e.py --run-e2e` 1 passed;`pytest server/tests/test_demo_flow_e2e.py --run-e2e` 1 passed (`registered/demo/copilot/triage` True / `forbidden=None`);`pytest server/tests/test_incident_report_e2e.py --run-e2e` 1 passed (`registered/demo/create/download` 都 True / `copy_status='已复制'`,**不再依赖 incident-list-item 点击**,直接等到 `incident-detail-panel`);三条 E2E 连续运行 `test_auth_session_e2e.py test_demo_flow_e2e.py test_incident_report_e2e.py --run-e2e` 3 passed in 20.83s,即便 register 已被同 IP 限流到 429,helper 也能 fallback 到稳定账号 `e2e-{prefix}-stable@example.com` 路径登录(`session_user_email='e2e-auth-stable@example.com'` 已实测),不再需要重启 dev server;后端全量 `342 passed, 4 skipped`(NEXT-02 baseline 333 + e2e helper 9 = 342;0 失败,0 回归);Guardrails 专项 `139 passed`(0 回归);前端 `npm run typecheck` 0 错误 + `npm run build` 通过(`/dashboard` 43.4 kB / First Load JS 191 kB)。运行日志:`docs/runs/2026-06-19-m3-09-incident-state-and-e2e-resilience.md`。
- `docs/agent/M3_10_DASHBOARD_ROUTE_COMPOSITION_TASK.md`：L5 级 M3-10 Dashboard route composition 战役，目标是在不改业务语义、不碰后端认证/Guardrails/SSRF/DB schema 的前提下，把 `web-next/app/dashboard/dashboard-client.tsx` 从 800+ 行 route 渲染大文件收口成“父层 controller 编排 + 子组件 route section 渲染 + 单一路由元数据”。**已交付**（2026-06-19）：新增 `web-next/constants/dashboardRoutes.ts` 统一 `overview / monitor / incidents / waf / ai / report` 导航、index 与 route 描述；`SystemStatusBar.tsx` 改读单一路由元数据，桌面/移动导航均补 `incidents` 一等入口、`data-testid`、`data-dashboard-route` 与 `aria-current`；新增 `SectionHeading` / `DashboardFields` / `DashboardRows` 与 `web-next/components/dashboard/sections/*.tsx`，把 route JSX 拆为 briefing、trends、alerts、terminal report、security timeline、incidents、system status、copilot、AI config、webhook、report 等 section；`dashboard-client.tsx` 从 840 行降到 406 行，继续持有所有业务 hook/controller 与跨区块 handler，子组件只接收 props 渲染 UI，未在 section 内重新创建 `useIncidents()` / `useAlerts()` 等业务 hook。新增 `server/tests/test_dashboard_route_sections_e2e.py`，先跑出目标 RED（缺少 `dashboard-section-stats` wrapper），再 GREEN 锁定六个 route tab 与核心 section wrapper。**真实验证**：新增 Dashboard route E2E `1 passed`；Auth/Demo/Incident/Dashboard 四条连续 E2E `4 passed in 32.46s`；后端全量 `342 passed, 5 skipped, 17 warnings`；Guardrails `139 passed, 17 warnings`；前端 `npm run typecheck` 与 `npm run build` 均通过（`/dashboard` 44 kB / First Load JS 191 kB）。**未改**认证/授权、Guardrails、SSRF、DB schema、后端 API、npm 依赖；未提交 `.coverage` / env / DB / 密钥。运行日志：`docs/runs/2026-06-19-m3-10-dashboard-route-composition.md`。
- `docs/agent/M3_11_DASHBOARD_SECTION_RESPONSIVE_QA_TASK.md`：L5 级 M3-11 Dashboard section 响应式 QA 与可访问性收口战役，覆盖桌面/移动真实浏览器 E2E、六个 route tab、核心 section wrapper、整页横向溢出、按钮文字溢出、icon-only 按钮命名、键盘 Enter 切换、DOM forbidden sentinel、截图证据、必要轻量 UI 修复、文档同步和通过后精确 push。**重要边界**：不改认证/授权、Guardrails、SSRF、DB schema、后端 API、npm 依赖，不重做视觉设计，不提交 `.coverage` / env / DB / 密钥。**已交付**（2026-06-19）：新增 `server/tests/test_dashboard_responsive_e2e.py`（默认 skip，需 `--run-e2e`），parametrize 桌面 1366×900 与移动 390×844 viewport，覆盖六个 route 切换、`aria-current=page`、核心 section wrapper、整页横向溢出（`scrollWidth ≤ clientWidth + 4`）、按钮文字溢出、icon-only 按钮 `title` / `aria-label`、键盘 Tab+Enter 路由切换、DOM forbidden sentinel（`sk-...` / `AKIA...` / `ghp_...` / `Traceback` / `ignore previous instructions` / `system:` / `developer:` / `PRIVATE KEY` 等），失败留 screenshot，成功保留 `desktop-overview.png` / `desktop-incidents.png` / `mobile-overview.png` / `mobile-incidents.png` 共 168 KB。RED 准确暴露 `SystemStatusBar.tsx` 主题切换按钮（`Moon` / `Sun`）与 `CopilotPanel.tsx` Copilot 提交按钮（`Send`）属于 icon-only 但缺 `title` / `aria-label`。GREEN 仅在 `web-next/components/dashboard/SystemStatusBar.tsx`（主题切换补 `title` + `aria-label`，已有 `title` 的 Bell / LogOut 顺手补 `aria-label`）和 `web-next/components/dashboard/CopilotPanel.tsx`（Send 提交按钮补 `title` + `aria-label`）共 6 行 +0 行 - 改动；**未改**业务 hook、state、路由、prompt、props 结构。**真实验证**：`pytest server/tests/test_dashboard_responsive_e2e.py --run-e2e` 2 passed in 17.40s（桌面 + 移动）；`pytest server/tests/test_dashboard_route_sections_e2e.py --run-e2e` 1 passed；五条 E2E 连续 `pytest server/tests/test_auth_session_e2e.py test_demo_flow_e2e.py test_incident_report_e2e.py test_dashboard_route_sections_e2e.py test_dashboard_responsive_e2e.py --run-e2e` 6 passed in 46.64s（重启 backend 清空 register rate limit 后；session_user_email='e2e-auth-local-...@example.com'，demo registered/demo/copilot/triage 全部 True，incident copy_status='已复制'，responsive desktop+mobile forbidden=None）；后端全量 `pytest server/tests` 342 passed, 7 skipped, 17 warnings；Guardrails 139 passed；前端 `npm run typecheck` 0 错误 + `npm run build` 通过（`/dashboard` 44 kB / First Load JS 191 kB）。**未改**认证/授权、Guardrails、SSRF、DB schema、后端 API、npm 依赖；未把 token 写进 `localStorage` / `sessionStorage` / DOM；未提交 `.coverage` / env / DB / 密钥。运行日志：`docs/runs/2026-06-19-m3-11-dashboard-section-responsive-qa.md`。
- `docs/agent/M3_02_PUSH_READINESS_AND_DOCS_CATCHUP_TASK.md`：L5 级 M3-02 推送前总审查与文档补交战役，覆盖本地 5 个 M3-02 commit 复核、遗漏任务文档补交、最终验证矩阵、禁止文件审查和通过后推送 `origin/main`。

当前 owner 偏好：

- 后续每次布置给 agent 的任务都默认写成 L4/L5 超长任务。
- 即使目标看起来像“小修复”或“提交收口”，也要包装成阶段化长任务：上下文读取、运行日志、验证矩阵、停止条件、提交/不提交边界。
- 聊天框里只发送短启动口令，详细任务放在 `docs/agent/*.md`。

最近一次 L5 战役执行结果（`docs/runs/2026-06-16-m2-soc-operations-baseline.md`）：

- 13 个阶段全部完成（基线 → E2E → Contract → Timeline → Security check → De-sloppify → 验证矩阵 → 安全审查 → 文档同步 → 最终报告）。
- 239 passed, 2 skipped, 139 guardrails passed；前端 typecheck/build 通过；env security check 本地开发返回 0。
- 新增 `test_demo_flow_e2e.py` / `test_copilot_contract.py` / `test_security_timeline.py`，共 19 个新测试。
- 建议在下一个 owner 工单里 stage 工作树并拆分为 5 个 commit（参考 `docs/runs/...-m2-soc-operations-baseline.md` 阶段 13）。

推荐启动口令：

```text
请基于 M3-11 的成果挑选下一条最小风险工单（建议候选：M3-12 Demo Flow E2E 连续运行稳定化 —— Copilot 降级态在五条 E2E 串跑时偶发 15s 超时；或 M3-12 Dashboard 移动 viewport 视觉精修：在不重做视觉设计的前提下，复用 M3-11 截图证据排查移动 overview/incidents 页面的字号、间距、卡片层级；或 M3-12 Incident report Markdown 截断/payload preview UX 收口）。在写新任务文档前必须读 `PRODUCT.md`、`AGENTS.md`、`CLAUDE.md`、`docs/agent/UNATTENDED_LONG_TASKS.md` 与 `docs/runs/2026-06-19-m3-11-dashboard-section-responsive-qa.md`，把候选包装成 L5 阶段化长任务（运行日志、TDD 红绿、验证矩阵、停止条件、精确 commit / push 边界），落到 `docs/agent/*.md`，再发短启动口令；继续禁止改认证/授权/Guardrails/SSRF/DB schema，禁止 `git add .`，禁止提交 `.coverage` / 真实 env / 数据库 / 密钥。
```

### 下一条建议工单（M3-11 已交付后）

**L5 / M3-12 候选**：
1. **Demo Flow E2E 五条连续运行稳定化**：M3-11 五条 E2E 连续运行时 `test_demo_flow_e2e.py` 第二次跑偶发 `Copilot 未在 15s 内返回降级态消息`（重启 backend 后通过）。下一条工单可在不放宽断言的前提下，把 Copilot fallback 等待提升为长 poll + diagnostic capture，或显式 isolate `analyze-current-alert` 与上一条 E2E 的浏览器/会话副作用。
2. **Dashboard 移动 viewport 视觉精修**：基于 `docs/runs/artifacts/m3-11-dashboard-responsive/mobile-*.png` 排查移动端字号、卡片层级、间距是否需要轻量修复，仍限定 layout class 调整，不重做视觉。
3. **Incident report Markdown payload preview UX 收口**：M3-07 报告导出已交付，但 markdown 中 payload preview 在 dashboard 复制按钮 / 下载按钮的 UX 还可补齐 toast / loading state 细节。
任何候选都必须先固化成 `docs/agent/M3_12_*_TASK.md` 工单文档，再发短启动口令，禁止改 auth / Guardrails / SSRF / DB schema。

---

## 9. 推荐无人值守队列

当前项目最适合无人值守的顺序：

1. **L1 / M0-01**：修复 README 与关键文档乱码，重写小白启动说明。
2. **L2 / M0-CI-COVERAGE-01**：对齐后端 CI 覆盖率门槛，补覆盖率或拆分覆盖率边界，不降低真实测试强度。
3. **L2 / M0-E2E-01**：安装 Playwright 浏览器并启动前后端后，跑通真实 `--run-e2e`。
4. **L2 / M1-01**：建立 demo 攻击闭环脚本和 smoke test。
5. **L2 / M1-02**：优化 Copilot 失败态与 Guardrails 拦截态 UI。

不建议一上来让 agent 做：

- 大规模重构 dashboard。
- Alembic 迁移。
- 改认证 / 授权。
- 改 LLM Guardrails 核心策略。
- 自动部署。

这些可以做，但要先写 RFC，再半自动执行。
