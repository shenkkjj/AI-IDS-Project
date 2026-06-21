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
   - `web-next/app/page.tsx` 仍偏大。
   - `web-next/app/dashboard/dashboard-client.tsx` 已在 M3-10 从 840 行降到 406 行，并把 route JSX 拆到 section 组件；后续风险主要是 section 响应式 QA、可访问性和浏览器截图证据不足。

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

### M3-04 安全事件 / 案件工作台（2026-06-18 已交付）

- 新增 `incidents` / `incident_alert_links` / `incident_events` 表 + Alembic migration `4f3c9a1d8b7e`（在 M3-03 `d33d40488e0f` 之上）。
- `GET /incidents?limit=50&status=...` 返回 owner 隔离的 incident 列表；`GET /incidents/{id}?event_limit=20` 返回 incident + linked_alerts + newest-first 事件时间线。
- `POST /incidents` 从 owner alert 创建案件并自动 link；`alert_id` 不属于当前 user / 不存在 → 404，不通过 403 暴露存在性。
- `PATCH /incidents/{id}` 推进 status / severity / title / summary 并写对应 `IncidentEvent`；`resolved / false_positive` 自动设置 `closed_at`、改回打开态清空；`note` 附在同事务事件上。
- `POST /incidents/{id}/alerts` 重复 link 幂等（不重复写 active link / `IncidentEvent` / Log）。
- `DELETE /incidents/{id}/alerts/{alert_id}` 软删除 link（`removed_at`），不删 `alert_records`。
- 重启恢复：清空 `app_state.alert.backlog` + 全新 SQLAlchemy engine + 同一 DB 文件，仍能从 DB 读出 incident / linked_alerts / events。
- 前端 `useIncidents` hook + `IncidentSection / IncidentList / IncidentDetailPanel / IncidentTimeline / IncidentLinkedAlerts` 5 个新组件 + `RouteKey="incidents"` + `AlertDetailPanel` 增加"从此告警创建案件"按钮（按 `riskLevel` 映射 incident severity）。
- Copilot 案件摘要走前端拼接消息模板（`buildCopilotPrompt`），不走后端 incident-aware contract；模板只含 incident id / title / severity / status / 关联告警数 / 最多 5 条告警摘要 + 四段式输出要求（风险 / 证据 / 影响 / 下一步处置），不含 secret / system prompt / stack trace。
- **审计边界**：`Log(action=incident_create / incident_update / incident_alert_link / incident_alert_unlink)` 仍只写脱敏摘要（`incident_id=...` / `changed=...` / `status=A->B` / `severity=A->B` / `note_length=...` / `alert_id=...`），不写完整 note / payload / secret / stack trace；`IncidentEvent.note` 在 DB 中以全文保存（1000 字上限），但只通过 owner API 私有返回给 owner。
- **当前不做**：多租户分派、SLA 计时、Jira/Slack 集成、批量选择 / 拖拽 / 多选表格、通知升级、负责人协作权限（`assignee_user_id` 仅作 owner 自身默认值预留）。
- 运行日志：`docs/runs/2026-06-18-m3-04-incident-case-workbench.md`。

### M3-05 案件感知 Copilot 合约（2026-06-18 已交付）

- `server/models/schemas.py::CopilotStreamIn` 新增 `incident_id: str | None = Field(default=None, max_length=64)`；与 `alert_id` 可独立使用，二者同时存在时 **incident 优先**，`alert_id` 仅作 `selected_alert_id` 行写入 context_block，不重复读 alert payload。
- `server/services/copilot_service.py` 新增受控 context builder：
  - `_load_incident_context(db, user, incident_id)` 走 `incident_service.get_incident_detail(db, user.id, incident_id, event_limit=5)`（M3-04 owner 隔离路径）；非 owner / 不存在统一返回 `None`，**不**区分。
  - `_build_context_from_incident(detail, *, selected_alert_id=None)` 构造受控 context_block：最多 5 条 linked_alerts + 5 条 events；incident summary 截断 500 字符，alert summary 截断 160 字符，event detail 截断 160 字符；event note **不**进 context（只放 `note_length`），alert payload **不**进 context（只放 `payload_length`），不放 secret / system prompt / stack trace / 完整 title。
  - context block 头部固定为 `[当前安全案件上下文]` + `incident_id:` / `title:` / `severity:` / `status:` / `alert_count:` / `selected_alert_id:`（仅 incident 路径写入）/ `summary:`；关联告警段 `[关联告警摘要]`，事件段 `[案件事件摘要]`。
- `copilot_stream` 顺序调整为：rate limit → user config → context lookup → Guardrails input → create_log → provider stream。incident 路径不能绕过 Guardrails；Guardrails block 后 provider 不被调用；incident 不存在 / 非 owner 走 SSE error（**不**走 Guardrails 路径）。
- SSE 错误净化：incident 不存在 → `案件上下文不可用或不存在`（不暴露 owner / 不存在区分，不暴露 incident_id）；Guardrails block → `请求被安全护栏拦截(类别: <category>)`（不暴露 full reason / regex / stack trace）。两条独立。
- audit 脱敏扩展：`Log(action="copilot_stream")` detail 现包含 `provider=...;model=...;alert_id=...;incident_id=...`（incident_id 仅在提供时出现）。`test_copilot_audit_log_includes_incident_id_without_note` 锁定 detail 不写 title / summary / note / fake key / stack trace。
- fake provider 合约测试 `server/tests/test_copilot_incident_contract.py` 9 通过：schema 三测（接受 / 拒长 / 可选）+ happy path 注入（context_block 含案件头部 + 关联告警段 + 事件段）+ incident 缺失（fake.call_count==0 + SSE error 文本）+ Guardrails block with valid incident（fake.call_count==0 + 不暴露 reason/regex）+ audit 脱敏 + 截断（10 alerts + 10 events → 仅前 5；note / payload 全文不进 context）+ alert_id + incident_id 同传时 incident 优先。
- `web-next/hooks/useCopilot.ts` 新增 `SendMessageOptions = { incidentId?: string | null; alertId?: string | null }` 第二参数；显式传 `incidentId` 时 hint 锁定为 `案件上下文: inc_xxx`，body 加 `incident_id` 字段；`alertId` 仍按旧逻辑回退到 `selected?.alertId`。
- `web-next/components/dashboard/IncidentDetailPanel.tsx` 不再调用 `buildCopilotPrompt(detail)`，只发短意图 `请分析当前安全案件,给出风险、证据、影响和下一步处置。` + `incidentId`；删除 `buildCopilotPrompt` 函数与 `sessionStorage` 中间态写入。
- `web-next/app/dashboard/dashboard-client.tsx` 监听 `incident:copilot` 事件，提取 `incidentId` 后调用 `copilotCtx.sendMessage(prompt, { incidentId })`。
- 前端 `npm run typecheck` 0 错误；`npm run build` 通过（`/dashboard` 42.9 kB / First Load JS 190 kB）。
- 后端 `pytest` 9/9 新测试通过；既有 incident / copilot contract / alert triage / demo flow 0 回归（`test_demo_alert_can_drive_copilot_fallback` 仍为 M3-04 baseline 预存 NeMo Guardrails `moderation_unavailable` 失败，与本任务无关）。
- **当前不做**：跨用户案件共享 / SOC 协作会话 / Copilot 案件对话历史持久化 / LLM 端 incident 子文档检索。
- 运行日志：`docs/runs/2026-06-18-m3-05-incident-aware-copilot-contract.md`。

### M3-08 案件报告浏览器验收与 Agent 文档归档（2026-06-18 已交付 / E2E dev 环境阻塞）

> 核心目的：把 M3-07 报告导出从后端契约 / 前端构建推进到真实浏览器级验收；同时收口 M3-07 任务文档未入库问题。

**已交付**：

