# Run: M2-01 Database URL and Alembic Baseline

> 开始时间：2026-06-17
> 运行模式：L5（数据库 + 迁移纪律，受 `docs/agent/UNATTENDED_LONG_TASKS.md` §2 L3 约束）
> 任务文档：`docs/agent/M2_01_DATABASE_URL_ALEMBIC_BASELINE_TASK.md`
> 预算：单次连续运行；同一测试最多连续修复 3 轮；diff 超过约 800 行停止

## 目标

让项目所有者和后续 agent 能清楚知道后端到底连哪个数据库：

- 本地默认仍安全使用 `data/app.db` SQLite；
- Docker / 部署路径可以通过 `DATABASE_URL` 显式连接；
- 未来任何 schema 变更都通过 Alembic revision 表达，而不是把 `ALTER TABLE` 藏在启动路径。

完成 `DATABASE_URL` 统一 → Alembic 初始化 → baseline revision → SQLite 新库/旧库兼容验证 → 文档同步 → 提交并 push。

## 范围

### 允许修改

- `server/core/database.py`
- `server/main.py`（仅调整数据库初始化/迁移调用）
- `server/db.py`（re-export 兼容）
- `server/models_db.py`（仅当 Alembic autogenerate 需要 import/metadata 修正，不新增业务字段）
- `server/migrations/**`
- `alembic.ini`
- `migrations/**`（推荐目录，二选一）
- `server/tests/test_database_config.py`
- `server/tests/test_migrations.py`
- `server/tests/conftest.py`（仅测试隔离必要调整）
- `requirements.txt`
- `.env.example`
- `README.md`
- `server/STRUCTURE.md`
- `docs/ALEMBIC_MIGRATION.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/runs/2026-06-17-m2-01-database-url-alembic-baseline.md`（本文件）

### 禁止修改

- `.coverage`
- `.claude/settings.local.json`
- 真实 `.env`
- `data/app.db`、`*.db`
- `server/security/**`
- 认证 / 授权 / session / cookie / JWT
- `web-next/**`
- `nginx/**`
- CI / deploy（仅文档说明）

### 禁止操作

- 不用 `git add .`
- 不 `git reset --hard`
- 不 `git clean`
- 不删本地数据库
- 不连真实生产数据库
- 不在日志或文档中写真实数据库 URL / 密码 / token

## 阶段计划

- [ ] 阶段 1：现状审计 + 创建运行日志
- [ ] 阶段 2：写 RED 测试
- [ ] 阶段 3：实现数据库 URL 事实来源
- [ ] 阶段 4：初始化 Alembic baseline
- [ ] 阶段 5：处理 `ensure_user_config_columns()` 兼容层
- [ ] 阶段 6：文档同步
- [ ] 阶段 7：全量验证矩阵
- [ ] 阶段 8：提交与 push
- [ ] 阶段 9：最终报告

---

## 阶段 1：现状审计

### 命令记录（2026-06-17）

```powershell
git status --short --branch
git rev-parse HEAD
git ls-remote origin refs/heads/main
git diff --cached --name-only
git log --oneline -10 origin/main
.venv\Scripts\python.exe -c "import alembic; print(alembic.__version__)"
.venv\Scripts\python.exe -c "import sqlalchemy; print(sqlalchemy.__version__)"
```

### 结果

- 当前分支：`main`
- 本地 HEAD：`14849cf8e87c74f0520ab31fcd8a1ae9c41aab6a`
- 远端 main：`14849cf8e87c74f0520ab31fcd8a1ae9c41aab6a`（**与本地一致，未前进，可继续**）
- 暂存区：空
- 工作树变更：
  - `M .claude/settings.local.json`（被 hooks 持续修改，禁止提交）
  - `M .coverage`（覆盖率产物，禁止提交）
  - `M docs/agent/UNATTENDED_LONG_TASKS.md`（M3-02 阶段任务累积改动，提交时应评估）
  - `?? docs/agent/M2_01_DATABASE_URL_ALEMBIC_BASELINE_TASK.md`（本任务文档，本次需纳入提交）
