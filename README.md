# AI-CyberSentinel

AI-CyberSentinel 是一个面向学习、演示和小型安全团队的 AI 辅助 IDS / WAF / SOC Copilot 项目。它把 Web 攻击检测、告警记录、仪表盘展示和 LLM 安全分析放在同一个仓库里，目标是让用户能跑通一条安全闭环：

```text
流量 / 模拟攻击 -> WAF / Sniffer -> 告警 -> Web Dashboard -> Copilot 分析 -> 审计与指标
```

当前最适合用它做三件事：

- **Protect**：识别并拦截常见 Web 攻击，例如 SQL 注入、XSS、扫描和暴力尝试。
- **Explain**：把告警解释成风险、证据、影响和建议动作。
- **Operate**：保留审计日志、健康状态和护栏指标，便于复盘。

## 新手先看

推荐先用“本地开发启动”跑起来。Docker Compose 路径还保留在仓库中，但当前数据库和后端环境变量接线有待确认，不建议作为第一次启动路径。

你需要准备：

- Windows PowerShell
- Python 3.12+（Dockerfile 当前使用 Python 3.13）
- Node.js 20+ 与 npm 10+
- 可选：Docker Desktop（只用于后面的 Docker 路径）

## 项目结构

```text
AI-IDS-Project/
├── server/                    # FastAPI 后端
│   ├── main.py                # 后端入口，挂载路由、/health、/ready、/mcp
│   ├── core/                  # 配置、数据库、认证依赖、限流、日志等基础设施
│   ├── routers/               # API 路由：auth、alerts、copilot、waf、metrics 等
│   ├── services/              # 业务服务：告警、Copilot、LLM provider、通知等
│   ├── security/              # LLM Guardrails 等安全模块
│   ├── middleware/            # WAF 中间件
│   └── tests/                 # pytest 测试
├── web-next/                  # Next.js 15 前端
│   ├── app/                   # App Router 页面与 API 代理
│   ├── components/            # Dashboard 组件
│   ├── hooks/                 # 前端数据与交互 hooks
│   └── package.json           # npm 脚本
├── agent/                     # 旧版 sniffer / defender 脚本
├── models/                    # 随机森林模型与训练脚本
├── simulator/                 # 攻击模拟脚本
├── docs/                      # 项目文档、计划、运行日志
├── nginx/                     # Nginx 反向代理配置
├── docker-compose.yml         # 容器编排（当前作为待确认路径）
├── deploy.ps1                 # Windows Docker 部署辅助脚本
├── .env.example               # 根环境变量模板
└── requirements.txt           # 后端 Python 依赖
```

更细的后端目录说明见 [`server/STRUCTURE.md`](server/STRUCTURE.md)。

## 本地开发启动

下面步骤假设你在仓库根目录执行命令。

### 1. 准备后端环境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

打开 `.env`，至少改这些值：

```env
APP_ENV=development
DEV_MODE=true
APP_SECRET=<换成至少 32 字符的随机字符串>
AUTH_SECRET=<换成至少 32 字符的随机字符串>
CORS_ORIGINS=http://127.0.0.1:3000,http://localhost:3000
NEMO_GUARDRAILS_ENABLED=false
```

生成随机字符串可以用：

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

注意：

- 不要直接使用 `.env.example` 里的 `change-me-*` 示例值，后端会拒绝弱默认密钥。
- 本地开发要把 `APP_ENV` 改成 `development`。模板默认是 `production`，生产模式下如果 CORS 仍允许 localhost，后端会拒绝启动。
- 当前后端数据库实际使用 `data/app.db` SQLite 文件；`.env` 里的 `DATABASE_URL` 暂未被 `server/core/database.py` 读取，PostgreSQL 路径待确认。

启动后端：

```powershell
.\.venv\Scripts\python.exe -m uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload
```

后端启动后，另开一个 PowerShell 验证：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

期望看到：

```json
{"status":"ok"}
```

### 2. 准备前端环境

另开一个 PowerShell：

```powershell
cd web-next
npm ci
Copy-Item .env.example .env.local
```

打开 `web-next/.env.local`，至少确认：

```env
AUTH_SECRET=<换成至少 32 字符的随机字符串>
BACKEND_BASE_URL=http://127.0.0.1:8000
```

`AUTH_SECRET` 可以和根 `.env` 中的 `AUTH_SECRET` 使用同一个本地随机值。

启动前端：

```powershell
npm run dev
```

访问：

- 前端：http://localhost:3000
- 后端健康检查：http://127.0.0.1:8000/health
- 后端 API 文档：http://127.0.0.1:8000/docs

## Demo Flow：模拟攻击闭环

启动前后端并登录 Dashboard 后，可以在“实时告警与 AI 助手”区域点击“触发 Demo 攻击”。系统会生成一条固定 SQL 注入样本，写入后端告警 backlog，并在 Dashboard 中选中该告警。Dashboard 会同时提示 Copilot 当前是否已具备真实分析条件。随后点击 AI 助手里的“分析当前告警”，Copilot 会带着 `alert_id` 请求后端。