- `server/tests/test_incident_report_e2e.py` Playwright 真实浏览器 E2E（默认 `pytest server/tests` 跳过；`--run-e2e` 显式触发）：唯一邮箱 → 后端 API 预 register → UI login → 触发 Demo 攻击 → 点击告警 → 创建案件 → 等待 `incident-detail-panel` → 点击"下载报告"（`expect_download` + `accept_downloads=True`）→ 读取 markdown 真实文件内容 → 验证 4 段固定结构（`# 案件证据报告` / `## 1. 案件摘要` / `## 2. 关联告警` / `## 3. 案件时间线` / `## 4. 安全与脱敏说明`） + `payload_length` / `payload_preview` 字段 → 12 条 forbidden sentinel（`sk-` / `sk-proj-` / `AKIA` / `ghp_` / `xox` / `PRIVATE KEY` / `Traceback` / `ignore previous instructions` / `disregard system prompt` / `forget instructions` / `system:` / `developer:`）→ 点击"复制报告" → 验证 `incident-report-status` 命中 `已复制` / `复制失败` / `报告生成失败` / `已下载` / `下载失败` 任一降级 marker → 整页 DOM 扫描 forbidden 文本。`pytestmark = [pytest.mark.e2e]` + `@pytest.mark.e2e` 显式双层 marker（pytest 9 + module-level pytestmark 合并规则兼容）。
- 最小后端修复 1 行：`server/main.py:36-51` `from server.routers import (...)` 漏导 `incidents_router`（M3-04 commit 引入时的回归，本任务首次启动 dev server 触发 `NameError: name 'incidents_router' is not defined`）。修复后 uvicorn 启动正常。
- 文档收口：M3-07 / M3-08 任务文档入库；`UNATTENDED_LONG_TASKS.md` M3-08 条目更新为"已交付"；推荐启动口令更新为下一条 NEXT-01 工单（修 next-auth 5 beta dev mode `useSession` 永 loading 阻塞）。

**E2E 阻塞摘要**（按 M3-08 任务 §15 处理）：

- **现状**：`pytest server/tests` 默认 1 skipped（E2E 不跑）；`--run-e2e` 显式触发时，E2E 在 dashboard 客户端"创建案件"之前 fail（`wait_for_selector('[data-testid="trigger-demo-attack"]')` 45s 超时）。
- **根因**：next-auth 5.0.0-beta.30 + Next.js 15 dev mode 下，`useSession()` 在 dashboard 客户端 `status` 永为 `loading`；`/api/auth/session` 客户端 fetch 返回 200 + user，但 React 状态不同步；`SYSTEM · LOADING` 60s 不消失。
- **不属于 M3-08 任务修复范围**：禁改认证/授权/Guardrails（§6）；`providers.tsx` / `lib/auth.ts` / `next-auth` 升级都属认证代码。
- **影响面**：M3-04 / M3-05 / M3-07 任务都已完成，但前端案件工作台、报告导出 UI 实际**未**在真实浏览器中跑通（E2E 都 fail 在同一阻塞点）；E2E 验收缺失。
- **下一条工单**：NEXT-01（修 `useSession` 永 loading；授权修改认证代码与升级 next-auth / Next.js）。

**验证矩阵（最终）**：

- `pytest server/tests` 默认基线：**332 passed, 3 skipped**（M3-07 baseline 318 + M3-07 新增 14 = 332；+1 skip = E2E 跳过；0 失败）。
- `pytest server/tests/test_incident_report_export.py` 专项：**14 passed**。
- `pytest server/tests/security/llm_guardrails` 专项：**139 passed**。
- 前端 `web-next`：`npm run typecheck` 0 错误；`npm run build` 通过（`/dashboard` 43.7 kB / First Load JS 191 kB）。
- 运行日志：`docs/runs/2026-06-18-m3-08-incident-report-browser-e2e-and-agent-docs-catchup.md`。

### NEXT-01 next-auth 会话 loading 阻塞收口（2026-06-19 已交付）

> 核心目的：解开 M3-08 暴露的 next-auth 5 beta + Next.js 15 dev mode `useSession()` 永 `loading` 阻塞，让真实浏览器 E2E 能进入 Dashboard。

**已交付**：

- `web-next/app/dashboard/page.tsx` 改为 Server Component：`auth()` + `redirect("/")` 决定放行，不再依赖客户端 `useSession()` 的 hydration。
- `web-next/app/layout.tsx` 在服务端调 `auth()` 把 session 透传给 `Providers`；`web-next/app/providers.tsx` 接受 `session?: Session | null` 并喂给 `<SessionProvider session=...>`。
- 不升级 next-auth / next；不改后端 `server/core/auth*` / `server/routers/auth*` / `server/security/**`。
- 新增 `server/tests/test_auth_session_e2e.py` 最小 E2E：注册 → UI 登录 + `/api/auth/callback/credentials` 兜底 → 等 dashboard URL → 断言 `trigger-demo-attack` 45s 内可见 / `SYSTEM · LOADING` 消失 / `/api/auth/session` 返回 user / DOM 无 sentinel。M3-08 `test_incident_report_e2e.py` helper 同步加 callback 兜底 + 列表点击等待。

**验证矩阵（最终）**：

- `pytest server/tests/test_auth_session_e2e.py --run-e2e` **1 passed**。
- `pytest server/tests/test_incident_report_e2e.py --run-e2e` **1 passed**（`registered/demo/create/download/copy_status='已复制'/forbidden=None`）。
- `pytest server/tests/test_incident_report_export.py` **14 passed**；Guardrails 专项 **139 passed**；前端 `npm run typecheck` 0 错误 + `npm run build` 通过（`/dashboard` 43.4 kB / First Load JS 191 kB）。
- 运行日志：`docs/runs/2026-06-19-next-01-auth-session-loading-e2e-recovery.md`。

### NEXT-02 E2E 与 SSRF 质量门硬化（2026-06-19 已交付）

> 核心目的：把 NEXT-01 之后仍残留的两条质量门缺口收口——旧 Demo Flow E2E 用 `expect_navigation` 等 App Router client-side route 不稳定，SSRF 公网域名测试依赖真实 DNS 在受限网络下误红——同时不降低生产 SSRF 防护与认证策略。

**已交付**：

- `server/tests/test_demo_flow_e2e.py` 的 `_register_via_ui` 重写为 NEXT-01 已验证路径：后端 API `/api/backend/auth/register`（409/"已存在"/"exists" 视为已存在）→ 等 `login-email` hydration + `login-submit` 可点击 → `/api/auth/csrf` + `/api/auth/callback/credentials` 直接种 httpOnly cookie → 点击 `login-submit` 兜底 → URL polling `window.location.pathname === '/dashboard'`，失败 fallback 显式 `page.goto("/dashboard")` 让服务端 `auth()` 决定接受 / redirect；`pytestmark` 改成 `[pytest.mark.e2e]` 列表风格；`_wait_for_demo_button` timeout 从 15s 提到 45s。
- `server/tests/test_ssrf.py` 抽出 module 级 `allow_public_dns` fixture（monkeypatch `_is_url_pointing_to_internal -> False`）只在 `test_public_domain_ok` / `test_build_url_with_ssrf_check` / `test_build_url_strips_trailing_slash` / `test_build_url_with_subpath` 4 个公网域名测试上启用；新增 `test_allow_public_dns_fixture_does_not_bypass_literal_internal_ip` 双保险，确认 fixture 启用时 literal IP 仍走生产阻断；保留 `test_loopback_blocked` / `test_private_ip_blocked` / `test_link_local_blocked` / `test_cloud_metadata_blocked` / `test_build_url_rejects_internal` / `test_multicast_blocked` / `test_reserved_blocked` / `test_build_url_rejects_empty` / `test_empty_hostname` 不加 fixture。
- **未改**生产 `server/analyzer.py` / `server/core/utils.py` SSRF 逻辑；未改 `web-next/app/{dashboard,layout,providers}` / 后端认证 / Guardrails / 数据库 schema / 部署配置。Copilot fallback `API Key`/`Base URL`、triage `data-triage-status="investigating"`、DOM forbidden sentinel 断言全部保留。

**安全边界（保持不降级）**：

- `_is_ssrf_safe` 阻断列表（loopback / RFC1918 / link-local / metadata / multicast / reserved）不变；`build_chat_completions_url` fail-closed 不变。
- `allow_public_dns` fixture 仅 monkeypatch DNS helper，literal IP 仍走生产阻断（双保险测试已验证）。
- Demo Flow E2E 仍通过 NextAuth callback + httpOnly cookie 进入 Dashboard，未禁用任何 auth check；不写 token 进 storage / DOM。
- DOM forbidden sentinel 仍扫描 secret / stack / system prompt；Copilot fallback 与 triage 状态切换断言保留。

