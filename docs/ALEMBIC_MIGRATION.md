# Alembic 迁移计划

> M4 子任务：当前使用 `ensure_user_config_columns()` 中的手写 ALTER TABLE，未来切换到 Alembic 的计划。

## 当前状态

`server/core/database.py` 包含 `ensure_user_config_columns()`，启动时执行一组幂等的
`ALTER TABLE` 语句。每个新列都要在这里加一行，可控性差，且无法回滚。

## 切换步骤

### 1. 安装

```bash
cd server
pip install alembic
alembic init alembic
```

### 2. 配置 `alembic/env.py`

```python
from server.core.database import Base
from server import models_db  # 确保模型被 import
target_metadata = Base.metadata
```

数据库 URL 从 `DATABASE_URL` 环境变量读取。

### 3. 首次基线

由于 `init_db()` 已经会执行 `Base.metadata.create_all`，先：
- 保留 `init_db()` 用于全新部署
- 第一次 `alembic revision --autogenerate -m "baseline"` 生成基线迁移
- 将基线迁移标记为已应用：`alembic stamp head`

### 4. 替换 ensure_user_config_columns

删除 `ensure_user_config_columns()`，在 `main.py` 启动时改为：

```python
from alembic.config import Config
from alembic import command
cfg = Config("alembic.ini")
command.upgrade(cfg, "head")
```

### 5. 持续工作流

```bash
# 修改 ORM 后
alembic revision --autogenerate -m "add foo column"
# 编辑生成的迁移文件
alembic upgrade head    # 本地
alembic downgrade -1    # 验证可回滚
```

## 共享受限（已完成）

`server/models/constants.py` 已抽取所有字段长度常量和枚举值。
Pydantic schemas 和 SQLAlchemy ORM 都应从这里 import，避免双向漂移。

迁移到 Alembic 后，新增列只要在 `models_db.py` 和 `models/schemas.py`
中用同一组常量即可：

```python
# models_db.py
from server.models.constants import MAX_TOTP_SECRET_LEN
totp_secret: Mapped[str | None] = mapped_column(String(MAX_TOTP_SECRET_LEN), nullable=True)

# models/schemas.py
from server.models.constants import MIN_TOTP_CODE_LEN, MAX_TOTP_CODE_LEN
totp_code: str | None = Field(default=None, min_length=MIN_TOTP_CODE_LEN, max_length=MAX_TOTP_CODE_LEN)
```

## 时间线

预计工作量：1 人/天。不在本批改进内，留待后续 sprint。
