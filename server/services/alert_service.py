"""告警服务 (M3-02 + M3-03)。

设计要点 (docs/agent/M3_02_*.md §3, M3_03_*.md §4/§5):

- M3-02: ``PATCH /alerts/{alert_id}/triage`` 状态保存到 ``app_state.alert.backlog``
  payload 中,跨重启不保留;5 个稳定状态 (``new / investigating / contained /
  false_positive / resolved``);``analyst_note`` 800 字上限;``Log(action=
  "alert_triage_update")`` 写脱敏审计。
- M3-03:
  - ``alert_records`` 是告警快照事实来源(``(user_id, alert_id)`` 唯一),
    保存 raw alert JSON、LLM analysis JSON、analysis error、processed_at、
    **最新 triage 字段**。``GET /alerts`` 重启后从它读。
  - ``alert_triage_events`` 是 triage 历史事实来源;每次 PATCH 写一条。
    ``GET /alerts/{alert_id}/triage/history`` 走它。
  - JSON 存 ``Text`` (``json.dumps(..., ensure_ascii=False)``),
    反序列化失败回退空 dict + warning,不让 ``GET /alerts`` 整体失败。
  - 内存 ``app_state.alert.backlog`` 仍用于 WebSocket 实时推送和 worker 缓存;
    持久化失败时回退 backlog 不可阻挡主请求(仅 worker ingest 路径)。
  - owner 隔离: ``(user_id, alert_id)`` 严格匹配;非 owner / 不存在统一返回 None,
    路由层映射为 404,不暴露 alert_id 是否存在。
  - 审计 ``Log`` 仅含脱敏摘要,不含完整 payload / note / secret / stack trace。
"""
import asyncio
import csv
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.concurrency import run_in_threadpool
from loguru import logger
from sqlalchemy.orm import Session

from server.analyzer import LLMAnalyzer
from server.core.config import ALERT_BACKLOG_SIZE, ALERT_EMAIL_COOLDOWN_SECONDS
from server.core.database import SessionLocal
from server.services.llm_service import get_runtime_llm_config
from server.core.state import app_state
from server.mailer import send_alert_email
from server.models.schemas import AlertIn, AlertTriageUpdateIn
from server.models_db import AlertRecord, AlertTriageEvent, User, UserConfig
from server.core.websocket import manager


# ---------------------------------------------------------------------------
# 告警研判 (M3-02 + M3-03)
# ---------------------------------------------------------------------------

_TRIAGE_DEFAULT_STATUS = "new"
_TRIAGE_AUDIT_ACTION = "alert_triage_update"


def default_alert_triage() -> dict[str, Any]:
    """新告警的默认 triage 字段。"""

    return {
        "status": _TRIAGE_DEFAULT_STATUS,
        "disposition": None,
        "analyst_note": None,
        "updated_at": 0,
        "updated_by": None,
    }


def _ensure_triage(payload: dict[str, Any]) -> dict[str, Any]:
    """确保 payload 含 triage 字段(旧告警自动补默认)."""

    if "triage" not in payload or not isinstance(payload.get("triage"), dict):
        payload["triage"] = default_alert_triage()
    return payload


def _epoch_to_dt(value: float | int | None) -> datetime | None:
    """``time.time()`` 秒级时间戳转 naive UTC ``datetime``。"""
    if value is None or not value:
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError, OSError):
        return None


def _dt_to_epoch(value: datetime | None) -> float:
    if value is None:
        return 0.0
    return float(value.replace(tzinfo=timezone.utc).timestamp())


def _json_dumps(obj: Any) -> str:
    """JSON 序列化 helper:``ensure_ascii=False`` 保留中文等。"""
    return json.dumps(obj, ensure_ascii=False, default=str)


def _json_loads_dict(text: str | None) -> dict[str, Any]:
    """反序列化为 dict;失败返回空 dict,不抛。"""
    if not text:
        return {}
    try:
        result = json.loads(text)
        return result if isinstance(result, dict) else {}
    except (TypeError, ValueError):
        return {}