**验证矩阵（最终）**：

- `pytest server/tests/test_demo_flow_e2e.py --run-e2e` **1 passed**（`registered/demo/copilot/triage` 全部 True / `forbidden=None`）。
- `pytest server/tests/test_auth_session_e2e.py --run-e2e` **1 passed**。
- `pytest server/tests/test_incident_report_e2e.py --run-e2e` **1 passed**（`copy_status='已复制'`）。
- `pytest server/tests/test_ssrf.py` **14 passed**（13 原 + 1 新增保护测试，正常解开本地 DNS 环境失败）。
- `pytest server/tests` **333 passed, 4 skipped**（4 个 e2e 默认 skip，与 NEXT-01 基线一致）。
- `pytest server/tests/security/llm_guardrails` **139 passed**。
- 前端 `npm run typecheck` 0 错误 + `npm run build` 通过（`/dashboard` 43.4 kB / First Load JS 191 kB）。
- 运行日志：`docs/runs/2026-06-19-next-02-e2e-and-ssrf-quality-gate-hardening.md`。

### M3-09 案件状态单一事实源与 E2E 韧性（2026-06-19 已交付）

> 核心目的：消除 `IncidentSection` 与 `dashboard-client.tsx` 各自独立 `useIncidents()` 带来的案件详情 race，并让多条浏览器 E2E 连续运行不再依赖重启 dev server 解锁注册限流。

**已交付**：

- `web-next/hooks/useIncidents.ts` 导出 `IncidentsController = ReturnType<typeof useIncidents>` 类型；`IncidentSection` 改为接收 `incidents` props，内部不再创建第二个 `useIncidents()` 实例。
- `dashboard-client.tsx` 将父层 `incidentsCtx` 注入 `IncidentSection`，从告警创建案件后列表、selectedIncident、detail、复制/下载报告共享同一 state。
- 新增 `server/tests/e2e_helpers.py` 与 `server/tests/test_e2e_helpers.py`，复用注册、NextAuth callback、稳定账号 fallback 和 dashboard URL 验收；Auth/Demo/Incident 三条 E2E 删除重复 helper。
- 未改生产注册限流、后端 auth/token/cookie 语义、Guardrails、SSRF、DB schema。

**验证矩阵（最终）**：

- `pytest server/tests/test_e2e_helpers.py` **9 passed**。
- Auth/Demo/Incident 三条连续 E2E **3 passed in 20.83s**。
- `pytest server/tests` **342 passed, 4 skipped**。
- `pytest server/tests/security/llm_guardrails` **139 passed**。
- 前端 `npm run typecheck` 0 错误 + `npm run build` 通过（`/dashboard` 43.4 kB / First Load JS 191 kB）。
- 运行日志：`docs/runs/2026-06-19-m3-09-incident-state-and-e2e-resilience.md`。

### M3-10 Dashboard route composition（2026-06-19 已交付）

> 核心目的：在不改业务语义、不碰认证/Guardrails/SSRF/DB schema 的前提下，把 Dashboard route 渲染大文件收口成“父层 controller 编排 + section 组件 props 渲染 + 单一路由元数据”。

**已交付**：

- 新增 `web-next/constants/dashboardRoutes.ts`，统一 `overview / monitor / incidents / waf / ai / report` 的 label、index、description 和导航项。
- `SystemStatusBar.tsx` 改读 `DASHBOARD_NAV_ITEMS`，桌面与移动导航都包含 `incidents` 一等入口，并补 `data-testid` / `data-dashboard-route` / `aria-current`。
- 新增 `SectionHeading` / `DashboardFields` / `DashboardRows` 与 `web-next/components/dashboard/sections/*.tsx`；`dashboard-client.tsx` 从 840 行降到 406 行，只保留 hook/controller、handler 和 route 组合。
- 父层继续持有 `useAlerts` / `useConfig` / `useCopilot` / `useTerminal` / `useReport` / `useSiteHealth` / `useSecurityTimeline` / `useThreatConfirm` / `useIncidents`；section 组件只接收 props，未重新创建 `useIncidents()` / `useAlerts()` 等业务 hook。
- 新增 `server/tests/test_dashboard_route_sections_e2e.py`，先跑出目标 RED（缺少 `dashboard-section-stats` wrapper），再 GREEN 锁住六个 route tab 与核心 section wrapper。
- 未改认证/授权、Guardrails、SSRF、DB schema、后端 API、npm 依赖；未提交 `.coverage` / env / DB / 密钥。

**验证矩阵（最终）**：

- Dashboard route E2E **1 passed**。
- Auth/Demo/Incident/Dashboard 四条连续 E2E **4 passed in 32.46s**。
- `pytest server/tests` **342 passed, 5 skipped, 17 warnings**。
- `pytest server/tests/security/llm_guardrails` **139 passed, 17 warnings**。
- 前端 `npm run typecheck` 0 错误 + `npm run build` 通过（`/dashboard` 44 kB / First Load JS 191 kB）。
- 运行日志：`docs/runs/2026-06-19-m3-10-dashboard-route-composition.md`。


### M3-11 Dashboard section 响应式 QA 与可访问性收口（2026-06-19 已交付）

> 核心目的：在 M3-10 已拆分 Dashboard route section 后，用真实浏览器 E2E + 必要轻量 UI/可访问性修复，收口桌面/移动响应式、按钮文字溢出、icon-only 命名、键盘可达性和 DOM forbidden sentinel；不重做视觉设计，不迁移状态管理，不改后端 / 认证 / Guardrails / SSRF / DB schema。

**已交付**：

- 新增 `server/tests/test_dashboard_responsive_e2e.py`（默认 skip，需 `--run-e2e`）：parametrize 桌面 1366×900 与移动 390×844 viewport，覆盖六个 Dashboard route 切换、`aria-current=page`、核心 section wrapper、整页横向溢出（`scrollWidth ≤ clientWidth + 4`）、按钮文字溢出、icon-only 按钮 `title` / `aria-label`、键盘 Tab+Enter 切换路由、forbidden sentinel（`sk-...` / `AKIA...` / `ghp_...` / `Traceback` / `ignore previous instructions` / `system:` / `developer:` / `PRIVATE KEY` 等），失败留 screenshot，成功保留 desktop/mobile overview/incidents 共 4 张截图。
- RED 准确暴露 `SystemStatusBar.tsx` 主题切换按钮 `Moon` / `Sun` 与 `CopilotPanel.tsx` Copilot 提交按钮 `Send` 属于 icon-only 但缺 `title` / `aria-label`。
- GREEN：`SystemStatusBar.tsx` 主题切换按钮加 `title` + `aria-label`，并把已有 `title` 的 `Bell` / `LogOut` 按钮顺手补 `aria-label`；`CopilotPanel.tsx` 提交按钮加 `title` + `aria-label`。**未触动业务语义** —— 没有改 hook、没有改 state、没有改路由、没有改 prompts、没有改 props 结构。
- 截图证据：`docs/runs/artifacts/m3-11-dashboard-responsive/desktop-overview.png` / `desktop-incidents.png` / `mobile-overview.png` / `mobile-incidents.png` 共 168 KB（< 5 MB 限额，随 commit 提交）。

**真实验证**：

- `pytest server/tests/test_dashboard_responsive_e2e.py --run-e2e` **2 passed in 17.40s**（桌面 + 移动 viewport）。
- `pytest server/tests/test_dashboard_route_sections_e2e.py --run-e2e` **1 passed**。
- `pytest server/tests/test_auth_session_e2e.py server/tests/test_demo_flow_e2e.py server/tests/test_incident_report_e2e.py server/tests/test_dashboard_route_sections_e2e.py server/tests/test_dashboard_responsive_e2e.py --run-e2e` **6 passed in 46.64s**（重启 backend 清空 register rate limit 后；五条 E2E 实测连续通过）。
- `pytest server/tests` **342 passed, 7 skipped, 17 warnings**（5 个 e2e + 2 既有 skip）。
- `pytest server/tests/security/llm_guardrails` **139 passed**（0 回归）。
- 前端 `npm run typecheck` 0 错误 + `npm run build` 通过（`/dashboard` 44 kB / First Load JS 191 kB）。
- 运行日志：`docs/runs/2026-06-19-m3-11-dashboard-section-responsive-qa.md`。

