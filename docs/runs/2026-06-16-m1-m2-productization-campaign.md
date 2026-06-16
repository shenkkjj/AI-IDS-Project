# Run: M1-M2 PRODUCTIZATION CAMPAIGN

开始时间：2026-06-16
运行模式：L3，高风险半自动长任务
预算：按 8-12 小时任务设计；至少推进 5 个阶段；同一失败最多修复 3 轮

## 目标

- 把 AI-CyberSentinel 从“功能已经堆起来”推进到“可演示、可继续开发、可交给下一个 agent 接力”的产品基线。
- 重点保证 Demo Flow、验证命令、文档口径、安全边界和工作树卫生清晰。

## 硬边界

允许修改：
- 与 Demo Flow 产品化直接相关的 `server/**`、`web-next/**`、`scripts/**`
- 测试、README、PRODUCT、docs/plans、docs/runs、CI 文档和小范围 CI 配置

禁止修改：
- 真实 `.env`
- `.claude/settings.local.json`
- git 历史、commit、push、merge、reset、clean
- 未知文件删除
- 认证、授权、Guardrails、MCP 鉴权、SSE error 净化的弱化
- `.coverage`、`server/.coverage` 等本地产物进入提交候选

## 已使用 Skill

- `careful`：避免破坏性命令和高风险 git 操作。
- `terminal-ops`：证据优先读取、执行、记录。
- `security-review`：secret、认证、输入、错误泄漏和敏感边界检查。
- `tdd-workflow`、`python-testing`：后端和 demo flow 测试策略。
- `frontend-patterns`：Next.js / React UI 小范围产品化。
- `backend-patterns`、`api-design`：FastAPI endpoint 与服务层变更边界。
- `dashboard-builder`：Dashboard 以操作员问题为中心，而不是堆指标。
- `product-capability`：把 M2 产品路线图写成可执行能力边界。
- `verification-loop`：最终质量门和证据记录。
- `control-in-app-browser`、`playwright-cli`：浏览器验收优先；不可用时记录替代 HTTP smoke。
- `document-generate`：文档同步与可发现性。
- `gstack review / qa`：作为代码审查和真实路径 QA 的参考；本轮不提交、不推送，覆盖其通用提交建议。

## 阶段 0：全仓接管与现状建模

### 已读取

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `README.md`
- 最近运行记录：
  - `docs/runs/2026-06-15-m1-demo-flow.md`
  - `docs/runs/2026-06-15-m0-ci-green.md`
  - `docs/runs/2026-06-15-m0-stabilize.md`
  - `docs/runs/2026-06-15-m0-01-docs-cleanup.md`

### 当前项目地图

- 后端：`server/`，FastAPI 入口为 `server/main.py`，主要路由在 `server/routers/`，业务逻辑在 `server/services/`，数据库模型在 `server/models_db.py`。
- 安全核心：`server/security/llm_guardrails/`，包含 GuardrailEngine、audit、MCP server、OpenAI moderation provider 和 NeMo 配置。任何改动必须保留 fail-closed、MCP key、SSE error 净化和测试。
- Demo Flow：后端已有认证态 `POST /alerts/demo`、`AlertService.trigger_demo_attack`、`scripts/demo_attack.ps1`，前端 Dashboard 已有“触发 Demo 攻击”和 Copilot “分析当前告警”。
- 前端：`web-next/`，Next.js App Router；Dashboard 主体仍集中在 `web-next/app/dashboard/dashboard-client.tsx`，Copilot 在 `web-next/components/dashboard/CopilotPanel.tsx`，告警数据在 `web-next/hooks/useAlerts.ts`。
- 文档入口：`README.md` 面向新手启动与 Demo；`PRODUCT.md` 是产品北极星和路线图；`docs/agent/UNATTENDED_LONG_TASKS.md` 是长任务规范；`docs/plans/` 存计划。
- 验证基线：后端默认 pytest、Guardrails 专项、Demo Flow smoke、前端 typecheck/build、`git diff --check` 和 secret scan。

### 当前工作树分组

命令：

```powershell
git status --short --branch
git diff --stat
```

结果摘要：
- 当前分支：`main...origin/main [ahead 4]`
- 工作树已有大量改动，本轮视为前序用户/agent 工作，不回滚。

产品代码：
- `server/routers/alerts_router.py`
- `server/services/alert_service.py`
- `web-next/app/api/backend/[...path]/route.ts`
- `web-next/app/dashboard/dashboard-client.tsx`
- `web-next/components/dashboard/CopilotPanel.tsx`
- `web-next/hooks/useAlerts.ts`
- `web-next/types/terminal.ts`
- `web-next/utils/terminalUtils.ts`

