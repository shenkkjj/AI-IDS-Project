import asyncio
import socket
import ssl
import time
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi.concurrency import run_in_threadpool
from loguru import logger
from sqlalchemy.orm import Session

from server.core.config import SITE_MONITOR_HTTP_TIMEOUT_SECONDS, SSL_CHECK_INTERVAL_SECONDS
from server.core.database import create_log, SessionLocal
from server.core.state import app_state
from server.core.utils import _is_private_or_loopback_ip, _is_url_pointing_to_internal, _resolve_url_host, _now
from server.models.schemas import AlertIn


def _check_target_uptime(url: str) -> dict[str, Any]:
    try:
        response = httpx.get(
            url,
            timeout=SITE_MONITOR_HTTP_TIMEOUT_SECONDS,
            follow_redirects=False,
        )
        status_code = int(response.status_code)
        if status_code >= 500:
            return {
                "uptime_status": "down",
                "uptime_http_status": status_code,
                "uptime_detail": f"upstream returned {status_code}",
            }
        return {
            "uptime_status": "up",
            "uptime_http_status": status_code,
            "uptime_detail": "ok",
        }
    except Exception as exc:
        return {
            "uptime_status": "down",
            "uptime_http_status": None,
            "uptime_detail": str(exc),
        }


def _check_target_ssl(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return {"status": "invalid", "detail": "invalid host"}
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    if parsed.scheme != "https":
        return {"status": "no_ssl", "detail": "target is not https"}

    context = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=5) as sock:
        with context.wrap_socket(sock, server_hostname=host) as ssock:
            cert = ssock.getpeercert()
            not_after = cert.get("notAfter")
            if not not_after:
                return {"status": "unknown", "detail": "certificate has no expiry"}
            expires_at = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
            days_left = (expires_at - _now()).days
            tone = "ok"
            if days_left <= 14:
                tone = "critical"
            elif days_left <= 30:
                tone = "warning"
            return {
                "status": "ok",
                "ssl_expires_at": expires_at.isoformat(),
                "ssl_days_left": days_left,
                "ssl_tone": tone,
            }


def _normalize_ssl_tone(status: str | None, ssl_tone: str | None) -> str:
    normalized_status = str(status or "").strip().lower()
    normalized_tone = str(ssl_tone or "").strip().lower()
    if normalized_status != "ok":
        return "none"
    if normalized_tone in {"warning", "critical", "ok"}:
        return normalized_tone
    return "ok"


def _build_site_monitor_alert(user_id: int, target_url: str, reason: str, detail: str = "") -> AlertIn:
    return AlertIn(
        event="site_down",
        source_ip="system:site-monitor",
        destination_ip=target_url,
        payload=(f"reason={reason};detail={detail}" if detail else f"reason={reason}")[:4000],
        alert_user_id=user_id,
        timestamp=time.time(),
        blocked=False,
        block_expires_at=None,
    )


def _enqueue_site_monitor_alert(user_id: int, target_url: str, reason: str, detail: str = "") -> None:
    alert = _build_site_monitor_alert(user_id, target_url, reason, detail)
    accepted, replaced_oldest = app_state.alert.enqueue_alert(alert)
    if not accepted:
        logger.warning("site monitor alert queue full, drop user_id={} reason={}", user_id, reason)
        return
    if replaced_oldest:
        logger.warning("site monitor alert queue full, evict oldest user_id={} reason={}", user_id, reason)


def record_site_monitor_log(*, user_id: int, level: str, action: str, detail: str) -> None:
    db = SessionLocal()
    try:
        create_log(db, user_id=user_id, level=level, action=action, detail=detail)
    except Exception as exc:
        logger.warning("site monitor log write failed user_id={} action={} err={}", user_id, action, exc)
    finally:
        db.close()


