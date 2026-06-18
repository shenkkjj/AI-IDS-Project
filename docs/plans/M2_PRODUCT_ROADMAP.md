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

**当前状态（2026-06-17）**：已交付。

- `server/core/database.py` 重写为 helper 化：``load_database_url`` /
  ``normalize_database_url`` / ``build_engine_kwargs`` / ``create_app_engine``，
  统一读取 ``DATABASE_URL``，未设置时回退到默认 SQLite；``sqlite+aiosqlite://``
  自动归一化为 ``sqlite://``；``connect_args={"check_same_thread": False}`` 只
  应用于 SQLite。
- Alembic 已初始化（``alembic.ini`` + ``migrations/``）；``migrations/env.py``
  显式 ``import server.core.database.Base`` 和 ``server.models_db``，与 app 走
  同一套 URL 解析。
- baseline revision：``d9af4388f20a_baseline_schema.py``，autogenerate 覆盖全部
  6 张表和全部索引（含 SC-22 复合索引）。
- ``ensure_user_config_columns()`` 保留为 legacy 兼容层（``server/main.py``
  启动路径标注），``init_db()`` 仍作为新空库快速回退。
- 新增 ``server/tests/test_database_config.py``（13 通过）和
  ``server/tests/test_migrations.py``（8 通过），覆盖 URL 解析、engine kwargs、
  模块级 engine 行为、alembic CLI、upgrade head / current 行为、env.py 元数据加载。
- 文档同步：``.env.example`` / ``README.md`` / ``server/STRUCTURE.md`` /
  ``docs/ALEMBIC_MIGRATION.md``（从"计划"改为"已建立 baseline"）/
  ``docs/plans/M2_PRODUCT_ROADMAP.md``（本节）/ ``PRODUCT.md``。
- 运行日志：``docs/runs/2026-06-17-m2-01-database-url-alembic-baseline.md``。
- 依赖新增：``alembic==1.13.2`` / ``psycopg[binary]==3.2.3``（写入
  ``requirements.txt``），但 PostgreSQL 端到端验收仍属 M2-07。

允许范围：

- `server/core/database.py`
- `server/main.py`（仅调整数据库初始化/迁移调用）
- `server/db.py`（re-export 兼容）
- `server/models_db.py`（仅当 Alembic autogenerate 需要 import/metadata 修正，不新增业务字段）
- `server/migrations/**`
- `alembic.ini`
- `migrations/**`
- `server/tests/test_database_config.py` / `test_migrations.py`
- `server/tests/conftest.py`（仅测试隔离必要调整）
- `requirements.txt`
- 文档（`.env.example` / `README.md` / `server/STRUCTURE.md` / `docs/ALEMBIC_MIGRATION.md`）

禁止范围：

- 不删除现有 `data/app.db`。
- 不破坏本地 SQLite 默认路径。
- 不自动迁移生产数据库。
- 不改认证语义。

验收标准：

- 新空 SQLite 库可创建完整 schema。✅
- 旧 SQLite 开发库可安全升级（`ensure_user_config_columns` 仍保留）。✅
- `pytest server/tests -q --tb=short` 通过。✅
- 文档说明 `DATABASE_URL` 的真实行为。✅
- Alembic `upgrade head` 在临时 SQLite 上成功；`alembic current` 返回 head revision。✅
- downgrade 策略已写入 `docs/ALEMBIC_MIGRATION.md`。✅

主要风险：

- SQLite/PostgreSQL 差异被测试遗漏：当前默认 URL 用 SQLite；PostgreSQL 走 `psycopg[binary]`，M2-07 端到端验收时再覆盖。
- 启动自动迁移可能引入生产风险：已记录为"不推荐"，新环境用 `alembic upgrade head` 显式执行。

### M2-02：Demo Flow 自动化 E2E

**当前状态（2026-06-16）**：已交付。`server/tests/test_demo_flow_e2e.py` 把"注册 → Dashboard → 触发 Demo → 告警表出现 → 分析当前告警 → Copilot 降级态"固化为可重复 E2E；显式 `--run-e2e` 才运行；缺 playwright / 缺浏览器 / 缺 dev server 都有清晰 skip 或 fail 文案。运行时通过 `data-testid="trigger-demo-attack"` / `analyze-current-alert` / `attack-log-row` / `copilot-message` 选择器。默认 `pytest server/tests` 仍稳定通过（基线 239 passed）。