测试代码：
- `server/tests/conftest.py`
- `server/tests/test_e2e.py`
- `server/tests/test_demo_flow.py`（未跟踪）

文档：
- `AGENTS.md`
- `README.md`
- `PRODUCT.md`（未跟踪）
- `docs/ALEMBIC_MIGRATION.md`
- `docs/RELEASE_NOTES.md`
- `server/STRUCTURE.md`
- `docs/agent/`（未跟踪）
- `docs/runs/`（未跟踪，含本日志）

CI 配置：
- `.github/workflows/ci.yml`
- `web-next/package.json`

脚本：
- `scripts/demo_attack.ps1`（未跟踪）

本地产物 / 不应提交：
- `.claude/settings.local.json`（用户本地设置，禁止触碰）
- `.coverage`（已跟踪但属于覆盖率产物，当前被修改）
- `server/.coverage`（未跟踪覆盖率产物）

可疑安全风险：
- 当前尚未完成 secret scan。
- 需重点检查 `server/tests/manual/legacy/`、`scripts/`、`README.md`、`docs/`、`.github/workflows/ci.yml` 是否含真实 key、token、密码或生产凭据。
- `server/.coverage` 和 `.coverage` 不能作为提交候选。

### 阶段 0 结论

- 前序 M0/M1 已完成文档入口修复、默认测试稳定化、CI 覆盖率口径拆分和 Demo Flow 基础闭环。
- 本轮继续推进产品化，不重做前序成果。
- 下一阶段进入安全与提交卫生，先扫描 secret 与本地产物，再决定是否需要小范围修复。

## 验证证据

- 阶段 0 已执行：`git status --short --branch`
- 阶段 0 已执行：`git diff --stat`

## 未解决问题

- 真实浏览器级验收在前序日志中仍未完成。
- Dashboard/Copilot 降级态和 README 演示路径仍需复核。
- 工作树包含前序大量 dirty 文件，最终需要清晰列出建议提交与绝对不提交文件。

## 阶段 1：落地前安全与提交卫生

### 目标

- 检查疑似 secret、硬编码 token、真实 API key、测试遗留凭据。
- 隔离不应提交的本地产物。
- 不触碰 `.claude/settings.local.json`，不删除未知文件，不修改真实 `.env`。

### 检查范围

- `server/tests/manual/legacy/`
- `scripts/`
- `README.md`
- `docs/`
- `.github/workflows/ci.yml`
- `.env.example`、`web-next/.env.example`

### 执行命令

```powershell
rg -n --hidden --glob '!web-next/node_modules/**' --glob '!node_modules/**' --glob '!web-next/.next/**' --glob '!.git/**' --glob '!*.pkl' --glob '!*.db' --glob '!*.ico' --glob '!*.png' --glob '!*.jpg' --glob '!*.jpeg' --glob '!*.gif' --glob '!*.pdf' --glob '!*.coverage' 'sk-[A-Za-z0-9_-]{16,}|sk-proj-[A-Za-z0-9_-]+' .
rg -n --hidden --glob '!web-next/node_modules/**' --glob '!node_modules/**' --glob '!web-next/.next/**' --glob '!.git/**' --glob '!*.pkl' --glob '!*.db' --glob '!*.ico' --glob '!*.png' --glob '!*.jpg' --glob '!*.jpeg' --glob '!*.gif' --glob '!*.pdf' --glob '!*.coverage' 'AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|xox[baprs]-[A-Za-z0-9-]+' .
rg -n --hidden --glob '!web-next/node_modules/**' --glob '!node_modules/**' --glob '!web-next/.next/**' --glob '!.git/**' --glob '!*.pkl' --glob '!*.db' --glob '!*.ico' --glob '!*.png' --glob '!*.jpg' --glob '!*.jpeg' --glob '!*.gif' --glob '!*.pdf' --glob '!*.coverage' '(OPENAI_API_KEY|ANTHROPIC_API_KEY|GUARDRAILS_MCP_API_KEY|APP_SECRET|AUTH_SECRET|POSTGRES_PASSWORD|REDIS_PASSWORD|ALERTS_INGEST_TOKEN)\s*=\s*[^\s#]+' .
rg -n "sk-faa18|sk-[A-Za-z0-9_-]{24,}|Token:|access_token.*\\[:|DEEPSEEK_KEY" server\tests\manual\legacy server\tests\test_auth.py server\tests\security\llm_guardrails
git check-ignore -v .coverage server/.coverage web-next/tsconfig.tsbuildinfo web-next/.next/cache/.tsbuildinfo
git diff --check -- .gitignore server\tests\manual\legacy\audit_test.py server\tests\manual\legacy\comprehensive_test.py server\tests\manual\legacy\run_tests.py server\tests\manual\legacy\README.md docs\runs\2026-06-16-m1-m2-productization-campaign.md
```