- 远端 origin/main 最近 10 个 commit：M3-02 推送收口相关，HEAD `14849cf` 即 `docs(runs): 记录 M3-02 推送前总审查与 push 成功`。
- 依赖现状：
  - SQLAlchemy 2.0.44（已装）
  - alembic：**未安装**（需 `pip install alembic` 并写入 `requirements.txt`）
  - 当前 `requirements.txt` 不含 `alembic`、`psycopg`、`psycopg2-binary`（PostgreSQL driver 待选型）

### 当前数据库事实

- `server/core/database.py` 硬编码 `DATABASE_URL = f"sqlite:///{DATA_DIR / 'app.db'}"`，**不读取环境变量**。
- `engine` 始终 `sqlite:///...`，`connect_args={"check_same_thread": False}` 永远注入（对 PostgreSQL 是错误参数）。
- `init_db()` 调 `Base.metadata.create_all(bind=engine)`，幂等。
- `ensure_user_config_columns()` 在 `server/main.py` 启动路径被调用，对 `users` / `user_configs` 跑一组幂等 `ALTER TABLE`。
- `server/db.py` 是 re-export 兼容层，对外暴露 `Base` / `SessionLocal` / `engine` / `TimestampMixin`。
- `server/migrations/sql/sc22_audit_indexes.sql` 是手写 SC-22 audit 索引脚本，注释要求 `psql "$DATABASE_URL" -f ...`，独立于启动路径。
- `.env.example` 第 31 行声明 `DATABASE_URL=sqlite+aiosqlite:///data/app.db`（async 驱动，但当前 sync engine 实际读不到）。
- `docker-compose.yml` 第 26 行给 backend 注入 `postgresql://cybersentinel:cybersentinel@postgres:5432/cybersentinel`。
- `server/tests/conftest.py` 第 24 行用 `sqlite+aiosqlite:///data/test.db` 作为测试默认 URL。

### 关键发现

1. `server/core/database.py` 是当前真正生效的 engine，**与 `.env.example` / docker-compose 不一致**。
2. 同步 SQLAlchemy engine 收到 `sqlite+aiosqlite:///` 时会因 driver 缺失抛错；当前是硬编码所以没触发，是隐藏雷。
3. `ensure_user_config_columns()` 已覆盖 ORM 启动时不建的所有列；做 Alembic baseline 时应把对应 ALTER 落入 revision，保留兼容路径同时标注 legacy。
4. 远端 main HEAD 与本地一致，可以继续 push。

### 允许 / 禁止范围已记录在本文 §范围。

### 阶段 1 结果

- 远端 main 未前进 ✅
- 工作树无禁止文件被 staged ✅
- 允许/禁止范围已明确 ✅
- 依赖现状已记录（alembic 缺失） ✅

---

## 阶段 2：写 RED 测试

- 新增 `server/tests/test_database_config.py`：13 个测试，覆盖 `default_database_url` / `load_database_url` / `normalize_database_url` / `build_engine_kwargs` / `create_app_engine` / 模块级 engine 行为。
- 新增 `server/tests/test_migrations.py`：8 个测试，覆盖 `alembic.ini` / env.py / `alembic --version` / `alembic upgrade head` 在临时 SQLite 上跑通 / `alembic current` / env.py Base 导入 / legacy sc22 sql 文档说明。
- 第一次跑：`test_database_config.py` 12 failed, 1 passed（RED，全部因 helper 缺失失败 — 合规）；`test_migrations.py` 4 failed, 1 passed, 3 skipped（RED，全部因 alembic 缺失 / alembic.ini 缺失失败 — 合规）。
- RED 失败原因均为缺失功能/迁移配置，无语法错误或 import path 错误 ✅。

### 阶段 2 结果

- RED 来自功能/迁移缺失 ✅
- 13 + 8 = 21 个测试已就位，等待 GREEN ✅

---

## 阶段 3：实现数据库 URL 事实来源

- 重写 `server/core/database.py`：
  - 新增 `default_database_url()` — `sqlite:///{repo}/data/app.db`；
  - 新增 `load_database_url()` — 优先 `os.getenv("DATABASE_URL")`，未设回退到默认；
  - 新增 `normalize_database_url()` — `sqlite+aiosqlite:///` 自动归一化为 `sqlite:///`；
  - 新增 `build_engine_kwargs()` — SQLite 加 `check_same_thread=False`，其他 dialect 不加；
  - 新增 `create_app_engine()` — 完整流程，让 SQLAlchemy 异常自然上抛，不静默降级；
  - 模块级 `engine` / `SessionLocal` 保持兼容。
