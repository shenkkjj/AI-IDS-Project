# Alembic 迁移手册

> 状态：2026-06-17，M2-01 已建立 baseline revision。
> 本文档以前是"计划"，现在记录：M2-01 落地的实际行为、当前实现细节、保留的 legacy 兼容点、downgrade 策略和后续工单。

## 当前状态（M2-01 实测后）

- `server/core/database.py` 现在通过 helper 读 `DATABASE_URL`：
  - `load_database_url()` — 优先返回 `os.getenv("DATABASE_URL")`，未设置时回退到 `default_database_url()`；
  - `normalize_database_url()` — 把 `sqlite+aiosqlite:///` 自动归一化为 `sqlite:///`，避免同步 engine 收到 async driver 报错；
  - `build_engine_kwargs()` — 只对 SQLite 注入 `connect_args={"check_same_thread": False}`，对 PostgreSQL 等不加；
  - `create_app_engine()` — 综合上述 helper 构造 engine；不在 SQLAlchemy 出错时做掩盖降级。
- `engine` / `SessionLocal` 仍保持模块级导出（向后兼容），但底层 URL 由 `DATABASE_URL` 决定。
- Alembic baseline 已建立：
  - `alembic.ini` 位于 repo 根，`script_location = migrations`；
  - `migrations/env.py` 显式 import `server.core.database.Base` 并 `import server.models_db`；
  - `migrations/env.py` 的 `run_migrations_online()` 通过 `_resolve_url()` 走与 app 同一套 `load_database_url()` / `normalize_database_url()`，避免 app 与 migration 用两套配置；
  - baseline revision：`d9af4388f20a_baseline_schema.py`，autogenerate 覆盖全部 6 张表（`users` / `user_configs` / `logs` / `audit_logs` / `auth_challenges` / `refresh_tokens`）和全部索引（含 SC-22 的 `ix_audit_logs_action_status_created` 和 `ix_audit_logs_user_action_created`）。
- 启动路径仍保留 `init_db()` + `ensure_user_config_columns()`：
  - `init_db()` 作为新空库的快速回退；新环境更推荐 `alembic upgrade head`；
  - `ensure_user_config_columns()` 已被显式标记为 **legacy 兼容层**（见 `server/core/database.py` 注释），专门补旧 `data/app.db` 上 `init_db()` 创建时缺失的列；新 schema 变更必须走 Alembic revision，**不要往 `ensure_user_config_columns` 加新 ALTER**。
- `server/migrations/sql/sc22_audit_indexes.sql`（legacy manual SQL）已被 baseline revision 自动覆盖（两个 SC-22 复合索引都进了 `d9af4388f20a`），但文件保留不删；任何新环境都不需要再 `psql ... -f` 应用它。如要清理，参见 §"清理"小节。

## 当前验证（2026-06-17）

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'