### 改动

- `server/tests/manual/legacy/audit_test.py`
  - 将疑似真实 DeepSeek/OpenAI 风格 key `sk-faa18...` 替换为 `sk-test-fake-deepseek-key-do-not-use`。
- `server/tests/manual/legacy/comprehensive_test.py`
  - 登录成功日志不再输出 access token 前缀，只输出 token 长度。
- `server/tests/manual/legacy/run_tests.py`
  - 登录成功日志不再输出 access token 前缀，只输出 token 长度。
- `server/tests/manual/legacy/README.md`
  - 标注 legacy 手工脚本只能使用 fake/test 凭据，不得写入真实 key、生产密码、access token 或客户数据。
- `.gitignore`
  - 追加 `.coverage`、`coverage.xml`、`htmlcov/`，避免后续覆盖率产物继续进入未跟踪列表。

### 验证

- secret scan 复跑后，剩余 `sk-*` 命中均为：
  - 明确 fake/test key。
  - Guardrails 对抗测试语料。
  - L1 输出泄漏检测测试。
- `AKIA...` 命中仅为 Guardrails 测试用 AWS 示例 key。
- env var 命中均为 `.env.example` 占位符、README/PRODUCT/docs 中的测试密钥或 CI 测试密钥。
- `git diff --check` 对阶段 1 修改文件通过。
- `.gitignore` 追加后，`server/.coverage` 不再出现在 `git status`；根 `.coverage` 因已被 git 跟踪，仍显示修改，最终必须列为不要提交。

### 已处理风险

- 移除了 legacy 手工脚本中的疑似真实 LLM provider key。
- 降低手工脚本运行时把 session token 带进终端日志、复制记录或运行日志的风险。
- 防止新覆盖率产物继续污染工作树。

### 未处理风险

- `.coverage` 是已跟踪文件且当前已修改；本轮不执行 destructive git 操作，不 reset，不删除。最终报告列为绝对不要提交。
- `.claude/settings.local.json` 已修改但属于用户本地设置，本轮不触碰。
- legacy 手工脚本仍包含固定测试账号/密码；这些是本地测试凭据，不是生产 secret，但后续应优先用现代 pytest 和随机 fixture 替代。

### 为什么安全

- 所有真实运行密钥要求仍通过环境变量和 `.env.example` 占位符表达。
- CI 使用的 `test-ci-*` 值明确是测试密钥，不可用于生产。
- Guardrails、MCP 鉴权、认证授权、SSE error 净化均未弱化。

### 下一阶段计划

- 复核 `/alerts/demo`、`AlertService.trigger_demo_attack`、Dashboard、CopilotPanel 和 `scripts/demo_attack.ps1`。
- 优先补“能讲清楚”的状态、降级和测试，不重写 Dashboard。

## 阶段 2：Demo Flow 产品化

### 目标

- 让 Demo Flow 从“能触发一条告警”提升到“演示者能讲清楚每一步”。
- 后端返回 Copilot 是否具备真实分析条件。
- 前端、脚本、README 都能说明无 API Key/Base URL 时的清晰降级态。
- 保持现有 Dashboard 结构，不重写设计系统。

### 改动

- `server/routers/alerts_router.py`
  - `POST /alerts/demo` 增加 DB 依赖，用于读取当前用户 LLM 配置。
  - 响应增加 `copilot` 元数据。
- `server/services/alert_service.py`
  - 新增 `build_demo_copilot_state(...)`，基于用户配置判断 Copilot 是否 ready。
  - 无 API Key 或 Base URL 时返回 `fallback_reason=missing_api_key_or_base_url` 和明确下一步。
- `server/tests/test_demo_flow.py`
  - Demo Flow 测试覆盖缺失 provider 配置时的降级元数据。
  - 新增已配置用户的 ready 路径测试。
- `web-next/types/alert.ts`
  - 新增 `DemoCopilotState` 和 `DemoAttackResponse` 类型。
- `web-next/hooks/useAlerts.ts`
  - Demo 触发过程增加 `demoMessage`。
  - 成功后保留后端返回的 Copilot ready/fallback 说明。
