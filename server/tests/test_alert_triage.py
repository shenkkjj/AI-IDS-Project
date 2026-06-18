"""``PATCH /alerts/{alert_id}/triage`` 端点测试。

设计目标（docs/agent/M3_02_ALERT_TRIAGE_RESPONSE_WORKBENCH_TASK.md §3）:

- 当前用户可更新自己的告警 triage（含 status / disposition / analyst_note）。
- 更新后 ``GET /alerts`` 必须返回新的 triage 字段。
- 其他用户更新同一 ``alert_id`` 必须返回 404（不能通过 403 暴露 ID 是否存在）。
- 未登录请求返回 401。
- 无效 status 返回 422。
- ``analyst_note`` 超过 800 字符返回 422。
- 审计日志 ``Log(action="alert_triage_update")`` 必须记录,
  但 detail 不得写入完整 payload / 完整 note / 完整 secret。

M3-03 改造:
- service 现在走真 DB(``alert_records`` + ``alert_triage_events``)。
- ``triage_env`` fixture 改用临时 SQLite + ``Base.metadata.create_all`` 建表,
  并在 DB 中预置 user 与 demo alert record。
"""
from __future__ import annotations

import asyncio
import re
import time
import uuid
from collections import deque
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import server.core.database as db_module
from server.core import state as state_module
from server.core.config import ALERT_BACKLOG_SIZE, ALERT_QUEUE_MAX_SIZE
from server.core.database import Base
from server.core.state import app_state
from server.models_db import User
from server.routers import alerts_router
from server.services import alert_service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def triage_env(tmp_path, monkeypatch):
    """构造一个干净的 app_state + 两个用户 + DB 临时库 + 一条 demo alert。"""
    db_file = tmp_path / "test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    test_engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    monkeypatch.setattr(db_module, "engine", test_engine, raising=False)
    monkeypatch.setattr(db_module, "SessionLocal", TestSessionLocal, raising=False)
    monkeypatch.setattr(alert_service, "SessionLocal", TestSessionLocal, raising=False)
    monkeypatch.setattr(alerts_router, "SessionLocal", TestSessionLocal, raising=False)

    user_a = User(
        id=1001,
        email="analyst-a@example.com",
        password_hash="x",
        is_active=True,
    )
    user_b = User(
        id=1002,
        email="analyst-b@example.com",
        password_hash="x",
        is_active=True,
    )
    setup_db = TestSessionLocal()
    setup_db.add(user_a)
    setup_db.add(user_b)
    setup_db.commit()
    setup_db.refresh(user_a)
    setup_db.refresh(user_b)
    setup_db.close()

    # 隔离 app_state.alert.backlog 与 queue
    monkeypatch.setattr(state_module, "app_state", state_module.AppState())
    app_state.alert.backlog = deque(maxlen=ALERT_BACKLOG_SIZE)
    app_state.alert.queue = asyncio.Queue(maxsize=ALERT_QUEUE_MAX_SIZE)

    # bypass manager.broadcast_json,避免 WS 干扰
    async def fake_broadcast(*_a, **_k):
        return None

    monkeypatch.setattr(
        "server.services.alert_service.manager.broadcast_json", fake_broadcast
    )

    # bypass _send_alert_email_if_enabled
    async def fake_email(*_a, **_k):
        return None

    monkeypatch.setattr(
        "server.services.alert_service._send_alert_email_if_enabled", fake_email
    )

    # 注入一条 user_a 拥有的告警 record(M3-03 走 DB)
    alert_id = uuid.uuid4().hex
    payload = {
        "alert_id": alert_id,
        "raw_alert": {
            "event": "waf_block",
            "source_ip": "203.0.113.45",
            "destination_ip": "10.0.0.15",
            "payload": "' UNION SELECT username,password FROM users --",
            "alert_user_id": user_a.id,
            "timestamp": time.time(),
            "blocked": True,
        },
        "llm_analysis": {
            "risk_level": "critical",
            "summary": "SQL 注入攻击",
        },
        "processed_at": time.time(),
    }
    seed_db = TestSessionLocal()
    alert_service.persist_alert_record(seed_db, payload, user_a.id)
    seed_db.commit()
    seed_db.close()

    # 同时写一份到 backlog,兼容老路径(WS 启动推送等)
    app_state.alert.backlog.append(payload)

    def make_client(user: User) -> TestClient:
        app = FastAPI()
        app.include_router(alerts_router.router)
        app.dependency_overrides[alerts_router.require_auth_user] = lambda: user
        app.dependency_overrides[alerts_router.get_db] = lambda: TestSessionLocal()
        return TestClient(app)

    client_a = make_client(user_a)
    client_b = make_client(user_b)

    try:
        yield client_a, client_b, TestSessionLocal, user_a, user_b, alert_id, test_engine
    finally:
        app_state.alert.backlog.clear()
        test_engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_FORBIDDEN_AUDIT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"sk-proj-[A-Za-z0-9_-]+"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"\bTraceback\s+\(most recent call last\)", re.IGNORECASE),
    re.compile(r"PRIVATE\s+KEY", re.IGNORECASE),
)


