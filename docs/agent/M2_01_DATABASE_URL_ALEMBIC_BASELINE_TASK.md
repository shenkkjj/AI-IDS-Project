# M2-01 Database URL and Alembic Baseline Task

> 任务级别：L5 无人值守基础设施战役。
> 适用场景：M3-02 已推送完成，产品能力继续前进前，需要先清理数据库事实来源和迁移纪律。当前后端硬编码 SQLite `data/app.db`，`.env.example` / Docker Compose 声明 `DATABASE_URL` / PostgreSQL，但 `server/core/database.py` 还没有读取它。
> 回复语言：中文。

---

## 0. 启动前必读

完整阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `README.md`
- `server/STRUCTURE.md`
- `docs/ALEMBIC_MIGRATION.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- 本文件

必须阅读实现面：

- `server/core/database.py`
- `server/main.py`
- `server/db.py`
- `server/models_db.py`
- `server/tests/conftest.py`
- `requirements.txt`
- `.env.example`
- `docker-compose.yml`
- `server/migrations/sql/sc22_audit_indexes.sql`

如果文档和当前代码冲突，以当前代码和测试为准，并在运行日志记录差异。

---

## 1. 产品能力定义

作为项目 owner 或后续 agent，我能清楚知道后端到底连接哪个数据库；本地默认仍安全使用 SQLite，而 Docker / 部署路径可以通过 `DATABASE_URL` 显式连接数据库；未来任何 schema 变更都通过 Alembic revision 表达，而不是继续把手写 `ALTER TABLE` 藏在启动路径里。

这条任务要完成的是“迁移基线”，不是生产数据库切换：

```text
统一 DATABASE_URL -> 初始化 Alembic -> 建立 baseline revision -> 验证 SQLite 新库/旧库 -> 文档同步 -> 提交并 push
```

---

## 2. 非目标

本任务不做：

- 不迁移任何真实生产数据库。
- 不删除 `data/app.db`。
- 不自动清空、重建或覆盖本地开发数据库。
- 不要求 Docker Compose 完整端到端通过；可以记录阻塞。
- 不把 PostgreSQL 声称为已完全生产可用，除非真的完成验证。
- 不修改认证、授权、JWT、cookie、Guardrails、Copilot 业务语义。
- 不新增业务表或业务字段。
- 不处理 M3-02 triage 持久化；那是后续业务迁移任务。

---

## 3. 目标边界

### 必须完成

1. `server/core/database.py` 从环境变量读取 `DATABASE_URL`。
2. 未设置 `DATABASE_URL` 时，本地默认仍使用 repo 内 `data/app.db` SQLite。
3. 同步支持常见 SQLAlchemy URL：
   - `sqlite:///...`
   - `sqlite+aiosqlite:///...`（如果当前同步 engine 不支持，要转换或清晰报错）
   - `postgresql://...`
   - `postgresql+psycopg://...` 或项目选择的 PostgreSQL driver
4. 引入 Alembic 依赖并初始化迁移目录。
5. 建立 baseline revision，覆盖当前 ORM schema。
6. 处理现有 `server/migrations/sql/sc22_audit_indexes.sql` 的归属：迁入 Alembic revision，或在文档中明确它仍是手动 SQL，且不能与 Alembic 口径冲突。
7. 保留或安全降级 `ensure_user_config_columns()`，不能让旧 SQLite 开发库升级路径断裂。
8. 新增测试，覆盖数据库 URL 解析、SQLite 默认路径、新空库建表/迁移。
9. 更新 README、server/STRUCTURE、docs/ALEMBIC_MIGRATION、PRODUCT、.env.example。

### 可以分阶段完成

Alembic 和启动时自动迁移之间可以选保守方案：

- 推荐：应用启动仍 `init_db()` + 兼容轻量升级；Alembic 作为显式迁移工具先落地。
- 不推荐：Web 进程启动时自动执行 `alembic upgrade head`，除非有清晰回滚策略和测试。

---

## 4. 允许修改范围

后端与迁移：

- `server/core/database.py`
- `server/main.py`（仅调整数据库初始化/迁移调用）
- `server/db.py`（如需 re-export 新 helper）
- `server/models_db.py`（仅当 Alembic autogenerate 需要 import/metadata 修正；不要新增业务字段）
- `server/migrations/**`
- `alembic.ini`
- `migrations/**` 或项目最终选择的 Alembic 目录
- `server/tests/test_database_config.py`
- `server/tests/test_migrations.py`
- `server/tests/conftest.py`（仅测试隔离必要调整）
- `requirements.txt`

文档：

- `.env.example`
- `README.md`
- `server/STRUCTURE.md`
- `docs/ALEMBIC_MIGRATION.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/runs/2026-06-17-m2-01-database-url-alembic-baseline.md`

---

## 5. 禁止修改范围

