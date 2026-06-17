"""Database engine, session factory, declarative base, schema-versioning helpers.

The single source of truth for:
- SQLAlchemy ``engine`` and ``SessionLocal``
- ``Base`` (declarative base) and ``TimestampMixin``
- ``get_db`` FastAPI dependency
- ``init_db`` / ``ensure_user_config_columns`` (legacy in-place migrations)
- ``create_log`` (transactional) and the async ``enqueue_log`` / ``flush_logs``
  pair used for high-volume paths.

.. note::

   M2-01 之后，``engine`` 不再硬编码 SQLite。它读取 ``DATABASE_URL`` 环境变量；
   未设置时回退到 repo 内 ``data/app.db``。同步 SQLAlchemy engine 收到
   ``sqlite+aiosqlite://`` 会被自动归一化为 ``sqlite:///``。

   Alembic baseline 见 ``docs/ALEMBIC_MIGRATION.md``；本文档只负责运行时 engine 行为。
"""
from __future__ import annotations

import asyncio
import os
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from loguru import logger


# ---- Engine / session factory ----

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def default_database_url() -> str:
    """默认数据库 URL：repo 内 ``data/app.db`` SQLite。

    未设置 ``DATABASE_URL`` 时使用；不依赖当前工作目录，而是基于本文件位置解析。
    """
    return f"sqlite:///{(DATA_DIR / 'app.db').as_posix()}"


def load_database_url() -> str:
    """从 ``DATABASE_URL`` 环境变量加载数据库 URL，未设置时回退到默认 SQLite。

    返回的 URL 不一定同步 engine 友好 — 若含有 ``sqlite+aiosqlite://``，调用方
    应再走 ``normalize_database_url``。
    """
    env = os.getenv("DATABASE_URL", "").strip()
    if env:
        return env
    return default_database_url()


def normalize_database_url(url: str) -> str:
    """把 SQLAlchemy URL 归一化为同步 engine 友好形式。

    - ``sqlite+aiosqlite:///...`` → ``sqlite:///...``（同步 engine 不支持 aiosqlite）
    - ``sqlite:///...`` 原样返回
    - 其他 driver（含 ``postgresql+psycopg://``、``postgresql+psycopg2://`` 等）原样返回

    不在此处做绝对路径展开；不连接数据库。
    """
    if url.startswith("sqlite+aiosqlite://"):
        return "sqlite://" + url[len("sqlite+aiosqlite://"):]
    return url


def build_engine_kwargs(url: str) -> dict[str, Any]:
    """根据 URL 构造 ``create_engine`` 的 kwargs。

    - SQLite 必须带 ``connect_args={"check_same_thread": False}``；
    - 其他 dialect 不应加 ``check_same_thread``（PostgreSQL 没有这个概念）；
    - 池参数与原实现保持一致。
    """
    is_sqlite = url.startswith("sqlite://")
    connect_args: dict[str, Any] = {"check_same_thread": False} if is_sqlite else {}
    return {
        "connect_args": connect_args,
        "pool_size": 5,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_recycle": 1800,
    }


def create_app_engine(url: str | None = None):
    """构造应用 engine。

    流程：``url or load_database_url()`` → ``normalize_database_url`` → ``build_engine_kwargs`` →
    ``sqlalchemy.create_engine``。失败时让 SQLAlchemy 异常自然向上抛出；本函数不静默
    降级到 SQLite 之类的掩盖行为。
    """
    target = normalize_database_url(url or load_database_url())
    try:
        return create_engine(target, **build_engine_kwargs(target))
    except ArgumentError:
        # SQLAlchemy 自身会清晰报错；不再二次包装
        raise


# Module-level engine / session factory. ``engine`` 在 import 时基于 ``DATABASE_URL``
# 初始化。``DATABASE_URL`` 后续改变需要 ``importlib.reload(server.core.database)``
# 才会生效（测试可用），运行时改 env 不会自动换库。
engine = create_app_engine()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ---- Declarative base + timestamp mixin ----

class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)


# ---- FastAPI dependency ----

def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """``Base.metadata.create_all`` 启动期建表。

    注意：M2-01 之后，``init_db()`` 仍保留作为新空库的"快速回退"路径；
    schema 变更的主路径是 Alembic revision（``alembic upgrade head``）。
    """
    Base.metadata.create_all(bind=engine)


# ---- Audit logging ----

def create_log(db: Session, *, user_id: int | None = None, level: str = "info",
               action: str, detail: str = "", ip_address: str | None = None) -> None:
    """Synchronous, transactional log write. Use `enqueue_log` for high-volume paths."""
    # Import inside the function to avoid a circular import at module load
    # (models_db imports Base from this module).
    from server.models_db import Log
    entry = Log(user_id=user_id, level=level, action=action, detail=detail, ip_address=ip_address)
    db.add(entry)
    db.commit()