def _build_audit_detail(
    *,
    alert_id: str,
    status: str,
    disposition: str | None,
    note_length: int,
    source_ip: str | None,
) -> str:
    """构造脱敏的审计 detail(不写完整 payload / note / secret)."""

    src = ""
    if source_ip:
        src = source_ip
    parts = [
        f"alert_id={alert_id}",
        f"status={status}",
        f"disposition={disposition or ''}",
        f"note_length={note_length}",
    ]
    if src:
        parts.append(f"source_ip={src}")
    return ";".join(parts)


# ---------------------------------------------------------------------------
# M3-03 持久化 helpers
# ---------------------------------------------------------------------------


def _payload_user_id(payload: dict[str, Any]) -> int:
    raw = payload.get("raw_alert") or {}
    try:
        return int(raw.get("alert_user_id") or 0)
    except (TypeError, ValueError):
        return 0


def _record_to_payload(record: AlertRecord) -> dict[str, Any]:
    """DB record → 前端 / 路由识别的 backend alert payload。"""
    raw = _json_loads_dict(record.raw_alert_json)
    analysis = _json_loads_dict(record.llm_analysis_json)
    processed_at_epoch = _dt_to_epoch(record.processed_at)
    triage = {
        "status": record.triage_status or _TRIAGE_DEFAULT_STATUS,
        "disposition": record.triage_disposition,
        "analyst_note": record.triage_note,
        "updated_at": _dt_to_epoch(record.triage_updated_at),
        "updated_by": int(record.triage_updated_by) if record.triage_updated_by else None,
    }
    return {
        "alert_id": record.alert_id,
        "raw_alert": raw,
        "llm_analysis": analysis,
        "analysis_error": record.analysis_error,
        "processed_at": processed_at_epoch,
        "triage": triage,
    }


def _build_record_defaults(payload: dict[str, Any], user_id: int) -> dict[str, Any]:
    """从 payload 抽取 AlertRecord 字段默认值;不调用 ``_ensure_triage`` 以保留 DB 写入语义。"""
    raw = payload.get("raw_alert") or {}
    analysis = payload.get("llm_analysis")
    return {
        "raw_alert_json": _json_dumps(raw),
        "llm_analysis_json": _json_dumps(analysis) if analysis is not None else None,
        "analysis_error": payload.get("analysis_error"),
        "processed_at": _epoch_to_dt(payload.get("processed_at")) or _epoch_to_dt(time.time()),
    }


def _triage_from_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    triage = payload.get("triage")
    if not isinstance(triage, dict):
        return None
    return {
        "status": triage.get("status") or _TRIAGE_DEFAULT_STATUS,
        "disposition": triage.get("disposition"),
        "analyst_note": triage.get("analyst_note"),
        "updated_at": _epoch_to_dt(triage.get("updated_at")),
        "updated_by": triage.get("updated_by"),
    }


def persist_alert_record(
    db: Session,
    payload: dict[str, Any],
    user_id: int,
) -> int:
    """把告警 payload 写入 ``alert_records``(upsert by user_id+alert_id)。

    - 已存在 record:保留历史 triage 字段(让 update_alert_triage 单独写 history),
      重新写 ``raw_alert_json / llm_analysis_json / analysis_error / processed_at``。
    - 新 record:默认 ``triage_status='new'``。
    - 返回 record.id。
    """
    alert_id = str(payload.get("alert_id") or uuid.uuid4().hex)
    payload = {**payload, "alert_id": alert_id}
    raw_alert = payload.get("raw_alert") or {}
    if not raw_alert.get("alert_user_id"):
        raw_alert = {**raw_alert, "alert_user_id": int(user_id)}
    payload = {**payload, "raw_alert": raw_alert}

    record = (
        db.query(AlertRecord)
        .filter(AlertRecord.user_id == int(user_id), AlertRecord.alert_id == alert_id)
        .first()
    )
    defaults = _build_record_defaults(payload, user_id)
    if record is None:
        record = AlertRecord(
            user_id=int(user_id),
            alert_id=alert_id,
            triage_status=_TRIAGE_DEFAULT_STATUS,
            **defaults,
        )
        db.add(record)
    else:
        # 保留历史 triage 字段;只刷新原始 alert 内容
        record.raw_alert_json = defaults["raw_alert_json"]
        record.llm_analysis_json = defaults["llm_analysis_json"]
        record.analysis_error = defaults["analysis_error"]
        record.processed_at = defaults["processed_at"]
    db.flush()
    return int(record.id)


