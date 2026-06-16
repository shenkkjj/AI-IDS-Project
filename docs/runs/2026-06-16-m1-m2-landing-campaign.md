# Run: M1-M2 LANDING AND CONTINUATION CAMPAIGN

开始时间：2026-06-16
运行模式：L4，落地整理与继续开发基线
预算：复核当前巨大未提交工作树，完成质量门、风险审查、提交拆分和可选精确 stage；不 commit，不 push。

## 目标

- 把当前未提交工作树整理成“可审查、可提交、可继续开发”的状态。
- 明确提交候选、本地产物、禁止提交文件和后续 M2 节奏。
- 保留安全边界：认证、授权、Guardrails、MCP 鉴权、SSE error 净化不弱化。

## 硬边界

禁止：
- `git push`
- `git reset`
- `git clean`
- 删除未知文件
- `git add .`
- 提交 `.coverage`、`.claude/settings.local.json`、`server/.coverage`、`htmlcov/`、`.next/`、数据库、真实 `.env`
- 弱化认证、授权、Guardrails、MCP 鉴权、SSE error 净化

允许：
- 读取和审计全仓。
- 写入本运行日志。
- 运行测试、构建、secret scan、diff 检查。
- 验证通过且提交候选清晰后，按精确路径 stage。

## 已使用 Skill

- `careful`：约束 destructive/git 操作。
- `terminal-ops`：证据优先执行命令并记录状态。
- `verification-loop`：最终质量门。
- `security-review`：secret、认证、错误泄漏、外部输入和敏感边界审查。
- `review`：采用其 pre-landing 差异审查和证据引用思路；不采用自动 commit/push 路径。
- `document-generate`：用于文档一致性和可发现性检查；不采用其提交发布步骤。

## 必读上下文

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/runs/2026-06-16-m1-m2-productization-campaign.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

## 阶段 0：工作树审计

### 命令

```powershell
git status --short --branch
git diff --stat
git ls-files --others --exclude-standard
git check-ignore -v .coverage server/.coverage htmlcov web-next/.next web-next/tsconfig.tsbuildinfo data/app.db
git diff --name-status
git ls-files .coverage .claude/settings.local.json server/.coverage htmlcov web-next/.next web-next/tsconfig.tsbuildinfo data/app.db
```

### 实时状态

- 分支：`main...origin/main [ahead 4]`
- 工作树：大量 tracked 修改 + 多个 untracked 交付文件。
- `git diff --stat`：27 个 tracked 文件，约 1050 行新增、438 行删除，另有二进制 `.coverage` 变化。
- 已跟踪但绝对不能提交：
  - `.coverage`
  - `.claude/settings.local.json`
- 已被 ignore 覆盖的本地产物：
  - `server/.coverage`
  - `htmlcov/`
  - `web-next/.next/`
  - `web-next/tsconfig.tsbuildinfo`
  - `data/app.db`

### 改动分组

#### 1. M0 稳定化与 CI

提交候选：
- `.github/workflows/ci.yml`
- `server/tests/conftest.py`
- `server/tests/test_e2e.py`
- `web-next/package.json`
- `web-next/app/api/backend/[...path]/route.ts`
- `web-next/types/terminal.ts`
- `web-next/utils/terminalUtils.ts`

含义：
- 后端默认测试与可选 E2E 口径稳定化。
- 前端 typecheck/build 命令与 Next.js 版本下的构建细节对齐。
- CI 不再依赖交互式 lint。

#### 2. M1 Demo Flow

提交候选：
- `server/routers/alerts_router.py`
- `server/services/alert_service.py`
- `server/tests/test_demo_flow.py`
- `scripts/demo_attack.ps1`
- `web-next/app/dashboard/dashboard-client.tsx`
- `web-next/components/dashboard/CopilotPanel.tsx`
- `web-next/hooks/useAlerts.ts`
- `web-next/types/alert.ts`

含义：
- 认证态 `/alerts/demo` 与后端 demo 告警生成。
- Dashboard 触发 Demo、告警表可见、Copilot 当前告警分析。
- 无 API Key/Base URL 时的明确降级态。

