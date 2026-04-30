from sqlalchemy.orm import Session
from server.db import SessionLocal, engine
from server.models_db import Base, Log
from sqlalchemy import text
from loguru import logger


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def create_log(db: Session, *, user_id: int | None = None, level: str = "info", action: str, detail: str = "", ip_address: str | None = None) -> None:
    entry = Log(user_id=user_id, level=level, action=action, detail=detail, ip_address=ip_address)
    db.add(entry)
    db.commit()


def ensure_user_config_columns() -> None:
    statements = [
        "ALTER TABLE user_configs ADD COLUMN ai_provider VARCHAR(24) NOT NULL DEFAULT 'openai'",
        "ALTER TABLE users ADD COLUMN password_changed_at DATETIME NULL",
    ]
    with engine.begin() as conn:
        for sql in statements:
            try:
                conn.execute(text(sql))
            except Exception as exc:
                err_msg = str(exc).lower()
                if "already exists" not in err_msg and "duplicate" not in err_msg:
                    logger.warning("ALTER failed: {} err={}", sql.strip(), exc)
