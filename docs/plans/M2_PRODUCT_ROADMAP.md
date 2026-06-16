# M2 Product Roadmap

> 状态：2026-06-16 草案，基于 M1-M2 productization campaign 的真实代码、测试和浏览器验收结果。
> 目标读者：项目 owner、后续 AI Agent、临时技术负责人。

## 1. 当前产品能力

AI-CyberSentinel 当前已经具备一个可演示的安全闭环：

- 用户可通过 Next.js 前端注册、登录并进入 Dashboard。
- Dashboard 可触发认证态 `POST /alerts/demo`，生成固定 SQL 注入告警。
- 告警会进入后端 backlog，并在 Dashboard 统计卡、告警表、日报摘要和 Copilot 上下文中可见。
- Copilot 可对选中告警发起 SSE 请求。
- 无真实 API Key/Base URL 时，Dashboard、终端日志和 Copilot SSE 都能展示清晰降级态。
- LLM Guardrails 有 L1/L4/NeMo 路径、audit、Prometheus `/metrics` 和 `/mcp` 工具入口。
- 当前验证基线：
  - 后端默认测试：`225 passed, 1 skipped`
  - Guardrails 专项：`139 passed, 17 warnings`
  - Demo Flow：`5 passed`
  - 前端：`npm run typecheck`、`npm run build` 通过

## 2. 当前最弱环节

1. 数据库来源不一致：
   - `server/core/database.py` 实际使用硬编码 SQLite `data/app.db`。
   - `.env.example` 和 Docker Compose 暗示 `DATABASE_URL` / PostgreSQL，但后端 engine 尚未读取。
   - 启动时仍用 `ensure_user_config_columns()` 手写 `ALTER TABLE`。

2. 运营可见性分散：
   - Guardrails audit 有 DB 行和 `/metrics`，但 Dashboard 没有统一展示。
   - demo attack、Copilot 请求、Guardrails 决策、普通操作日志分散在不同表/端点。

3. 部署路径尚未可信：
   - Docker Compose 可 build，但数据库、迁移、生产 env、nginx allowlist、MCP key、metrics 暴露边界还没有端到端验收。

4. 前端大组件风险：
   - `web-next/app/page.tsx` 和 `web-next/app/dashboard/dashboard-client.tsx` 偏大，后续 agent 改状态容易误伤。

5. E2E 仍是可选：
   - 默认 pytest 跳过 Playwright E2E。
   - 已通过 in-app Browser 手工验收 Demo Flow，但还没有稳定自动化浏览器测试。

6. 真实 LLM 分析路径未形成可重复测试：
   - 当前能验证无 key 降级态。
   - 有 key 的 provider 流式分析依赖外部服务，缺少可控 fake provider 或 contract test。

## 3. M2 应做什么

M2 的主题是“安全运营化”，不是继续堆新功能。M2 应把 M1 的可演示闭环变成可长期维护的小型 SOC 基线：

- 统一数据库配置和迁移策略。
- 让健康、metrics、Guardrails、审计、demo flow 有一致的运维说明和验证入口。
- 建立可自动运行的浏览器级 Demo Flow 验收。
- 收敛 Dashboard 状态和组件边界，降低后续 agent 修改风险。
- 明确生产最小安全配置：secret、CORS、cookie、MCP key、metrics 暴露、nginx allowlist。

## 4. M2 不应该做什么

- 不做企业级 SIEM、复杂多租户、计费、资产平台。
- 不重写前端框架或后端框架。
- 不把 Docker Compose 声称为生产可用，除非完成数据库和安全边界验收。
- 不为了跑通 demo 而弱化认证、MCP 鉴权、Guardrails、SSE error 净化或测试。
- 不引入真实生产密钥到代码、测试、日志或文档。
- 不用 skip 掩盖默认测试失败。

## 5. 可无人值守执行的长任务

### M2-01：数据库配置与 Alembic 基线

目标：统一数据库 URL 来源，建立 Alembic 迁移基线，替代启动时手写 schema 漂移。

允许范围：

- `server/core/database.py`
- `server/models_db.py`
- `migrations/**` 或新建 `alembic/**`
- `requirements.txt`
- `.env.example`
- `docs/ALEMBIC_MIGRATION.md`
- 后端数据库相关测试

禁止范围：

- 不删除现有 `data/app.db`。
- 不破坏本地 SQLite 默认路径。
- 不自动迁移生产数据库。
- 不改认证语义。

验收标准：

- 新空 SQLite 库可创建完整 schema。
- 旧 SQLite 开发库可安全升级。
- `pytest server/tests -q --tb=short` 通过。
- 文档说明 `DATABASE_URL` 的真实行为。
- 若引入 Alembic，必须能执行 `upgrade head`，并记录 downgrade 策略。

主要风险：

- SQLite/PostgreSQL 差异被测试遗漏。
- 启动自动迁移可能引入生产风险。优先文档化并使用显式迁移命令。

### M2-02：Demo Flow 自动化 E2E

目标：把 2026-06-16 手工浏览器验收固化成可重复测试。

允许范围：

- `server/tests/test_e2e.py`
- `web-next/scripts/**`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- README 的 E2E 说明
- 必要的 test fixture 或 smoke helper

禁止范围：

- 不把 E2E 放回默认必跑基线。
- 不全局安装 Playwright。
- 不依赖真实 LLM API key。

验收标准：

- 显式 `--run-e2e` 可启动或连接前后端，完成登录、触发 Demo、告警表可见、Copilot 降级态可见。
- 缺少 Playwright 浏览器时清晰 skip。
- 默认 `pytest server/tests` 仍稳定通过。

