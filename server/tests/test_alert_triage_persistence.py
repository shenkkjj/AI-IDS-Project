"""M3-03 告警研判持久化 + 历史记录 RED→GREEN 测试集。

设计目标（docs/agent/M3_03_ALERT_TRIAGE_PERSISTENCE_AND_HISTORY_TASK.md §5/§8 阶段 3）：

- ``alert_records`` 是告警快照事实来源；``alert_triage_events`` 是 triage 历史事实来源。
- ``GET /alerts`` 重启后从 DB 读,内存 backlog 清空也能恢复。
- 每次 ``PATCH /alerts/{alert_id}/triage`` 写一条 history event,``/triage/history`` 端点
  返回该用户可见的历史。
- owner 隔离:非 owner / 不存在统一 404。
- DB 写失败不允许 silent success;demo 路由失败返回 503,worker 失败记录 warning。
- 审计 ``Log(action="alert_triage_update")`` 仍只写脱敏摘要,不含完整 payload / note / secret。

所有测试用 ``tmp_path`` 临时 SQLite(``Base.metadata.create_all`` 一次性建表),不污染
真实 ``data/app.db``,也不需要预先跑 Alembic migration(避免把 RED 测试和 migration
ordering 绑死)。
"""
from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
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
def tmp_db(tmp_path, monkeypatch):
    """临时 SQLite 库 + 替换 module-level engine / SessionLocal。"""
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

    try:
        yield test_engine, TestSessionLocal
    finally:
        test_engine.dispose()


@pytest.fixture
def reset_app_state(monkeypatch):
    """隔离 ``app_state.alert`` 的内存 backlog 和 queue。"""
    monkeypatch.setattr(state_module, "app_state", state_module.AppState())
    app_state.alert.backlog = type(app_state.alert.backlog)()
    app_state.alert.queue = asyncio.Queue(maxsize=ALERT_QUEUE_MAX_SIZE)
    yield
    app_state.alert.backlog.clear()


def _build_payload(user_id: int, *, alert_id: str | None = None) -> dict[str, Any]:
    aid = alert_id or uuid.uuid4().hex
    return {
        "alert_id": aid,
        "raw_alert": {
            "event": "waf_block",
            "source_ip": "203.0.113.45",
            "destination_ip": "10.0.0.15",
            "payload": "' UNION SELECT username,password FROM users --",
            "alert_user_id": user_id,
            "timestamp": time.time(),
            "blocked": True,
        },
        "llm_analysis": {
            "risk_level": "critical",
            "summary": "SQL 注入攻击",
        },
        "processed_at": time.time(),
    }


def _insert_user(session_local, user_id: int, email: str) -> tuple[User, Any]:
    """插入 user,保持 attached(不关闭 session,避免 detach)。"""
    user = User(
        id=user_id,
        email=email,
        password_hash="x",
        is_active=True,
    )
    db = session_local()
    db.add(user)
    db.commit()
    db.refresh(user)
    # 返回 user 和 db;测试在结束时负责 close。
    return user, db


def _make_client(
    user: User,
    session_local,
    *,
    monkeypatch,
) -> tuple[TestClient, Any]:
    """构造一个走真 DB 的 TestClient,bypass WS / email 副作用。"""
    async def fake_broadcast(*_a, **_k):
        return None

    monkeypatch.setattr(
        "server.services.alert_service.manager.broadcast_json", fake_broadcast
    )
    monkeypatch.setattr(
        "server.services.alert_service._send_alert_email_if_enabled", fake_broadcast
    )

    app = FastAPI()
    app.include_router(alerts_router.router)
    app.dependency_overrides[alerts_router.require_auth_user] = lambda: user
    app.dependency_overrides[alerts_router.get_db] = lambda: session_local()
    return TestClient(app), session_local


# ---------------------------------------------------------------------------
# Sentinel / sanitizer
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