禁止修改：

- `.coverage`
- `.claude/settings.local.json`
- 真实 `.env`
- `data/app.db`
- `*.db`
- `server/security/**`
- 认证 / 授权 / session / cookie / JWT 语义
- `web-next/**`
- `nginx/**`
- CI / deploy，除非只是文档说明

禁止操作：

- 不要使用 `git add .`
- 不要 `git reset --hard`
- 不要 `git clean`
- 不要删除本地数据库文件
- 不要运行会连接真实生产数据库的迁移
- 不要把真实数据库 URL、密码、token 写入日志或文档

---

## 6. 阶段计划

### 阶段 1：运行日志与现状审计

创建：

```text
docs/runs/2026-06-17-m2-01-database-url-alembic-baseline.md
```

记录：

- 当前分支
- 本地 HEAD
- 远端 main
- 初始 `git status --short --branch`
- 当前数据库事实
- 允许 / 禁止范围

命令：

```powershell
git status --short --branch
git rev-parse HEAD
git ls-remote origin refs/heads/main
git diff --cached --name-only
rg -n "DATABASE_URL|ensure_user_config_columns|init_db|create_engine|alembic|sqlite|postgres" server README.md docs .env.example docker-compose.yml
```

如果远端 main 已前进，停止并报告。

### 阶段 2：写 RED 测试

先新增测试，再改实现。

建议新增 `server/tests/test_database_config.py`，覆盖：

1. 未设置 `DATABASE_URL` 时返回默认 SQLite 文件路径。
2. 设置 `DATABASE_URL=sqlite:///...` 时 engine 使用该路径。
3. 设置 `DATABASE_URL=sqlite+aiosqlite:///...` 时同步 engine 能明确转换为 `sqlite:///...`，或明确拒绝并给出说明。
4. PostgreSQL URL 不应被静默忽略。
5. `connect_args={"check_same_thread": False}` 只应用于 SQLite，不应用于 PostgreSQL。
6. 测试不会污染真实 `data/app.db`。

建议新增 `server/tests/test_migrations.py`，覆盖：

1. Alembic 配置文件存在。
2. migration env 能加载 `Base.metadata`。
3. 对临时 SQLite 空库执行 `alembic upgrade head` 成功。
4. `alembic downgrade base` 或至少 `downgrade -1` 行为被文档化；若不可逆，测试或文档必须说明。

RED 命令：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_database_config.py server\tests\test_migrations.py -q --tb=short
```

RED 必须来自缺失功能/迁移配置，不得来自语法错误、fixture 坏掉或导入路径错误。

### 阶段 3：实现数据库 URL 事实来源

建议实现：

- 在 `server/core/database.py` 增加小型 helper：
  - `default_database_url()`
  - `load_database_url()`
  - `normalize_database_url(url)`
  - `build_engine_kwargs(url)`
  - `create_app_engine(url=None)`
- 默认行为：
  - 未设置 `DATABASE_URL`：使用 `sqlite:///{repo}/data/app.db`。
  - `.env.example` 中的 `sqlite+aiosqlite:///data/app.db` 如用于同步 SQLAlchemy engine，要转换为 `sqlite:///...` 或把样例改成同步 URL。
- PostgreSQL 支持：
  - 选择项目依赖能支持的 driver，并同步 `requirements.txt`。
  - 如果使用 `psycopg`，添加 `psycopg[binary]` 或等价依赖。
  - 不要只在文档里说支持，代码必须不再静默忽略 PostgreSQL URL。
- `engine` / `SessionLocal` / `get_db` 对外导出保持兼容。

验证：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_database_config.py -q --tb=short
```

### 阶段 4：初始化 Alembic baseline

落地方式由 agent 根据 repo 选择，但必须一致：

- 推荐目录：`migrations/` 或 `server/migrations/alembic/`，二选一，不要混乱。
- 保留现有 `server/migrations/sql/` 时，要在文档中说明它是 legacy/manual SQL。

必须做到：

- `alembic.ini` 能找到 migration script location。
- `env.py` 能导入 `server.core.database.Base` 和 `server.models_db`。
- baseline revision 能创建当前 ORM 表和索引。
- `alembic upgrade head` 对临时 SQLite 空库成功。
- 对已存在的开发库，有 `stamp head` 或兼容说明，不破坏旧库。

重要：`Base.metadata.create_all()` 和 Alembic 的关系要讲清楚。若短期保留 `init_db()`，就不要声称 Alembic 已完全替代启动建表。

验证：

```powershell
.venv\Scripts\python.exe -m alembic --version
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest server\tests\test_migrations.py -q --tb=short
```

如 `alembic upgrade head` 会碰默认 `data/app.db`，必须改为测试临时库或在文档中说明，并避免污染真实本地数据库。

### 阶段 5：处理 `ensure_user_config_columns()`

保守策略：

- 可以暂时保留 `ensure_user_config_columns()` 作为旧 SQLite 开发库兼容层。
- 但必须改名/注释/文档明确它是 legacy compatibility，不是未来 schema 变更方式。
- 新 schema 变更必须走 Alembic。

激进策略只有在测试充分时才可采用：

- 从启动路径移除 `ensure_user_config_columns()`。
- 用 Alembic revision 覆盖所有历史 ALTER。
- 证明旧 SQLite 开发库能安全升级。

本任务建议保守策略，避免把启动路径一次性打碎。

验证：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_auth.py server\tests\test_demo_flow.py server\tests\test_alert_triage.py -q --tb=short
```