**安全边界**：

- 未改 `server/services/auth_service.py` / `server/core/auth*` / `server/routers/auth*` / `server/security/**` / `server/core/state.py` / `server/core/config.py` / `server/analyzer.py` / `server/core/utils.py` / Alembic migration / DB schema。
- 未改后端 API contract / npm 依赖 / `REGISTER_RATE_LIMIT_MAX` 等限流配置。
- 未把 token 写进 `localStorage` / `sessionStorage` / DOM；E2E helper 仍走 httpOnly cookie path。
- 未提交 `.coverage` / `.env` / 真实 env / 数据库 / 密钥。

**改动文件（精确 stage）**：

- `server/tests/test_dashboard_responsive_e2e.py`（新增 RED→GREEN E2E）
- `web-next/components/dashboard/SystemStatusBar.tsx`（Moon/Sun/Bell/LogOut 按钮加 `aria-label`，主题切换补 `title`）
- `web-next/components/dashboard/CopilotPanel.tsx`（Send 按钮加 `title` + `aria-label`）
- `docs/runs/2026-06-19-m3-11-dashboard-section-responsive-qa.md`（本任务 run log）
- `docs/runs/artifacts/m3-11-dashboard-responsive/{desktop,mobile}-{overview,incidents}.png`（成功截图）
- `docs/agent/M3_11_DASHBOARD_SECTION_RESPONSIVE_QA_TASK.md`（任务文档入库）
- `docs/agent/UNATTENDED_LONG_TASKS.md`（M3-11 索引更新为"已交付"，下一条建议工单刷新）
- `PRODUCT.md` §2.2 新增第 20 项 M3-11 说明
- `docs/plans/M2_PRODUCT_ROADMAP.md`（本节）

**未解决问题**：无。

**当前不做**：重做视觉设计、迁移状态管理、新增后端 API、引入 PDF/DOCX、可视化埋点、performance budget 调整、bundle 拆分、Tailwind 主题重构。


### M3-12 Demo Flow E2E 稳定性收口（2026-06-19 已交付）

> 核心目的：把 M3-11 暴露的 Demo Flow Copilot fallback 串跑偶发 15s 超时收口为可诊断、可重复、不放宽断言的稳定 E2E。仅动测试层 + 文档；不改认证、Guardrails、SSRF、DB schema、后端 API、npm 依赖或 rate limit 常量。

**已交付**：

- 新增 `server/tests/e2e_copilot_helpers.py`（test-only diagnostic helper）：
  - `ARTIFACT_DIR=docs/runs/artifacts/m3-12-demo-flow-stability`。
  - `_SENSITIVE_PATTERNS` 正则脱敏 `sk-...` / `sk-proj-...` / `AKIA...` / `ghp_...` / `xox...`。
  - `wait_for_copilot_fallback_message`：用 `page.wait_for_function` 在 DOM 内扫描 `[data-testid="copilot-message"][data-role="assistant"]` 是否含 `API Key` 或 `Base URL`，默认 45s。
  - `install_network_diagnostics`：监听 `console`(error/warning)、`pageerror`、`response`，仅记录 `/api/backend/copilot/stream` / `/api/backend/alerts/demo` / `/api/backend/health` / `/api/auth/session` 的 method/path/status。
  - `save_copilot_failure_artifacts`：失败时 full-page screenshot + sanitized JSON。
- 修改 `server/tests/test_demo_flow_e2e.py`：把 30×500ms 手写轮询替换为 `wait_for_copilot_fallback_message(page, timeout_ms=45000)` + 失败 artifact 落盘 + `pytest.fail`，保留 `assert "API Key" in assistant_text or "Base URL" in assistant_text` 严格断言。
- 新增 `server/tests/test_demo_flow_stability_e2e.py`（默认 skip，需 `--run-e2e`）：同一 chromium context + page，连续两次 `trigger-demo-attack → analyze-current-alert → wait_for_copilot_fallback_message`，第二次 `attack-log-row` 数量 ≥ 2，整体跑完做 forbidden sentinel 扫描。

**真实验证**：

- 单条 Demo Flow E2E ×3 不重启 backend：`1 passed in 10.38s` / `10.53s` / `10.51s`（无放宽断言）。
- Stability ×2 不重启 backend：`1 passed in 10.28s` / `6.63s`。
- 六组关键 E2E 连续 `pytest server/tests/test_auth_session_e2e.py test_demo_flow_e2e.py test_incident_report_e2e.py test_dashboard_route_sections_e2e.py test_dashboard_responsive_e2e.py test_demo_flow_stability_e2e.py --run-e2e` **7 passed in 58.27s**（Auth 1 + Demo 1 + Incident 1 + Route 1 + Responsive 2 + Stability 1）。
- `pytest server/tests` **342 passed, 8 skipped, 17 warnings**（baseline + stability 默认 skip）。
- `pytest server/tests/security/llm_guardrails` **139 passed**（0 回归）。
- 前端 `npm run typecheck` 0 错误 + `npm run build` 通过（`/dashboard` 44 kB / First Load JS 191 kB 不变）。
- 运行日志：`docs/runs/2026-06-19-m3-12-demo-flow-e2e-stability.md`。

**根因排查**：

- 本机环境 `curl https://api.openai.com` exit 28（5s 超时不可达）。
- Fresh backend 时 `GuardrailEngine.check_input` 1.5s rail timeout 优先于 `OpenAIModerationClient` 5s ConnectTimeout 触发 → return None → 放行 Copilot → 进入 `stream_user_chat_completion` 的"无 LLM key"分支返回 `请先在配置页设置可用的 API Key 与 Base URL`。
- 长时运行 backend 中 moderation httpx pool 退化后 < 1.5s 立即抛 exc → fail-closed 拦截 Copilot → 出现 `moderation_unavailable` 文案。本任务在 fresh backend 状态下行为正确，**未动 Guardrails 代码**。建议作为另一条独立工单（owner 单独授权）补 client 健康探测 + 周期性重建。

**安全边界**：

- 未改 `server/services/auth_service.py` / `server/core/auth*` / `server/routers/auth*` / `server/security/**` / `server/core/state.py` / `server/core/config.py` / `server/analyzer.py` / `server/core/utils.py` / Alembic migration / DB schema。
- 未改后端 API contract / npm 依赖 / `REGISTER_RATE_LIMIT_*` / `COPILOT_RATE_LIMIT_*` 限流配置。
- 未把 token 写进 `localStorage` / `sessionStorage` / DOM；helper 不打印 cookie / token / password / API key / 全量响应体。
- 未提交 `.coverage` / `.env` / 真实 env / 数据库 / 密钥；artifact 目录成功路径不留文件。

**改动文件（精确 stage）**：

- `server/tests/e2e_copilot_helpers.py`（新增）
- `server/tests/test_demo_flow_e2e.py`（接入条件等待 + 失败 artifact）
- `server/tests/test_demo_flow_stability_e2e.py`（新增）
- `docs/runs/2026-06-19-m3-12-demo-flow-e2e-stability.md`（本任务 run log）
- `docs/agent/M3_12_DEMO_FLOW_E2E_STABILITY_TASK.md`（任务文档入库）
- `docs/agent/UNATTENDED_LONG_TASKS.md`（M3-12 索引更新为"已交付"，下一条建议工单刷新）
- `PRODUCT.md` §2.2 新增第 21 项 M3-12 说明
- `docs/plans/M2_PRODUCT_ROADMAP.md`（本节）

**未解决问题**：长时运行的 dev backend 中 OpenAIModerationClient httpx pool 偶发退化、moderation `check` 在 < 1.5s 内抛 exc → rail timeout 来不及触发 → fail-closed 拦截 Copilot。在 fresh backend 状态下行为正确，本任务不修。该问题需 owner 单独授权动 `server/security/llm_guardrails/**`，列入后续 Guardrails 健康监控候选工单。

**当前不做**：修改 Guardrails 代码（包括 moderation client 健康监控、`_init_moderation` 空 key 检测、rail timeout 调整），改 rate limit 常量，改后端 API contract，改前端业务 hook / state / 路由。


### M3-13 Dashboard 移动 viewport 视觉 QA 收口（2026-06-19 已交付）