- 安装依赖：`alembic==1.13.2`、`psycopg[binary]==3.2.3`（写入 `requirements.txt`）。
- 跑 `pytest server/tests/test_database_config.py`：13 passed（1 个 reload helper 行为修正：先 monkeypatch 再 reload，避免 monkeypatch.delenv 把 setenv 的值擦掉）。

### 阶段 3 结果

- 13 passed, 0 failed ✅
- 现有 `test_auth.py` / `test_demo_flow.py` / `test_alert_triage.py` 不受影响（27 passed）✅

---

## 阶段 4：初始化 Alembic baseline

- 跑 `python -m alembic init -t generic migrations` → 生成 `alembic.ini` / `migrations/env.py` / `migrations/script.py.mako` / `migrations/README`。
- 把 `migrations/env.py` 改为：
  - 加 `sys.path.insert(0, repo_root)`；
  - `from server.core.database import Base, load_database_url, normalize_database_url`；
  - `import server.models_db`（保证 metadata 可见）；
  - `_resolve_url()` 与 app 走同一份 `load_database_url()` / `normalize_database_url()`；
  - `context.configure(..., render_as_batch=sqlite)` 兼容 SQLite。
- 改 `alembic.ini`：把 `sqlalchemy.url = driver://user:pass@localhost/dbname` 注释化（Windows GBK locale 解析中文注释会失败，把中文注释改成英文）。
- 跑 `python -m alembic revision --autogenerate -m "baseline schema"` → 生成 `migrations/versions/d9af4388f20a_baseline_schema.py`，覆盖 6 张表 + 全部索引（含 SC-22 复合索引）。
- 临时空 SQLite 上跑 `alembic upgrade head`：✅ 0 错误，建出全部表和索引。
- 跑 `alembic current`：输出 `d9af4388f20a (head)` ✅。
- 跑 `pytest server/tests/test_migrations.py`：8 passed ✅（其中 1 个测试由 `alembic current on empty` 改为 `alembic current after upgrade`，符合实际行为）。

### 阶段 4 结果

- baseline revision `d9af4388f20a_baseline_schema.py` ✅
- env.py 走 `load_database_url()` / `normalize_database_url()` 同一份事实来源 ✅
- upgrade head 在临时 SQLite 0 错误 ✅

---

## 阶段 5：处理 `ensure_user_config_columns()` 兼容层

- 保守策略：保留 `ensure_user_config_columns()`，在 `server/core/database.py` 注释中明确标注为 legacy 兼容层，专门补旧 `data/app.db` 上 `init_db()` 创建时缺失的列。
- `server/main.py` 启动路径加注释：明确 `init_db()` + `ensure_user_config_columns()` 是 legacy 兼容层，新 schema 变更必须走 Alembic。
- `server/migrations/sql/sc22_audit_indexes.sql` 不删除（已由 baseline 覆盖两个复合索引），但文件保留并在 `docs/ALEMBIC_MIGRATION.md` §"清理"小节中说明后续可清理路径。
- 跑 `pytest server/tests/test_auth.py server/tests/test_demo_flow.py server/tests/test_alert_triage.py`：27 passed ✅（确认兼容层不破坏现有行为）。

### 阶段 5 结果

- 兼容层保留，但已被显式标注 ✅
- 不破坏现有测试 ✅

---

## 阶段 6：文档同步

- `requirements.txt`：新增 `alembic==1.13.2`、`psycopg[binary]==3.2.3`。
- `.env.example`：`DATABASE_URL=sqlite:///data/app.db`（原 `sqlite+aiosqlite:///...`），加注释说明 Docker / 部署可改 `postgresql+psycopg://...`。
- `README.md`：改"暂未被读取"为"现在统一读取"；`当前已知限制` 段落更新 Docker Compose 数据库接线现状。
- `server/STRUCTURE.md`：core/database.py 描述更新；`数据库现状` 小节重写。
- `docs/ALEMBIC_MIGRATION.md`：从"计划"改为"已建立 baseline / 仍保留哪些 legacy 兼容"完整手册。
- `docs/plans/M2_PRODUCT_ROADMAP.md`：M2-01 状态改为"已交付"，列详细落地项。
- `PRODUCT.md`：当前基线新增 M2-01 落地项；M2 任务清单第 4 条改为"已完成"。
- `docs/agent/UNATTENDED_LONG_TASKS.md`：M2_01 索引补全运行日志路径。