def test_demo_attack_writes_alert_record(tmp_db, reset_app_state, monkeypatch):
    """POST /alerts/demo 后,alert_records 表应有对应记录,且 raw_alert_json 可反序列化。"""
    _engine, SessionLocal = tmp_db
    user, _user_db = _insert_user(SessionLocal, 9001, "demo-record@example.com")
    client, _sl = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    resp = client.post("/alerts/demo", json={"scenario": "sql_injection"})
    assert resp.status_code == 200, resp.text
    alert_id = resp.json()["alert"]["alert_id"]

    from server.models_db import AlertRecord

    db = SessionLocal()
    try:
        rec = (
            db.query(AlertRecord)
            .filter(AlertRecord.alert_id == alert_id, AlertRecord.user_id == 9001)
            .first()
        )
        assert rec is not None, "demo 攻击后未在 alert_records 找到记录"
        assert rec.triage_status == "new"
        raw = json.loads(rec.raw_alert_json)
        assert raw["alert_user_id"] == 9001
        assert raw["payload"].startswith("' UNION SELECT")
    finally:
        db.close()


def test_get_alerts_recovers_from_empty_backlog(tmp_db, reset_app_state, monkeypatch):
    """清空 app_state.alert.backlog 后,GET /alerts 仍能返回 DB 中的 demo alert。"""
    _engine, SessionLocal = tmp_db
    user, _user_db = _insert_user(SessionLocal, 9002, "recover@example.com")
    client, _sl = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    created = client.post("/alerts/demo", json={"scenario": "xss"})
    assert created.status_code == 200
    target_alert_id = created.json()["alert"]["alert_id"]

    app_state.alert.backlog.clear()
    assert len(app_state.alert.backlog) == 0

    resp = client.get("/alerts")
    assert resp.status_code == 200
    body = resp.json()
    alert_ids = [item["alert_id"] for item in body["items"]]
    assert target_alert_id in alert_ids, (
        f"清空 backlog 后 GET /alerts 找不到 DB 中的 demo alert: {alert_ids}"
    )


def test_triage_updates_db_latest(tmp_db, reset_app_state, monkeypatch):
    """PATCH /alerts/{alert_id}/triage 后,alert_records.triage_status 应被更新。"""
    _engine, SessionLocal = tmp_db
    user, _user_db = _insert_user(SessionLocal, 9003, "update@example.com")
    client, _sl = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    created = client.post("/alerts/demo", json={"scenario": "scanner"})
    assert created.status_code == 200
    target_alert_id = created.json()["alert"]["alert_id"]

    patch_resp = client.patch(
        f"/alerts/{target_alert_id}/triage",
        json={"status": "contained", "disposition": "blocked_at_waf", "analyst_note": "已确认"},
    )
    assert patch_resp.status_code == 200, patch_resp.text

    from server.models_db import AlertRecord

    db = SessionLocal()
    try:
        rec = (
            db.query(AlertRecord)
            .filter(AlertRecord.alert_id == target_alert_id, AlertRecord.user_id == 9003)
            .first()
        )
        assert rec is not None
        assert rec.triage_status == "contained"
        assert rec.triage_disposition == "blocked_at_waf"
        assert rec.triage_note == "已确认"
        assert rec.triage_updated_by == 9003
        assert rec.triage_updated_at is not None
    finally:
        db.close()


def test_triage_persists_across_backlog_clear(tmp_db, reset_app_state, monkeypatch):
    """清空 backlog 后,GET /alerts 仍返回保存后的 triage。"""
    _engine, SessionLocal = tmp_db
    user, _user_db = _insert_user(SessionLocal, 9004, "persist@example.com")
    client, _sl = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    created = client.post("/alerts/demo", json={"scenario": "sql_injection"})
    alert_id = created.json()["alert"]["alert_id"]
    client.patch(
        f"/alerts/{alert_id}/triage",
        json={"status": "investigating", "disposition": "needs_review"},
    )

    app_state.alert.backlog.clear()

    resp = client.get("/alerts")
    items = resp.json()["items"]
    target = next(item for item in items if item["alert_id"] == alert_id)
    assert target["triage"]["status"] == "investigating"
    assert target["triage"]["disposition"] == "needs_review"


