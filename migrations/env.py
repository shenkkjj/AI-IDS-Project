"""Alembic env:加载 server.core.database 的 Base + ORM models，从 DATABASE_URL 读 URL。

设计要点（docs/agent/M2_01_DATABASE_URL_ALEMBIC_BASELINE_TASK.md §4 阶段 4）：

- 走 ``server.core.database.load_database_url`` 同一份事实来源，避免 app 与
  migration 用两套配置；
- ``target_metadata`` 直接绑 ``Base.metadata``，autogenerate 能 diff 真实 ORM；
- ``sqlalchemy.url`` 不在 alembic.ini hardcode，env.py 调
  ``context.config.set_main_option`` 覆盖。
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# 让 ``from server.core.database import ...`` 能解析到 repo 根
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 加载 ORM metadata
from server.core.database import (  # noqa: E402
    Base,
    load_database_url,
    normalize_database_url,
)

# 确保 models_db 被 import，metadata 里才能看到表
import server.models_db  # noqa: F401,E402

target_metadata = Base.metadata


def _resolve_url() -> str:
    """从 env 读 DATABASE_URL，缺省时回退到 server.core.database 的默认 SQLite。"""
    return normalize_database_url(load_database_url())


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    只用 URL，不创建 Engine。Emit SQL 语句到脚本输出。
    """
    url = _resolve_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    用 ``_resolve_url`` 构造 engine。
    """
    # 通过 config 注入 url，让 engine_from_config 能正确解析
    config.set_main_option("sqlalchemy.url", _resolve_url())
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
