# M2 SOC Operations Baseline Task

> 用途：给 AI Agent 执行的 L5 级超长任务说明。
> 使用方式：不要复制全文，只让 agent 读取并执行本文件。
> 当前建议任务名：`M2 SOC OPERATIONS BASELINE CAMPAIGN`

## 0. 给用户的短启动口令

把下面这一小段发给 agent 即可：

```text
请执行 `docs/agent/M2_SOC_OPERATIONS_BASELINE_TASK.md` 中定义的 L5 超长任务。先完整阅读该文件和其中列出的必读上下文，创建运行日志，按阶段推进；不要问我小问题，不要 commit/push/reset/clean，不要使用 git add .。完成后按任务文档输出最终报告。
```

## 1. 角色与目标

你是 AI-CyberSentinel 的临时技术负责人、产品负责人、测试负责人和安全负责人。

本任务不是做一个小功能，而是把当前 M1-M2 产品化基线继续推进成“小型 SOC 可运营基线”。

主线目标：

1. 固化 Demo Flow 自动化 E2E。
2. 建立 Copilot fake provider / contract 测试。
3. 建立最小安全运营时间线。
4. 建立生产最小安全配置检查。
5. 同步文档、验证矩阵和提交候选。

## 2. 当前背景

- 已完成 commit：`chore: 建立 M1-M2 产品化基线`。
- 当前工作树理论上只剩 `.coverage` 和 `.claude/settings.local.json` 两个本地改动。
- 不要提交它们，不要 stage 它们，不要 reset 它们。
- 本轮不要 push。
- 本轮不要 git reset，不要 git clean，不要删除未知文件。
- 不要使用 `git add .`。

## 3. 启动前必读

必须先读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `README.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`
- `docs/runs/2026-06-16-m1-m2-landing-campaign.md`
- `docs/runs/2026-06-16-m1-m2-productization-campaign.md`

启动后先确认：

```powershell
git status --short --branch
```

如果出现 `.coverage` 和 `.claude/settings.local.json` 之外的新改动，先记录来源，不要覆盖。

## 4. 硬规则

必须遵守：

- 全程中文回复。
- 遵守 skill-first workflow。
- 安全相关改动必须按 security-review 思路执行。
- 测试相关改动必须按 TDD / python-testing / e2e-testing 思路执行。
- 前端改动必须按 frontend-patterns / frontend-design 思路执行。
- 每个阶段必须更新运行日志。
- 能从代码和文档推断的问题自行决定，不要问用户小问题。

禁止：

- 不要 push。
- 不要 commit，除非用户在任务后明确要求。
- 不要 git reset。
- 不要 git clean。
- 不要删除未知文件。
- 不要使用 `git add .`。
- 不要修改真实 `.env` / `.env.local`。
- 不要提交 `.coverage`、`.claude/settings.local.json`、`server/.coverage`、`htmlcov/`、`.next/`、数据库。
- 不要弱化认证、授权、Guardrails、MCP 鉴权、SSE error 净化。
- 不要引入真实 API key。
- 不要把 E2E 放回默认必跑基线。
- 不要把 fake provider 暴露成生产默认 provider。
- 不要做数据库/Alembic 大迁移。
- 不要做 Docker Compose 端到端改造。
- 不要重写前端框架。
- 不要重写认证系统。

## 5. 运行日志

创建并持续更新：

```text
docs/runs/YYYY-MM-DD-m2-soc-operations-baseline.md
```

每个阶段必须记录：

- 目标
- 已读文件
- 改动文件
- 验证命令
- 结果
- 风险
- 下一阶段计划

如果上下文快满，写：

```text
docs/runs/YYYY-MM-DD-m2-soc-operations-handoff.md
```

handoff 必须包含：

- 已完成阶段
- 未完成阶段
- 当前 git 状态
- 已改文件
- 已跑验证
- 失败和阻塞
- 下一步建议

## 6. 预算与停止条件

按 12-24 小时任务设计。

至少推进 8 个阶段。同一失败最多修复 3 轮。如果一个阶段遇到非关键阻塞，记录后转向下一个阶段，不要卡死。

满足任一条件必须停止并总结：