def test_triage_writes_history_event(tmp_db, reset_app_state, monkeypatch):
    """每次 PATCH /alerts/{alert_id}/triage 写一条 alert_triage_events。"""
    _engine, SessionLocal = tmp_db
    user, _user_db = _insert_user(SessionLocal, 9005, "history@example.com")
    client, _sl = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    created = client.post("/alerts/demo", json={"scenario": "sql_injection"})
    alert_id = created.json()["alert"]["alert_id"]

    for status in ("investigating", "contained", "resolved"):
        r = client.patch(
            f"/alerts/{alert_id}/triage",
            json={"status": status, "disposition": f"to-{status}"},
        )
        assert r.status_code == 200

    from server.models_db import AlertRecord, AlertTriageEvent

    db = SessionLocal()
    try:
        rec = (
            db.query(AlertRecord)
            .filter(AlertRecord.alert_id == alert_id, AlertRecord.user_id == 9005)
            .first()
        )
        assert rec is not None
        events = (
            db.query(AlertTriageEvent)
            .filter(AlertTriageEvent.alert_record_id == rec.id)
            .order_by(AlertTriageEvent.id.asc())
            .all()
        )
        assert len(events) == 3, f"应写 3 条 history,实际 {len(events)}"
        assert events[0].from_status == "new"
        assert events[0].to_status == "investigating"
        assert events[1].from_status == "investigating"
        assert events[1].to_status == "contained"
        assert events[2].from_status == "contained"
        assert events[2].to_status == "resolved"
        for ev in events:
            assert ev.user_id == 9005
            assert ev.alert_id == alert_id
    finally:
        db.close()


def test_triage_history_endpoint_returns_events(tmp_db, reset_app_state, monkeypatch):
    """GET /alerts/{alert_id}/triage/history 返回当前用户可见的历史。"""
    _engine, SessionLocal = tmp_db
    user, _user_db = _insert_user(SessionLocal, 9006, "history-endpoint@example.com")
    client, _sl = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    created = client.post("/alerts/demo", json={"scenario": "xss"})
    alert_id = created.json()["alert"]["alert_id"]
    client.patch(
        f"/alerts/{alert_id}/triage",
        json={"status": "investigating", "analyst_note": "first update"},
    )
    client.patch(
        f"/alerts/{alert_id}/triage",
        json={"status": "contained", "analyst_note": "second update"},
    )

    resp = client.get(f"/alerts/{alert_id}/triage/history?limit=50")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ok"
    assert body["alert_id"] == alert_id
    assert body["count"] == 2
    assert len(body["items"]) == 2
    notes = {item["analyst_note"] for item in body["items"]}
    assert notes == {"first update", "second update"}
    statuses = [(item["from_status"], item["to_status"]) for item in body["items"]]
    assert ("new", "investigating") in statuses
    assert ("investigating", "contained") in statuses


def test_triage_history_other_user_returns_404(tmp_db, reset_app_state, monkeypatch):
    """其他用户查同一 alert_id 的 history 返回 404,不暴露存在性。"""
    _engine, SessionLocal = tmp_db
    owner, _o_db = _insert_user(SessionLocal, 9007, "owner@example.com")
    intruder, _i_db = _insert_user(SessionLocal, 9008, "intruder@example.com")

    owner_client, _ = _make_client(owner, SessionLocal, monkeypatch=monkeypatch)
    created = owner_client.post("/alerts/demo", json={"scenario": "sql_injection"})
    alert_id = created.json()["alert"]["alert_id"]
    owner_client.patch(
        f"/alerts/{alert_id}/triage",
        json={"status": "investigating", "analyst_note": "owner secret note"},
    )

    intruder_client, _ = _make_client(intruder, SessionLocal, monkeypatch=monkeypatch)
    resp = intruder_client.get(f"/alerts/{alert_id}/triage/history")
    assert resp.status_code == 404


def test_triage_history_endpoint_validates_limit(tmp_db, reset_app_state, monkeypatch):
    """limit 越界返回 422;默认 50。"""
    _engine, SessionLocal = tmp_db
    user, _user_db = _insert_user(SessionLocal, 9009, "limit@example.com")
    client, _sl = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    created = client.post("/alerts/demo", json={"scenario": "scanner"})
    alert_id = created.json()["alert"]["alert_id"]

    resp_low = client.get(f"/alerts/{alert_id}/triage/history?limit=0")
    assert resp_low.status_code == 422
    resp_high = client.get(f"/alerts/{alert_id}/triage/history?limit=101")
    assert resp_high.status_code == 422
    resp_default = client.get(f"/alerts/{alert_id}/triage/history")
    assert resp_default.status_code == 200
    assert resp_default.json()["count"] == 0


