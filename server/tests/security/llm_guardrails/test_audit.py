"""Unit tests for `server.security.llm_guardrails.audit`.

Contract:
- `log_guardrail_event` writes one row to AuditLog with action='guardrail_check',
  resource_type=scope, resource_id=layer, status=passed|blocked|warning.
- Never raises — the guardrail layer must never fail a request because auditing
  itself broke. Failures are swallowed (logged) so the request still returns.
- `get_stats()` aggregates the last 24h into {passed, blocked, warning} dict.
"""
from __future__ import annotations

from typing import Any

import pytest

from server.security.llm_guardrails.audit import log_guardrail_event, get_stats


class _FakeAuditLog:
    """In-memory stand-in for the SQLAlchemy AuditLog model."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def add(self, row: Any) -> None:
        self.rows.append({
            "action": row.action,
            "resource_type": row.resource_type,
            "resource_id": row.resource_id,
            "status": row.status,
            "detail": row.detail,
        })


def test_log_guardrail_event_passes_through(monkeypatch: pytest.MonkeyPatch) -> None:
    from server.security.llm_guardrails import audit as audit_mod

    fake = _FakeAuditLog()
    captured: list[dict[str, Any]] = []

    class _FakeDB:
        def add(self, row: Any) -> None:
            fake.add(row)

        def commit(self) -> None:
            captured.append({"committed": True})

        def rollback(self) -> None:
            captured.append({"rolled_back": True})

        def close(self) -> None:
            captured.append({"closed": True})

    monkeypatch.setattr(audit_mod, "SessionLocal", lambda: _FakeDB())
    monkeypatch.setattr(audit_mod, "AuditLog", _FakeAuditLog)

    log_guardrail_event(scope="copilot", layer="input", status="passed", reason="")

    assert len(fake.rows) == 1
    row = fake.rows[0]
    assert row["action"] == "guardrail_check"
    assert row["resource_type"] == "copilot"
    assert row["resource_id"] == "input"
    assert row["status"] == "passed"


def test_log_guardrail_event_status_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    from server.security.llm_guardrails import audit as audit_mod

    fake = _FakeAuditLog()

    class _FakeDB:
        def add(self, row: Any) -> None:
            fake.add(row)

        def commit(self) -> None:
            pass

        def rollback(self) -> None:
            pass

        def close(self) -> None:
            pass

    monkeypatch.setattr(audit_mod, "SessionLocal", lambda: _FakeDB())
    monkeypatch.setattr(audit_mod, "AuditLog", _FakeAuditLog)

    log_guardrail_event(
        scope="copilot", layer="input", status="blocked", reason="ignore previous",
    )
    assert fake.rows[0]["status"] == "blocked"
    assert "ignore previous" in fake.rows[0]["detail"]


def test_log_guardrail_event_status_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    from server.security.llm_guardrails import audit as audit_mod

    fake = _FakeAuditLog()

    class _FakeDB:
        def add(self, row: Any) -> None:
            fake.add(row)

        def commit(self) -> None:
            pass

        def rollback(self) -> None:
            pass

        def close(self) -> None:
            pass

    monkeypatch.setattr(audit_mod, "SessionLocal", lambda: _FakeDB())
    monkeypatch.setattr(audit_mod, "AuditLog", _FakeAuditLog)

    log_guardrail_event(
        scope="copilot", layer="input", status="warning", reason="timeout",
    )
    assert fake.rows[0]["status"] == "warning"


def test_log_guardrail_event_reason_truncated_to_200(monkeypatch: pytest.MonkeyPatch) -> None:
    from server.security.llm_guardrails import audit as audit_mod

    fake = _FakeAuditLog()

    class _FakeDB:
        def add(self, row: Any) -> None:
            fake.add(row)

        def commit(self) -> None:
            pass

        def rollback(self) -> None:
            pass

        def close(self) -> None:
            pass

    monkeypatch.setattr(audit_mod, "SessionLocal", lambda: _FakeDB())
    monkeypatch.setattr(audit_mod, "AuditLog", _FakeAuditLog)

    long_reason = "x" * 500
    log_guardrail_event(
        scope="x", layer="input", status="blocked", reason=long_reason,
    )
    # detail 形如 "status=blocked;reason=xxxxxxxx..." 不超过 ~250 字符
    assert len(fake.rows[0]["detail"]) < 260


def test_log_guardrail_event_swallows_db_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit must never break the calling request — exceptions are caught."""
    from server.security.llm_guardrails import audit as audit_mod

    class _BrokenDB:
        def add(self, row: Any) -> None:
            raise RuntimeError("db down")

        def commit(self) -> None:
            pass

        def rollback(self) -> None:
            pass

        def close(self) -> None:
            pass

    monkeypatch.setattr(audit_mod, "SessionLocal", lambda: _BrokenDB())
    monkeypatch.setattr(audit_mod, "AuditLog", _FakeAuditLog)

    # 必须不抛
    log_guardrail_event(scope="x", layer="input", status="passed", reason="")


def test_get_stats_returns_three_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    from server.security.llm_guardrails import audit as audit_mod

    fake_rows = [
        # (status, count) — what the SQL GROUP BY returns
        ("passed", 2),
        ("blocked", 1),
        ("warning", 1),
    ]

    class _Query:
        def __init__(self, rows):
            self.rows = rows

        def filter(self, *args, **kwargs):
            return self

        def group_by(self, *args, **kwargs):
            return self

        def all(self):
            return list(self.rows)

    class _FakeDB:
        def __init__(self):
            self.rows = fake_rows

        def query(self, *args, **kwargs):
            return _Query(self.rows)

        def close(self):
            pass

    monkeypatch.setattr(audit_mod, "SessionLocal", lambda: _FakeDB())

    stats = get_stats()
    assert set(stats.keys()) >= {"passed", "blocked", "warning"}
    assert stats["passed"] == 2
    assert stats["blocked"] == 1
    assert stats["warning"] == 1