> 核心目的：基于 M3-11 `mobile-overview.png` / `mobile-incidents.png` 截图证据，用真实浏览器 E2E 锁住移动端 stats 卡片密度、section 间距、移动 nav active tab 可见性、整页横向溢出、forbidden sentinel 与 `N` 浮层 DOM 来源；只做轻量 Tailwind/layout class 修复，不重做视觉设计，不碰认证、Guardrails、SSRF、DB schema、后端 API、npm 依赖或 rate limit 常量。

**已交付**：

- 新增 `server/tests/test_dashboard_mobile_visual_e2e.py`（默认 skip，需 `--run-e2e`）：覆盖 390×844 与 430×932 两个 viewport，分别检查 `overview` / `incidents` route。
- E2E 断言 active mobile nav tab 在横向滚动容器可见区域、整页 `scrollWidth <= clientWidth + 4`、stats grid 高度不超过 viewport 42%、单卡高度不超过 160px、stats 到 briefing section 间距不超过 64px、DOM forbidden sentinel 为 `None`、形似圆形 `N` 的应用 DOM 候选 count 为 0。
- 成功保存 4 张 full-page 截图：`docs/runs/artifacts/m3-13-dashboard-mobile-visual/mobile-390-overview.png` / `mobile-390-incidents.png` / `mobile-430-overview.png` / `mobile-430-incidents.png`，合计约 913 KB。
- `StatsCards.tsx` 轻量收口移动端 padding、最小高度、header 间距、label tracking 与 value 换行，并给 grid 增加 `data-testid="stats-card-grid"`。
- `SystemStatusBar.tsx` 收紧移动 nav gap/tracking，并显式使用 `overflow-x-auto overscroll-x-contain`，提升 active tab 可见性。
- `DashboardBriefingSection.tsx` / `DashboardIncidentWorkspaceSection.tsx` 将 section 顶距从 `mt-14` 调整为 `mt-8 sm:mt-14`。
- 截图中仍可见左下圆形 `N` 浮层，但 DOM candidates 为 0，判定为浏览器/外部 overlay，不修改应用代码。

**真实验证**：

- `pytest server/tests/test_dashboard_mobile_visual_e2e.py --run-e2e` **1 passed in 13.82s**。
- `pytest server/tests/test_dashboard_responsive_e2e.py --run-e2e` **2 passed in 20.08s**。
- `pytest server/tests/test_demo_flow_stability_e2e.py --run-e2e` **1 passed in 6.32s**。
- 七组关键 E2E 连续 `pytest server/tests/test_auth_session_e2e.py test_demo_flow_e2e.py test_incident_report_e2e.py test_dashboard_route_sections_e2e.py test_dashboard_responsive_e2e.py test_demo_flow_stability_e2e.py test_dashboard_mobile_visual_e2e.py --run-e2e` **8 passed in 69.21s**。
- `pytest server/tests` **342 passed, 9 skipped, 17 warnings**。
- `pytest server/tests/security/llm_guardrails` **139 passed, 17 warnings**。
- 前端 typecheck 等价命令通过（本机 npm shim 损坏，使用 `next.cmd typegen` + `tsc.cmd --noEmit`）；`next.cmd build` 通过（`/dashboard` 44.1 kB / First Load JS 191 kB）。
- 运行日志：`docs/runs/2026-06-19-m3-13-dashboard-mobile-visual-qa.md`。

**安全边界**：

- 未改 `server/services/auth_service.py` / `server/core/auth*` / `server/routers/auth*` / `server/security/**` / `server/core/state.py` / `server/core/config.py` / `server/analyzer.py` / `server/core/utils.py` / Alembic migration / DB schema。
- 未改后端 API contract、npm 依赖、`REGISTER_RATE_LIMIT_*`、`COPILOT_RATE_LIMIT_*`。
- 未把 token 写进 `localStorage` / `sessionStorage` / DOM。
- 未提交 `.coverage` / `.env` / 真实 env / 数据库 / 密钥。

**改动文件（精确 stage）**：

- `server/tests/test_dashboard_mobile_visual_e2e.py`（新增移动视觉 E2E）
- `web-next/components/dashboard/StatsCards.tsx`（移动 stats 密度与测试定位）
- `web-next/components/dashboard/SystemStatusBar.tsx`（移动 nav active tab 可见性）
- `web-next/components/dashboard/sections/DashboardBriefingSection.tsx`（移动 section 间距）
- `web-next/components/dashboard/sections/DashboardIncidentWorkspaceSection.tsx`（移动 section 间距）
- `docs/runs/2026-06-19-m3-13-dashboard-mobile-visual-qa.md`（本任务 run log）
- `docs/runs/artifacts/m3-13-dashboard-mobile-visual/*.png`（成功截图）
- `docs/agent/M3_13_DASHBOARD_MOBILE_VISUAL_QA_TASK.md`（任务文档入库）
- `docs/agent/UNATTENDED_LONG_TASKS.md`（M3-13 索引更新为已交付）
- `PRODUCT.md` §2.2 新增第 22 项 M3-13 说明
- `docs/plans/M2_PRODUCT_ROADMAP.md`（本节）

**未解决问题**：无阻塞。`N` 浮层不是应用 DOM；本任务仅用 E2E 防止应用 DOM 引入同类浮层。

**当前不做**：重做视觉设计、改 Dashboard 业务 hook/state/prompt、改认证/授权、改 Guardrails、改 SSRF、改 DB schema、改后端 API、改 npm 依赖、改 rate limit 常量。

### M3-14 案件报告预览 UX 收口（2026-06-20 已交付）

> 核心目的：基于 M3-07/M3-08 已交付的 Markdown 报告复制/下载能力，在 Dashboard 案件详情内补齐可见、可截图、可回归的内联报告预览体验；只消费后端已脱敏 report API，不改认证、Guardrails、SSRF、DB schema、后端 report API、npm 依赖或 rate limit。

**已交付**：

- 新增 `web-next/components/dashboard/IncidentReportPreview.tsx`，展示报告文件名、生成时间、告警/事件/脱敏/截断 meta、脱敏/截断说明，以及后端 markdown 的安全预览片段。
- `IncidentDetailPanel.tsx` 新增 `incident-preview-report` 按钮、loading/error/close 状态、Escape 关闭、切换案件清空预览；复制/下载仍即时调用 `onLoadReport()` 拉取完整脱敏报告，不复用截断预览 state。
- 预览正文不引入 markdown 依赖，不使用 `dangerouslySetInnerHTML` / `innerHTML`，按行渲染标题、表格、列表与段落；组件 state 只保留截断后的 `previewMarkdown`，不写 `localStorage` / `sessionStorage`。
- 新增 `server/tests/test_incident_report_preview_e2e.py`（默认 skip，需 `--run-e2e`），覆盖登录、Demo 告警、创建案件、预览报告、文件名/meta/body、桌面/移动截图、复制/下载报告、Escape/关闭按钮和 DOM/markdown forbidden sentinel。
- 成功保存 2 张 full-page 截图：`docs/runs/artifacts/m3-14-incident-report-preview/incident-report-preview-desktop.png` / `incident-report-preview-mobile.png`。

**真实验证**：

- 新增 preview E2E：**1 passed in 10.34s**。
- 既有 incident report E2E：**1 passed in 6.12s**。
- mobile visual E2E：**1 passed in 12.09s**。
- 八组关键 E2E（Auth / Demo / Incident report / Dashboard route / Responsive desktop+mobile / Demo stability / Mobile visual / Incident report preview）：**9 passed in 77.63s**。
- 后端全量：**342 passed, 10 skipped, 17 warnings in 85.57s**。
- Guardrails 专项：**139 passed, 17 warnings in 19.48s**。
- 前端 typecheck 等价命令通过（`next.cmd typegen` + `tsc.cmd --noEmit`）；`next.cmd build` 通过（`/dashboard` 45.7 kB / First Load JS 193 kB）。
- 运行日志：`docs/runs/2026-06-19-m3-14-incident-report-preview-ux.md`。

**安全边界**：

