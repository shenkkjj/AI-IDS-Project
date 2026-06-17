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