允许范围：

- `server/tests/test_e2e.py` / `server/tests/test_demo_flow_e2e.py`
- 少量前端 `data-testid`（CopilotPanel / AttackLogTable / Dashboard / page.tsx）
- README / PRODUCT / UNATTENDED_LONG_TASKS 中的 E2E 说明

禁止范围：

- 不把 E2E 放回默认必跑基线。
- 不全局安装 Playwright。
- 不依赖真实 LLM API key。

验收标准：

- 显式 `--run-e2e` 可启动或连接前后端，完成登录、触发 Demo、告警表可见、Copilot 降级态可见。
- 缺少 Playwright 浏览器时清晰 skip。
- 默认 `pytest server/tests` 仍稳定通过。

主要风险：

- Windows/CI 浏览器依赖不一致（已通过缺依赖 skip 路径解决）。
- NextAuth cookie/session 在热更新或跨 host 时不稳定（已通过走 Next.js API 路由 + E2E 容忍。

### M2-03：审计时间线与 Guardrails 可见性

**当前状态（2026-06-16）**：已交付。`GET /logs/security-timeline`（`server/routers/logs_router.py`）合并 `Log` + `AuditLog`，按时间倒序，取最近 50 条（硬上限 100）。前端 `web-next/components/dashboard/SecurityTimeline.tsx` + `web-next/hooks/useSecurityTimeline.ts` 渲染 § 03.5 段。Sentinel 脱敏（`sk-*` / `AKIA*` / `ghp_*` / `xox*` / `PRIVATE KEY` / `Traceback` / L1 regex / `system:`）；失败保护（DB 异常返回 `degraded: True`）。`POST /alerts/demo` 写 `Log(action="demo_attack")`。

允许范围：

- `server/routers/logs_router.py`
- `server/routers/alerts_router.py`（仅 demo attack 写 Log）
- `web-next/components/dashboard/SecurityTimeline.tsx` / `hooks/useSecurityTimeline.ts` / `types/securityTimeline.ts`
- `web-next/app/dashboard/dashboard-client.tsx`（§ 03.5 段集成）
- `server/tests/test_security_timeline.py`

禁止范围：

- 不暴露 regex 模式、stack trace、API key、系统 prompt。
- 不弱化 SSE error 净化。
- 不把 audit 写失败变成用户请求失败。

验收标准：

- Dashboard 可看到最近关键安全事件。
- Guardrails block/pass/warning 有用户可理解的类别摘要。
- Audit log 仍保留 SOC 排查所需完整 reason。
- Guardrails 专项测试通过。
- timeline 测试覆盖未登录 401 / limit cap / 4 个 sentinel 不外泄。

主要风险：

- 用户可见信息过度详细导致安全泄漏：已通过 sentinel 脱敏 + 9 个测试覆盖。
- audit 查询无分页导致性能问题：已硬上限 100 条。

### M2-04：生产最小安全配置文档与检查

**当前状态（2026-06-16）**：已交付。`scripts/check_env_security.py` 重写为四类输出（`[BLOCK]` / `[WARN]` / `[INFO]` / `[PASS]`），覆盖 `.gitignore` / `.env`-in-git / 明文密钥 / 占位值 / 生产必填 secret（`APP_SECRET` / `AUTH_SECRET` / `ALERTS_INGEST_TOKEN`，最小长度 32）/ 生产建议 secret（`GUARDRAILS_MCP_API_KEY` / `POSTGRES_PASSWORD` / `REDIS_PASSWORD`）/ `APP_ENV=production` CORS / `DEV_MODE` / `BIND_HOST` / metrics / MCP 鉴权 / 邮件 / NeMo Guardrails。退出码 0/1 区分通过/阻塞。所有真实值输出都做 `_mask` 脱敏。

允许范围：