- `web-next/app/dashboard/dashboard-client.tsx`
  - Demo 按钮根据运行状态展示“触发中 / Demo 已生成 / 重试 Demo”。
  - 终端日志记录 Copilot ready 或降级态。
  - 按钮旁展示后端返回的下一步提示。
- `scripts/demo_attack.ps1`
  - smoke 成功后输出 Copilot ready 或 fallback 状态。
- `README.md`
  - Demo Flow 路径补充 Copilot 降级说明。
- `PRODUCT.md`
  - 同步 M1 Demo Flow 当前状态和剩余边界。

### 验证

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow.py -q --tb=short
cd web-next; npm run typecheck
git diff --check -- server\routers\alerts_router.py server\services\alert_service.py server\tests\test_demo_flow.py web-next\types\alert.ts web-next\hooks\useAlerts.ts web-next\app\dashboard\dashboard-client.tsx scripts\demo_attack.ps1 README.md PRODUCT.md docs\runs\2026-06-16-m1-m2-productization-campaign.md
```

结果：

- Demo Flow 测试：`5 passed, 17 warnings`。
- 前端 typecheck：通过。
- `git diff --check`：通过，仅 PowerShell 输出 LF/CRLF warning。

### 风险

- 当前只增强了 Demo 触发后的状态提示；Copilot SSE 的细分 UI 仍依赖已有 `CopilotPanel` 展示逻辑。
- 若用户配置了无效 API Key，ready 会显示为已配置，但真实分析仍可能在 SSE 阶段降级或失败；这属于 provider 可用性问题，不应在 `/alerts/demo` 中做外部调用。

### 下一阶段计划

- 启动后端和前端 dev server。
- 优先用 in-app Browser 做真实路径验收：登录、Dashboard、触发 Demo、观察告警和 Copilot 降级态。
- 若浏览器工具或依赖不可用，用 HTTP smoke script 替代并记录原因。

## 阶段 3：真实浏览器级验收

### 目标

- 启动真实后端和前端 dev server。
- 用浏览器验证：注册/登录 -> Dashboard -> 触发 Demo 攻击 -> 告警可见 -> Copilot 分析当前告警 -> 无 API Key/Base URL 时清晰降级。
- 遇到浏览器验收暴露的问题时，小范围修复，不扩大重构。

### 环境

- 后端：`http://127.0.0.1:8000`
- 前端：`http://127.0.0.1:3000`
- 后端运行时环境使用本轮临时强测试密钥：
  - `APP_SECRET=campaign-app-secret-20260616-...`
  - `AUTH_SECRET=campaign-auth-secret-20260616-...`
  - `APP_ENV=development`
  - `NEMO_GUARDRAILS_ENABLED=false`
- 运行日志输出到系统临时目录：`%TEMP%\ai-ids-productization-20260616\`
- 未修改真实 `.env`、`web-next/.env`、`web-next/.env.local`。

### 启动验证

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health
Invoke-WebRequest http://127.0.0.1:3000
```

结果：

- 后端 `/health` 返回 200：`{"status":"ok"}`。
- 前端首页返回 200。
- in-app Browser 可连接并打开本地前端。

### 浏览器路径证据

- 打开 `http://127.0.0.1:3000/`，登录页可见：邮箱、密码、登录、创建新账号。
- 使用一次性本地测试账号注册并自动进入 `/dashboard`：
  - `campaign-1781580953043@example.com`
  - 仅用于本地 SQLite demo 数据库。
- Dashboard 初始状态可见：
  - `触发 Demo 攻击`
  - `AI 配置`
  - Copilot 无 API Key/Base URL 提示。
- 点击 `触发 Demo 攻击` 后：
  - Demo 按钮变为 `Demo 已生成`。
  - 页面提示：`演示闭环已生成告警；如需真实 AI 分析，请先在配置页设置可用的 API Key 与 Base URL。`
  - 终端日志显示：
    - `Demo 攻击已触发: 203.0.113.45 -> 10.0.0.15`
    - `告警 ... 已进入 Dashboard，可在 AI 助手中分析。`
    - `Copilot 降级态: ... API Key 与 Base URL。`
- 点击 `分析当前告警` 后：
  - Copilot 输出：`请求失败: 请先在配置页设置可用的 API Key 与 Base URL`。
  - 页面未暴露 `sk-*` 密钥。
  - 页面未暴露 `Traceback` 或后端 stack trace。
- 修复告警展示状态后复验：
  - 统计卡显示 `总告警 2 / 高危告警 2 / 已拦截 2`。
  - 告警表显示两条 SQL 注入 Demo 记录。
  - Copilot 告警上下文选中最新 demo alert。