def list_alert_records(
    db: Session,
    user_id: int,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """从 DB 读 user 全部 alert record(按 processed_at desc),反序列化为 payload。"""
    bounded = max(1, min(int(limit), ALERT_BACKLOG_SIZE))
    records = (
        db.query(AlertRecord)
        .filter(AlertRecord.user_id == int(user_id))
        .order_by(AlertRecord.processed_at.desc(), AlertRecord.id.desc())
        .limit(bounded)
        .all()
    )
    # API 返回顺序: 旧 -> 新, 与原 backlog 行为保持一致
    return [_record_to_payload(r) for r in reversed(records)]


def get_alert_triage_history(
    db: Session,
    user_id: int,
    alert_id: str,
    limit: int = 50,
) -> list[dict[str, Any]] | None:
    """读取 triage 历史。

    - 找不到 record / 非 owner → 返回 ``None``(路由层映射为 404)。
    - 返回 list[newest-first],每条含 ``id / from_status / to_status / disposition /
      analyst_note / updated_by / created_at``。
    """
    record = (
        db.query(AlertRecord)
        .filter(AlertRecord.user_id == int(user_id), AlertRecord.alert_id == str(alert_id))
        .first()
    )
    if record is None:
        return None
    bounded = max(1, min(int(limit), 100))
    events = (
        db.query(AlertTriageEvent)
        .filter(
            AlertTriageEvent.alert_record_id == int(record.id),
            AlertTriageEvent.user_id == int(user_id),
        )
        .order_by(AlertTriageEvent.created_at.desc(), AlertTriageEvent.id.desc())
        .limit(bounded)
        .all()
    )
    return [
        {
            "id": int(ev.id),
            "from_status": ev.from_status,
            "to_status": ev.to_status,
            "disposition": ev.disposition,
            "analyst_note": ev.analyst_note,
            "updated_by": int(ev.updated_by) if ev.updated_by else None,
            "created_at": _dt_to_epoch(ev.created_at),
        }
        for ev in events
    ]


async def update_alert_triage(
    db: Session,
    user_id: int,
    alert_id: str,
    data: AlertTriageUpdateIn,
) -> dict[str, Any] | None:
    """更新告警 triage;非 owner / 不存在返回 ``None``。

    流程:
      1. 查 record(``(user_id, alert_id)``);不存在 → ``None``。
      2. 写 ``AlertTriageEvent``(from=old, to=new),持有 ``analyst_note`` 等。
      3. 更新 record 最新 triage 字段 + ``triage_updated_at``。
      4. 尝试同步内存 backlog;失败不阻断。
      5. 写 ``Log`` 脱敏审计(由路由层处理,这里只返回 audit dict)。
    """
    record = (
        db.query(AlertRecord)
        .filter(AlertRecord.user_id == int(user_id), AlertRecord.alert_id == str(alert_id))
        .first()
    )
    if record is None:
        return None

    previous_status = record.triage_status or _TRIAGE_DEFAULT_STATUS
    previous_disposition = record.triage_disposition
    now_epoch = time.time()
    now_dt = _epoch_to_dt(now_epoch) or datetime.now(timezone.utc).replace(tzinfo=None)

    # 1. 写 history
    event = AlertTriageEvent(
        alert_record_id=int(record.id),
        user_id=int(user_id),
        alert_id=str(alert_id),
        from_status=previous_status,
        to_status=data.status,
        disposition=data.disposition,
        analyst_note=data.analyst_note,
        updated_by=int(user_id),
        created_at=now_dt,
    )
    db.add(event)

    # 2. 更新 record 最新 triage 字段
    record.triage_status = data.status
    record.triage_disposition = data.disposition
    record.triage_note = data.analyst_note
    record.triage_updated_at = now_dt
    record.triage_updated_by = int(user_id)
    db.commit()
    db.refresh(record)

    payload = _record_to_payload(record)

    # 3. 尝试同步内存 backlog(失败不阻断)
    try:
        updated = await app_state.alert.update_backlog_triage(
            user_id=int(user_id),
            alert_id=str(alert_id),
            triage=payload["triage"],
        )
        if updated is not None:
            payload = updated
    except Exception as exc:  # noqa: BLE001
        logger.warning("backlog triage sync failed alert_id={} err={}", alert_id, exc)

    return {
        "triage": payload["triage"],
        "alert": payload,
        "audit": {
            "action": _TRIAGE_AUDIT_ACTION,
            "detail": _build_audit_detail(
                alert_id=str(alert_id),
                status=data.status,
                disposition=data.disposition,
                note_length=len(data.analyst_note or ""),
                source_ip=str((payload.get("raw_alert") or {}).get("source_ip") or ""),
            ),
            "user_id": int(user_id),
        },
    }


# ---------------------------------------------------------------------------
# Alert 生命周期(worker / ingest / demo)
# ---------------------------------------------------------------------------


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

    return _ensure_triage({
        "alert_id": uuid.uuid4().hex,
        "raw_alert": alert.model_dump(),
        "llm_analysis": analysis,
        "analysis_error": analysis_error,
        "processed_at": time.time(),
    })


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
    """后台 alert 处理 worker。

    M3-03: 持久化失败时只记录 warning,不广播未持久化 alert,
    避免前端误以为已落库 / 已可恢复。"""
    logger.info("Alert worker started id={}", worker_id)
    while True:
        alert = await app_state.alert.queue.get()
        try:
            payload = await process_alert(alert)
            await app_state.alert.append_backlog(payload)
            alert_user_id = int((payload.get("raw_alert") or {}).get("alert_user_id") or 0)
            if alert_user_id > 0:
                # 持久化尝试
                try:
                    db = SessionLocal()
                    try:
                        persist_alert_record(db, payload, alert_user_id)
                        db.commit()
                    finally:
                        db.close()
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "alert worker persist failed worker_id={} alert_id={} err={}",
                        worker_id, payload.get("alert_id"), exc,
                    )
                await manager.broadcast_json(alert_user_id, payload)
                await _send_alert_email_if_enabled(payload)
        except Exception as exc:
            logger.exception("Alert worker failed id={} err={}", worker_id, exc)
        finally:
            app_state.alert.queue.task_done()


async def get_alerts(db: Session, user_id: int, limit: int = 100) -> dict[str, Any]:
    """读取当前用户的告警列表。

    优先级:DB → 内存 backlog 兜底。DB 读失败时记录 warning 并回退到 backlog,
    不让主请求 5xx。"""
    try:
        items = list_alert_records(db, user_id, limit)
        return {
            "items": [_ensure_triage(item) for item in items],
            "count": len(items),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_alerts DB read failed, falling back to backlog: {}", exc)
        backlog = await app_state.alert.get_backlog_snapshot()
        user_items = [
            _ensure_triage(item)
            for item in backlog
            if (item.get("raw_alert") or {}).get("alert_user_id") == user_id
        ]
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


async def trigger_demo_attack(
    *,
    db: Session,
    user_id: int,
    scenario: str,
) -> dict[str, Any]:
    """Create a deterministic demo alert for the current authenticated user.

    M3-03: 写 ``alert_records`` 失败时,主请求返回 ``None``(路由层映射 503),
    保证用户期待"重启可恢复"不被静默破坏。"""
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
    payload = _ensure_triage({
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
    })

    # 持久化优先:失败时由路由层返回 5xx
    persist_alert_record(db, payload, user_id)
    db.commit()

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
