"""Database engine, session factory, declarative base, schema-versioning helpers.

The single source of truth for:
- SQLAlchemy `engine` and `SessionLocal`
- `Base` (declarative base) and `TimestampMixin`
- `get_db` FastAPI dependency
- `init_db` / `ensure_user_config_columns` (lightweight in-place migrations)
- `create_log` (transactional) and the async `enqueue_log` / `flush_logs`
  pair used for high-volume paths.
"""
from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from loguru import logger


# ---- Engine / session factory ----

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{(DATA_DIR / 'app.db').as_posix()}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
)

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


# ---- Lightweight in-place migrations ----
# TODO(M4): replace with Alembic once the schema stabilises. These statements
# are idempotent (each catches "already exists" / "duplicate" errors) so they
# are safe to run on every startup.

def ensure_user_config_columns() -> None:
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