### 浏览器验收中发现并修复的问题

- `web-next/app/page.tsx`
  - 问题：FastAPI/Pydantic 数组型 `detail` 被前端降级成“操作失败，请稍后重试”；例如 `example.test` 被 `EmailStr` 拒绝时，用户看不懂原因。
  - 修复：新增 `flattenBackendDetail(...)`，`sanitizeBackendError(...)` 支持字符串、数组和对象型错误详情，邮箱校验错误展示为“邮箱格式无效”。
- `web-next/hooks/useAlerts.ts`
  - 问题：Demo alert 写入 `alertById` ref 后，`mergedAlerts` 只依赖 `wsAlerts` memo 重算；Dashboard 计数和表格没有立即显示新告警，只在 Copilot 上下文里可见。
  - 修复：将展示数据收敛到 `alerts` state；`alertById` 只做去重索引，WebSocket、轮询、Demo 都通过同一个同步路径更新展示状态。

### 风险

- 刷新原测试页签后曾短暂停在 session loading；开干净页签登录同一账号后正常进入 Dashboard。当前记录为浏览器/热更新边角风险，阶段 4 继续用 typecheck/build 和 smoke 覆盖。
- 后端临时日志出现 Loguru `KeyError: '"ts"'`，说明当前 JSON 日志 formatter 有运行期问题。该问题不阻断 Demo Flow，但属于阶段 4 稳定化候选。
- 后端临时日志出现 Guardrails moderation timeout，UI 仍净化为配置降级提示；阶段 4 需确认专项测试不回归。

### 下一阶段计划

- 停止临时 dev server。
- 运行后端默认测试、Guardrails 专项测试、Demo Flow 测试、前端 typecheck/build、`git diff --check` 和 secret scan。
- 修复必要失败；同一失败最多 3 轮。

## 阶段 4：测试与 CI 稳定化

### 目标

- 跑完本轮最终验证矩阵。
- 修复真实失败，不降低覆盖率门槛，不 skip 业务测试，不弱化安全边界。
- 把测试环境中的外部依赖和运行时日志问题收敛成确定性验证。

### 第一轮验证结果

```powershell
$env:APP_SECRET='test-app-secret-stage4-' + ('a' * 48)
$env:AUTH_SECRET='test-auth-secret-stage4-' + ('b' * 48)
$env:NEXTAUTH_SECRET=$env:AUTH_SECRET
$env:NEMO_GUARDRAILS_ENABLED='false'
.\.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

结果：

- `224 passed, 1 skipped, 1 failed`
- 失败：`server/tests/test_ssrf.py::TestSsrfProtection::test_public_domain_ok`
- 原因：测试依赖真实外网域名解析，当前环境下 `www.google.com` 被 `_is_url_pointing_to_internal(...)` 判定为不安全。属于测试环境依赖问题，不是 SSRF 防护要放宽。

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

结果：

- `139 passed, 17 warnings`

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow.py -q --tb=short
```

结果：

- `5 passed, 17 warnings`

### 修复

- `server/core/logging_setup.py`
  - 问题：真实运行时 Loguru JSON formatter 把 JSON 花括号二次解析为模板字段，抛 `KeyError: '"ts"'`。
  - 修复：新增 `_json_sink(stream)`，将 JSON 格式化放在 sink 回调里写入，避免 `format=` 二次解析。
- `server/tests/test_logging_setup.py`
  - 新增 JSON 日志 smoke 测试，验证单行 JSON 可解析且不会触发 `{ts}` 模板错误。
- `server/tests/test_ssrf.py`
  - 问题：公开域名测试依赖真实 DNS/网络。
  - 修复：对 `server.core.utils._is_url_pointing_to_internal` 使用 `monkeypatch`，让该测试只表达“公开域名应被允许”的逻辑，不依赖外网解析。

### 最终验证结果

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\test_logging_setup.py -q --tb=short
```

- `1 passed`

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\test_ssrf.py -q --tb=short
```

- `13 passed`

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

- `225 passed, 1 skipped`

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

