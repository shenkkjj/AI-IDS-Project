"""Audit helpers for the LLM guardrail layer.

Every guardrail decision (pass, block, warning) writes one AuditLog row so
the SOC can answer questions like "how many prompt-injection attempts
hit the Copilot endpoint last week?" without parsing free-form logs.

DB failures are swallowed — the guardrail layer must never break a
request because auditing itself broke. We still log via `loguru` so an
operator can spot the failure in infrastructure logs.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger
from sqlalchemy import func

from server.core.database import SessionLocal
from server.models_db import AuditLog


def _build_audit_row(
    *, scope: str, layer: str, status: str, reason: str, user_id: int | None = None,
) -> Any:
    """Construct an `AuditLog` ORM instance.

    We use ``setattr`` instead of constructor kwargs so unit tests can
    substitute a lightweight stand-in class that doesn't accept the full
    AuditLog signature.
    """
    row = AuditLog()
    row.user_id = user_id
    row.action = "guardrail_check"
    row.resource_type = scope
    row.resource_id = layer
    row.detail = f"status={status};reason={reason[:200]}"
    row.status = status
    return row


def log_guardrail_event(
    *,
    scope: str,
    layer: str,
    status: str,
    reason: str,
    user_id: int | None = None,
) -> None:
    """Write one guardrail decision to the audit log.

    `status` MUST be one of ``"passed"`` / ``"blocked"`` / ``"warning"``.
    `reason` is truncated to 200 chars to keep the detail column small.
    `user_id` is the requesting user (if known) — without it the SOC
    cannot answer "which user tried this attack", per security review SC-22.
    """
    db = SessionLocal()
    try:
        row = _build_audit_row(
            scope=scope, layer=layer, status=status, reason=reason, user_id=user_id,
        )
        db.add(row)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.warning("guardrail audit write failed scope={} layer={} err={}", scope, layer, exc)
    finally:
        db.close()


def get_stats(*, hours: int = 24) -> dict[str, int]:
    """Aggregate `guardrail_check` rows from the last `hours` hours via SQL
    ``GROUP BY status`` — no full-table scan, no row materialisation.

    H-1 fix: the previous implementation did
    ``db.query(AuditLog.status).filter(...).all()`` and counted in Python,
    which is O(N) memory + a full table scan on every dashboard refresh.
    The new implementation pushes aggregation into the database; the
    response payload is at most 3 rows (one per status value).

    Returns ``{passed, blocked, warning}`` counts. Missing keys are filled
    with zero so callers can rely on the shape.
    """
    counts: dict[str, int] = {"passed": 0, "blocked": 0, "warning": 0}
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=max(1, hours))
        rows = (
            db.query(AuditLog.status, func.count(AuditLog.id))
            .filter(AuditLog.action == "guardrail_check")
            .filter(AuditLog.created_at >= cutoff)
            .group_by(AuditLog.status)
            .all()
        )
        for status, n in rows:
            # status is a str column; n is the SQL count.
            key = str(status) if status is not None else None
            if key in counts:
                counts[key] = int(n or 0)
        return counts
    except Exception as exc:  # noqa: BLE001
        logger.warning("guardrail stats read failed err={}", exc)
        return counts
    finally:
        db.close()


def iter_metrics(
    *, hours: int = 24,
) -> list[tuple[str, str, str, int]]:
    """Return ``(scope, layer, status, count)`` tuples for Prometheus.

    P2-B hardening: the ``/metrics`` endpoint consumes this to emit
    ``guardrail_checks_total{scope,layer,status}`` counters. Grouping
    is done in SQL so the cardinality stays bounded — at most
    ``len(scopes) * 2 (input|output) * 3 (passed|blocked|warning)`` rows.
    """
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=max(1, hours))
        rows = (
            db.query(
                AuditLog.resource_type,
                AuditLog.resource_id,
                AuditLog.status,
                func.count(AuditLog.id),
            )
            .filter(AuditLog.action == "guardrail_check")
            .filter(AuditLog.created_at >= cutoff)
            .group_by(AuditLog.resource_type, AuditLog.resource_id, AuditLog.status)
            .all()
        )
        return [
            (str(rt or "unknown"), str(ri or "unknown"), str(s or "unknown"), int(n or 0))
            for rt, ri, s, n in rows
        ]
    except Exception as exc:  # noqa: BLE001
        logger.warning("guardrail metrics read failed err={}", exc)
        return []
    finally:
        db.close()


def cleanup_old_audit_logs(*, days: int = 90) -> int:
    """Delete guardrail audit rows older than ``days`` (P2-C hardening).

    GDPR / PCI-DSS require a documented retention policy for security
    telemetry. The default 90 days matches the SOC's standard review
    cycle; deployments with stricter rules should set
    ``GUARDRAIL_AUDIT_CLEANUP_DAYS`` to a smaller value.

    Returns the number of rows deleted. Errors are swallowed (logged)
    so a transient DB blip never blocks application startup.
    """
    if days < 1:
        return 0
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
        result = (
            db.query(AuditLog)
            .filter(AuditLog.action == "guardrail_check")
            .filter(AuditLog.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
        deleted = int(result or 0)
        if deleted:
            logger.info("audit cleanup: removed {} rows older than {}d", deleted, days)
        return deleted
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.warning("audit cleanup failed days={} err={}", days, exc)
        return 0
    finally:
        db.close()
