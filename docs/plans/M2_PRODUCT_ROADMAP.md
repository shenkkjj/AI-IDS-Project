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

### M3-06 测试与安全质量门收口（2026-06-18 已交付）

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