def test_triage_audit_log_still_no_secret(tmp_db, reset_app_state, monkeypatch):
    """DB 持久化 + history 落地后,Log 仍只写脱敏摘要,不含完整 note / payload / secret。"""
    _engine, SessionLocal = tmp_db
    user, _user_db = _insert_user(SessionLocal, 9010, "audit@example.com")
    client, _sl = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    created = client.post("/alerts/demo", json={"scenario": "sql_injection"})
    alert_id = created.json()["alert"]["alert_id"]

    note = (
        "已确认 WAF 拦截,载荷含 UNION SELECT 凭据枚举。"
        "fake-key sk-test-abcdef0123456789"
    )
    resp = client.patch(
        f"/alerts/{alert_id}/triage",
        json={"status": "contained", "disposition": "blocked_at_waf", "analyst_note": note},
    )
    assert resp.status_code == 200

    from server.models_db import Log

    db = SessionLocal()
    try:
        logs = (
            db.query(Log)
            .filter(Log.user_id == 9010, Log.action == "alert_triage_update")
            .order_by(Log.id.desc())
            .all()
        )
        assert logs, "alert_triage_update 审计日志缺失"
        detail = logs[0].detail
        assert note not in detail
        assert "UNION SELECT" not in detail
        _assert_no_secret_in_text(detail)
        assert "status=contained" in detail
        assert f"note_length={len(note)}" in detail
    finally:
        db.close()


def test_db_write_failure_returns_5xx(tmp_db, reset_app_state, monkeypatch):
    """DB 写入失败时,POST /alerts/demo 必须返回 5xx,不能 silent success。"""
    _engine, SessionLocal = tmp_db
    user, _user_db = _insert_user(SessionLocal, 9011, "fail@example.com")

    async def fake_broadcast(*_a, **_k):
        return None

    monkeypatch.setattr(
        "server.services.alert_service.manager.broadcast_json", fake_broadcast
    )
    monkeypatch.setattr(
        "server.services.alert_service._send_alert_email_if_enabled", fake_broadcast
    )

    real_session = SessionLocal

    class _FailingSession:
        def __init__(self):
            self._inner = real_session()

        def add(self, obj):
            raise RuntimeError("simulated DB write failure")

        def commit(self):
            return self._inner.commit()

        def rollback(self):
            return self._inner.rollback()

        def close(self):
            return self._inner.close()

        def query(self, *a, **k):
            return self._inner.query(*a, **k)

        def refresh(self, obj):
            return self._inner.refresh(obj)

    monkeypatch.setattr(alerts_router, "SessionLocal", lambda: _FailingSession())
    monkeypatch.setattr(alert_service, "SessionLocal", lambda: _FailingSession())

    app = FastAPI()
    app.include_router(alerts_router.router)
    app.dependency_overrides[alerts_router.require_auth_user] = lambda: user
    app.dependency_overrides[alerts_router.get_db] = lambda: _FailingSession()
    client = TestClient(app)

    resp = client.post("/alerts/demo", json={"scenario": "sql_injection"})
    assert resp.status_code in (500, 503), (
        f"DB 写失败时应返回 5xx,实际 {resp.status_code}: {resp.text}"
    )