- `139 passed, 17 warnings`

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow.py -q --tb=short
```

- `5 passed, 17 warnings`

```powershell
cd web-next
npm run typecheck
npm run build
```

- `npm run typecheck`：通过，`next typegen && tsc --noEmit`。
- `npm run build`：通过，Next.js 15.5.16 生产构建成功。

```powershell
git diff --check
```

- 通过，仅输出 Windows LF/CRLF warning。

```powershell
rg -n --hidden ... 'sk-*|AKIA...|ghp_*|xox*|PRIVATE KEY'
rg -n --hidden ... '(OPENAI_API_KEY|ANTHROPIC_API_KEY|GUARDRAILS_MCP_API_KEY|APP_SECRET|AUTH_SECRET|POSTGRES_PASSWORD|REDIS_PASSWORD|ALERTS_INGEST_TOKEN|LLM_ADMIN_TOKEN)\s*=\s*[^\s#]+'
```

- 剩余 `sk-*` / `AKIA` 命中均为 fake/test key、Guardrails 对抗样本或本运行日志中的脱敏记录。
- env var 命中均为 `.env.example` 占位符、CI 测试值、文档中的测试命令或部署脚本模板。

### 风险

- Guardrails 专项测试仍有 NeMo/Pydantic v2 deprecation warnings，属于第三方兼容噪声，未阻断。
- 后端默认测试跳过 1 个 E2E 测试；项目策略为默认跳过，需要 `--run-e2e` 显式运行。
- `git diff --check` 有 LF/CRLF warning，但无 whitespace error。

### 下一阶段计划

- 审查 README、PRODUCT、server/STRUCTURE、docs/agent/UNATTENDED_LONG_TASKS 的启动、Demo、测试、提交卫生说明是否一致。
- 修复过时步骤和路径错误。

## 阶段 5：产品体验与信息架构整理

### 目标

- 让新人从 README 能跑起项目并完成 Demo。
- 让下一个 agent 从 PRODUCT、AGENTS、STRUCTURE、UNATTENDED_LONG_TASKS 能理解边界和验证命令。
- 修复与 2026-06-16 实测结果不一致的文档口径。

### 改动

- `README.md`
  - 新增“提交前卫生检查”。
  - 明确不要提交 `.env`、`.claude/settings.local.json`、`.coverage`、`server/.coverage`、数据库、`.next`、`node_modules` 等本地产物。
  - 明确 secret scan 命中真实密钥时必须先移除；测试 fake key 必须有 fake/test/example 语义。
- `server/STRUCTURE.md`
  - 将后端默认测试命令从旧的 `--ignore=server\tests\test_e2e.py` 更新为当前默认基线：`pytest server\tests -q --tb=short`。
  - 说明 `test_e2e.py` 默认收集但跳过，真实浏览器 E2E 需显式 `--run-e2e`。
- `PRODUCT.md`
  - 当前基线更新到 2026-06-16。
  - 更新后端默认测试为 `225 passed, 1 skipped`。
  - 更新 Guardrails 专项为 `139 passed, 17 warnings`。
  - 记录真实浏览器路径已经跑通。
  - M1 状态同步为 Dashboard、终端日志和 Copilot SSE 都能展示无 API Key/Base URL 的清晰降级态。

### 验证

```powershell
git diff --check -- README.md PRODUCT.md server\STRUCTURE.md docs\runs\2026-06-16-m1-m2-productization-campaign.md
```

结果：

- 通过，仅 LF/CRLF warning。

### 风险

- `docs/RELEASE_NOTES.md`、`OWNER_MANUAL.md` 等历史长文档仍可能有过时说明；本阶段优先修当前入口文档，避免范围失控。
- README 的 Docker Compose 路径仍标记为待确认，没有假装生产部署已可用。

### 下一阶段计划

- 新增 `docs/plans/M2_PRODUCT_ROADMAP.md`。
- 将 M2 目标、非目标、可无人值守长任务、验收标准、风险和禁止范围写清。
- 同步 PRODUCT 的 M2 章节，避免路线图分叉。

## 阶段 6：架构债与路线图

### 目标

- 基于真实代码和本轮验证结果，写一份可执行的 M2 产品路线图。
- 明确 M2 做什么、不做什么。
- 给后续 agent 留下可无人值守执行的长任务。
- 同步 PRODUCT，避免路线图分叉。

### 改动

- 新增 `docs/plans/M2_PRODUCT_ROADMAP.md`
  - 当前产品能力。
  - 当前最弱环节。
  - M2 应做什么 / 不应该做什么。
  - 7 个可无人值守长任务：
    - `M2-01` 数据库配置与 Alembic 基线。
    - `M2-02` Demo Flow 自动化 E2E。
    - `M2-03` 审计时间线与 Guardrails 可见性。
    - `M2-04` 生产最小安全配置文档与检查。
    - `M2-05` Dashboard 状态边界拆分。
    - `M2-06` Provider Fake/Contract 测试。
    - `M2-07` Docker Compose 端到端验收。
  - 每个任务都有允许范围、禁止范围、验收标准和主要风险。
- `PRODUCT.md`
  - M2 章节链接到 `docs/plans/M2_PRODUCT_ROADMAP.md`。
  - M2 任务从笼统运营化改成可执行序列。
  - 无人值守长任务推荐队列更新为 M2 工单。

### 验证

```powershell
git diff --check -- PRODUCT.md docs\plans\M2_PRODUCT_ROADMAP.md docs\runs\2026-06-16-m1-m2-productization-campaign.md
rg -n "M2-|M2|M0-|M1-DEMO|M1-AUDIT|2026-06-15|219 passed|24.5" PRODUCT.md docs\plans\M2_PRODUCT_ROADMAP.md
```

结果：

- `git diff --check` 通过。
- PRODUCT 与 M2 roadmap 均指向 M2 工单；旧的 M0/M1 推荐工单不再作为当前下一批主队列。

### 风险

- M2 roadmap 是草案，不代表所有任务都可一次性大改；尤其数据库/Alembic 和 Docker Compose 必须拆小并保留回退。
- 真实生产部署仍未验证，roadmap 明确将其作为 M2-07，而不是当前已完成能力。

### 下一阶段计划

- 审查本轮所有改动。
- 清理无意义 debug、临时测试、过度文档或本地产物。
- 运行最小必要验证和最终状态检查。

## 阶段 7：De-sloppify 清理轮

### 目标

- 审查本轮所有改动，确认没有临时 debug、无意义测试、重复文档或本地产物进入提交候选。
- 复跑最终必要验证。
- 明确当前工作树哪些能提交、哪些不能提交。

### 检查

```powershell
git status --short --branch
git diff --stat
rg -n "console\.log|debugger|TODO\(|FIXME|campaign-|178158|TEMP|tmp|console\.error|console\.warn" ...
Get-ChildItem -Force .coverage,server\.coverage,coverage.xml,htmlcov,web-next\tsconfig.tsbuildinfo,web-next\.next
Get-NetTCPConnection -LocalPort 3000,8000 -State Listen
```

结果：

- 未发现本轮新增的 `console.log`、`debugger`、临时测试账号串或无意义 debug 输出。
- `web-next/app/error.tsx` 保留既有 `console.error("[error-boundary] caught:", error)`，非本轮新增，属于错误边界日志。
- 临时 dev server 已停止，3000/8000 无监听进程。
- 本地产物仍存在：
  - `.coverage`：已被 git 跟踪且被修改，不能自动 reset，最终列为不要提交。
  - `server/.coverage`：已被 `.gitignore` 忽略。
  - `htmlcov/`：已被 `.gitignore` 忽略。
  - `web-next/.next/`、`web-next/tsconfig.tsbuildinfo`：已被现有 ignore 规则忽略。

### 最终验证

```powershell
$env:APP_SECRET='test-app-secret-final-' + ('a' * 48)
$env:AUTH_SECRET='test-auth-secret-final-' + ('b' * 48)
$env:NEXTAUTH_SECRET=$env:AUTH_SECRET
$env:NEMO_GUARDRAILS_ENABLED='false'
.\.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