def _assert_no_secret_in_text(text: str) -> None:
    for pat in _FORBIDDEN_AUDIT_PATTERNS:
        assert not pat.search(text), f"审计 detail 命中禁止 sentinel: {pat.pattern}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_triage_requires_auth(triage_env):
    """未登录请求 401."""
    _a, _b, _db, _ua, _ub, _alert_id, _engine = triage_env
    app = FastAPI()
    app.include_router(alerts_router.router)
    anon = TestClient(app)
    resp = anon.patch(
        "/alerts/some-id/triage",
        json={"status": "investigating"},
    )
    assert resp.status_code == 401


def test_triage_updates_own_alert(triage_env):
    """当前用户可更新自己的告警 triage."""
    client_a, _b, _db, _ua, _ub, alert_id, _engine = triage_env
    resp = client_a.patch(
        f"/alerts/{alert_id}/triage",
        json={
            "status": "investigating",
            "disposition": "needs_review",
            "analyst_note": "已确认 WAF 拦截生效，继续观察同源 IP。",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ok"
    assert body["alert_id"] == alert_id
    assert body["triage"]["status"] == "investigating"
    assert body["triage"]["disposition"] == "needs_review"
    assert body["triage"]["analyst_note"] == "已确认 WAF 拦截生效，继续观察同源 IP。"
    assert body["triage"]["updated_by"] == _ua.id
    assert body["triage"]["updated_at"] > 0
    assert body["alert"]["alert_id"] == alert_id


def test_triage_appears_in_get_alerts(triage_env):
    """更新后 GET /alerts 必须返回 triage 字段."""
    client_a, _b, _db, _ua, _ub, alert_id, _engine = triage_env
    resp = client_a.patch(
        f"/alerts/{alert_id}/triage",
        json={"status": "contained", "disposition": "blocked_at_waf"},
    )
    assert resp.status_code == 200

    resp_list = client_a.get("/alerts")
    assert resp_list.status_code == 200
    body = resp_list.json()
    assert body["count"] >= 1
    target = next(item for item in body["items"] if item["alert_id"] == alert_id)
    assert "triage" in target
    assert target["triage"]["status"] == "contained"
    assert target["triage"]["disposition"] == "blocked_at_waf"


def test_triage_other_user_returns_404(triage_env):
    """其他用户更新同一 alert_id 返回 404(不能通过 403 暴露 ID 是否存在)."""
    _a, client_b, _db, _ua, _ub, alert_id, _engine = triage_env
    resp = client_b.patch(
        f"/alerts/{alert_id}/triage",
        json={"status": "false_positive"},
    )
    assert resp.status_code == 404


def test_triage_unknown_alert_returns_404(triage_env):
    """告警不存在返回 404."""
    client_a, _b, _db, _ua, _ub, _alert_id, _engine = triage_env
    resp = client_a.patch(
        "/alerts/nonexistent-id-1234567890/triage",
        json={"status": "investigating"},
    )
    assert resp.status_code == 404


def test_triage_invalid_status_returns_422(triage_env):
    """无效 status 返回 422."""
    client_a, _b, _db, _ua, _ub, alert_id, _engine = triage_env
    resp = client_a.patch(
        f"/alerts/{alert_id}/triage",
        json={"status": "firing_lasers"},
    )
    assert resp.status_code == 422


def test_triage_note_too_long_returns_422(triage_env):
    """analyst_note 超过 800 字符返回 422."""
    client_a, _b, _db, _ua, _ub, alert_id, _engine = triage_env
    long_note = "x" * 801
    resp = client_a.patch(
        f"/alerts/{alert_id}/triage",
        json={"status": "investigating", "analyst_note": long_note},
    )
    assert resp.status_code == 422


def test_triage_writes_audit_log_without_payload(triage_env):
    """审计 Log 必须记录,detail 不能含完整 payload / 完整 note / 完整 secret."""
    client_a, _b, SessionLocal, _ua, _ub, alert_id, _engine = triage_env
    note_text = (
        "已确认 WAF 拦截，载荷含 UNION SELECT 凭据枚举。"
        "fake-key sk-test-abcdef0123456789"
    )
    resp = client_a.patch(
        f"/alerts/{alert_id}/triage",
        json={
            "status": "contained",
            "disposition": "blocked_at_waf",
            "analyst_note": note_text,
        },
    )
    assert resp.status_code == 200

    from server.models_db import Log

    db = SessionLocal()
    try:
        logs = (
            db.query(Log)
            .filter(Log.user_id == _ua.id, Log.action == "alert_triage_update")
            .order_by(Log.id.desc())
            .all()
        )
        assert logs, "create_log 没被调用"
        log = logs[0]
        assert log.action == "alert_triage_update"
        assert log.user_id == _ua.id
        detail = log.detail
        assert isinstance(detail, str)

        # detail 不含完整 note
        assert note_text not in detail, f"审计 detail 含完整 note: {detail}"
        # detail 不含完整 payload 关键字
        assert "UNION SELECT" not in detail, f"审计 detail 含完整 payload: {detail}"
        # detail 不含 API key
        _assert_no_secret_in_text(detail)
        # 关键摘要必须出现
        assert "status=contained" in detail
        assert "disposition=blocked_at_waf" in detail
        # note 长度必须被记录
        assert f"note_length={len(note_text)}" in detail
    finally:
        db.close()


def test_triage_disposition_optional(triage_env):
    """disposition 字段是可选的."""
    client_a, _b, _db, _ua, _ub, alert_id, _engine = triage_env
    resp = client_a.patch(
        f"/alerts/{alert_id}/triage",
        json={"status": "resolved"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["triage"]["status"] == "resolved"
    assert body["triage"].get("disposition") in (None, "")


def test_triage_old_alert_has_default_state_in_get(triage_env):
    """未带 triage 字段的旧告警,GET /alerts 映射为默认 new."""
    client_a, _b, _db, _ua, _ub, alert_id, _engine = triage_env
    resp_list = client_a.get("/alerts")
    target = next(
        item for item in resp_list.json()["items"] if item["alert_id"] == alert_id
    )
    assert "triage" in target
    assert target["triage"]["status"] == "new"
    assert (
        target["triage"]["disposition"] is None
        or target["triage"]["disposition"] == ""
    )


def test_triage_audit_log_failure_does_not_break_request(monkeypatch, triage_env):
    """Log 写入失败时,主请求依然 200."""
    client_a, _b, _db, _ua, _ub, alert_id, _engine = triage_env

    def boom(*_a, **_k):
        raise RuntimeError("Traceback (most recent call last):\n  KeyError: 'x'")

    monkeypatch.setattr("server.routers.alerts_router.create_log", boom)

    resp = client_a.patch(
        f"/alerts/{alert_id}/triage",
        json={"status": "investigating", "analyst_note": "test note"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["triage"]["status"] == "investigating"
    assert body["status"] == "ok"
