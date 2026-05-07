import asyncio
import csv
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi.concurrency import run_in_threadpool
from loguru import logger

from server.analyzer import LLMAnalyzer
from server.core.config import ALERT_BACKLOG_SIZE, ALERT_EMAIL_COOLDOWN_SECONDS
from server.core.database import SessionLocal
from server.services.llm_service import get_runtime_llm_config
from server.core.state import app_state
from server.mailer import send_alert_email
from server.models.schemas import AlertIn
from server.models_db import User, UserConfig
from server.core.websocket import manager


def _feature_value(raw: dict[str, Any], key: str) -> Any:
    feature_values = raw.get("feature_values") or {}
    if key in feature_values:
        return feature_values.get(key)
    return ""


async def append_new_threat_csv(payload: dict[str, Any], label: str) -> None:
    raw = payload.get("raw_alert") or {}
    from models.train import FEATURE_COLUMNS
    path = Path(__file__).resolve().parents[2] / "data" / "new_threats.csv"
    path.parent.mkdir(parents=True, exist_ok=True)

    header = [
        "alert_id",
        "label",
        "confirmed_at",
        "source_ip",
        "destination_ip",
        "payload",
        "model_probability",
        "blocked",
        "block_expires_at",
        *FEATURE_COLUMNS,
    ]

    row = {
        "alert_id": payload.get("alert_id", ""),
        "label": label,
        "confirmed_at": time.time(),
        "source_ip": raw.get("source_ip", ""),
        "destination_ip": raw.get("destination_ip", ""),
        "payload": raw.get("payload", ""),
        "model_probability": raw.get("model_probability"),
        "blocked": raw.get("blocked", False),
        "block_expires_at": raw.get("block_expires_at"),
    }

    for feature_name in FEATURE_COLUMNS:
        row[feature_name] = _feature_value(raw, feature_name)

    async with (
        app_state.rate_limit._new_threats_lock
        if hasattr(app_state.rate_limit, '_new_threats_lock')
        else asyncio.Lock()
    ):
        exists = path.exists()
        with path.open("a", encoding="utf-8", newline="") as fp:
            writer = csv.DictWriter(fp, fieldnames=header)
            if not exists:
                writer.writeheader()
            writer.writerow(row)


async def find_alert_by_id(alert_id: str, *, user_id: int | None = None) -> dict[str, Any] | None:
    async with app_state.alert.backlog_lock:
        for item in app_state.alert.backlog:
            if str(item.get("alert_id", "")) != alert_id:
                continue
            if user_id is None:
                return item
            raw_alert = item.get("raw_alert") or {}
            if raw_alert.get("alert_user_id") == user_id:
                return item
    return None


async def process_alert(alert: AlertIn) -> dict[str, Any]:
    analysis: dict[str, Any] | None = None
    analysis_error: str | None = None

    try:
        config = await get_runtime_llm_config()
        if not config.api_key or not config.base_url:
            raise ValueError("Missing LLM_API_KEY or LLM_BASE_URL environment variables.")

        analyzer = LLMAnalyzer(config=config)
        analysis = await run_in_threadpool(
            analyzer.analyze_alert,
            alert.source_ip,
            alert.destination_ip,
            alert.payload,
        )
    except Exception as exc:
        analysis_error = str(exc)
        logger.exception("LLM analysis failed: {}", exc)

    return {
        "alert_id": uuid.uuid4().hex,
        "raw_alert": alert.model_dump(),
        "llm_analysis": analysis,
        "analysis_error": analysis_error,
        "processed_at": time.time(),
    }


async def _should_send_alert_email(user_id: int) -> bool:
    async with app_state.alert.email_lock:
        last_sent = app_state.alert.email_last_sent.get(user_id, 0)
        if time.time() - last_sent < ALERT_EMAIL_COOLDOWN_SECONDS:
            return False
        app_state.alert.email_last_sent[user_id] = time.time()
        return True


async def _send_alert_email_if_enabled(payload: dict[str, Any]) -> None:
    raw_alert = payload.get("raw_alert") or {}
    alert_user_id = int(raw_alert.get("alert_user_id") or 0)
    if alert_user_id <= 0:
        return

    if not await _should_send_alert_email(alert_user_id):
        return

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == alert_user_id, User.is_active.is_(True)).first()
        if not user:
            return

        config = db.query(UserConfig).filter(UserConfig.user_id == alert_user_id).first()
        if not config or not config.alert_email_enabled:
            return

        llm_analysis = payload.get("llm_analysis") or {}
        risk_level = str(llm_analysis.get("risk_level") or "high").lower()

        await send_alert_email(
            email=user.email,
            alert_type=str(raw_alert.get("event") or "unknown"),
            source_ip=str(raw_alert.get("source_ip") or "unknown"),
            destination=str(raw_alert.get("destination_ip") or "unknown"),
            payload=str(raw_alert.get("payload") or ""),
            risk_level=risk_level,
            blocked=bool(raw_alert.get("blocked")),
        )
        logger.info("Alert email sent user_id={} email={}", alert_user_id, user.email)
    except Exception as exc:
        logger.warning("Alert email failed user_id={} err={}", alert_user_id, exc)
    finally:
        db.close()


async def alert_worker(worker_id: int) -> None:
    logger.info("Alert worker started id={}", worker_id)
    while True:
        alert = await app_state.alert.queue.get()
        try:
            payload = await process_alert(alert)
            await app_state.alert.append_backlog(payload)
            alert_user_id = int((payload.get("raw_alert") or {}).get("alert_user_id") or 0)
            if alert_user_id > 0:
                await manager.broadcast_json(alert_user_id, payload)
                await _send_alert_email_if_enabled(payload)
        except Exception as exc:
            logger.exception("Alert worker failed id={} err={}", worker_id, exc)
        finally:
            app_state.alert.queue.task_done()


async def get_alerts(user_id: int, limit: int = 100) -> dict[str, Any]:
    backlog = await app_state.alert.get_backlog_snapshot()
    user_items = [item for item in backlog if (item.get("raw_alert") or {}).get("alert_user_id") == user_id]
    bounded = max(1, min(limit, ALERT_BACKLOG_SIZE))
    return {
        "items": user_items[-bounded:],
        "count": len(user_items),
    }


async def receive_alert(alert: AlertIn, request) -> dict[str, Any]:
    from server.core.utils import _is_allowed_alert_ingest_source
    if not _is_allowed_alert_ingest_source(request):
        raise Exception("Alert ingest source is not allowed")

    accepted, replaced_oldest = app_state.alert.enqueue_alert(alert)
    if not accepted:
        raise Exception("Alert queue is full")

    return {
        "status": "accepted",
        "queued": True,
        "received_at": time.time(),
        "replaced_oldest": replaced_oldest,
    }