def test_get_stats_handles_missing_statuses(monkeypatch: pytest.MonkeyPatch) -> None:
    """If SQL returns only the statuses that have rows, the missing ones
    must be filled with zero (not omitted). The shape contract matters
    for the /mcp dashboard."""
    from server.security.llm_guardrails import audit as audit_mod

    fake_rows = [("passed", 5)]  # only "passed" exists in the window

    class _Query:
        def __init__(self, rows):
            self.rows = rows

        def filter(self, *args, **kwargs):
            return self

        def group_by(self, *args, **kwargs):
            return self

        def all(self):
            return list(self.rows)

    class _FakeDB:
        def query(self, *args, **kwargs):
            return _Query(fake_rows)

        def close(self):
            pass

    monkeypatch.setattr(audit_mod, "SessionLocal", lambda: _FakeDB())

    stats = get_stats()
    assert stats == {"passed": 5, "blocked": 0, "warning": 0}


def test_get_stats_swallows_db_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """DB outage must not propagate — return the zero-filled shape so
    the dashboard can still render '0 blocked today' rather than 500."""
    from server.security.llm_guardrails import audit as audit_mod

    class _BrokenQuery:
        def filter(self, *args, **kwargs):
            return self

        def group_by(self, *args, **kwargs):
            return self

        def all(self):
            raise RuntimeError("db down")

    class _BrokenDB:
        def query(self, *args, **kwargs):
            return _BrokenQuery()

        def close(self):
            pass

    monkeypatch.setattr(audit_mod, "SessionLocal", lambda: _BrokenDB())

    stats = get_stats()
    assert stats == {"passed": 0, "blocked": 0, "warning": 0}


# ---- P2-B: iter_metrics for /metrics Prometheus endpoint --------------------


def test_iter_metrics_returns_grouped_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    from server.security.llm_guardrails import audit as audit_mod
    from server.security.llm_guardrails.audit import iter_metrics

    fake_rows = [
        ("copilot", "input", "passed", 10),
        ("copilot", "input", "blocked", 2),
        ("copilot", "output", "passed", 9),
        ("mcp", "input", "blocked", 1),
    ]

    class _Query:
        def __init__(self, rows):
            self.rows = rows

        def filter(self, *args, **kwargs):
            return self

        def group_by(self, *args, **kwargs):
            return self

        def all(self):
            return list(self.rows)

    class _FakeDB:
        def query(self, *args, **kwargs):
            return _Query(fake_rows)

        def close(self):
            pass

    monkeypatch.setattr(audit_mod, "SessionLocal", lambda: _FakeDB())

    rows = iter_metrics(hours=24)
    assert ("copilot", "input", "passed", 10) in rows
    assert ("copilot", "input", "blocked", 2) in rows
    assert ("mcp", "input", "blocked", 1) in rows


def test_iter_metrics_handles_db_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    from server.security.llm_guardrails import audit as audit_mod
    from server.security.llm_guardrails.audit import iter_metrics

    class _BrokenQuery:
        def filter(self, *args, **kwargs):
            return self

        def group_by(self, *args, **kwargs):
            return self

        def all(self):
            raise RuntimeError("db down")

    class _BrokenDB:
        def query(self, *args, **kwargs):
            return _BrokenQuery()

        def close(self):
            pass

    monkeypatch.setattr(audit_mod, "SessionLocal", lambda: _BrokenDB())

    # /metrics scrape must never 500 — return empty list on error.
    assert iter_metrics() == []


# ---- P2-C: cleanup_old_audit_logs (GDPR/PCI retention) --------------------


def test_cleanup_old_audit_logs_deletes_old_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    from server.security.llm_guardrails import audit as audit_mod
    from server.security.llm_guardrails.audit import cleanup_old_audit_logs

    deleted_count = {"n": 0}

    class _Query:
        def filter(self, *args, **kwargs):
            return self

        def filter2(self, *args, **kwargs):
            return self

        def delete(self, *args, **kwargs):
            deleted_count["n"] += 1
            return 42  # pretend 42 rows matched the filter

    class _FakeDB:
        def query(self, *args, **kwargs):
            return _Query()

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(audit_mod, "SessionLocal", lambda: _FakeDB())

    n = cleanup_old_audit_logs(days=90)
    assert n == 42


def test_cleanup_old_audit_logs_zero_days_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    from server.security.llm_guardrails import audit as audit_mod
    from server.security.llm_guardrails.audit import cleanup_old_audit_logs

    called = {"db": False}

    class _FakeDB:
        def query(self, *args, **kwargs):
            called["db"] = True
            return self

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(audit_mod, "SessionLocal", lambda: _FakeDB())

    n = cleanup_old_audit_logs(days=0)
    assert n == 0
    assert called["db"] is False  # short-circuit before touching DB


def test_cleanup_old_audit_logs_swallows_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    from server.security.llm_guardrails import audit as audit_mod
    from server.security.llm_guardrails.audit import cleanup_old_audit_logs

    class _BrokenDB:
        def query(self, *args, **kwargs):
            raise RuntimeError("db down")

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(audit_mod, "SessionLocal", lambda: _BrokenDB())

    # Must not propagate — startup must not block on a cleanup failure.
    assert cleanup_old_audit_logs(days=30) == 0