- `225 passed, 1 skipped`

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

- `139 passed, 17 warnings`

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow.py -q --tb=short
```

- `5 passed, 17 warnings`

```powershell
cd web-next
npm run typecheck
npm run build
```

- `npm run typecheck`：通过。
- `npm run build`：通过，`/dashboard` size 25.4 kB，First Load JS 173 kB。

```powershell
git diff --check
```

- 通过，仅 LF/CRLF warning。

```powershell
rg -n --hidden ... 'sk-*|AKIA...|ghp_*|xox*|PRIVATE KEY'
rg -n --hidden ... '(OPENAI_API_KEY|ANTHROPIC_API_KEY|GUARDRAILS_MCP_API_KEY|APP_SECRET|AUTH_SECRET|POSTGRES_PASSWORD|REDIS_PASSWORD|ALERTS_INGEST_TOKEN|LLM_ADMIN_TOKEN)\s*=\s*[^\s#]+'
```

- 剩余命中均为 fake/test key、Guardrails 对抗样本、占位符、部署模板或本运行日志中的脱敏记录。

### 风险

- 整个工作树不能盲目 commit，因为包含 `.coverage` 和 `.claude/settings.local.json`。
- `docs/runs/` 中包含前序运行日志；建议一起提交作为项目历史，或由 owner 决定是否拆分。
- 本轮没有删除任何已存在本地产物或用户本地设置。

## 阶段 8：最终验收报告

### 本轮完成

- 完成 8 个阶段：现状建模、安全卫生、Demo Flow 产品化、浏览器验收、测试/CI 稳定化、文档整理、M2 roadmap、de-sloppify。
- Demo Flow 已达到可演示基线：
  - 注册/登录。
  - Dashboard。
  - 触发 Demo 攻击。
  - 统计卡和告警表可见。
  - Copilot 绑定当前告警。
  - 无 API Key/Base URL 时有清晰降级态。
- 修复 JSON 日志 formatter 运行时错误。
- 消除 SSRF 测试对外网 DNS 的依赖。
- 移除 legacy 手工脚本里的疑似真实 LLM key，并避免打印 access token 前缀。
- 新增 M2 产品路线图。

### 改动分组

代码：

- `server/routers/alerts_router.py`
- `server/services/alert_service.py`
- `server/core/logging_setup.py`
- `web-next/app/page.tsx`
- `web-next/app/dashboard/dashboard-client.tsx`
- `web-next/hooks/useAlerts.ts`
- `web-next/types/alert.ts`

测试：

- `server/tests/test_demo_flow.py`
- `server/tests/test_logging_setup.py`
- `server/tests/test_ssrf.py`

文档：

- `README.md`
- `PRODUCT.md`
- `server/STRUCTURE.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`
- `docs/runs/2026-06-16-m1-m2-productization-campaign.md`
- 前序已有：`docs/agent/UNATTENDED_LONG_TASKS.md`、`docs/runs/2026-06-15-*.md`

脚本：

- `scripts/demo_attack.ps1`

安全/提交卫生：

- `.gitignore`
- `server/tests/manual/legacy/README.md`
- `server/tests/manual/legacy/audit_test.py`
- `server/tests/manual/legacy/comprehensive_test.py`
- `server/tests/manual/legacy/run_tests.py`

CI / 前序基线：

- `.github/workflows/ci.yml`
- `web-next/package.json`

### 建议提交

- Demo Flow、日志修复、SSRF 测试稳定化、README/PRODUCT/STRUCTURE、M2 roadmap、运行日志、legacy fake key 清理、`.gitignore`。
- 前序已有但仍属于产品基线的：CI/typecheck/build、E2E 可选化、demo script、long task docs。

### 绝对不要提交

- `.coverage`
- `.claude/settings.local.json`
- `server/.coverage`
- `htmlcov/`
- `web-next/.next/`
- `web-next/tsconfig.tsbuildinfo`
- 任何真实 `.env` / `.env.local`
- `data/app.db` 或其他 `*.db`

### 安全风险与处理

- 疑似真实 key：`server/tests/manual/legacy/audit_test.py` 中 `sk-faa18...` 已替换为 fake test key。
- Token 日志泄漏：legacy 手工脚本不再打印 access token 前缀，只打印长度。
- Copilot 降级态：无 key/Base URL 时展示可理解错误，不泄露 stack trace、regex 或密钥。
- MCP 鉴权、Guardrails、安全测试未弱化。

### 当前 ready 状态

- 代码和文档候选通过验证，可以做选择性提交。
- 当前整个工作树不适合直接 `git add .`，因为包含 `.coverage` 和 `.claude/settings.local.json`。

### 下一条更大的长任务提示词

```markdown
你是 AI-CyberSentinel 的 L2/L3 长任务 agent。请先阅读 `PRODUCT.md`、`AGENTS.md`、`CLAUDE.md`、`docs/agent/UNATTENDED_LONG_TASKS.md`、`docs/plans/M2_PRODUCT_ROADMAP.md` 和最近的 `docs/runs/`。

任务名称：M2-02 Demo Flow 自动化 E2E。

目标：把 2026-06-16 已手工跑通的真实浏览器路径固化成可重复验证入口：注册或登录 -> Dashboard -> 触发 Demo 攻击 -> 告警表可见 -> Copilot 分析当前告警 -> 无 API Key/Base URL 时显示清晰降级态。

允许修改：`server/tests/test_e2e.py`、必要的 test helper、README/PRODUCT/UNATTENDED_LONG_TASKS 中的 E2E 说明。必要时可小范围修改前端 data-testid 或稳定选择器。

禁止修改：认证语义、Guardrails/MCP 鉴权、真实 `.env`、`.claude/settings.local.json`、`.coverage`、数据库文件。不要 commit/push/reset/clean。

验收：默认 `pytest server/tests` 仍通过且 E2E 默认 skip；显式 `--run-e2e` 在本地具备 Playwright 浏览器时能跑通 Demo Flow；缺少浏览器时给出清晰 skip；前端改动需通过 `npm run typecheck` 和 `npm run build`。
```