#### 3. M1-M2 产品化与安全卫生

提交候选：
- `.gitignore`
- `server/core/logging_setup.py`
- `server/tests/test_logging_setup.py`
- `server/tests/test_ssrf.py`
- `server/tests/manual/legacy/README.md`
- `server/tests/manual/legacy/audit_test.py`
- `server/tests/manual/legacy/comprehensive_test.py`
- `server/tests/manual/legacy/run_tests.py`
- `web-next/app/page.tsx`

含义：
- JSON 日志稳定化。
- SSRF 测试去除外网 DNS 依赖。
- legacy 手工脚本 fake key 和 token 输出卫生。
- 首页后端错误详情净化，避免 Pydantic 数组 detail 变成不可理解错误。

#### 4. 文档与路线图

提交候选：
- `AGENTS.md`
- `README.md`
- `PRODUCT.md`
- `docs/ALEMBIC_MIGRATION.md`
- `docs/RELEASE_NOTES.md`
- `server/STRUCTURE.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`
- `docs/runs/2026-06-15-m0-01-docs-cleanup.md`
- `docs/runs/2026-06-15-m0-ci-green.md`
- `docs/runs/2026-06-15-m0-stabilize.md`
- `docs/runs/2026-06-15-m1-demo-flow.md`
- `docs/runs/2026-06-16-m1-m2-productization-campaign.md`
- `docs/runs/2026-06-16-m1-m2-landing-campaign.md`

含义：
- README/PRODUCT/STRUCTURE/路线图口径对齐到 2026-06-16 验证结果。
- 运行日志作为 agent 接力证据。

#### 5. 不应提交的本地产物

绝对不提交：
- `.coverage`
- `.claude/settings.local.json`
- `server/.coverage`
- `htmlcov/`
- `web-next/.next/`
- `web-next/tsconfig.tsbuildinfo`
- `data/app.db`
- 任何真实 `.env` / `.env.local`

说明：
- `.coverage` 和 `.claude/settings.local.json` 是 tracked 修改，后续精确 stage 时必须避开。
- 本轮不 reset、不 clean、不删除这些文件。

### 阶段 0 结论

- 当前工作树可以整理成 4 个主要提交主题。
- 不能使用 `git add .`，因为会混入禁止提交文件。
- 下一阶段进入提交候选清单：逐个确认 untracked 文件是否应纳入版本控制，并写清楚每组不提交项。

## 阶段 1：提交候选清单

### 命令

```powershell
git ls-files --others --exclude-standard
git diff -- .gitignore
git diff -- .github/workflows/ci.yml web-next/package.json server/tests/conftest.py server/tests/test_e2e.py
git diff -- server/routers/alerts_router.py server/services/alert_service.py web-next/app/dashboard/dashboard-client.tsx web-next/components/dashboard/CopilotPanel.tsx web-next/hooks/useAlerts.ts web-next/types/alert.ts
git diff -- server/core/logging_setup.py server/tests/test_ssrf.py web-next/app/page.tsx server/tests/manual/legacy/README.md server/tests/manual/legacy/audit_test.py server/tests/manual/legacy/comprehensive_test.py server/tests/manual/legacy/run_tests.py
Get-Content -Raw scripts/demo_attack.ps1
Get-Content -Raw server/tests/test_demo_flow.py
Get-Content -Raw server/tests/test_logging_setup.py
```

### 未跟踪文件判定