# ---- 批量异步日志 ----
# 在高吞吐场景下（例如告警风暴），每条 log 单独 commit 会触发 SQLite 写锁
# 竞争。`enqueue_log` 把日志条目加入内存队列，由后台任务周期性 flush。
_LOG_QUEUE: deque[dict[str, Any]] = deque(maxlen=10_000)
_LOG_FLUSH_BATCH = 200
_LOG_FLUSH_INTERVAL_SECONDS = 1.0
_LOG_FLUSH_TASK: asyncio.Task[None] | None = None
_LOG_FLUSH_LOCK = asyncio.Lock()


def enqueue_log(*, user_id: int | None = None, level: str = "info",
                action: str, detail: str = "", ip_address: str | None = None) -> None:
    """Buffer a log entry for batched insertion.

    The queue is bounded (10k entries). Under sustained overflow the oldest
    entries are dropped — call sites should use this only for routine
    high-volume events (alert pipeline, monitor ticks). Audit-grade events
    (auth, config change) should still use `create_log` for durability.
    """
    if len(_LOG_QUEUE) >= _LOG_QUEUE.maxlen:
        logger.warning("log queue overflow — dropping oldest entry")
    _LOG_QUEUE.append({
        "user_id": user_id,
        "level": level,
        "action": action,
        "detail": detail,
        "ip_address": ip_address,
    })


async def _log_flush_loop() -> None:
    """Periodically drain the in-memory log queue into the database."""
    while True:
        await asyncio.sleep(_LOG_FLUSH_INTERVAL_SECONDS)
        await flush_logs()


async def flush_logs() -> int:
    """Drain queued log entries in a single transaction. Returns the count flushed."""
    if not _LOG_QUEUE:
        return 0
    async with _LOG_FLUSH_LOCK:
        batch: list[dict[str, Any]] = []
        while _LOG_QUEUE and len(batch) < _LOG_FLUSH_BATCH:
            batch.append(_LOG_QUEUE.popleft())
    if not batch:
        return 0
    try:
        db = SessionLocal()
        try:
            from server.models_db import Log
            db.bulk_insert_mappings(Log, batch)
            db.commit()
            return len(batch)
        finally:
            db.close()
    except Exception as exc:
        logger.warning("batch log flush failed count={} err={}", len(batch), exc)
        return 0


def start_log_flusher() -> None:
    """Spawn the background flush task. Idempotent."""
    global _LOG_FLUSH_TASK
    if _LOG_FLUSH_TASK is not None and not _LOG_FLUSH_TASK.done():
        return
    _LOG_FLUSH_TASK = asyncio.create_task(_log_flush_loop())


def stop_log_flusher() -> None:
    """Cancel the background flush task. Pending entries are flushed on next start."""
    global _LOG_FLUSH_TASK
    if _LOG_FLUSH_TASK is None:
        return
    _LOG_FLUSH_TASK.cancel()
    _LOG_FLUSH_TASK = None


# ---- Lightweight in-place migrations (legacy compatibility) ----
# TODO(M4): 全部 ALTER TABLE 迁入 Alembic revision 后，从启动路径移除
# ``ensure_user_config_columns``。当前保留作为旧 SQLite 开发库的"原地升级"兼容层。
# 新 schema 变更必须走 Alembic（``alembic revision --autogenerate``），不要往这里
# 加新 ALTER。

def ensure_user_config_columns() -> None:
    """Legacy 启动期 ALTER TABLE 兼容层。

    保留原因：旧本地开发库 ``data/app.db`` 是在 ``init_db()`` 基础上由这些 ALTER
    逐步补列形成的；Alembic baseline 落地后，新环境会直接由 ``alembic upgrade head``
    建出完整 schema，但旧 ``data/app.db`` 仍可能需要这套幂等 ALTER。

    语句都包了 try/except；"already exists" / "duplicate" 错误被吞掉，其他错误
    记 warning，不让启动失败。
    """
    statements = [
        "ALTER TABLE user_configs ADD COLUMN ai_provider VARCHAR(24) NOT NULL DEFAULT 'openai'",
        "ALTER TABLE users ADD COLUMN password_changed_at DATETIME NULL",
        "ALTER TABLE users ADD COLUMN role VARCHAR(16) NOT NULL DEFAULT 'analyst'",
        "ALTER TABLE user_configs ADD COLUMN webhook_url VARCHAR(500) NOT NULL DEFAULT ''",
        "ALTER TABLE user_configs ADD COLUMN webhook_type VARCHAR(16) NOT NULL DEFAULT 'generic'",
        "ALTER TABLE users ADD COLUMN totp_secret VARCHAR(64) NULL",
        "ALTER TABLE users ADD COLUMN totp_enabled BOOLEAN NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN login_notify_enabled BOOLEAN NOT NULL DEFAULT 1",
        "ALTER TABLE users ADD COLUMN last_login_at DATETIME NULL",
        "ALTER TABLE users ADD COLUMN last_login_ip VARCHAR(64) NULL",
    ]
    with engine.begin() as conn:
        for sql in statements:
            try:
                conn.execute(text(sql))
            except Exception as exc:
                err_msg = str(exc).lower()
                if "already exists" not in err_msg and "duplicate" not in err_msg:
                    logger.warning(
                        "ALTER failed: sql={} err_type={} err_msg={}",
                        sql[:60], type(exc).__name__, str(exc)[:200])