def test_restart_recovery_via_fresh_engine_connection(tmp_path, monkeypatch):
    """模拟进程重启:同一个 DB 文件 + 全新 SQLAlchemy engine 仍能读出 record / triage / history。

    本测试独立构造 tmp_db(不走 ``tmp_db`` fixture),用 ``tmp_path`` 直接传
    ``db_file``,然后丢弃原 engine,新建 engine + SessionLocal,模拟"重启后
    第一次连 DB"。
    """
    db_file = tmp_path / "restart_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    # ---- 阶段 A:旧"进程" ----
    old_engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.drop_all(bind=old_engine)
    Base.metadata.create_all(bind=old_engine)
    OldSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=old_engine)
    monkeypatch.setattr(db_module, "engine", old_engine, raising=False)
    monkeypatch.setattr(db_module, "SessionLocal", OldSessionLocal, raising=False)
    monkeypatch.setattr(alert_service, "SessionLocal", OldSessionLocal, raising=False)
    monkeypatch.setattr(alerts_router, "SessionLocal", OldSessionLocal, raising=False)

    user = User(id=9100, email="restart@example.com", is_active=True)
    db = OldSessionLocal()
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()

    async def fake_broadcast(*_a, **_k):
        return None
    monkeypatch.setattr(
        "server.services.alert_service.manager.broadcast_json", fake_broadcast
    )
    monkeypatch.setattr(
        "server.services.alert_service._send_alert_email_if_enabled", fake_broadcast
    )

    app_a = FastAPI()
    app_a.include_router(alerts_router.router)
    app_a.dependency_overrides[alerts_router.require_auth_user] = lambda: user
    app_a.dependency_overrides[alerts_router.get_db] = lambda: OldSessionLocal()
    client_a = TestClient(app_a)

    # 触发 demo + 2 次 triage
    created = client_a.post("/alerts/demo", json={"scenario": "sql_injection"})
    assert created.status_code == 200
    target_alert_id = created.json()["alert"]["alert_id"]
    client_a.patch(
        f"/alerts/{target_alert_id}/triage",
        json={"status": "investigating", "disposition": "needs_review", "analyst_note": "first"},
    )
    client_a.patch(
        f"/alerts/{target_alert_id}/triage",
        json={"status": "contained", "disposition": "blocked_at_waf", "analyst_note": "second"},
    )

    # 模拟"关闭旧连接"——dispose 旧 engine(类似进程退出)
    old_engine.dispose()
    app_state.alert.backlog.clear()  # backlog 也清空,模拟内存丢失

    # ---- 阶段 B:新"进程"(全新 engine,同一 DB 文件) ----
    new_engine = create_engine(db_url, connect_args={"check_same_thread": False})
    NewSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=new_engine)
    monkeypatch.setattr(db_module, "engine", new_engine, raising=False)
    monkeypatch.setattr(db_module, "SessionLocal", NewSessionLocal, raising=False)
    monkeypatch.setattr(alert_service, "SessionLocal", NewSessionLocal, raising=False)
    monkeypatch.setattr(alerts_router, "SessionLocal", NewSessionLocal, raising=False)

    # 1. 直接用新 session 查 DB(record + history 都在)
    from server.models_db import AlertRecord, AlertTriageEvent

    new_db = NewSessionLocal()
    try:
        rec = (
            new_db.query(AlertRecord)
            .filter(AlertRecord.user_id == 9100, AlertRecord.alert_id == target_alert_id)
            .first()
        )
        assert rec is not None, "重启后 record 丢失"
        assert rec.triage_status == "contained", f"重启后 triage 状态错误: {rec.triage_status}"
        assert rec.triage_disposition == "blocked_at_waf"
        assert rec.triage_note == "second"

        events = (
            new_db.query(AlertTriageEvent)
            .filter(AlertTriageEvent.alert_record_id == rec.id)
            .order_by(AlertTriageEvent.id.asc())
            .all()
        )
        assert len(events) == 2, f"重启后 history 缺失,实际 {len(events)}"
    finally:
        new_db.close()

    # 2. 用新 TestClient 验证 API
    user_reload = NewSessionLocal().query(User).filter(User.id == 9100).first()
    app_b = FastAPI()
    app_b.include_router(alerts_router.router)
    app_b.dependency_overrides[alerts_router.require_auth_user] = lambda: user_reload
    app_b.dependency_overrides[alerts_router.get_db] = lambda: NewSessionLocal()
    client_b = TestClient(app_b)

    resp_list = client_b.get("/alerts")
    assert resp_list.status_code == 200
    items = resp_list.json()["items"]
    target = next(item for item in items if item["alert_id"] == target_alert_id)
    assert target["triage"]["status"] == "contained"
    assert target["triage"]["disposition"] == "blocked_at_waf"
    assert target["triage"]["analyst_note"] == "second"

    resp_history = client_b.get(f"/alerts/{target_alert_id}/triage/history")
    assert resp_history.status_code == 200
    body = resp_history.json()
    assert body["count"] == 2
    notes = {item["analyst_note"] for item in body["items"]}
    assert notes == {"first", "second"}

    new_engine.dispose()