- 未改 `server/services/auth_service.py` / `server/core/auth*` / `server/routers/auth*` / `server/security/**` / SSRF / Alembic migration / DB schema。
- 未改后端 report API contract、`server/services/incident_report_service.py`、npm 依赖、`REGISTER_RATE_LIMIT_*`、`COPILOT_RATE_LIMIT_*`。
- 未把报告 markdown 写入 `localStorage` / `sessionStorage`；未使用 `dangerouslySetInnerHTML` / `innerHTML` 渲染报告。
- 未提交 `.coverage` / `.env` / 真实 env / 数据库 / 密钥；本地 dev server 日志不纳入提交。

**改动文件（精确 stage）**：

- `server/tests/test_incident_report_preview_e2e.py`（新增报告预览浏览器 E2E）
- `web-next/components/dashboard/IncidentReportPreview.tsx`（新增内联预览组件）
- `web-next/components/dashboard/IncidentDetailPanel.tsx`（接入预览按钮与状态）
- `docs/runs/2026-06-19-m3-14-incident-report-preview-ux.md`（本任务 run log）
- `docs/runs/artifacts/m3-14-incident-report-preview/*.png`（成功截图）
- `docs/agent/M3_14_INCIDENT_REPORT_PREVIEW_UX_TASK.md`（任务文档入库）
- `docs/agent/UNATTENDED_LONG_TASKS.md`（M3-14 索引更新为已交付，下一条建议刷新）
- `PRODUCT.md` §2.2 新增第 23 项 M3-14 说明
- `docs/plans/M2_PRODUCT_ROADMAP.md`（本节）

**未解决问题**：无本任务阻塞。无真实 OpenAI key / 外网 moderation 快速失败时，Demo Copilot fallback E2E 需要隔离的本地 no-key 测试环境验证；这属于 Guardrails moderation client 健康监控后续独立授权工单，不在本次预览 UX 范围内。

**当前不做**：改 Guardrails fail-closed 策略、改认证/授权、改 SSRF、改 DB schema、改后端 report API、改 npm 依赖、改 rate limit 常量、持久化报告文件、PDF/DOCX/HTML 渲染。

### M3-15 SOC 时间线筛选与详情展开 UX 收口（2026-06-20 已交付）

> 核心目的：基于已交付的 `GET /logs/security-timeline` 和 `SecurityTimelinePanel`，把审计时间线从只读列表升级为可筛选、可展开、可复制脱敏摘要、可截图验收的 SOC 运营证据面板；只改前端 timeline UX、E2E、截图和文档，不改认证、Guardrails、SSRF、DB schema、后端 timeline API、npm 依赖或 rate limit。

**已交付**：

- `SecurityTimelinePanel.tsx` 新增 `全部 / Demo / Copilot / 护栏 / 系统` 筛选按钮、筛选计数和空筛选态，基于现有 timeline `category` 做前端分类，不新增后端参数。
- 单条事件可展开详情，展示时间、来源、类别、状态、脱敏摘要和安全说明；支持 Escape 收起，筛选切换会收起不再可见的详情。
- 新增脱敏 SOC 摘要复制按钮，复制内容只由当前可见字段拼接，clipboard 不可用时给出降级状态；不写 `localStorage` / `sessionStorage`，不使用 `dangerouslySetInnerHTML` / `innerHTML`。
- 新增 `server/tests/test_security_timeline_drilldown_e2e.py`（默认 skip，需 `--run-e2e`），覆盖登录、Demo 事件进入 SOC 时间线、筛选状态、展开详情、复制摘要、Escape、桌面/移动截图和 DOM/copy forbidden sentinel。
- 成功保存 2 张 full-page 截图：`docs/runs/artifacts/m3-15-soc-timeline-drilldown/security-timeline-desktop.png` / `security-timeline-mobile.png`。

**真实验证**：

- 新增 timeline drilldown E2E：**1 passed in 18.51s**。
- 后端 timeline 契约测试：**12 passed in 2.88s**。
- Dashboard responsive E2E：**2 passed in 30.06s**。
- 九组关键 E2E（Auth / Demo / Incident report / Dashboard route / Responsive desktop+mobile / Demo stability / Mobile visual / Incident report preview / Security timeline drilldown）：**10 passed in 144.89s**。
- 后端全量：**342 passed, 11 skipped, 17 warnings in 129.68s**（首次固定 `.tmp\pytest` 目录复跑遇到 Windows `PermissionError`，改用本次专属临时目录后通过；未改后端代码）。
- Guardrails 专项：**139 passed, 17 warnings in 21.84s**。
- 前端 typecheck 等价命令通过（`next.cmd typegen` + `tsc.cmd --noEmit`）；`next.cmd build` 通过（`/dashboard` 47.1 kB / First Load JS 194 kB）。
- 运行日志：`docs/runs/2026-06-20-m3-15-soc-timeline-drilldown-filter-ux.md`。

**安全边界**：

- 未改 `server/services/auth_service.py` / `server/core/auth*` / `server/routers/auth*` / `server/security/**` / SSRF / Alembic migration / DB schema。
- 未改后端 timeline API contract、`server/routers/logs_router.py`、npm 依赖、`REGISTER_RATE_LIMIT_*`、`COPILOT_RATE_LIMIT_*`。
- 未把 timeline 或复制摘要写入 `localStorage` / `sessionStorage`；未使用 `dangerouslySetInnerHTML` / `innerHTML` 渲染详情。
- 未提交 `.coverage` / `.env` / 真实 env / 数据库 / 密钥；本地 dev server 日志不纳入提交。

**改动文件（精确 stage）**：

- `server/tests/test_security_timeline_drilldown_e2e.py`（新增 SOC 时间线浏览器 E2E）
- `web-next/components/dashboard/SecurityTimelinePanel.tsx`（新增筛选、详情展开与复制摘要 UX）
- `docs/runs/2026-06-20-m3-15-soc-timeline-drilldown-filter-ux.md`（本任务 run log）
- `docs/runs/artifacts/m3-15-soc-timeline-drilldown/*.png`（成功截图）
- `docs/agent/M3_15_SOC_TIMELINE_DRILLDOWN_FILTER_UX_TASK.md`（任务文档入库）
- `docs/agent/UNATTENDED_LONG_TASKS.md`（M3-15 索引更新为已交付，下一条建议刷新）
- `PRODUCT.md` §2.2 新增第 24 项 M3-15 说明
- `docs/plans/M2_PRODUCT_ROADMAP.md`（本节）

**未解决问题**：无本任务阻塞。九组关键 E2E 首轮在长时运行 dev backend 上触发 register/login rate limit，最终用 fresh 本地 E2E backend/frontend 和稳定测试账号完成真实浏览器验证；未改 rate limit 常量或认证逻辑。

**当前不做**：改 Guardrails fail-closed 策略、改认证/授权、改 SSRF、改 DB schema、改后端 timeline API、改 npm 依赖、改 rate limit 常量、持久化 timeline 快照、引入外部渲染库或可视化库。

### M3-16 Dashboard Operational Runbook / Health Checklist UX 收口（2026-06-21 已交付）

> 核心目的：在不修改认证/授权、Guardrails、SSRF、DB schema、后端 API、npm 依赖或生产 rate limit 的前提下，把 Dashboard 系统状态区补齐为可自助排障的 operational runbook / health checklist 面板；只改前端 Dashboard runbook UX、E2E、截图和文档。

**已交付**：

- 新增 `web-next/components/dashboard/OperationalRunbookPanel.tsx`，在概览 route 与 `WAF 管理` route 的 `dashboard-section-system-status` 内展示 `Operational Runbook / Health Checklist`。
- 面板包含六项检查：Backend health、Next API proxy、Login session、Demo readiness、E2E readiness、Env security check；状态 tone 限定为 `ok / warn / manual / blocked`。
- 登录身份只展示脱敏邮箱（例如 `e***@example.com`）；目标站点 URL 仅显示安全 origin 或通用文案，不展示 query。
- 五条关键命令仅作为人工执行清单展示：后端全量、Guardrails、前端 typecheck、前端 build、`scripts/check_env_security.py`；面板不在浏览器执行 PowerShell/Python，也不读取真实 `.env`。
- 复制摘要按钮 `runbook-copy-summary` 写入安全诊断文本，包含 timestamp、health、proxy probe、masked session、item statuses 和 recommended commands；剪贴板不可用时给出降级状态。
- `DashboardSystemStatusRouteSection.tsx` 只新增 `userEmail` prop 并挂载 runbook；`dashboard-client.tsx` 只传递现有 `userEmail`，未调整认证 hook 或后端 API。
- 新增 `server/tests/test_dashboard_operational_runbook_e2e.py`（默认 skip，需 `--run-e2e`），真实浏览器覆盖 WAF route 面板、六项 checklist、五条命令、复制摘要、桌面/移动截图和 DOM/copy forbidden sentinel。
- `server/tests/e2e_helpers.py` 增强测试侧稳定账号 env 复用：显式设置 `E2E_<PREFIX>_EMAIL` 且账号可登录时优先复用，避免长串 E2E 被本地 register rate limit 误挡；不改后端限流常量或认证生产代码。
- 成功保存 2 张 full-page 截图：`docs/runs/artifacts/m3-16-dashboard-operational-runbook/operational-runbook-desktop.png` / `operational-runbook-mobile.png`。