应纳入版本控制：
- `PRODUCT.md`：产品操作系统，是 README/AGENTS 之外的产品事实源。
- `docs/agent/UNATTENDED_LONG_TASKS.md`：无人值守长任务协议，是后续 M2 执行入口。
- `docs/plans/M2_PRODUCT_ROADMAP.md`：M2 路线图和 agent 工单。
- `docs/runs/2026-06-15-m0-01-docs-cleanup.md`：历史运行证据。
- `docs/runs/2026-06-15-m0-ci-green.md`：历史运行证据。
- `docs/runs/2026-06-15-m0-stabilize.md`：历史运行证据。
- `docs/runs/2026-06-15-m1-demo-flow.md`：历史运行证据。
- `docs/runs/2026-06-16-m1-m2-productization-campaign.md`：上一轮产品化完整证据。
- `docs/runs/2026-06-16-m1-m2-landing-campaign.md`：本轮 landing 证据。
- `scripts/demo_attack.ps1`：本地 Demo Flow smoke 脚本，使用用户输入账号密码，不硬编码真实 secret，不打印 token。
- `server/tests/test_demo_flow.py`：Demo Flow 后端和 Copilot 降级态测试，使用 fake DB/user/provider。
- `server/tests/test_logging_setup.py`：JSON 日志 sink 回归测试。

不纳入版本控制：
- 无。本轮 `git ls-files --others --exclude-standard` 中未发现数据库、coverage、`.next`、真实 `.env` 或其他本地产物。

### 每组建议提交文件

#### Commit A：M0 稳定化与 CI

建议提交：
- `.github/workflows/ci.yml`
- `server/tests/conftest.py`
- `server/tests/test_e2e.py`
- `web-next/package.json`
- `web-next/app/api/backend/[...path]/route.ts`
- `web-next/types/terminal.ts`
- `web-next/utils/terminalUtils.ts`

不提交：
- `.coverage`
- `.claude/settings.local.json`
- `web-next/.next/`
- `web-next/tsconfig.tsbuildinfo`

理由：
- 这些文件共同把默认后端测试、可选 E2E、前端 typecheck/build 和 CI 口径对齐。

#### Commit B：M1 Demo Flow 安全闭环

建议提交：
- `server/routers/alerts_router.py`
- `server/services/alert_service.py`
- `server/tests/test_demo_flow.py`
- `scripts/demo_attack.ps1`
- `web-next/app/dashboard/dashboard-client.tsx`
- `web-next/components/dashboard/CopilotPanel.tsx`
- `web-next/hooks/useAlerts.ts`
- `web-next/types/alert.ts`

不提交：
- 任意本地数据库。
- 任意真实 provider key。

理由：
- 这些文件共同构成“登录后触发 Demo -> 告警可见 -> Copilot 分析或降级”的可演示闭环。

#### Commit C：安全卫生、日志与测试稳定化

建议提交：
- `.gitignore`
- `server/core/logging_setup.py`
- `server/tests/test_logging_setup.py`
- `server/tests/test_ssrf.py`
- `server/tests/manual/legacy/README.md`
- `server/tests/manual/legacy/audit_test.py`
- `server/tests/manual/legacy/comprehensive_test.py`
- `server/tests/manual/legacy/run_tests.py`
- `web-next/app/page.tsx`

不提交：
- `.coverage`
- `server/.coverage`
- `htmlcov/`
- 真实 `.env`

理由：
- 这些文件处理真实落地风险：覆盖率产物污染、疑似真实 key、token 日志、JSON 日志运行时错误、SSRF 测试外网依赖、前端错误详情净化。

#### Commit D：产品文档、路线图与运行记录

建议提交：
- `AGENTS.md`
- `README.md`
- `PRODUCT.md`
- `docs/ALEMBIC_MIGRATION.md`
- `docs/RELEASE_NOTES.md`
- `server/STRUCTURE.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`
- `docs/runs/2026-06-15-m0-01-docs-cleanup.md`
- `docs/runs/2026-06-15-m0-ci-green.md`
- `docs/runs/2026-06-15-m0-stabilize.md`
- `docs/runs/2026-06-15-m1-demo-flow.md`
- `docs/runs/2026-06-16-m1-m2-productization-campaign.md`
- `docs/runs/2026-06-16-m1-m2-landing-campaign.md`

不提交：
- 临时计划草稿之外的本地状态文件。

理由：
- 这些文件让 README、PRODUCT、STRUCTURE、长任务协议和 M2 roadmap 对齐，让下一个 agent 能继续。

### 阶段 1 结论

- 当前未跟踪文件均可解释，建议纳入版本控制。
- 提交候选清晰，但尚未 stage。
- 下一阶段进入最终质量门，只有验证通过后才考虑精确 stage。

