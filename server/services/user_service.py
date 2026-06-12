import json
from typing import Any, Callable

from sqlalchemy.orm import Session

from server.core.database import create_log
from server.core.llm_utils import normalize_ai_provider
from server.core.security import _mask_key, _safe_decrypt
from server.models.schemas import UserConfigIn
from server.models_db import User, UserConfig


# Field whitelist: every updatable scalar field on UserConfig, with its
# normalizer. Add a new field here when extending UserConfigIn — no need to
# touch the body of `update_user_config`.
def _normalize_str(value: Any, *, max_length: int | None = None, default: str = "") -> str:
    text = str(value or "").strip()
    if max_length is not None:
        text = text[:max_length]
    return text or default


def _normalize_base_url(value: Any) -> str:
    return str(value or "").strip().rstrip("/")


def _normalize_provider(value: Any) -> str:
    return normalize_ai_provider(value)


def _normalize_int(value: Any) -> int:
    return int(value)


def _normalize_bool(value: Any) -> bool:
    return bool(value)


CONFIG_FIELD_WHITELIST: dict[str, tuple[str, Callable[[Any], Any]]] = {
    "ai_provider": ("ai_provider", _normalize_provider),
    "model": ("model", lambda v: _normalize_str(v, max_length=120)),
    "base_url": ("base_url", _normalize_base_url),
    "timeout_seconds": ("timeout_seconds", _normalize_int),
    "alert_email_enabled": ("alert_email_enabled", _normalize_bool),
    "alert_voice_enabled": ("alert_voice_enabled", _normalize_bool),
    "webhook_url": ("webhook_url", lambda v: _normalize_str(v, max_length=500)),
    "webhook_type": ("webhook_type", lambda v: _normalize_str(v, max_length=16, default="generic")),
    "ui_theme": ("ui_theme", lambda v: _normalize_str(v, max_length=32, default="dark")),
    "ui_density": ("ui_density", lambda v: _normalize_str(v, max_length=16, default="comfortable")),
}


def build_default_config(user_id: int) -> UserConfig:
    from server.core.config import load_timeout_seconds
    return UserConfig(
        user_id=user_id,
        ai_provider="custom",
        model="",
        base_url="",
        timeout_seconds=load_timeout_seconds(),
        alert_email_enabled=True,
        alert_voice_enabled=False,
        ui_theme="dark",
        ui_density="comfortable",
    )


def get_or_create_user_config(db: Session, user_id: int) -> UserConfig:
    config = db.query(UserConfig).filter(UserConfig.user_id == user_id).first()
    if config:
        return config
    config = build_default_config(user_id)
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def get_user_config(user: User, db: Session) -> dict[str, Any]:
    config = get_or_create_user_config(db, user.id)

    try:
        api_key_plain = _safe_decrypt(user.encrypted_api_key)
    except Exception:
        api_key_plain = None

    return {
        "ai_provider": config.ai_provider,
        "model": config.model,
        "base_url": config.base_url,
        "timeout_seconds": config.timeout_seconds,
        "alert_email_enabled": config.alert_email_enabled,
        "alert_voice_enabled": config.alert_voice_enabled,
        "webhook_url": config.webhook_url,
        "webhook_type": config.webhook_type,
        "ui_theme": config.ui_theme,
        "ui_density": config.ui_density,
        "has_api_key": bool(api_key_plain),
        "api_key_masked": _mask_key(api_key_plain),
    }


def update_user_config(user: User, data: UserConfigIn, db: Session) -> dict[str, Any]:
    config = get_or_create_user_config(db, user.id)

    payload = data.model_dump(exclude_none=True)
    log_payload = payload.copy()
    if "api_key" in log_payload:
        log_payload["api_key"] = "***"

    # Walk the whitelist instead of an if-per-field chain. New fields only
    # require a (field, normalizer) entry in CONFIG_FIELD_WHITELIST.
    for key, (attr_name, normalizer) in CONFIG_FIELD_WHITELIST.items():
        if key in payload:
            setattr(config, attr_name, normalizer(payload[key]))

    if "api_key" in payload:
        key_text = str(payload["api_key"]).strip()
        from server.security_utils import encrypt_api_key
        user.encrypted_api_key = encrypt_api_key(key_text) if key_text else user.encrypted_api_key

    db.add(config)
    db.add(user)
    db.commit()
    db.refresh(config)

    create_log(db, user_id=user.id, level="info", action="user_config_update", detail=json.dumps(log_payload, ensure_ascii=False))  # noqa: E501
    return {
        "status": "updated",
        "config": {
            "ai_provider": config.ai_provider,
            "model": config.model,
            "base_url": config.base_url,
            "timeout_seconds": config.timeout_seconds,
            "alert_email_enabled": config.alert_email_enabled,
            "alert_voice_enabled": config.alert_voice_enabled,
            "webhook_url": config.webhook_url,
            "webhook_type": config.webhook_type,
            "ui_theme": config.ui_theme,
            "ui_density": config.ui_density,
            "has_api_key": bool(user.encrypted_api_key),
            "api_key_masked": _mask_key(_safe_decrypt(user.encrypted_api_key)),
        },
    }