没有真实 LLM API Key 或 Base URL 时，Demo Flow 会明确返回 `missing_api_key_or_base_url` 降级信号，Copilot 会展示“请先在配置页设置可用的 API Key 与 Base URL”的降级态；这也是可演示路径的一部分，表示告警闭环已跑通，只是模型分析不可用。有 API Key 时，Copilot 会基于选中的告警上下文流式输出分析。

也可以用脚本跑同一条后端 smoke flow：

```powershell
.\scripts\demo_attack.ps1 `
  -BaseUrl http://127.0.0.1:8000 `
  -Email demo-analyst@example.com `
  -Password DemoPass123! `
  -Scenario sql_injection
```

脚本会依次检查 `/health`、注册或登录 demo 用户、触发 `/alerts/demo`、确认 `/alerts` 可读取该告警，打印 Copilot `ready` 或 fallback 状态，并调用 `/copilot/stream` 验证流式接口或降级态。

## Docker Compose 启动（待确认）

仓库保留了 `docker-compose.yml` 和 `deploy.ps1`，但它们当前不作为新手首选路径。

已确认事实：

- `deploy.ps1` 第一次运行时，如果没有 `.env`，会复制 `.env.example` 为 `.env` 并退出，要求你先编辑密钥。
- `docker-compose.yml` 会启动 backend、frontend、nginx、postgres、redis。
- `docker-compose.yml` 当前给 backend 传入 `APP_SECRET`，但没有显式传入 `AUTH_SECRET`；而 `server/main.py` 启动时要求 `AUTH_SECRET` 非默认。
- `server/core/database.py` 当前硬编码 SQLite `data/app.db`，没有读取 `DATABASE_URL`，所以 Compose 中的 PostgreSQL 接线仍待确认。

如果你仍要尝试 Docker 路径：

```powershell
Copy-Item .env.example .env
# 编辑 .env：填入 APP_SECRET、AUTH_SECRET、POSTGRES_PASSWORD、REDIS_PASSWORD 等真实随机值
.\deploy.ps1
# 如果第一次运行只是创建 .env 并退出，编辑完成后再运行一次：
.\deploy.ps1
```

## 当前验证基线

不需要每次都跑全量测试。当前推荐的验证命令如下。

### 前端

```powershell
cd web-next
npm run typecheck
npm run build
```

### 后端默认测试

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.\.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

### 可选 Playwright E2E

E2E 默认不阻塞后端测试。需要显式跑浏览器端到端测试时，先安装 Playwright 和浏览器，再加 `--run-e2e`：

```powershell
.\.venv\Scripts\python.exe -m pip install playwright
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m pytest server\tests\test_e2e.py -q --tb=short --run-e2e
```

### Demo Flow 浏览器级 E2E

`server/tests/test_demo_flow_e2e.py` 把"注册 → Dashboard → 触发 Demo 攻击 → 告警表出现 → 分析当前告警 → Copilot 降级态"固化为可重复 E2E。运行前先启动后端和前端 dev server，再：

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow_e2e.py -q --tb=short --run-e2e
```

缺 Playwright / 缺浏览器 / 缺 dev server 时会打印明确指引并 skip，不会让默认 pytest 失败。

### Copilot Contract 测试

`server/tests/test_copilot_contract.py` 用 `FakeLLMProvider`（duck-typed SSE 模拟）覆盖"有 key 成功流式 / 无 key 降级 / Guardrails block"三条路径，不依赖真实外部 LLM。`FakeLLMProvider` 仅通过 `register_provider("fake_test", ...)` 在测试中显式注入；`_PROVIDERS` 默认 registry 不含 `fake_test`。

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\test_copilot_contract.py -q --tb=short
```

### 安全运营时间线

`GET /logs/security-timeline` 返回当前用户最近 50 条安全运营事件（demo 攻击、Copilot 请求、Guardrails 决策摘要、认证 / 配置变更），全字段脱敏：不含 regex / stack trace / API key / system prompt。Dashboard § 03.5 段可视化。

### 生产最小安全配置检查

`scripts/check_env_security.py` 检查 `.env`、gitignore、生产必填 secret、placeholder、APP_ENV/CORS、DEV_MODE、metrics/MCP 暴露边界。退出码 0 = 通过；1 = 存在阻塞项。

```powershell
PYTHONIOENCODING=utf-8 .\.venv\Scripts\python.exe scripts\check_env_security.py
```

### Guardrails

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.\.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

### GitHub Actions 后端覆盖率门槛

CI 后端作业仍运行 `server\tests` 全量测试，但覆盖率门槛只统计当前 M0 守护的核心模块：LLM Guardrails、RBAC、安全工具和 ORM 模型。这样不会删除或跳过业务测试，也不会把尚未治理的 demo、legacy、router、service 面积混入同一个 80% 门槛。

```powershell
$env:APP_SECRET='test-ci-secret-key-for-testing-only-32chars'
$env:AUTH_SECRET='test-ci-auth-secret-for-testing-only-32chars'
.\.venv\Scripts\python.exe -m pytest server\tests -q --tb=short `
  --cov=server.security.llm_guardrails `
  --cov=server.core.rbac `
  --cov=server.security_utils `
  --cov=server.models_db `
  --cov-report=term `
  --cov-fail-under=80