async def set_site_target(user_id: int, url: str, db: Session) -> dict[str, Any]:
    normalized = url.strip()
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise Exception("site target must be valid http(s) url")

    if _is_url_pointing_to_internal(normalized):
        raise Exception("不允许监控内网地址")

    pre_resolve = _resolve_url_host(normalized)
    await asyncio.sleep(0.05)
    post_resolve = _resolve_url_host(normalized)
    if pre_resolve != post_resolve:
        logger.warning(
            "DNS rebinding detected on site target: {} resolved to {} then {}",
            normalized, pre_resolve, post_resolve,
        )  # noqa: E501
        raise Exception("DNS解析不稳定，请稍后重试")
    if post_resolve and _is_private_or_loopback_ip(post_resolve):
        raise Exception("不允许监控内网地址")

    app_state.site_monitor.targets[user_id] = normalized

    initial_health: dict[str, Any] = {"checked_at": _now().isoformat(), "url": normalized}
    uptime_info = await run_in_threadpool(_check_target_uptime, normalized)
    initial_health.update(uptime_info)

    if str(uptime_info.get("uptime_status", "")).lower() == "down":
        detail = str(uptime_info.get("uptime_detail", "target unreachable"))
        initial_health.update({"status": "error", "detail": detail, "alert_tone": "critical"})
        _enqueue_site_monitor_alert(
            user_id=user_id,
            target_url=normalized,
            reason="uptime_down",
            detail=detail,
        )
        record_site_monitor_log(
            user_id=user_id,
            level="error",
            action="site_target_down",
            detail=f"url={normalized};detail={detail}",
        )
    else:
        try:
            ssl_info = await run_in_threadpool(_check_target_ssl, normalized)
            initial_health.update(ssl_info)
        except Exception as exc:
            initial_health.update({"status": "error", "detail": str(exc), "alert_tone": "critical"})

    app_state.site_monitor.health_status[user_id] = initial_health

    create_log(db, user_id=user_id, level="info", action="site_target_set", detail=normalized)
    return {"status": "ok", "target": normalized}


def get_site_health(user_id: int) -> dict[str, Any]:
    item = app_state.site_monitor.health_status.get(user_id)
    if item is None:
        return {"status": "idle", "detail": "尚未设置监测站点"}
    return item


async def _ssl_monitor_loop() -> None:
    while True:
        try:
            for user_id, url in list(app_state.site_monitor.targets.items()):
                health = {"checked_at": _now().isoformat(), "url": url}
                previous = app_state.site_monitor.health_status.get(user_id) or {}

                uptime_info = await run_in_threadpool(_check_target_uptime, url)
                health.update(uptime_info)

                was_down = str(previous.get("uptime_status", "")).lower() == "down"
                is_down = str(uptime_info.get("uptime_status", "")).lower() == "down"

                if is_down:
                    detail = str(uptime_info.get("uptime_detail", "target unreachable"))
                    health.update({"status": "error", "detail": detail, "alert_tone": "critical"})
                    if not was_down:
                        _enqueue_site_monitor_alert(
                            user_id=user_id,
                            target_url=url,
                            reason="uptime_down",
                            detail=detail,
                        )
                        record_site_monitor_log(
                            user_id=user_id,
                            level="error",
                            action="site_target_down",
                            detail=f"url={url};detail={detail}",
                        )
                else:
                    try:
                        ssl_info = await run_in_threadpool(_check_target_ssl, url)
                        health.update(ssl_info)

                        current_ssl_tone = _normalize_ssl_tone(ssl_info.get("status"), ssl_info.get("ssl_tone"))
                        previous_ssl_tone = _normalize_ssl_tone(previous.get("status"), previous.get("ssl_tone"))

                        if current_ssl_tone in {"warning", "critical"} and current_ssl_tone != previous_ssl_tone:
                            days_left = ssl_info.get("ssl_days_left")
                            detail = f"ssl_tone={current_ssl_tone};days_left={days_left}"
                            _enqueue_site_monitor_alert(
                                user_id=user_id,
                                target_url=url,
                                reason=f"ssl_{current_ssl_tone}",
                                detail=detail,
                            )
                            record_site_monitor_log(
                                user_id=user_id,
                                level="warning" if current_ssl_tone == "warning" else "error",
                                action="site_ssl_expiring",
                                detail=f"url={url};{detail}",
                            )
                    except Exception as exc:
                        health.update({"status": "error", "detail": str(exc), "alert_tone": "critical"})

                app_state.site_monitor.health_status[user_id] = health
        except Exception as exc:
            logger.warning("ssl monitor loop error: {}", exc)
        await asyncio.sleep(SSL_CHECK_INTERVAL_SECONDS)