### 阶段 6：文档同步

更新：

- `.env.example`：让 `DATABASE_URL` 示例和实际同步 engine 一致。
- `README.md`：删掉“DATABASE_URL 暂未被读取”的过时说法，改成当前真实行为。
- `server/STRUCTURE.md`：同步数据库入口事实。
- `docs/ALEMBIC_MIGRATION.md`：从“计划”更新为“已建立 baseline / 仍保留哪些 legacy 兼容”。
- `docs/plans/M2_PRODUCT_ROADMAP.md`：更新 M2-01 状态。
- `PRODUCT.md`：更新当前明显问题和近期路线图。
- `docs/agent/UNATTENDED_LONG_TASKS.md`：加入本任务索引。

不要过度承诺 PostgreSQL / Docker Compose 已生产可用，除非真的完成验证。

### 阶段 7：全量验证矩阵

按顺序运行：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_database_config.py server\tests\test_migrations.py -q --tb=short
.venv\Scripts\python.exe -m pytest server\tests\test_auth.py server\tests\test_demo_flow.py server\tests\test_alert_triage.py -q --tb=short
.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
cd web-next
npm run typecheck
npm run build
cd ..
git diff --check
```

如果修改 `requirements.txt`，还要验证：

```powershell
.venv\Scripts\python.exe -m pip check
```

可选但推荐：

```powershell
python scripts/check_env_security.py
```

### 阶段 8：安全与迁移审查

运行日志必须回答：

- 是否会连接真实生产数据库。
- 测试是否只使用临时 SQLite。
- `DATABASE_URL` 是否可能被打印泄露。
- PostgreSQL URL 无 driver 时如何失败。
- 旧 SQLite 开发库如何兼容。
- Alembic baseline 是否可重复应用到新空库。
- downgrade/rollback 策略是什么。
- `ensure_user_config_columns()` 当前状态是什么，未来如何退出。

### 阶段 9：提交与 push

允许在验证通过后 commit 和 push。

推荐拆分：

1. `test(db): 增加数据库配置与迁移基线测试`
2. `feat(db): 统一 DATABASE_URL 与 Alembic 基线`
3. `docs(db): 同步数据库迁移事实与运行手册`

每次只精确 stage：

```powershell
git add -- <明确路径>
git diff --cached --name-only
```

禁止 `git add .`。

push 前：

```powershell
git status --short --branch
git diff --cached --name-only
git log --oneline origin/main..HEAD
git log --name-only --format="commit %h %s" origin/main..HEAD -- .coverage .claude/settings.local.json data/app.db
git ls-remote origin refs/heads/main
```

只有满足以下条件才允许 push：

- 当前分支是 `main`
- 远端 main 未前进
- 暂存区为空
- `.coverage`、`.claude/settings.local.json`、`data/app.db`、真实 `.env` 没有进入 commit
- 验证矩阵通过

push：

```powershell
git push origin main
```

push 后：

```powershell
git rev-parse HEAD
git ls-remote origin refs/heads/main
git status --short --branch
```

---

## 7. 停止条件

遇到任一情况必须停止：

- 远端 main 已前进，需要 rebase/merge。
- 迁移会修改或删除真实 `data/app.db`。
- 必须连接真实生产 PostgreSQL 才能继续。
- 同一测试失败连续修复 3 轮仍失败。
- 需要改认证、授权、Guardrails 或业务 schema。
- Alembic baseline 与 ORM 生成结果不可信，无法解释差异。
- 依赖安装失败且无法用当前环境解决。
- 禁止文件被 staged。

停止时输出阻塞证据、当前 git 状态和下一条建议任务。

---

## 8. 最终报告

完成后用中文输出：

- 完成状态：完成 / 部分完成 / 阻塞
- push 状态
- commit hash 与 message
- 数据库 URL 当前真实行为
- Alembic baseline 路径与 revision id
- `ensure_user_config_columns()` 当前处理方式
- 验证命令与结果
- 迁移安全审查结论
- 运行日志路径
- 最终 `git status --short --branch`
- 本地 HEAD 与远端 HEAD
- 剩余本地噪声文件