## 阶段 2：最终质量门

### 后端默认测试

```powershell
$env:APP_SECRET='test-app-secret-landing-' + ('a' * 48)
$env:AUTH_SECRET='test-auth-secret-landing-' + ('b' * 48)
$env:NEXTAUTH_SECRET=$env:AUTH_SECRET
$env:NEMO_GUARDRAILS_ENABLED='false'
.\.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

结果：
- `225 passed, 1 skipped`

### Guardrails 专项测试

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

结果：
- `139 passed`

### Demo Flow 测试

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow.py -q --tb=short
```

结果：
- `5 passed`

### logging setup 测试

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\test_logging_setup.py -q --tb=short
```

结果：
- `1 passed`

### SSRF 测试

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\test_ssrf.py -q --tb=short
```

结果：
- `13 passed`

### 前端 typecheck

```powershell
cd web-next
npm run typecheck
```

结果：
- `next typegen && tsc --noEmit` 通过。
- Route types 生成成功。

### 前端 build

```powershell
cd web-next
npm run build
```

结果：
- Next.js 15.5.16 production build 通过。
- `/dashboard` size `25.4 kB`，First Load JS `173 kB`。

### git diff whitespace 检查

```powershell
git diff --check
```

结果：
- 通过。
- 仅有 Windows `LF will be replaced by CRLF` warning，无 whitespace error。

### secret scan

```powershell
rg -n --hidden --glob '!web-next/node_modules/**' --glob '!node_modules/**' --glob '!web-next/.next/**' --glob '!.git/**' --glob '!*.pkl' --glob '!*.db' --glob '!*.ico' --glob '!*.png' --glob '!*.jpg' --glob '!*.jpeg' --glob '!*.gif' --glob '!*.pdf' --glob '!*.coverage' 'sk-[A-Za-z0-9_-]{16,}|sk-proj-[A-Za-z0-9_-]+|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|xox[baprs]-[A-Za-z0-9-]+|-----BEGIN (RSA |EC |OPENSSH |DSA |)PRIVATE KEY-----' .

rg -n --hidden --glob '!web-next/node_modules/**' --glob '!node_modules/**' --glob '!web-next/.next/**' --glob '!.git/**' --glob '!*.pkl' --glob '!*.db' --glob '!*.ico' --glob '!*.png' --glob '!*.jpg' --glob '!*.jpeg' --glob '!*.gif' --glob '!*.pdf' --glob '!*.coverage' '(OPENAI_API_KEY|ANTHROPIC_API_KEY|GUARDRAILS_MCP_API_KEY|APP_SECRET|AUTH_SECRET|POSTGRES_PASSWORD|REDIS_PASSWORD|ALERTS_INGEST_TOKEN|LLM_ADMIN_TOKEN)\s*=\s*[^\s#]+' .
```

结果判定：
- `sk-*` 命中均为：
  - `sk-test-fake-deepseek-key-do-not-use`
  - `sk-test-api-key-12345678`
  - Guardrails 输出泄漏检测样本
  - 本运行日志中的脱敏记录
- `AKIA...` 命中为 Guardrails 对抗样本：`AKIAIOSFODNN7EXAMPLE`。
- env var 命中均为：
  - `.env.example` / `web-next/.env.example` 占位符
  - CI test-only secret
  - README/PRODUCT/docs/runs 中的 test-only 命令
  - `deploy.ps1` / `docker-compose.yml` 的模板表达式
  - `OWNER_MANUAL.md` 的占位符示例
- 未发现真实生产密钥、私钥、GitHub token、Slack token。

### 阶段 2 结论

- 最终质量门全部通过。
- 当前 ready for precise staging，但 stage 前仍需完成风险审查和提交拆分方案。

## 阶段 3：审查风险

### `/alerts/demo` 安全边界

审查文件：
- `server/routers/alerts_router.py`
- `server/services/alert_service.py`
- `server/core/security.py`
- `server/core/state.py`
- `server/tests/test_demo_flow.py`