### 阶段 6 结果

- 文档已全部同步 ✅
- 没有过度承诺 PostgreSQL / Compose 端到端通过 ✅

---

## 阶段 7：全量验证矩阵

按任务文档 §7 顺序执行：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server/tests/test_database_config.py server/tests/test_migrations.py -q --tb=short
.venv\Scripts\python.exe -m pytest server/tests/test_auth.py server/tests/test_demo_flow.py server/tests/test_alert_triage.py -q --tb=short
.venv\Scripts\python.exe -m pytest server/tests -q --tb=short
cd web-next && npm run typecheck && npm run build
git diff --check
.venv\Scripts\python.exe -m pip check
```

### 结果

| 命令 | 结果 |
|---|---|
| 新测试（test_database_config + test_migrations） | **21 passed** ✅ |
| auth + demo_flow + alert_triage | **27 passed** ✅ |
| 全量 `pytest server/tests` | **274 passed, 2 skipped, 17 warnings** ✅ |
| `npm run typecheck` | ✅ Route types generated successfully |
| `npm run build` | ✅ /dashboard 36.4 kB / First Load JS 184 kB |
| `git diff --check` | ✅ 仅 LF/CRLF 警告，无 trailing whitespace 错误 |
| `pip check` | ✅ No broken requirements found |

### 阶段 7 结果

- 全量验证矩阵全部通过 ✅
- 无新警告、错误、回归 ✅

---

## 阶段 8：安全与迁移审查

| 维度 | 状态 |
|---|---|
| 是否连接真实生产数据库 | 否 — 所有 alembic 操作在临时 SQLite（`$TEMP/alembic_*.db`）上跑通 |
| 测试是否只使用临时 SQLite | 是 — `test_migrations.py` 用 `tmp_path`；`test_database_config.py` 用 `tmp_path` 或 reload 验证 |
| `DATABASE_URL` 是否被打印泄露 | 否 — 测试断言只比较 URL 字符串，不打印内容；运行日志不写 URL |
| PostgreSQL URL 无 driver 时如何失败 | `test_create_app_engine_rejects_postgres_without_driver` 验证：`create_app_engine("postgresql+nonexistent_driver://...")` 抛 SQLAlchemy 异常，无掩盖降级 |
| 旧 SQLite 开发库如何兼容 | 保留 `ensure_user_config_columns()` 作为 legacy 兼容层；新环境用 `alembic upgrade head` 起新库 |
| Alembic baseline 是否可重复应用到新空库 | `test_alembic_upgrade_head_on_empty_sqlite` 验证（可重入：每个测试用独立 tmp_path） |
| downgrade / rollback 策略 | baseline revision 提供 `downgrade()`（drop 表 + 索引）；`docs/ALEMBIC_MIGRATION.md` §"downgrade 策略" 已记录不可逆操作的约束 |
| `ensure_user_config_columns()` 当前状态 | 保留为 legacy 兼容层；`server/core/database.py` 和 `server/main.py` 显式标注；未来退出路径记录在 `docs/ALEMBIC_MIGRATION.md` §"后续工单" |

### 阶段 8 结果

- 安全 / 迁移审查问题全部有显式答案 ✅
- 无未解决问题 ✅

---

## 验证证据汇总

- `pytest server/tests/test_database_config.py`：13 passed
- `pytest server/tests/test_migrations.py`：8 passed
- `pytest server/tests/test_auth.py server/tests/test_demo_flow.py server/tests/test_alert_triage.py`：27 passed
- `pytest server/tests`：274 passed, 2 skipped
- `npm run typecheck` / `npm run build`：通过
- `pip check`：通过
- `alembic upgrade head` 在临时 SQLite：0 错误
- `alembic current`：输出 `d9af4388f20a (head)`

---

## 剩余本地噪声文件

- `.claude/settings.local.json`（M — 禁止提交）
- `.coverage`（M — 禁止提交）
- `docs/agent/UNATTENDED_LONG_TASKS.md`（M — 与本任务相关，但已更新；本任务建议纳入 commit 1）

## 最终状态

- M2-01 全部阶段已完成
- 通过验证矩阵
- 准备精确 stage 并 commit


