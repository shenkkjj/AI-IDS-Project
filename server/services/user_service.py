import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from server.core.config import PROVIDER_BASE_URL_DEFAULTS, PROVIDER_MODEL_DEFAULTS
from server.core.database import create_log
from server.core.llm_utils import choose_provider, normalize_ai_provider
from server.core.security import _mask_key, _safe_decrypt
from server.models.schemas import UserConfigIn
from server.models_db import User, UserConfig


def build_default_config(user_id: int) -> UserConfig:
    from server.core.config import load_timeout_seconds
    return UserConfig(
        user_id=user_id,
        ai_provider="openai",
        model="gpt-4o-mini",
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

    provider = choose_provider(getattr(config, "ai_provider", None), config.model, config.base_url)
    return {
        "ai_provider": provider,
        "model": config.model,
        "base_url": config.base_url,
        "timeout_seconds": config.timeout_seconds,
        "alert_email_enabled": config.alert_email_enabled,
        "alert_voice_enabled": config.alert_voice_enabled,
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
    if "ai_provider" in payload:
        config.ai_provider = normalize_ai_provider(payload["ai_provider"])
    if "model" in payload:
        config.model = str(payload["model"]).strip() or config.model
    if "base_url" in payload:
        config.base_url = str(payload["base_url"]).strip().rstrip("/")
    if "timeout_seconds" in payload:
        config.timeout_seconds = int(payload["timeout_seconds"])
    if "alert_email_enabled" in payload:
        config.alert_email_enabled = bool(payload["alert_email_enabled"])
    if "alert_voice_enabled" in payload:
        config.alert_voice_enabled = bool(payload["alert_voice_enabled"])
    if "ui_theme" in payload:
        config.ui_theme = str(payload["ui_theme"]).strip() or config.ui_theme
    if "ui_density" in payload:
        config.ui_density = str(payload["ui_density"]).strip() or config.ui_density

    if "api_key" in payload:
        key_text = str(payload["api_key"]).strip()
        from server.security_utils import encrypt_api_key
        user.encrypted_api_key = encrypt_api_key(key_text) if key_text else user.encrypted_api_key

    provider = choose_provider(config.ai_provider, config.model, config.base_url)
    config.ai_provider = provider
    if not config.base_url:
        config.base_url = PROVIDER_BASE_URL_DEFAULTS[provider]
    if not config.model:
        config.model = PROVIDER_MODEL_DEFAULTS[provider]

    db.add(config)
    db.add(user)
    db.commit()
    db.refresh(config)

    create_log(db, user_id=user.id, level="info", action="user_config_update", detail=json.dumps(log_payload, ensure_ascii=False))
    return {
        "status": "updated",
        "config": {
            "ai_provider": provider,
            "model": config.model,
            "base_url": config.base_url,
            "timeout_seconds": config.timeout_seconds,
            "alert_email_enabled": config.alert_email_enabled,
            "alert_voice_enabled": config.alert_voice_enabled,
            "ui_theme": config.ui_theme,
            "ui_density": config.ui_density,
            "has_api_key": bool(user.encrypted_api_key),
            "api_key_masked": _mask_key(_safe_decrypt(user.encrypted_api_key)),
        },
    }
