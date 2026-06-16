# Alembic 迁移计划

本文记录数据库迁移从“启动时手写 ALTER TABLE”切换到 Alembic 的计划。当前只是计划文档，尚未实施。

## 当前状态

后端数据库入口在 `server/core/database.py`。

已确认事实：

- 当前 engine 使用硬编码 SQLite 文件：`data/app.db`。
- 当前 `DATABASE_URL` 环境变量尚未被 `server/core/database.py` 读取。
- `init_db()` 会执行 `Base.metadata.create_all(bind=engine)`。
- `ensure_user_config_columns()` 会在启动时执行一组幂等 `ALTER TABLE`。
- `server/migrations/sql/sc22_audit_indexes.sql` 是现有手写 SQL 索引脚本，不是 Alembic revision。

这意味着：

- 本地开发实际跑的是 SQLite。
- Docker Compose 中声明的 PostgreSQL 接线待确认。
- 新增列目前需要同步改 ORM / Schema / 手写 ALTER TABLE，无法自动回滚。

## 为什么要迁移

手写 `ALTER TABLE` 适合早期小步补列，但它有几个问题：

- 迁移历史不清晰，难以知道某个环境应用到了哪一步。
- 回滚没有标准流程。
- SQLite 与 PostgreSQL 差异容易被隐藏。
- 容器部署、测试库、开发库之间容易漂移。

Alembic 迁移后，希望达到：

- schema 变更有 revision 文件。
- 本地和部署环境使用同一套迁移流程。
- 能执行 `upgrade` 和 `downgrade` 验证。
- 新 Agent 修改数据库时有明确边界。

## 推荐实施步骤

### 1. 先统一数据库 URL 来源

在引入 Alembic 前，先让 `server/core/database.py` 从环境变量读取数据库 URL，并保留 SQLite 作为本地默认值。

计划目标：

```python
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{(DATA_DIR / 'app.db').as_posix()}",
)
```

注意：这是计划示例，不是当前已实施代码。

### 2. 安装并初始化 Alembic

```powershell
.\.venv\Scripts\python.exe -m pip install alembic
.\.venv\Scripts\python.exe -m alembic init migrations
```

是否把 `alembic` 加入 `requirements.txt`：待确认。实施时必须同步依赖。

### 3. 配置 `alembic/env.py`

需要导入同一份 `Base.metadata`，并确保 ORM 模型被 import：

```python
from server.core.database import Base
from server import models_db

target_metadata = Base.metadata
```

数据库 URL 应从同一套配置读取，避免 app 和 migration 使用不同数据库。

### 4. 建立首次基线

由于当前环境可能已有 `data/app.db`，建议采用“基线迁移 + stamp”的方式。

计划步骤：

```powershell
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "baseline"
.\.venv\Scripts\python.exe -m alembic stamp head
```

对全新环境，需要确认是：

- 继续由 `init_db()` 创建空库，再 `stamp head`。
- 还是完全交给 `alembic upgrade head` 创建 schema。

该选择待确认，不能在没有回滚方案时直接替换启动逻辑。

### 5. 替换 `ensure_user_config_columns()`

目标是把 `ensure_user_config_columns()` 中的列变更迁入 revision 文件，然后从启动路径移除它。

最终启动路径可能变成：

```python
from alembic.config import Config
from alembic import command

cfg = Config("alembic.ini")
command.upgrade(cfg, "head")
```

是否在应用启动时自动跑迁移：待确认。生产环境通常更推荐发布流程显式执行迁移，而不是 Web 进程自行迁移。

## 持续工作流

修改 ORM 后：

```powershell
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "add foo column"
```

人工检查生成文件，然后本地验证：

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic downgrade -1
.\.venv\Scripts\python.exe -m alembic upgrade head
```

## 与共享常量的关系

`server/models/constants.py` 已抽取字段长度常量和枚举值。新增字段时，ORM 和 Pydantic schema 应尽量共享这些常量，减少漂移。

示例：

```python
# models_db.py
from server.models.constants import MAX_TOTP_SECRET_LEN

totp_secret: Mapped[str | None] = mapped_column(
    String(MAX_TOTP_SECRET_LEN),
    nullable=True,
)
```

```python
# models/schemas.py
from server.models.constants import MIN_TOTP_CODE_LEN, MAX_TOTP_CODE_LEN

totp_code: str | None = Field(
    default=None,
    min_length=MIN_TOTP_CODE_LEN,
    max_length=MAX_TOTP_CODE_LEN,
)
```

## 验收标准

迁移完成后，至少应验证：

- 新空库能通过 `alembic upgrade head` 创建完整 schema。
- 旧 SQLite 开发库能安全升级。
- 若支持 PostgreSQL，Docker Compose 环境能连到 PostgreSQL 并完成迁移。
- `pytest server/tests -q --tb=short --ignore=server/tests/test_e2e.py` 通过。
- 迁移文档和 `.env.example` 与实际配置一致。

## 时间线

预计工作量：1 人/天起。当前 M0-01 不实施迁移，只修正文档事实口径。建议作为后续 M2 数据库工单处理。