主要风险：

- Windows/CI 浏览器依赖不一致。
- NextAuth cookie/session 在热更新或跨 host 时不稳定。

### M2-03：审计时间线与 Guardrails 可见性

目标：把 demo attack、Copilot 请求、Guardrails 决策、登录/配置变更整理成可查询的时间线。

允许范围：

- `server/services/audit_service.py`
- `server/routers/logs_router.py`
- `server/security/llm_guardrails/audit.py`
- `web-next/app/dashboard/dashboard-client.tsx`
- 新增小型 timeline 组件
- 相关测试

禁止范围：

- 不暴露 regex 模式、stack trace、API key、系统 prompt。
- 不弱化 SSE error 净化。
- 不把 audit 写失败变成用户请求失败。

验收标准：

- Dashboard 可看到最近关键安全事件。
- Guardrails block/pass/warning 有用户可理解的类别摘要。
- Audit log 仍保留 SOC 排查所需完整 reason。
- Guardrails 专项测试通过。

主要风险：

- 用户可见信息过度详细导致安全泄漏。
- audit 查询无分页导致性能问题。

### M2-04：生产最小安全配置文档与检查

目标：让部署前必须配置的安全项可检查、可解释。

允许范围：

- `scripts/check_env_security.py`
- `.env.example`
- `README.md`
- `OWNER_MANUAL.md`
- `nginx/nginx.conf`
- CI security check

禁止范围：

- 不写真实 secret。
- 不把公网 metrics/MCP 作为默认开放。
- 不降低 CORS、cookie、TrustedHost、MCP key 要求。

验收标准：

- 缺少 `AUTH_SECRET`、`APP_SECRET`、`GUARDRAILS_MCP_API_KEY` 时行为和文档一致。
- 生产模式下 localhost CORS 被拒绝的说明清楚。
- metrics 和 MCP 的推荐 nginx allowlist 写清。
- CI 的 env security check 通过。

主要风险：

- 文档与代码启动检查不一致。
- 过度严格导致本地开发体验变差。

### M2-05：Dashboard 状态边界拆分

目标：降低 `dashboard-client.tsx` 的改动风险，把 Demo、alerts、Copilot、system status 分成更清楚的组件边界。

允许范围：

- `web-next/app/dashboard/dashboard-client.tsx`
- `web-next/components/dashboard/**`
- `web-next/hooks/useAlerts.ts`
- `web-next/hooks/useCopilot.ts`
- 前端类型与测试/构建

禁止范围：

- 不重写视觉系统。
- 不做 landing page。
- 不改变 API 契约，除非同步后端测试。

验收标准：

- `npm run typecheck` 和 `npm run build` 通过。
- Demo Flow 浏览器路径仍可用。
- 组件拆分后单文件复杂度下降，状态流向更清晰。

主要风险：

- 拆分时打断 selected alert、pagination、terminal/report 的状态同步。

### M2-06：Provider Fake/Contract 测试

目标：让 Copilot 有 key 路径在不依赖真实外部 LLM 的情况下可测。

允许范围：

- `server/services/llm_providers.py`
- `server/services/copilot_service.py`
- `server/tests/**`
- 必要的 fake provider 或 monkeypatch fixture

禁止范围：

- 不把 fake provider 暴露成生产默认 provider。
- 不跳过 Guardrails。
- 不记录真实 prompt 或真实 key。

验收标准：

- Copilot SSE 成功流式输出可通过 fake provider 测试。
- 无 key 降级态仍通过 Demo Flow 测试。
- Guardrails 输入/输出检查仍执行并有 audit。

主要风险：

- fake provider 与真实 OpenAI-compatible provider 行为偏离。

### M2-07：Docker Compose 端到端验收

目标：把 Compose 从“可 build 但待确认”推进到“明确可用或明确阻塞”。

允许范围：

- `docker-compose.yml`
- `server/Dockerfile`
- `web-next/Dockerfile`
- `nginx/nginx.conf`
- `.env.example`
- `README.md`
- `docs/deploy/**` 或部署说明

禁止范围：

- 不推镜像。
- 不部署到公网。
- 不使用真实生产密钥。

验收标准：

- `docker compose build` 通过。
- 使用测试 `.env` 可启动到健康状态，或明确列出阻塞。
- 前端能通过 nginx 访问并登录。
- metrics/MCP 暴露边界明确。

主要风险：

- PostgreSQL 与当前 SQLite 代码路径不一致。
- 容器网络和 NextAuth host/cookie 配置易出错。

## 6. 推荐执行顺序

1. M2-02：先把 Demo Flow E2E 自动化，保护当前已跑通的产品基线。
2. M2-06：补 Copilot fake provider contract，保护 Explain 路径。
3. M2-03：做审计时间线，让安全运营闭环可见。
4. M2-01：推进数据库配置和迁移，但要拆小并保留 SQLite 回退。
5. M2-04：生产安全配置检查与文档。
6. M2-05：Dashboard 状态边界拆分。
7. M2-07：Compose 端到端验收。

## 7. M2 完成定义

M2 完成时，项目应满足：

- 新人按 README 能本地启动、注册登录、触发 Demo、看到告警、看到 Copilot 降级或分析。
- 默认测试、Guardrails、Demo Flow、前端 typecheck/build 通过。
- 至少一个浏览器级 Demo Flow 自动化入口可用。
- 数据库配置和迁移策略不再自相矛盾。
- 生产最小安全配置文档与启动检查一致。
- 当前工作树能明确区分提交候选、本地产物和后续债务。