证据：
- `DemoAttackIn.scenario` 使用 `Literal["sql_injection", "xss", "scanner"]`，请求体只能进入固定场景集合。
- `POST /alerts/demo` 依赖 `require_auth_user`，未登录请求会经 `get_current_user` 返回 401。
- `require_auth_user` 会检查 token、active user、password changed timestamp、token version 和 session id。
- Demo alert 写入 `alert_user_id=user.id`，`get_alerts(user.id, limit)` 只返回当前用户告警。
- `find_alert_by_id(..., user_id=user.id)` 只返回当前用户可见告警。
- WebSocket 广播使用 `manager.broadcast_json(user_id, payload)`，不是全局广播。
- alert backlog 使用 `deque(maxlen=ALERT_BACKLOG_SIZE)`，当前上限为 200。
- `server/tests/test_demo_flow.py` 覆盖当前用户 id、广播 user id、未知 scenario 422、无 key fallback、有配置 ready。

结论：
- 未发现认证/授权退化。
- Demo 场景固定，不接受任意 payload，不触发外部网络调用。
- 非阻塞债务：`/alerts/demo` 目前没有独立 per-user rate limit 或 audit event。因为它必须认证、只写内存 backlog 且场景固定，本轮不阻塞；建议 M2-03 审计时间线或 M2-04 安全检查时补上。

### Copilot 降级态与错误净化

审查文件：
- `server/services/copilot_service.py`
- `server/services/llm_providers.py`
- `web-next/hooks/useCopilot.ts`
- `web-next/app/page.tsx`
- `web-next/components/dashboard/AttackLogTable.tsx`

证据：
- 缺少 API Key/Base URL 时，`stream_user_chat_completion` 只返回 `请先在配置页设置可用的 API Key 与 Base URL`。
- provider 异常只在服务端 logger 记录 `err_type`，SSE 给用户的是 `AI 服务暂时不可用，请稍后重试`。
- Guardrails input block 时，完整 reason 只进 audit；用户可见 SSE 只显示 `类别: {category}`。
- `sse_error` 只序列化 `message` 字段，不写 stack trace。
- 前端 `useCopilot` 只把 SSE `message` 展示为 `请求失败: ...`。
- 首页 `sanitizeBackendError` 把后端 detail 映射成固定用户可读文案，不展示原始复杂对象。
- 告警表用 React 文本插值展示 payload，没有 `dangerouslySetInnerHTML`。

结论：
- 未发现 API key、stack trace、regex 或系统 prompt 泄漏。
- Guardrails SSE error 净化仍符合 `AGENTS.md` 要求。

### logging JSON 修复合理性

审查文件：
- `server/core/logging_setup.py`
- `server/tests/test_logging_setup.py`

证据：
- `_json_sink(stream)` 使用 sink 回调写入 `_json_formatter(message.record)`，避免 Loguru 把 JSON 花括号当作 `format=` 模板字段二次解析。
- `configure_logging()` 在 `LOG_FORMAT=json` 时使用 `logger.add(_json_sink(sys.stderr), ...)`。
- 测试验证单行 JSON 可解析，包含 `message`、`level`、`ts`。

结论：
- 修复范围小，符合运行时问题根因。
- 不改变默认文本日志行为。

### legacy 手工测试 fake key

审查文件：
- `server/tests/manual/legacy/README.md`
- `server/tests/manual/legacy/audit_test.py`
- `server/tests/manual/legacy/comprehensive_test.py`
- `server/tests/manual/legacy/run_tests.py`

证据：
- `audit_test.py` 中 provider key 为 `sk-test-fake-deepseek-key-do-not-use`。
- legacy README 明确禁止写入真实 API key、生产密码、access token 或客户数据。
- `comprehensive_test.py` 和 `run_tests.py` 只打印 token 长度，不打印 token 前缀。

结论：
- 已处理疑似真实 secret 和 token 日志泄漏。
- legacy 固定测试账号仍存在，但属于手工测试样例，不是生产 secret。

### README / PRODUCT / M2 roadmap 一致性

审查文件：
- `README.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`
- `server/STRUCTURE.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/ALEMBIC_MIGRATION.md`

