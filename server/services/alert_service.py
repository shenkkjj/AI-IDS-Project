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

    # Single JOIN to load user + config in one round-trip (was N+1 with two
    # sequential queries). `contains_eager` tells SQLAlchemy the relationship
    # is already populated so it does not lazy-load `config` again below.
    db = SessionLocal()
    try:
        from sqlalchemy.orm import joinedload
        user = (
            db.query(User)
            .options(joinedload(User.config))
            .filter(User.id == alert_user_id, User.is_active.is_(True))
            .first()
        )
        if user is None:
            return
        config = getattr(user, "config", None)
        if config is None or not config.alert_email_enabled:
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


DEMO_ATTACK_SCENARIOS: dict[str, dict[str, Any]] = {
    "sql_injection": {
        "event": "waf_block",
        "source_ip": "203.0.113.45",
        "destination_ip": "10.0.0.15",
        "payload": "' UNION SELECT username,password FROM users --",
        "model_probability": 0.98,
        "blocked": True,
        "risk_level": "critical",
        "summary": "Demo 攻击：WAF 拦截到疑似 SQL 注入，攻击者尝试枚举用户凭据。",
        "recommended_actions": [
            "确认目标接口已使用参数化查询",
            "检查同源 IP 是否还有扫描或撞库行为",
            "保留载荷与访问日志用于复盘",
        ],
    },
    "xss": {
        "event": "waf_block",
        "source_ip": "198.51.100.23",
        "destination_ip": "10.0.0.22",
        "payload": "<script>fetch('/session')</script>",
        "model_probability": 0.92,
        "blocked": True,
        "risk_level": "high",
        "summary": "Demo 攻击：WAF 拦截到脚本注入载荷，疑似尝试窃取会话信息。",
        "recommended_actions": [
            "检查受影响页面是否正确转义用户输入",
            "确认 CSP 与 HttpOnly cookie 配置",
            "搜索相同 payload 是否重复出现",
        ],
    },
    "scanner": {
        "event": "anomaly",
        "source_ip": "192.0.2.88",
        "destination_ip": "10.0.0.10",
        "payload": "nmap scan /admin /wp-login.php /phpmyadmin",
        "model_probability": 0.81,
        "blocked": False,
        "risk_level": "medium",
        "summary": "Demo 事件：检测到自动化路径扫描，建议关注后续爆破或漏洞利用尝试。",
        "recommended_actions": [
            "启用路径访问频率限制",
            "确认管理入口不暴露在公网",
            "将来源 IP 加入观察列表",
        ],
    },
}


async def trigger_demo_attack(*, user_id: int, scenario: str) -> dict[str, Any]:
    """Create a deterministic demo alert for the current authenticated user."""
    template = DEMO_ATTACK_SCENARIOS[scenario]
    now = time.time()
    alert = AlertIn(
        event=template["event"],
        source_ip=template["source_ip"],
        destination_ip=template["destination_ip"],
        payload=template["payload"],
        alert_user_id=user_id,
        timestamp=now,
        model_probability=template["model_probability"],
        blocked=template["blocked"],
        block_expires_at=now + 1800 if template["blocked"] else None,
    )
    payload = {
        "alert_id": uuid.uuid4().hex,
        "raw_alert": alert.model_dump(),
        "llm_analysis": {
            "risk_level": template["risk_level"],
            "summary": template["summary"],
            "recommended_actions": template["recommended_actions"],
            "demo_mode": True,
        },
        "analysis_error": None,
        "processed_at": now,
        "demo": {
            "scenario": scenario,
            "story": "模拟攻击 -> 告警入队 -> Dashboard 展示 -> Copilot 告警上下文",
        },
    }

    await app_state.alert.append_backlog(payload)
    await manager.broadcast_json(user_id, payload)
    return payload


def build_demo_copilot_state(user: User, db) -> dict[str, Any]:
    from server.core.llm_utils import user_config_to_llm_runtime
    from server.services.user_service import get_or_create_user_config

    config = get_or_create_user_config(db, user.id)
    runtime, provider = user_config_to_llm_runtime(config, user)
    ready = bool(runtime.api_key and runtime.base_url)
    return {
        "ready": ready,
        "provider": provider,
        "model": runtime.model,
        "fallback_reason": None if ready else "missing_api_key_or_base_url",
        "next_action": (
            "点击 AI 助手中的“分析当前告警”获取流式分析。"
            if ready
            else "演示闭环已生成告警；如需真实 AI 分析，请先在配置页设置可用的 API Key 与 Base URL。"
        ),
    }