**真实验证**：

- 新增 runbook E2E：**1 passed in 3.67s**。
- Dashboard route + responsive E2E：**3 passed in 25.42s**。
- 关键 E2E 串跑（Auth / Demo / Incident report / Dashboard route / Responsive desktop+mobile / Demo stability / Mobile visual / Incident report preview / Security timeline drilldown / Dashboard operational runbook）：**11 passed in 80.00s**。
- 后端 timeline 专项：**12 passed in 1.03s**。
- 后端全量：**344 passed, 12 skipped, 17 warnings in 85.19s**。
- Guardrails 专项：**139 passed, 17 warnings in 19.51s**。
- 前端 `npm run typecheck` 通过；`npm run build` 通过（`/dashboard` 49.2 kB / First Load JS 197 kB）。
- 运行日志：`docs/runs/2026-06-21-m3-16-dashboard-operational-runbook-health-checklist-ux.md`。

**安全边界**：

- 未改 `server/services/auth_service.py` / `server/core/auth*` / `server/routers/auth*` / `server/security/**` / SSRF / Alembic migration / DB schema。
- 未改后端 API contract、`scripts/check_env_security.py` 行为、npm 依赖、`REGISTER_RATE_LIMIT_*`、`COPILOT_RATE_LIMIT_*`。
- 未把 runbook 摘要、命令或会话信息写入 `localStorage` / `sessionStorage`；未使用 `dangerouslySetInnerHTML` / `innerHTML`。
- 未提交 `.coverage` / `.env` / 真实 env / 数据库 / 密钥；本地 dev server 日志不纳入提交。

**改动文件（精确 stage）**：

- `server/tests/test_dashboard_operational_runbook_e2e.py`（新增 runbook 浏览器 E2E）
- `server/tests/e2e_helpers.py` / `server/tests/test_e2e_helpers.py`（测试侧稳定账号 env 复用与单测）
- `web-next/components/dashboard/OperationalRunbookPanel.tsx`（新增 runbook/checklist 面板）
- `web-next/components/dashboard/sections/DashboardSystemStatusRouteSection.tsx`（接入面板）
- `web-next/app/dashboard/dashboard-client.tsx`（传递现有 `userEmail`）
- `docs/runs/2026-06-21-m3-16-dashboard-operational-runbook-health-checklist-ux.md`（本任务 run log）
- `docs/runs/artifacts/m3-16-dashboard-operational-runbook/*.png`（成功截图）
- `docs/agent/M3_16_DASHBOARD_OPERATIONAL_RUNBOOK_HEALTH_CHECKLIST_UX_TASK.md`（任务文档入库）
- `docs/agent/UNATTENDED_LONG_TASKS.md`（M3-16 索引更新为已交付，下一条建议刷新）
- `PRODUCT.md` §2.2 新增第 25 项 M3-16 说明
- `docs/plans/M2_PRODUCT_ROADMAP.md`（本节）

**未解决问题**：无本任务阻塞。完整关键 E2E 首轮暴露现有 helper 在长串里每测先注册唯一账号会耗尽本地注册限流；本次仅在测试 helper 中增加显式稳定账号 env 优先路径，生产认证和后端限流保持不变。

**当前不做**：改认证/授权、改 Guardrails fail-closed 策略、改 SSRF、改 DB schema、改后端 API、改 npm 依赖、改生产 rate limit 常量、在浏览器执行运维命令、读取真实 env、引入外部渲染库。


> 核心目的：把 M3-04 / M3-05 run log 里反复标记为"预存失败"的 3 大测试债务收口为可重复、可解释、可验证的质量门；不允许通过 skip / xfail / 删除断言 / 弱化 Guardrails fail-closed / 放宽 SSRF 生产策略来制造绿色。

**3 大失败面全部清零**：

1. **Demo Flow fallback（1 个）** — `test_demo_alert_can_drive_copilot_fallback` 因 L4 moderation `moderation_unavailable` fail-closed 阻断（无真实 OpenAI key）。**修复**：在 `test_demo_flow.py` 内 stub `GuardrailEngine.instance().check_input` 为 allow（与 `test_copilot_contract._stub_guardrails` 同模式）。该测试只验证 demo alert → copilot → no-key fallback 路径，不验证 Guardrails 决策。

2. **Guardrails Colang corpus（9 个 benign 失败）** — `test_colang_flows.py::test_benign_not_blocked[sample0..8]` 因 L4 moderation client 真实发请求 → httpx `ConnectError` / `LocalProtocolError` → fail-closed `moderation_unavailable` → benign 被错误阻断。**修复**：在 `server/tests/security/llm_guardrails/conftest.py` 新增 `_safe_moderation_for_colang` autouse fixture（仅对 `test_colang_flows.py` 生效），把 `OpenAIModerationClient.check` 替换为 pass-through fake（用 `staticmethod` 包装规避 self 绑定 TypeError，否则 fail-closed 会包装 `TypeError` → `moderation_unavailable (L4: fail-closed, exc=TypeError)`）。同步修复同 bug 的 `mock_openai_moderation_pass/block/fail` fixtures。生产 `core.GuardrailEngine._run_rails` fail-closed **不变** —— 这里只动测试夹具。

3. **SSRF 防护** — M3-04 记录有 3 个 SSRF 预存失败；实测 `server/tests/test_ssrf.py` 13/13 已稳定通过（M3-04 记录已过时，monkeypatch 命中 `_is_ssrf_safe` → `_is_url_pointing_to_internal` 内部导入路径）。**无修复需要**。

**安全边界（保持不降级）**：

- `GuardrailEngine._run_rails` L1 → L4 → L2/L3 顺序与 fail-closed 策略不变。
- `check_output` P2-D 工具调用白名单 / `unauthorised_tool_call` 阻断不变。
- `_l1_check` SSE error 净化（只暴露 category，不暴露 regex / stack trace）不变。
- `audit log` 脱敏（`Log(action=...)` 不写 secret / API key / 完整 note / payload / system prompt）不变。
- `analyzer._is_ssrf_safe` 阻断列表（loopback / RFC1918 / link-local / metadata / multicast / reserved）不变。
- `build_chat_completions_url` 仍对 base URL 做 SSRF 检查不变。
- 所有测试 stub 仅存在于 `server/tests/`，未触碰 `server/security/**` 任何生产代码。

**验证矩阵（最终）**：

- `pytest server/tests` 默认基线：**318 passed, 2 skipped**（0 失败，83.68s）。
- `pytest server/tests/security/llm_guardrails` 专项：**139 passed**。
- `pytest server/tests/test_demo_flow.py`：**5 passed**。
- `pytest server/tests/test_ssrf.py`：**13 passed**。
- M3-03 / M3-04 / M3-05 回归矩阵（copilot_contract + copilot_incident_contract + incidents + incident_persistence + alert_triage + alert_triage_persistence + demo_flow + ssrf）：**72 passed**。
- 前端 `web-next`：`npm run typecheck` 0 错误；`npm run build` 通过（`/dashboard` 42.9 kB / First Load JS 190 kB）。

**改动文件（精确 stage）**：

- `server/tests/test_demo_flow.py`（GuardrailEngine.instance stub）
- `server/tests/security/llm_guardrails/conftest.py`（autouse `_safe_moderation_for_colang` + 修 `mock_openai_moderation_*` self-bug）
- `PRODUCT.md` §2.2 第 13 项 M3-06 说明
- `docs/agent/UNATTENDED_LONG_TASKS.md` M3-06 索引更新为"已交付 + 2026-06-18 落点"
- `docs/runs/2026-06-18-m3-06-test-and-security-quality-gate-closure.md`（本任务 run log）