```

已知基线：

- 前端：`npm run typecheck`、`npm run build`
- 后端默认测试：`pytest server/tests`
- Demo Flow smoke：`pytest server/tests/test_demo_flow.py`
- 可选 E2E：`pytest server/tests/test_e2e.py --run-e2e`
- Guardrails：`pytest server/tests/security/llm_guardrails`
- 后端 CI 核心覆盖率门槛：全量测试 + 核心模块覆盖率 >= 80%

## 提交前卫生检查

提交前至少看两眼工作树：

```powershell
git status --short --branch
git diff --stat
git diff --check
```

不要提交这些本地产物或本机配置：

- `.env`、`.env.*`，但 `.env.example` 需要跟随新增配置同步。
- `web-next/.env`、`web-next/.env.local`。
- `.claude/settings.local.json`。
- `.coverage`、`server/.coverage`、`coverage.xml`、`htmlcov/`。
- `data/app.db`、`*.db`、`backups/`。
- `web-next/.next/`、`web-next/tsconfig.tsbuildinfo`、`node_modules/`。

如果 secret scan 命中真实 `sk-*`、GitHub token、私钥、生产密码或真实用户 token，先移除再继续。测试用 fake key 必须带有 `test`、`fake` 或示例语义。

## 常见问题

### PowerShell 里看到中文乱码怎么办？

这些 Markdown 文件按 UTF-8 编写。PowerShell 如果用默认编码读取，可能显示乱码。读取时使用：

```powershell
Get-Content -Raw -Encoding UTF8 README.md
```

### 后端一启动就退出怎么办？

优先检查 `.env`：

- `APP_SECRET` 不能是 `change-me`、`secret` 或空值。
- `AUTH_SECRET` 不能是 `change-me`、`secret` 或空值。
- 本地开发建议设置 `APP_ENV=development`。

### 为什么默认 pytest 不再被 E2E 卡住？

`server/tests/test_e2e.py` 已标记为可选 E2E。默认 `pytest server/tests` 会跳过它；只有显式传入 `--run-e2e` 时才运行浏览器端到端测试。缺少 Playwright 时，E2E 会给出 skip，而不是让默认收集失败。

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
.\.venv\Scripts\python.exe -m pytest server\tests\test_e2e.py -q --tb=short --run-e2e
```

### `npx next lint` 可以作为验证吗？

不要把 `npx next lint` 放进默认验证或 CI。当前 Next.js 15 项目没有独立 ESLint 配置，CI 使用非交互式命令：

```powershell
npm run typecheck
npm run build
```

## 文档地图

- [`PRODUCT.md`](PRODUCT.md)：产品边界、路线图和当前任务队列。
- [`AGENTS.md`](AGENTS.md)：AI Agent 路由、关键模块速查和项目规则。
- [`CLAUDE.md`](CLAUDE.md)：Claude / Agent 的硬规则和流程纪律。
- [`docs/agent/UNATTENDED_LONG_TASKS.md`](docs/agent/UNATTENDED_LONG_TASKS.md)：无人值守长任务规范。
- [`docs/plans/LLM_GUARDRAILS_PLAN.md`](docs/plans/LLM_GUARDRAILS_PLAN.md)：LLM Guardrails 设计稿。
- [`docs/ALEMBIC_MIGRATION.md`](docs/ALEMBIC_MIGRATION.md)：数据库迁移到 Alembic 的计划。
- [`docs/RELEASE_NOTES.md`](docs/RELEASE_NOTES.md)：LLM Guardrails 批次发布说明。

## 当前已知限制

- Docker Compose 数据库路径待确认：Compose 声明 PostgreSQL，但后端当前实际使用 SQLite。
- Docker Compose backend 的 `AUTH_SECRET` 传入待确认。
- Playwright E2E 是可选验证，默认 pytest 会跳过；显式运行时需要安装 Playwright 浏览器。
- LLM / 邮件 / OAuth / 威胁情报等外部服务需要真实凭证；没有凭证时应按降级或待确认处理。
- `start_all.bat` 启动的是旧版静态 `web/` 前端，不是当前推荐的 `web-next/` 新前端。

## 许可证

本项目仅供学习、研究和演示使用。用于真实网络环境前，请先完成安全审查、密钥配置、部署验证和数据合规评估。