- `scripts/check_env_security.py`
- `.env.example`
- `README.md`
- `PRODUCT.md`
- CI security check（未来）

禁止范围：

- 不写真实 secret。
- 不把公网 metrics/MCP 作为默认开放。
- 不降低 CORS、cookie、TrustedHost、MCP key 要求。

验收标准：

- 缺少 `AUTH_SECRET`、`APP_SECRET`、`GUARDRAILS_MCP_API_KEY` 时行为和文档一致。
- 生产模式下 localhost CORS 被拒绝的说明清楚。
- metrics 和 MCP 的推荐 nginx allowlist 写清。
- CI 的 env security check 通过。
- 退出码 0（通过）/ 1（存在 `[BLOCK]`）。

主要风险：

- 文档与代码启动检查不一致：已通过 sentinel 脱敏 + README 同步。
- 过度严格导致本地开发体验变差：本地开发只 INFO/WARN，不 BLOCK。

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

**当前状态（2026-06-16）**：已交付。`server/services/llm_providers.py` 新增 `FakeLLMProvider`（仅 in-memory 记录 `user_message` / `context_block` / `history_len`），duck-typed `fake_stream()` hook；`stream_completion` 通过 `getattr(provider, "fake_stream", None)` 判断走 fake 路径，不 import 测试类。`_PROVIDERS` 默认 registry 不含 `fake_test`，生产不可达 fake。`server/tests/test_copilot_contract.py` 5 个测试：静态（registry 不暴露 / 解析回退）、动态（成功流式 + alert_id 注入 / 无 key 降级 fake 不被调 / Guardrails block fake 不被调 + reason 全文不外泄）。

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
- `_PROVIDERS` 默认不含 `fake_test`；`resolve_provider("fake_test")` 回退到 OpenAI。
- Guardrails block 时 fake 调用计数=0；sse_error 仅含 category 摘要，reason 全文不外泄。

主要风险：

- fake provider 与真实 OpenAI-compatible provider 行为偏离：fake 仅 emit 8-char 切片近似；contract 测试断言 alert_id 上下文注入、event: done 收尾、不含 event: error。

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

---

## 8. M3 路线图（产品体验升级）

> 详细任务在 `docs/agent/M3_*.md`；本节只记录交付状态与边界。

### M3-02 告警研判与处置工作台（已交付）

- `PATCH /alerts/{alert_id}/triage`（5 个稳定状态 / 800 字 note 上限 / 非 owner 404 / 脱敏审计）。
- Dashboard `AlertTriagePanel` 紧凑控件 + 简报“待研判 / 已闭环”计数。
- **边界（已被 M3-03 升级）**：triage 状态保存到当前进程告警 backlog payload，跨重启不保留，跨进程实例不共享。

### M3-03 告警研判持久化与历史（2026-06-18 已交付）

- 新增 `alert_records` / `alert_triage_events` 表 + Alembic migration `d33d40488e0f`（在 baseline `d9af4388f20a` 之上）。
- `GET /alerts` 重启后从 `alert_records` 恢复；DB 读失败回退内存 backlog。
- `PATCH /alerts/{alert_id}/triage` 同步写 `alert_records.triage_*` 与一条 `alert_triage_events`。
- `GET /alerts/{alert_id}/triage/history?limit=50` 返回 owner 隔离的 newest-first 历史。
- 前端 `AlertTriageHistory` 集成到 `AlertTriagePanel` 末尾，保存成功后由 `historyRefreshKey` 自增自动刷新。
- **存储策略**：raw alert / LLM analysis 用 `Text` 列 + `json.dumps(..., ensure_ascii=False)`，不依赖 PostgreSQL JSONB；SQLite 测试库与 Compose PostgreSQL 走同一份代码。
- **审计边界**：`Log(action="alert_triage_update")` 仍只写脱敏摘要（`status=...` / `disposition=...` / `note_length=...` / `source_ip=...`），不写完整 note / payload / secret。
- **当前不做**：完整工单系统、SLA、负责人分派、批量处置、通知升级、Jira/Slack 集成。
- 运行日志：`docs/runs/2026-06-18-m3-03-alert-triage-persistence-and-history.md`。