**未解决问题**：无。

**当前不做**：CI 自动化 fail-closed 复测、Provider 多区域 key 故障演练、SSRF 真实公网域名 mock 库扩充。
- 运行日志：`docs/runs/2026-06-18-m3-06-test-and-security-quality-gate-closure.md`。

### M3-07 案件证据报告导出（2026-06-18 已交付）

> 核心目的：把 M3-04 / M3-05 已建立的"案件 + 告警 + 时间线 + Copilot 上下文"能力，收束成可复制、可下载、可审计、可脱敏的 SOC 案件证据报告；不依赖 PDF / DOCX / 外部渲染，不调用 LLM，不导出完整 payload / note / secret / system prompt / stack trace。

**新端点契约**：

- `GET /incidents/{incident_id}/report?format=json`（默认）：返回 `{status, incident_id, filename, markdown, meta}` envelope，meta 含 `generated_at` / `alert_count` / `included_alerts` / `event_count` / `included_events` / `redaction_count` / `truncated`。
- `GET /incidents/{incident_id}/report?format=markdown`：返回 `text/markdown; charset=utf-8` body + `Content-Disposition: attachment; filename=incident-<incident_id>-report.md`。
- 错误：401 未登录 / 404 非 owner 或不存在（不区分）/ 422 invalid format / 503 DB 失败。
- filename 只由 `incident_id` 派生（防注入 + 防 title 泄密），非法字符降级为 `_`。

**报告内容规范**：

- 固定结构：`# 案件证据报告` + 4 段（案件摘要 / 关联告警 / 案件时间线 / 安全与脱敏说明）。
- 截断限制：summary 1000 / alert summary 240 / payload preview 180 / event detail 240 / event note preview 160 / linked_alerts ≤ 20 / events ≤ 50（newest-first）。
- 脱敏 sentinel：复用 `server.routers.logs_router._SENTINEL_PATTERNS`（sk- / sk-proj- / AKIA / ghp_ / xox[baprs]- / PRIVATE KEY / Traceback / ignore previous instructions / disregard system prompt / forget instructions / system:）并新增 `developer:` 触发。
- 报告正文**禁止**包含：完整 raw payload（只放 `payload_length` + preview）、完整 `IncidentEvent.note`（只放 `note_length` + preview）、fake secret、system prompt、stack trace、Guardrails regex。

**后端实现要点**：

- `server/services/incident_report_service.py`（新增）：纯函数 `sanitize_report_text` / `build_incident_report`；不依赖 ORM / DB；`build_incident_report` 接收 `incident_service.get_incident_detail` 返回的 dict 派生 `{filename, markdown, meta}`。
- `server/routers/incidents_router.py` 增加 `GET /incidents/{incident_id}/report?format=json|markdown`：复用 owner 隔离（`get_incident_detail`），非 owner / 不存在统一 404；format 校验走白名单 `{"json", "markdown"}`；audit `Log(action="incident_report_export")` 仅在成功生成时写，detail 只含 `incident_id / format / alert_count / included_alerts / event_count / included_events / redaction_count`，**不**含 title / summary / payload / note / markdown 全文。
- 审计写入失败仅 `logger.warning`，不阻断主请求；非 owner / 不存在 / invalid format / DB 失败均**不**写 success Log。
- `event_limit` 默认 100（让 detail 拉全量事件以满足 `event_count >= 60` 的大案件场景，再由 report service 截断到 50）。

**前端实现要点**：

- `web-next/types/incident.ts` 新增 `IncidentReportMeta` / `IncidentReportResponse` 类型。
- `web-next/hooks/useIncidents.ts` 新增 `loadIncidentReport(incidentId)` helper：不保存 markdown 到 React 长期 state，按按钮请求；返回 `{ok, incidentId, filename, markdown, meta, error}`。
- `web-next/components/dashboard/IncidentDetailPanel.tsx` 在事件时间线工具区增加 `复制报告` / `下载报告` 两个紧凑按钮（`Clipboard` / `ClipboardCheck` / `Download` / `Loader2` 图标；`data-testid="incident-copy-report"` / `incident-download-report"` / `incident-report-status"`），短小状态文案 `生成中 / 已复制 / 已下载 / 报告生成失败`。
- 复制：`navigator.clipboard.writeText(markdown)`；不可用时降级提示 `复制失败`，不崩溃。
- 下载：`Blob([markdown], { type: "text/markdown;charset=utf-8" })` + `URL.createObjectURL` + `anchor.click()` + `URL.revokeObjectURL`，文件名用后端 `filename`。
- `web-next/components/dashboard/IncidentSection.tsx` 注入 `onLoadReport={(id) => incidents.loadIncidentReport(id)}` 到 `IncidentDetailPanel`。
- 视觉：与现有 `用 AI 分析案件` 按钮并排；不挤压时间线标题；不新增大卡片；按钮内文字不溢出。
- **不在前端拼报告 / 不读 payload / note 全文**：前端只消费后端脱敏后的 markdown。

**安全边界（保持不降级）**：

- `server/security/**` 未触碰；Guardrails / LLM provider / MCP 路径全部未修改。
- audit `Log(action="incident_report_export")` 不含 title / summary / payload / note / markdown 全文（已用 regex + 反向断言锁定）。
- filename 只由 incident_id 派生，含非法字符（`; / " \n`）时降级为 `_`；测试 `test_report_filename_derived_only_from_incident_id` 锁定。
- 失败错误不含 stack trace；用户可见 detail 走中文。
- 复用 `logs_router._SENTINEL_PATTERNS` 脱敏集合 + `developer:` 触发，未引入新 sentinel 漂移。
- 不调用 LLM 生成报告，不依赖真实 API key；不新增数据库表 / Alembic migration / env var。

**验证矩阵（最终）**：

- `pytest server/tests/test_incident_report_export.py`：**14 passed**（含 401 / 404 / 422 / json envelope / markdown body / payload 截断 / note 截断 / 脱敏 sentinel / audit 脱敏 / 大案件截断 / filename 派生）。
- `pytest server/tests/test_incidents.py test_incident_persistence.py test_security_timeline.py`：0 回归。
- `pytest server/tests` 全量基线：**332 passed, 2 skipped**（M3-06 baseline 318 + M3-07 新增 14；0 失败）。
- `pytest server/tests/security/llm_guardrails` 专项：**139 passed**（与 M3-06 一致，0 回归）。
- 前端 `web-next`：`npm run typecheck` 0 错误；`npm run build` 通过（`/dashboard` 43.7 kB / First Load JS 191 kB）。

**改动文件（精确 stage）**：

- `server/services/incident_report_service.py`（新增纯函数 service）
- `server/routers/incidents_router.py`（新增 `GET /incidents/{id}/report` 端点 + audit helper）
- `server/tests/test_incident_report_export.py`（新增 14 个 RED→GREEN 测试）
- `web-next/types/incident.ts`（新增 `IncidentReportMeta` / `IncidentReportResponse`）
- `web-next/hooks/useIncidents.ts`（新增 `loadIncidentReport` helper）
- `web-next/components/dashboard/IncidentDetailPanel.tsx`（事件时间线工具区加 `复制报告` / `下载报告` 按钮 + `onLoadReport` prop + 状态机）
- `web-next/components/dashboard/IncidentSection.tsx`（注入 `onLoadReport` 到 `IncidentDetailPanel`）
- `PRODUCT.md` §2.2 第 14 项 M3-07 说明 + §5 M3-07 验收
- `docs/agent/UNATTENDED_LONG_TASKS.md` M3-07 索引更新为"已交付 + 2026-06-18 落点"
- `docs/runs/2026-06-18-m3-07-incident-evidence-report-export.md`（本任务 run log）

**未解决问题**：无。

**当前不做**：PDF / DOCX / HTML 渲染、批量案件导出、跨用户共享、签名审批、SLA、工单系统、Jira / Slack 集成、报告文件持久化、外部存储、报告正文 LLM 摘要、案件模板。
- 运行日志：`docs/runs/2026-06-18-m3-07-incident-evidence-report-export.md`。