证据：
- README 明确 Demo Flow 和 `missing_api_key_or_base_url` 降级态。
- README 明确不要提交 `.claude/settings.local.json`、`.coverage`、`server/.coverage`、`coverage.xml`、`htmlcov/`、`.next`、`tsbuildinfo`、数据库和真实 `.env`。
- PRODUCT 当前基线为后端默认 `225 passed, 1 skipped`，Guardrails `139 passed, 17 warnings`。
- PRODUCT M2 章节链接 `docs/plans/M2_PRODUCT_ROADMAP.md`。
- M2 roadmap 明确当前能力、最弱环节、M2 做/不做、7 个长任务和完成定义。
- README、server/STRUCTURE、docs/ALEMBIC_MIGRATION 均承认 `DATABASE_URL` 目前不是后端 engine 的事实来源，没有假装 Docker/PostgreSQL 已完成。

结论：
- 文档口径一致，没有发现当前完成状态和路线图互相矛盾。
- AGENTS 中 Guardrails 测试数量仍写“M1 P0 94 tests passed / 覆盖率 76%”，这是历史 M1 快照，而 PRODUCT/M2 roadmap 使用当前专项 `139 passed`。不阻塞 landing，但后续改 AGENTS 的实施状态时可同步。

### 阶段 3 结论

- 未发现阻塞级安全风险。
- 未发现需要停止的认证、授权、Guardrails、MCP 鉴权或 SSE error 净化回归。
- 风险可接受，进入提交拆分方案。

## 阶段 4：准备提交拆分方案

### Commit 1

提交信息：

```text
test/ci: 稳定默认测试与前端构建基线
```

文件：
- `.github/workflows/ci.yml`
- `server/tests/conftest.py`
- `server/tests/test_e2e.py`
- `web-next/package.json`
- `web-next/app/api/backend/[...path]/route.ts`
- `web-next/types/terminal.ts`
- `web-next/utils/terminalUtils.ts`

为什么放在一起：
- 这些改动共同定义当前可重复验证口径：默认后端测试、可选 Playwright E2E、前端 typecheck/build、Next proxy 的构建兼容性。
- 不包含业务 Demo 逻辑，方便 reviewer 先确认基线稳定化。

验证命令：
- `.\\.venv\\Scripts\\python.exe -m pytest server\\tests -q --tb=short`
- `cd web-next; npm run typecheck`
- `cd web-next; npm run build`
- `git diff --check`

### Commit 2

提交信息：

```text
feat: 建立 Demo Flow 安全演示闭环
```

文件：
- `server/routers/alerts_router.py`
- `server/services/alert_service.py`
- `server/tests/test_demo_flow.py`
- `scripts/demo_attack.ps1`
- `web-next/app/dashboard/dashboard-client.tsx`
- `web-next/components/dashboard/CopilotPanel.tsx`
- `web-next/hooks/useAlerts.ts`
- `web-next/types/alert.ts`

为什么放在一起：
- 这些文件共同实现可演示路径：登录态触发 Demo 攻击、告警入队、Dashboard 可见、Copilot 当前告警分析或降级。
- 后端、前端、脚本和测试必须一起审查，避免 UI 有按钮但 API/测试不同步。

验证命令：
- `.\\.venv\\Scripts\\python.exe -m pytest server\\tests\\test_demo_flow.py -q --tb=short`
- `.\\.venv\\Scripts\\python.exe -m pytest server\\tests -q --tb=short`
- `cd web-next; npm run typecheck`
- `cd web-next; npm run build`

### Commit 3

提交信息：

```text
fix: 清理敏感测试痕迹并修复日志与 SSRF 稳定性
```

文件：
- `.gitignore`
- `server/core/logging_setup.py`
- `server/tests/test_logging_setup.py`
- `server/tests/test_ssrf.py`
- `server/tests/manual/legacy/README.md`
- `server/tests/manual/legacy/audit_test.py`
- `server/tests/manual/legacy/comprehensive_test.py`
- `server/tests/manual/legacy/run_tests.py`
- `web-next/app/page.tsx`