- 需要真实生产 key。
- 需要破坏性 git 操作。
- 需要重写认证或 Guardrails。
- 测试大面积失败且 3 轮无法定位。
- 发现安全泄漏且无法安全修复。
- 工作树出现用户未知改动冲突。
- 上下文不足且没有写 handoff。

## 7. 阶段 0：启动审计与基线确认

目标：确认任务开始时的工作树、测试基线和禁止文件状态。

执行：

```powershell
git status --short --branch
git log -1 --oneline
```

确认：

- 当前 commit 是 M1-M2 产品化基线之后。
- 未提交文件只应包含 `.coverage` 和 `.claude/settings.local.json`。
- 这两个文件不能 stage。

运行基础 smoke：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.\.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
.\.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow.py -q --tb=short
```

前端：

```powershell
cd web-next
npm run typecheck
```

## 8. 阶段 1：M2-02 Demo Flow E2E 方案

目标：把手工 Demo Flow 浏览器验收固化为可重复 E2E。

读取：

- `server/tests/test_e2e.py`
- `server/tests/conftest.py`
- `server/tests/test_demo_flow.py`
- `web-next/app/page.tsx`
- `web-next/app/dashboard/dashboard-client.tsx`
- `web-next/hooks/useAlerts.ts`
- `web-next/components/dashboard/CopilotPanel.tsx`
- `README.md`

设计要求：

- 默认 `pytest server/tests` 仍跳过真实浏览器 E2E。
- 显式 `--run-e2e` 才运行浏览器测试。
- 缺少 Playwright 或浏览器时清晰 skip。
- 不依赖真实 LLM API key。
- 不依赖公网。
- 可连接已有 dev server，或清晰说明需要先启动服务。
- 如需稳定选择器，只允许少量 `data-testid`。

输出到运行日志：

- E2E 入口策略。
- 是否自启动前后端。
- 缺依赖时 skip 策略。
- 选择器方案。

## 9. 阶段 2：实现 Demo Flow E2E

目标路径：

1. 注册或登录测试用户。
2. 进入 Dashboard。
3. 点击触发 Demo 攻击。
4. 等待告警表出现 Demo 告警。
5. 点击分析当前告警。
6. 验证无 API Key/Base URL 时 Copilot 显示清晰降级态。
7. 验证页面不显示 stack trace、Traceback、`sk-`、regex 细节。

允许修改：

- `server/tests/test_e2e.py`
- `server/tests/conftest.py`
- 必要前端 `data-testid`
- `README.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`

验收：

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\test_e2e.py -q --tb=short
.\.venv\Scripts\python.exe -m pytest server\tests\test_e2e.py -q --tb=short --run-e2e
.\.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

如果显式 E2E 因缺浏览器 skip，必须证明 skip 文案清晰。

## 10. 阶段 3：M2-06 Copilot Contract 方案

目标：让有 key 的 Copilot 成功流式路径可测，不依赖真实外部 LLM。

读取：

- `server/services/copilot_service.py`
- `server/services/llm_providers.py`
- `server/models/schemas.py`
- `server/tests/test_demo_flow.py`
- `server/tests/security/llm_guardrails/`

要求：

- Fake provider 只能用于测试。
- 不能成为生产默认 provider。
- 不能绕过 Guardrails input/output 检查。
- 不能记录真实 prompt 或真实 key。
- 测试覆盖无 key 降级态、fake provider 成功 SSE、`alert_id` 上下文拼接、Guardrails block 时错误净化。

优先策略：

1. 如果现有 provider 架构支持 monkeypatch，优先写测试 fixture。
2. 如果必须新增 fake provider，只能通过测试环境显式启用。
3. 生产配置不可默认走 fake。

## 11. 阶段 4：实现 Copilot Fake Provider / Contract 测试

允许修改：

- `server/services/llm_providers.py`
- `server/services/copilot_service.py`
- `server/tests/**`

验收：

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow.py -q --tb=short
.\.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
.\.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

必须在运行日志说明：

- fake 路径是否进入生产代码。
- Guardrails 是否仍执行。
- SSE 成功路径和降级路径分别如何验证。

## 12. 阶段 5：M2-03 审计时间线方案

目标：让 Dashboard 可看到“安全运营时间线”，但不泄露敏感信息。

读取：

- `server/security/llm_guardrails/audit.py`
- `server/routers/logs_router.py`
- `server/models_db.py`
- `web-next/app/dashboard/dashboard-client.tsx`
- `web-next/components/dashboard/**`
- `web-next/hooks/**`

用户可见 timeline 只显示安全摘要，例如：

- demo attack generated
- copilot requested
- guardrail passed / blocked / warning
- auth/config relevant events if already available

用户可见内容不得包含：

- regex 模式
- stack trace
- API key
- system prompt
- 原始敏感 payload

要求：

- SOC 排查所需完整 reason 可以留在 audit log，不要丢。
- audit 写失败不能导致用户主请求失败。
- 查询必须分页或限量。

## 13. 阶段 6：实现最小审计时间线

允许修改：

- `server/security/llm_guardrails/audit.py`
- `server/routers/logs_router.py` 或新增小路由
- `server/services/**` 中最小必要部分
- `web-next/components/dashboard/**`
- `web-next/app/dashboard/dashboard-client.tsx`
- `web-next/types/**`
- 相关测试

最小实现：

1. 后端提供当前用户最近安全事件接口，例如 `/logs/security-timeline`。
2. 返回固定上限，例如最近 50 条。
3. Dashboard 新增轻量时间线区域。
4. Demo attack 和 Copilot 降级至少能形成可理解事件。
5. Guardrails 事件如果已有审计数据，展示类别摘要；数据不足时只展示安全字段。

验收：

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
.\.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
cd web-next
npm run typecheck
npm run build
```

测试必须覆盖：

- 未登录不能读 timeline。
- limit 有上限。
- 返回值不包含 regex、stack trace、API key、system prompt。

## 14. 阶段 7：M2-04 生产最小安全配置检查

目标：让部署前最容易踩雷的安全配置可检查、可解释。

读取：

- `scripts/check_env_security.py`
- `.env.example`
- `README.md`
- `OWNER_MANUAL.md`
- `nginx/nginx.conf`
- `docker-compose.yml`
- `server/core/config.py`
- `server/main.py`
- `server/security/llm_guardrails/mcp_server.py`

检查项至少包含：

- `APP_SECRET`
- `AUTH_SECRET`
- `GUARDRAILS_MCP_API_KEY`
- `ALERTS_INGEST_TOKEN`
- CORS origins
- trusted hosts
- production debug/config
- metrics/MCP 暴露说明

要求：

- 不写真实 secret。
- 不要求本地开发必须配置生产项。
- 生产模式下缺失关键 secret 必须有清晰失败或警告。
- README 中说明如何运行检查。

验收：

```powershell
python scripts/check_env_security.py
```

如果项目使用 `.venv`：

```powershell
.\.venv\Scripts\python.exe scripts\check_env_security.py
```

输出必须清晰区分：

- 本地开发提醒
- 生产阻塞项
- 安全建议项

## 15. 阶段 8：产品体验整理与前端 de-sloppify

目标：避免前面阶段把 Dashboard 搞乱。

检查：

- Dashboard 文案是否面向安全分析员。
- 按钮状态是否清晰。
- 长文本是否溢出。
- 无 API key 时是否明确告诉用户下一步。
- timeline 是否泄露敏感字段。
- 是否新增 `console.log`、`debugger`、临时账号。

允许小范围优化：

- 组件拆分
- 文案
- 空状态
- loading/error 状态
- `data-testid`

禁止：

- 不要重写视觉系统。
- 不要做 landing page。
- 不要引入大 UI 库。
- 不要大面积重构 Dashboard。

验收：

```powershell
cd web-next
npm run typecheck
npm run build
```

如果浏览器工具可用，做一次 Dashboard smoke。

## 16. 阶段 9：全量验证矩阵

必须运行：

```powershell
git status --short --branch
git diff --stat
git diff --check
```

后端：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.\.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
.\.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
.\.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow.py -q --tb=short
.\.venv\Scripts\python.exe -m pytest server\tests\test_e2e.py -q --tb=short
.\.venv\Scripts\python.exe -m pytest server\tests\test_e2e.py -q --tb=short --run-e2e
.\.venv\Scripts\python.exe -m pytest server\tests\test_logging_setup.py server\tests\test_ssrf.py -q --tb=short
```

前端：

```powershell
cd web-next
npm run typecheck
npm run build
```

Secret scan：

```powershell
rg -n --hidden --glob '!web-next/node_modules/**' --glob '!node_modules/**' --glob '!web-next/.next/**' --glob '!.git/**' --glob '!*.pkl' --glob '!*.db' --glob '!*.ico' --glob '!*.png' --glob '!*.jpg' --glob '!*.jpeg' --glob '!*.gif' --glob '!*.pdf' --glob '!*.coverage' -- 'sk-[A-Za-z0-9_-]{24,}|sk-proj-[A-Za-z0-9_-]+|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|xox[baprs]-[A-Za-z0-9-]+|PRIVATE KEY' .
```

如果某项无法运行：

- 写清原因。
- 写替代验证。
- 不要假装通过。

## 17. 阶段 10：安全审查

重点审查：

- `/alerts/demo` 仍必须登录。
- timeline 接口必须登录。
- timeline 不泄露 regex、stack trace、API key、system prompt。
- Copilot fake provider 不可生产默认启用。
- Guardrails fail-closed / SSE 净化没有被弱化。
- MCP 鉴权没有被绕过。
- 没有真实 secret。
- 没有把 `.coverage`、`.claude/settings.local.json`、数据库、`.env` 纳入提交候选。

输出：

- 阻塞风险
- 非阻塞风险
- 已修复风险
- 后续债务

## 18. 阶段 11：文档同步

更新：

- `README.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`
- 必要时 `server/STRUCTURE.md`

文档必须写清：

- 怎么跑 E2E。
- 怎么跑 Copilot contract test。
- 怎么看安全时间线。
- 怎么跑 env security check。
- 哪些东西仍然是 M2 剩余债务。

## 19. 阶段 12：最终 de-sloppify

清理：

- `console.log`
- `debugger`
- 临时文件
- 过度测试
- 无意义注释
- 重复文档
- 本地构建产物
- 被错误 stage 的文件

保留：

- 业务测试
- 安全测试
- 运行日志
- 有实际解释价值的文档

检查：

```powershell
rg -n -- "console\.log|debugger|TODO\(|FIXME|temporary|tmp-|campaign-" server web-next scripts docs
git status --short --branch
```

## 20. 阶段 13：提交准备，但不要提交

最终允许精确 stage，但不 commit。

要求：

1. 先输出建议 commit 拆分。
2. 每个 commit 给中文 message。
3. 每个 commit 给文件清单。
4. 每个 commit 给验证命令。
5. 只允许用精确路径 stage。
6. 不允许 `git add .`。
7. 如果 `.coverage` 或 `.claude/settings.local.json` 被 stage，立即停止并报告。

建议拆分：

1. `test/e2e: 固化 Demo Flow 浏览器验收`
2. `test/copilot: 增加 Copilot fake provider contract 测试`
3. `feat/audit: 增加安全运营时间线`
4. `security: 增加生产最小安全配置检查`
5. `docs: 同步 M2 运行手册与路线图`

禁止 stage：

- `.coverage`
- `.claude/settings.local.json`
- `server/.coverage`
- `htmlcov/`
- `web-next/.next/`
- `web-next/tsconfig.tsbuildinfo`
- `data/app.db`
- 任何真实 `.env` / `.env.local`

## 21. 最终输出格式

完成时输出：

```text
完成阶段：
- 

改动文件：
- 代码：
- 测试：
- 前端：
- 文档：
- 脚本：

验证结果：
- 

安全审查：
- 阻塞：
- 非阻塞：
- 已修复：

Git 状态：
- 已 stage：
- 未 stage：
- 不能提交：

Ready for commit：
- 是 / 否
- 原因：

下一条超长任务建议：
-
```

## 22. 判断完成的标准

至少满足以下条件才可以说完成：

- 运行日志完整。
- 至少推进 8 个阶段，或清楚说明阻塞。
- 默认后端测试通过。
- Guardrails 专项通过。
- Demo Flow 测试通过。
- 前端 typecheck/build 通过。
- E2E 默认 skip/显式运行策略清楚。
- Copilot contract 路径有验证。
- 安全时间线不泄露敏感字段。
- env security check 可运行或清楚说明阻塞。
- 文档同步。
- 禁止文件未 stage。