# 临时空 SQLite
$env:DATABASE_URL='sqlite:///' + ($env:TEMP + '\alembic_test.db').Replace('\','/')
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic current
```

实测结果：

- `alembic upgrade head` 在空 SQLite 上 0 错误，建出 6 张表 + 全部索引；
- `alembic current` 输出 `d9af4388f20a (head)`；
- `pytest server/tests/test_database_config.py` 13 passed；
- `pytest server/tests/test_migrations.py` 8 passed。

## 已确认事实

1. **本地开发路径**（默认）：`DATABASE_URL` 未设置 → `data/app.db` SQLite。
2. **Docker / 部署路径**：`DATABASE_URL=postgresql+psycopg://cybersentinel:cybersentinel@postgres:5432/cybersentinel`（与 `docker-compose.yml` 对齐）；driver 由 `psycopg[binary]==3.2.3` 提供。
3. **测试路径**：`server/tests/conftest.py` 仍 `os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///data/test.db")`；同步 engine 在初始化时会把 `sqlite+aiosqlite:///` 归一化为 `sqlite:///`，所以测试库仍是同步 SQLite。
4. **旧本地开发库**：`data/app.db` 如果只跑过 `init_db()` 而没 `alembic stamp head`，可以保留 `ensure_user_config_columns()` 兜底补列；新环境请直接 `alembic upgrade head`。

## 行为契约

### `DATABASE_URL` 解析

- 读取顺序：`os.getenv("DATABASE_URL")` → `default_database_url()`；
- 默认 URL：`sqlite:///{repo}/data/app.db`，使用 `pathlib` 解析，不依赖 CWD；
- 归一化：仅处理 `sqlite+aiosqlite:///` → `sqlite:///`，其他 driver 不动。

### engine 行为

- SQLite：`connect_args={"check_same_thread": False}`，池参数保持 `pool_size=5` / `max_overflow=10` / `pool_timeout=30` / `pool_recycle=1800`；
- PostgreSQL：不加 `check_same_thread`，池参数同上；
- 错误时：直接抛 SQLAlchemy 异常，不静默降级到 SQLite 之类的掩盖行为。

### 启动路径

```text
load_dotenv(.env) → init_db() → ensure_user_config_columns() → FastAPI 启动
```

- `init_db()` 仍调用 `Base.metadata.create_all(bind=engine)`（幂等）；
- `ensure_user_config_columns()` 仅对 `users` / `user_configs` 跑一组幂等 ALTER；任一语句失败只记 `loguru warning`（"already exists" / "duplicate" 不算失败），不阻断启动。

## 新 schema 变更工作流

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'

# 1. 改 ORM（server/models_db.py）
# 2. autogenerate
.venv\Scripts\python.exe -m alembic revision --autogenerate -m "<change>"

# 3. 人工 review 生成文件，去掉误判
# 4. 临时库验证
$env:DATABASE_URL='sqlite:///' + ($env:TEMP + '\alembic_review.db').Replace('\','/')
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic downgrade -1
.venv\Scripts\python.exe -m alembic upgrade head

# 5. 跑回归
.venv\Scripts\python.exe -m pytest server/tests/test_database_config.py server/tests/test_migrations.py -q --tb=short
```

## 旧库升级路径

- 已有 `data/app.db` 且无 `alembic_version` 表：先 `alembic stamp head`（标记为已 baseline），再 `alembic upgrade head`（其实无变化），后续新变更走标准流程。
- 已有 `data/app.db` 且跑过旧 `init_db() + ensure_user_config_columns()`：保留兼容层即可，新环境用 `alembic upgrade head` 起新库；建议在新机器上重新建库后再迁移数据，避免 baseline revision 与手工补列的时序差。

## downgrade 策略

- baseline revision 的 `downgrade()` 会按依赖反序 drop 表和索引；这是可逆的。
- baseline 之后新增的 revision 必须自行写 `downgrade()`；不可逆操作（破坏性 rename / drop column）需在 commit message 显式标注。
- `alembic downgrade base` 会回到无表空库；不要在生产环境直接 `downgrade base`，必须先做数据备份。

## 清理

- `server/migrations/sql/sc22_audit_indexes.sql` 已被 baseline 覆盖；后续如要清理，建议把 `server/migrations/sql/` 整个目录删掉，并把 `server/STRUCTURE.md` 对应描述从"手写 SQL 迁移"改为"Alembic baseline + versions/"。
- 当前保留是为了不破坏 git blame 与"兼容旧 README/PRODUCT"事实；不在 M2-01 删除。

## 后续工单

- M2-07 Compose 端到端验收：把 `docker-compose.yml` 中的 PostgreSQL 接线端到端跑通。
- 把 `server/tests/conftest.py` 的 `setdefault` 从 `sqlite+aiosqlite:///` 改为 `sqlite:///`，与生产同步 engine 路径一致（低风险，留给下一轮清理）。
- `ensure_user_config_columns()` 退出路径：所有旧 `data/app.db` 都迁出后，从 `server/main.py` 启动路径移除。

---

## M3-03 告警研判持久化（revision `d33d40488e0f`）

`docs/agent/M3_03_ALERT_TRIAGE_PERSISTENCE_AND_HISTORY_TASK.md` 在 2026-06-18 落地。

- baseline revision `d9af4388f20a` 之上追加新 revision `d33d40488e0f`（`alembic upgrade head` 在 baseline 库上 0 错误继续推进）。
- 新增两张表：
  - `alert_records` — 告警快照事实来源；`(user_id, alert_id)` 唯一；保存 raw alert JSON、LLM analysis JSON、analysis error、processed_at、**最新 triage 字段**。
  - `alert_triage_events` — triage 历史事实来源；按 `alert_record_id` 关联；保存 from/to、disposition、analyst_note、updated_by、created_at。
- 关键索引：
  - `ix_alert_records_user_processed` / `ix_alert_records_user_status_processed` — 服务 `GET /alerts` 的常规分页与按状态过滤。
  - `ix_alert_records_alert_id` — 服务 history 端点先按 `alert_id` 定位 record。
  - `ix_alert_triage_events_user_alert_created` / `ix_alert_triage_events_record_created` — 服务 history 端点的 user/record 维度时间排序。
- JSON 存储策略：`raw_alert_json` / `llm_analysis_json` 用 `Text` 列 + `json.dumps(..., ensure_ascii=False)`。不依赖 PostgreSQL JSONB，让 SQLite 测试库与 Compose PostgreSQL 走同一份代码；后续若要 JSONB 索引搜索，需另开 RFC。
- `downgrade()` 按依赖反序 drop indexes / tables，可 `alembic downgrade base` 完整回滚。
- 验证：见 `server/tests/test_migrations.py::test_alembic_upgrade_head_creates_alert_records_tables` / `test_alembic_upgrade_head_creates_alert_records_indexes` / `test_alembic_downgrade_drops_alert_records_tables`。

### 启动期行为变化

- `GET /alerts` 现在走 DB（`alert_records`）；读失败回退内存 `app_state.alert.backlog` 并写 warning，不让主请求 5xx。
- `POST /alerts/demo` 写 `alert_records` 失败时，主请求返回 503（用户期待"重启可恢复"，不静默成功）。
- `PATCH /alerts/{alert_id}/triage` 写 `alert_records` + `alert_triage_events` 失败时同样返回 503；审计 `Log` 写失败仅 warning，不阻断主请求。
- worker ingest (`alert_worker`) 写 DB 失败时记录 warning，不广播未持久化 alert（避免前端误以为已可恢复）。

---

## M3-04 安全事件 / 案件工作台（revision `4f3c9a1d8b7e`）

`docs/agent/M3_04_INCIDENT_CASE_WORKBENCH_TASK.md` 在 2026-06-18 落地。

- `d33d40488e0f` 之上追加新 revision `4f3c9a1d8b7e`（`alembic upgrade head` 在 M3-03 库上 0 错误继续推进）。
- 新增三张表：
  - `incidents` — 案件事实来源；`(user_id, incident_id)` 唯一；保存 title / summary / severity / status / assignee_user_id / created_from_alert_id / closed_at / created_at / updated_at。
  - `incident_alert_links` — 告警 ↔ 案件关联事实来源；按 `incident_record_id` 关联；保存 alert_record_id / alert_id 字符串冗余 / linked_by / linked_at / **removed_at**（软删除）；重复 link 的幂等检查放在 service 层。
  - `incident_events` — 事件时间线事实来源；按 `incident_record_id` 关联；保存 event_type（`created` / `status_changed` / `alert_linked` / `alert_unlinked` / `note_added` / `summary_updated` / `severity_changed` / `title_changed`）/ from_status / to_status / detail（脱敏摘要）/ note（owner API 私有返回）/ actor_user_id / created_at。
- 关键索引：
  - `ix_incidents_user_updated` / `ix_incidents_user_status_updated` — 服务 `GET /incidents` 的常规分页与按状态过滤。
  - `ix_incidents_created_from_alert` — 服务从首条告警反查 incident。
  - `ix_incident_alert_links_incident_active` — 服务 incident 详情中 active link 的快速查询（配合 `removed_at IS NULL`）。
  - `ix_incident_alert_links_user_alert` / `ix_incident_alert_links_alert_record` — 服务 user/alert_record 维度反查。
  - `ix_incident_events_incident_created` / `ix_incident_events_user_created` — 服务事件时间线的 user/record 维度时间排序。
- 存储策略：`detail` / `note` 用 `Text`；不依赖 PostgreSQL JSONB。`created_at` / `updated_at` / `closed_at` / `linked_at` / `removed_at` 用 `DateTime`（naive UTC，与 M3-03 一致）。
- `downgrade()` 按依赖反序 drop indexes / tables，可 `alembic downgrade base` 完整回滚。
- 验证：见 `server/tests/test_migrations.py::test_alembic_upgrade_head_creates_incident_tables` / `test_alembic_upgrade_head_creates_incident_indexes` / `test_alembic_downgrade_drops_incident_tables`。

### 启动期行为变化

- `GET /incidents` 走 DB（`incidents` + active link 计数）；`GET /incidents/{id}` 返回 incident + linked_alerts + events。
- `POST /incidents` 写失败 → 路由返回 503（用户期待"重启可恢复"）。
- `POST /incidents/{id}/alerts` 写失败 → 503；重复 link 幂等返回 200 + `idempotent: true`。
- `DELETE /incidents/{id}/alerts/{alert_id}` 软删除 link，不删 `alert_records`；写失败 → 503。
- `PATCH /incidents/{id}` 与 status / severity / title / summary 变化同事务写 `IncidentEvent`；`closed_at` 由 service 自动维护；写失败 → 503。
- 审计 `Log(action=incident_create / incident_update / incident_alert_link / incident_alert_unlink)` 写失败仅 warning，不阻断主请求。
- `app_state.alert.backlog` 仍存在，但仅用于 WebSocket 实时推送与短期缓存；新事实来源是 `alert_records`。