为什么放在一起：
- 这些改动都是落地前卫生和稳定性修复：coverage ignore、疑似真实 key 清理、token 输出收敛、JSON logging 修复、SSRF 测试去外网依赖、登录页错误净化。
- 共同降低“能演示但不可提交”的风险。

验证命令：
- `.\\.venv\\Scripts\\python.exe -m pytest server\\tests\\test_logging_setup.py -q --tb=short`
- `.\\.venv\\Scripts\\python.exe -m pytest server\\tests\\test_ssrf.py -q --tb=short`
- `.\\.venv\\Scripts\\python.exe -m pytest server\\tests -q --tb=short`
- secret scan 两条 `rg`
- `git diff --check`

### Commit 4

提交信息：

```text
docs: 更新产品基线、长任务协议与 M2 路线图
```

文件：
- `AGENTS.md`
- `README.md`
- `PRODUCT.md`
- `docs/ALEMBIC_MIGRATION.md`
- `docs/RELEASE_NOTES.md`
- `server/STRUCTURE.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`
- `docs/runs/2026-06-15-m0-01-docs-cleanup.md`
- `docs/runs/2026-06-15-m0-ci-green.md`
- `docs/runs/2026-06-15-m0-stabilize.md`
- `docs/runs/2026-06-15-m1-demo-flow.md`
- `docs/runs/2026-06-16-m1-m2-productization-campaign.md`
- `docs/runs/2026-06-16-m1-m2-landing-campaign.md`

为什么放在一起：
- 这些文件是项目接力口径：新人启动、Demo、测试、不要提交文件、M2 任务队列和运行证据。
- 文档提交应在代码/测试提交后落地，确保描述的是已经验证的基线。

验证命令：
- `git diff --check`
- secret scan 两条 `rg`
- `rg -n "M2_PRODUCT_ROADMAP|225 passed|139 passed|Demo Flow|\\.coverage|settings.local" README.md PRODUCT.md docs/plans/M2_PRODUCT_ROADMAP.md server/STRUCTURE.md docs/agent/UNATTENDED_LONG_TASKS.md`

### 提交前禁止项

提交时绝对不要 stage：
- `.coverage`
- `.claude/settings.local.json`
- `server/.coverage`
- `htmlcov/`
- `web-next/.next/`
- `web-next/tsconfig.tsbuildinfo`
- `data/app.db`
- 任何真实 `.env` / `.env.local`

### 阶段 4 结论

- 4 个 commit 拆分清晰。
- 质量门已通过。
- 可以进入可选精确 stage。

## 阶段 5：可选精确 stage

### Stage 命令

使用精确路径数组：

```powershell
git --literal-pathspecs add -- <38 个明确候选路径>
```

说明：
- 没有使用 `git add .`。
- 使用 `--literal-pathspecs` 避免 `web-next/app/api/backend/[...path]/route.ts` 被当作通配符。
- 首次 `git diff --cached --check` 发现 `docs/agent/UNATTENDED_LONG_TASKS.md` 模板占位行有 trailing whitespace。
- 已用 `apply_patch` 清理这些尾随空格，并只重新 stage 该文件。

### Stage 后检查

```powershell
git status --short --branch
git diff --cached --name-only
git diff --cached --check
git diff --cached --stat
git diff --check
```

结果：
- `git diff --cached --check`：通过。
- `git diff --check`：通过，仅 `.claude/settings.local.json` 换行 warning。
- `NO_FORBIDDEN_STAGED`。
- staged 文件：38 个候选文件。
- unstaged 仍保留：
  - `.claude/settings.local.json`
  - `.coverage`

### 已 stage 文件

