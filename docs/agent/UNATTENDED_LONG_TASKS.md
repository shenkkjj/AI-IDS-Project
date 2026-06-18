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
请执行 `docs/agent/M2_SOC_OPERATIONS_BASELINE_TASK.md` 中定义的 L5 超长任务。先完整阅读该文件和其中列出的必读上下文，创建运行日志，按阶段推进；不要问我小问题，不要 commit/push/reset/clean，不要使用 git add .。完成后按任务文档输出最终报告。
```

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