```text
.github/workflows/ci.yml
.gitignore
AGENTS.md
PRODUCT.md
README.md
docs/ALEMBIC_MIGRATION.md
docs/RELEASE_NOTES.md
docs/agent/UNATTENDED_LONG_TASKS.md
docs/plans/M2_PRODUCT_ROADMAP.md
docs/runs/2026-06-15-m0-01-docs-cleanup.md
docs/runs/2026-06-15-m0-ci-green.md
docs/runs/2026-06-15-m0-stabilize.md
docs/runs/2026-06-15-m1-demo-flow.md
docs/runs/2026-06-16-m1-m2-landing-campaign.md
docs/runs/2026-06-16-m1-m2-productization-campaign.md
scripts/demo_attack.ps1
server/STRUCTURE.md
server/core/logging_setup.py
server/routers/alerts_router.py
server/services/alert_service.py
server/tests/conftest.py
server/tests/manual/legacy/README.md
server/tests/manual/legacy/audit_test.py
server/tests/manual/legacy/comprehensive_test.py
server/tests/manual/legacy/run_tests.py
server/tests/test_demo_flow.py
server/tests/test_e2e.py
server/tests/test_logging_setup.py
server/tests/test_ssrf.py
web-next/app/api/backend/[...path]/route.ts
web-next/app/dashboard/dashboard-client.tsx
web-next/app/page.tsx
web-next/components/dashboard/CopilotPanel.tsx
web-next/hooks/useAlerts.ts
web-next/package.json
web-next/types/alert.ts
web-next/types/terminal.ts
web-next/utils/terminalUtils.ts
```

### 阶段 5 结论

- 当前 staged 区域 ready for commit。
- 没有 commit。
- 没有 push。
- 禁止提交文件未 stage。

## 最终状态

### Ready for commit

是，当前 staged 区域 ready for commit。

前提：
- 只提交 staged 文件。
- 不使用 `git add .`。
- 不把 unstaged 的 `.coverage` 和 `.claude/settings.local.json` 纳入提交。

### 当前 staged / unstaged

Staged：
- 38 个提交候选文件。
- `git diff --cached --check` 通过。
- 禁止文件检查结果：`NO_FORBIDDEN_STAGED`。

Unstaged：
- `.coverage`
- `.claude/settings.local.json`

说明：
- `git diff --stat` 在 stage 后只显示 unstaged `.coverage` 二进制变化，这是预期结果。
- 提交候选 stat 见 `git diff --cached --stat`。

### 完整验证结果

- 后端默认测试：`225 passed, 1 skipped`
- Guardrails 专项测试：`139 passed`
- Demo Flow 测试：`5 passed`
- logging setup 测试：`1 passed`
- SSRF 测试：`13 passed`
- `web-next npm run typecheck`：通过
- `web-next npm run build`：通过
- `git diff --check`：通过，仅 `.claude/settings.local.json` 换行 warning
- `git diff --cached --check`：通过
- secret scan：未发现真实生产密钥；剩余命中为 fake/test key、占位符、Guardrails 对抗样本或运行日志脱敏记录

### 推荐下一条 M2 长任务

```markdown
你是 AI-CyberSentinel 的 M2 长任务 agent。请先阅读 `PRODUCT.md`、`AGENTS.md`、`CLAUDE.md`、`docs/agent/UNATTENDED_LONG_TASKS.md`、`docs/plans/M2_PRODUCT_ROADMAP.md` 和最近 `docs/runs/`。

任务名称：M2-02 Demo Flow 自动化 E2E。

目标：把 2026-06-16 手工跑通的浏览器路径固化成可重复验证入口：注册或登录 -> Dashboard -> 触发 Demo 攻击 -> 告警表可见 -> Copilot 分析当前告警 -> 无 API Key/Base URL 时显示清晰降级态。

允许修改：`server/tests/test_e2e.py`、必要的 test helper、README/PRODUCT/UNATTENDED_LONG_TASKS 中的 E2E 说明。必要时可小范围添加前端稳定选择器。

禁止修改：认证语义、Guardrails/MCP 鉴权、真实 `.env`、`.claude/settings.local.json`、`.coverage`、数据库文件。不要 commit/push/reset/clean。

验收：默认 `pytest server/tests` 仍通过且 E2E 默认 skip；显式 `--run-e2e` 在本地具备 Playwright 浏览器时能跑通 Demo Flow；缺少浏览器时清晰 skip；前端改动需通过 `npm run typecheck` 和 `npm run build`。
```
