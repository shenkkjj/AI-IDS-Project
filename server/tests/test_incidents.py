"""M3-04 安全事件 / 案件工作台 RED→GREEN 测试集。

设计目标（docs/agent/M3_04_INCIDENT_CASE_WORKBENCH_TASK.md §5/§9 阶段 3）:

- ``incidents`` 是案件事实来源；``incident_alert_links`` 是告警关联事实来源；
  ``incident_events`` 是事件时间线事实来源。
- ``POST /incidents`` 可以从 owner alert 创建 incident,自动 link alert。
- ``GET /incidents`` 只返回当前 user 的 incident。
- ``GET /incidents/{id}`` 返回 linked alerts + 最近事件时间线(newest-first)。
- ``PATCH /incidents/{id}`` 更新 status/severity/title/summary,写 incident_events。
- ``resolved / false_positive`` 自动设置 closed_at;从关闭态改回打开态清空 closed_at。
- ``POST /incidents/{id}/alerts`` link 第二条 alert;重复 link 幂等,不写新 active link / event。
- ``DELETE /incidents/{id}/alerts/{alert_id}`` 软删除 link(removed_at)。
- 非 owner / 不存在统一 404,不暴露存在性。
- ``incident_events.note`` 可由 owner API 返回,但 Log 仍不含完整 note。
- 审计 ``Log(action=incident_create / incident_update / incident_alert_link /
  incident_alert_unlink)`` 只写脱敏摘要。
- DB 写失败不允许 silent success;主路径返回 5xx。

所有测试用 ``tmp_path`` 临时 SQLite(``Base.metadata.create_all`` 一次性建表),
不污染真实 ``data/app.db``,也不需要预先跑 Alembic migration(避免把 RED 测试
和 migration ordering 绑死)。
"""
from __future__ import annotations

import asyncio
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
from server.core.config import ALERT_QUEUE_MAX_SIZE
from server.core.database import Base
from server.core.state import app_state
from server.models_db import User
from server.routers import alerts_router, incidents_router
from server.services import alert_service, incident_service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """临时 SQLite 库 + 替换 module-level engine / SessionLocal。"""
    db_file = tmp_path / "incidents_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    test_engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    monkeypatch.setattr(db_module, "engine", test_engine, raising=False)
    monkeypatch.setattr(db_module, "SessionLocal", TestSessionLocal, raising=False)
    monkeypatch.setattr(alert_service, "SessionLocal", TestSessionLocal, raising=False)
    monkeypatch.setattr(alerts_router, "SessionLocal", TestSessionLocal, raising=False)
    monkeypatch.setattr(incident_service, "SessionLocal", TestSessionLocal, raising=False)
    monkeypatch.setattr(incidents_router, "SessionLocal", TestSessionLocal, raising=False)

    try:
        yield test_engine, TestSessionLocal
    finally:
        test_engine.dispose()


@pytest.fixture
def reset_app_state(monkeypatch):
    """隔离 ``app_state.alert`` 的内存 backlog 和 queue。"""
    monkeypatch.setattr(state_module, "app_state", state_module.AppState())
    app_state.alert.queue = asyncio.Queue(maxsize=ALERT_QUEUE_MAX_SIZE)
    yield
    app_state.alert.backlog.clear()


def _build_alert_payload(user_id: int, *, alert_id: str | None = None) -> dict[str, Any]:
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
    app.include_router(incidents_router.router)
    app.dependency_overrides[incidents_router.require_auth_user] = lambda: user
    app.dependency_overrides[alerts_router.require_auth_user] = lambda: user
    app.dependency_overrides[incidents_router.get_db] = lambda: session_local()
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
# Tests: 创建 / 列表
# ---------------------------------------------------------------------------


def test_post_incident_creates_and_auto_links_alert(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """POST /incidents 携带 alert_id 时,创建 incident 并自动 link 该 alert。"""
    _engine, SessionLocal = tmp_db
    user, _user_db = _insert_user(SessionLocal, 7001, "creator@example.com")
    client, _sl = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    # 先创建一条 alert record(必须 commit 才能被后续请求读到)
    payload = _build_alert_payload(user.id)
    seed_db = SessionLocal()
    alert_service.persist_alert_record(seed_db, payload, user.id)
    seed_db.commit()
    seed_db.close()

    resp = client.post(
        "/incidents",
        json={
            "title": "SQL 注入案件",
            "summary": "同源 IP 多次注入",
            "severity": "high",
            "alert_id": payload["alert_id"],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ok"
    incident = body["incident"]
    assert incident["title"] == "SQL 注入案件"
    assert incident["severity"] == "high"
    assert incident["status"] == "open"
    assert incident["user_id"] == 7001
    assert incident["created_from_alert_id"] == payload["alert_id"]
    assert incident["closed_at"] is None
    assert incident["alert_count"] == 1
    # linked_alerts 必须含首条 alert
    linked = body["linked_alerts"]
    assert len(linked) == 1
    assert linked[0]["alert_id"] == payload["alert_id"]


def test_post_incident_from_other_user_alert_returns_404(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """非 owner alert_id 创建 incident 返回 404,不暴露存在性。"""
    _engine, SessionLocal = tmp_db
    owner, _o_db = _insert_user(SessionLocal, 7002, "owner-inc@example.com")
    intruder, _i_db = _insert_user(SessionLocal, 7003, "intruder-inc@example.com")

    # owner 创建 alert
    payload = _build_alert_payload(owner.id)
    seed_db = SessionLocal()
    alert_service.persist_alert_record(seed_db, payload, owner.id)
    seed_db.commit()
    seed_db.close()

    intruder_client, _ = _make_client(intruder, SessionLocal, monkeypatch=monkeypatch)
    resp = intruder_client.post(
        "/incidents",
        json={"title": "x", "severity": "high", "alert_id": payload["alert_id"]},
    )
    assert resp.status_code == 404


def test_get_incidents_returns_only_current_user(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """GET /incidents 只返回当前 user 的 incident。"""
    _engine, SessionLocal = tmp_db
    owner, _o_db = _insert_user(SessionLocal, 7004, "owner-list@example.com")
    intruder, _i_db = _insert_user(SessionLocal, 7005, "intruder-list@example.com")

    # 各创建自己的 incident
    owner_client, _ = _make_client(owner, SessionLocal, monkeypatch=monkeypatch)
    intruder_client, _ = _make_client(intruder, SessionLocal, monkeypatch=monkeypatch)

    owner_resp = owner_client.post(
        "/incidents",
        json={"title": "owner case", "severity": "high"},
    )
    assert owner_resp.status_code == 200
    owner_incident_id = owner_resp.json()["incident"]["incident_id"]

    intruder_resp = intruder_client.post(
        "/incidents",
        json={"title": "intruder case", "severity": "low"},
    )
    assert intruder_resp.status_code == 200

    list_owner = owner_client.get("/incidents")
    assert list_owner.status_code == 200
    body = list_owner.json()
    assert body["count"] == 1
    assert body["items"][0]["incident_id"] == owner_incident_id
    assert body["items"][0]["title"] == "owner case"


def test_get_incident_detail_returns_linked_alerts_and_events(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """GET /incidents/{id} 返回 linked alerts + 时间线(默认 limit=20, newest-first)。"""
    _engine, SessionLocal = tmp_db
    user, _user_db = _insert_user(SessionLocal, 7006, "detail@example.com")
    client, _sl = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    payload = _build_alert_payload(user.id)
    seed_db = SessionLocal()
    alert_service.persist_alert_record(seed_db, payload, user.id)
    seed_db.commit()
    seed_db.close()

    create_resp = client.post(
        "/incidents",
        json={"title": "t", "severity": "high", "alert_id": payload["alert_id"]},
    )
    incident_id = create_resp.json()["incident"]["incident_id"]

    # PATCH 两次触发 status_changed 事件
    client.patch(
        f"/incidents/{incident_id}",
        json={"status": "investigating", "note": "first note"},
    )
    client.patch(
        f"/incidents/{incident_id}",
        json={"status": "contained", "note": "second note"},
    )

    detail = client.get(f"/incidents/{incident_id}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["incident"]["incident_id"] == incident_id
    # linked_alerts 应含 1 条
    assert len(body["linked_alerts"]) == 1
    assert body["linked_alerts"][0]["alert_id"] == payload["alert_id"]
    # events 应含 created + 2 次 status_changed(顺序: newest-first)
    events = body["events"]
    assert len(events) >= 3
    # newest-first: 第一个应该是最近一次 status_changed
    first = events[0]
    assert first["event_type"] == "status_changed"
    assert first["to_status"] == "contained"
    assert first["from_status"] == "investigating"
    # note 必须可被 owner API 看到
    assert first["note"] == "second note"
    # created 应排在最后
    assert events[-1]["event_type"] == "created"


# ---------------------------------------------------------------------------
# Tests: PATCH
# ---------------------------------------------------------------------------


def test_patch_incident_updates_status_and_severity_with_events(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """PATCH /incidents/{id} 改 status / severity 时写 incident_events。"""
    _engine, SessionLocal = tmp_db
    user, _user_db = _insert_user(SessionLocal, 7007, "patch@example.com")
    client, _sl = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    create_resp = client.post(
        "/incidents",
        json={"title": "t", "severity": "high"},
    )
    incident_id = create_resp.json()["incident"]["incident_id"]

    resp = client.patch(
        f"/incidents/{incident_id}",
        json={
            "status": "investigating",
            "severity": "critical",
            "title": "updated title",
            "summary": "updated summary",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["incident"]["status"] == "investigating"
    assert body["incident"]["severity"] == "critical"
    assert body["incident"]["title"] == "updated title"
    assert body["incident"]["summary"] == "updated summary"

    # 时间线里应该有 status_changed + severity_changed + summary_updated
    events = body["events"]
    event_types = {e["event_type"] for e in events}
    assert "status_changed" in event_types
    assert "severity_changed" in event_types


def test_resolved_sets_closed_at_and_reopen_clears_it(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """resolved / false_positive 自动设置 closed_at;改回 investigating 清空。"""
    _engine, SessionLocal = tmp_db
    user, _user_db = _insert_user(SessionLocal, 7008, "close@example.com")
    client, _sl = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    create_resp = client.post(
        "/incidents",
        json={"title": "t", "severity": "high"},
    )
    incident_id = create_resp.json()["incident"]["incident_id"]
    assert create_resp.json()["incident"]["closed_at"] is None

    # resolved 应自动设置 closed_at
    resp_resolved = client.patch(
        f"/incidents/{incident_id}",
        json={"status": "resolved"},
    )
    assert resp_resolved.status_code == 200
    closed_at = resp_resolved.json()["incident"]["closed_at"]
    assert closed_at is not None and closed_at > 0

    # 改回 investigating 应清空 closed_at
    resp_reopen = client.patch(
        f"/incidents/{incident_id}",
        json={"status": "investigating"},
    )
    assert resp_reopen.status_code == 200
    assert resp_reopen.json()["incident"]["closed_at"] is None

    # false_positive 也应自动设置 closed_at
    resp_fp = client.patch(
        f"/incidents/{incident_id}",
        json={"status": "false_positive"},
    )
    assert resp_fp.status_code == 200
    assert resp_fp.json()["incident"]["closed_at"] is not None


# ---------------------------------------------------------------------------
# Tests: link / unlink
# ---------------------------------------------------------------------------


def test_post_incident_alert_links_second_alert(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """POST /incidents/{id}/alerts 可 link 第二条 alert,不影响首条。"""
    _engine, SessionLocal = tmp_db
    user, _user_db = _insert_user(SessionLocal, 7009, "link2@example.com")
    client, _sl = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    # 第一条 alert
    first_payload = _build_alert_payload(user.id)
    seed_db = SessionLocal()
    alert_service.persist_alert_record(seed_db, first_payload, user.id)
    seed_db.commit()
    seed_db.close()

    create_resp = client.post(
        "/incidents",
        json={"title": "t", "severity": "high", "alert_id": first_payload["alert_id"]},
    )
    incident_id = create_resp.json()["incident"]["incident_id"]

    # 第二条 alert
    second_payload = _build_alert_payload(user.id)
    seed_db2 = SessionLocal()
    alert_service.persist_alert_record(seed_db2, second_payload, user.id)
    seed_db2.commit()
    seed_db2.close()

    link_resp = client.post(
        f"/incidents/{incident_id}/alerts",
        json={"alert_id": second_payload["alert_id"]},
    )
    assert link_resp.status_code == 200, link_resp.text
    body = link_resp.json()
    assert body["status"] == "ok"
    assert body["alert_count"] == 2

    detail = client.get(f"/incidents/{incident_id}")
    linked_ids = {a["alert_id"] for a in detail.json()["linked_alerts"]}
    assert linked_ids == {first_payload["alert_id"], second_payload["alert_id"]}


def test_post_incident_alert_idempotent_for_duplicate_link(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """重复 link 同一 alert 幂等,不创建新 active link,不写新 incident_events。"""
    _engine, SessionLocal = tmp_db
    user, _user_db = _insert_user(SessionLocal, 7010, "idempotent@example.com")
    client, _sl = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    payload = _build_alert_payload(user.id)
    seed_db = SessionLocal()
    alert_service.persist_alert_record(seed_db, payload, user.id)
    seed_db.commit()
    seed_db.close()

    create_resp = client.post(
        "/incidents",
        json={"title": "t", "severity": "high", "alert_id": payload["alert_id"]},
    )
    incident_id = create_resp.json()["incident"]["incident_id"]
    before_events = create_resp.json()["events"]
    before_event_count = len(before_events)

    # 重复 link 同一 alert
    dup_resp = client.post(
        f"/incidents/{incident_id}/alerts",
        json={"alert_id": payload["alert_id"]},
    )
    assert dup_resp.status_code == 200
    assert dup_resp.json()["alert_count"] == 1

    detail = client.get(f"/incidents/{incident_id}")
    events = detail.json()["events"]
    # 重复 link 后 alert_linked 事件总数应保持不变(create 时已写一次)
    after_linked_count = sum(1 for e in events if e["event_type"] == "alert_linked")
    assert after_linked_count == 1, (
        f"重复 link 不应新增 alert_linked 事件;实际 {after_linked_count}"
    )
    # 总事件数也不应增加
    assert len(events) == before_event_count, (
        f"重复 link 事件数变化: before={before_event_count}, after={len(events)}"
    )


def test_delete_incident_alert_soft_deletes_link(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """DELETE /incidents/{id}/alerts/{alert_id} 软删除 link(removed_at),不删 alert。"""
    _engine, SessionLocal = tmp_db
    user, _user_db = _insert_user(SessionLocal, 7011, "unlink@example.com")
    client, _sl = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    payload = _build_alert_payload(user.id)
    seed_db = SessionLocal()
    alert_service.persist_alert_record(seed_db, payload, user.id)
    seed_db.commit()
    seed_db.close()

    create_resp = client.post(
        "/incidents",
        json={"title": "t", "severity": "high", "alert_id": payload["alert_id"]},
    )
    incident_id = create_resp.json()["incident"]["incident_id"]

    # unlink
    del_resp = client.delete(
        f"/incidents/{incident_id}/alerts/{payload['alert_id']}"
    )
    assert del_resp.status_code == 200, del_resp.text
    assert del_resp.json()["status"] == "ok"

    # linked_alerts 应为空
    detail = client.get(f"/incidents/{incident_id}")
    assert detail.json()["linked_alerts"] == []
    # 事件应有 alert_unlinked
    event_types = {e["event_type"] for e in detail.json()["events"]}
    assert "alert_unlinked" in event_types

    # alert_records 必须仍然存在(不应被删除)
    from server.models_db import AlertRecord

    db = SessionLocal()
    try:
        rec = (
            db.query(AlertRecord)
            .filter(AlertRecord.user_id == user.id, AlertRecord.alert_id == payload["alert_id"])
            .first()
        )
        assert rec is not None, "unlink 不应删除 alert_records"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tests: owner 隔离 / 404
# ---------------------------------------------------------------------------


def test_get_incident_other_user_returns_404(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """非 owner 查 /incidents/{id} 返回 404,不暴露存在性。"""
    _engine, SessionLocal = tmp_db
    owner, _o_db = _insert_user(SessionLocal, 7012, "owner-iso@example.com")
    intruder, _i_db = _insert_user(SessionLocal, 7013, "intruder-iso@example.com")

    owner_client, _ = _make_client(owner, SessionLocal, monkeypatch=monkeypatch)
    intruder_client, _ = _make_client(intruder, SessionLocal, monkeypatch=monkeypatch)

    create_resp = owner_client.post(
        "/incidents",
        json={"title": "secret case", "severity": "high"},
    )
    incident_id = create_resp.json()["incident"]["incident_id"]

    intr = intruder_client.get(f"/incidents/{incident_id}")
    assert intr.status_code == 404


def test_patch_incident_other_user_returns_404(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """非 owner PATCH 别人 incident 返回 404。"""
    _engine, SessionLocal = tmp_db
    owner, _o_db = _insert_user(SessionLocal, 7014, "owner-patch@example.com")
    intruder, _i_db = _insert_user(SessionLocal, 7015, "intruder-patch@example.com")

    owner_client, _ = _make_client(owner, SessionLocal, monkeypatch=monkeypatch)
    intruder_client, _ = _make_client(intruder, SessionLocal, monkeypatch=monkeypatch)

    create_resp = owner_client.post(
        "/incidents",
        json={"title": "secret", "severity": "high"},
    )
    incident_id = create_resp.json()["incident"]["incident_id"]

    intr = intruder_client.patch(
        f"/incidents/{incident_id}",
        json={"status": "resolved"},
    )
    assert intr.status_code == 404


def test_link_other_user_incident_returns_404(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """非 owner 往别人 incident 加 alert 返回 404。"""
    _engine, SessionLocal = tmp_db
    owner, _o_db = _insert_user(SessionLocal, 7016, "owner-link@example.com")
    intruder, _i_db = _insert_user(SessionLocal, 7017, "intruder-link@example.com")

    owner_client, _ = _make_client(owner, SessionLocal, monkeypatch=monkeypatch)
    intruder_client, _ = _make_client(intruder, SessionLocal, monkeypatch=monkeypatch)

    # owner 创建 incident
    create_resp = owner_client.post(
        "/incidents",
        json={"title": "private", "severity": "high"},
    )
    incident_id = create_resp.json()["incident"]["incident_id"]

    # intruder 准备自己的 alert
    intruder_payload = _build_alert_payload(intruder.id)
    seed_db = SessionLocal()
    alert_service.persist_alert_record(seed_db, intruder_payload, intruder.id)
    seed_db.commit()
    seed_db.close()

    intr = intruder_client.post(
        f"/incidents/{incident_id}/alerts",
        json={"alert_id": intruder_payload["alert_id"]},
    )
    assert intr.status_code == 404


# ---------------------------------------------------------------------------
# Tests: 审计 / 脱敏
# ---------------------------------------------------------------------------


def test_incident_audit_log_does_not_contain_full_note(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """Log 写脱敏摘要,不含完整 note / secret / stack trace。"""
    _engine, SessionLocal = tmp_db
    user, _user_db = _insert_user(SessionLocal, 7018, "audit@example.com")
    client, _sl = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    note = "这是案件 note · fake-key sk-test-abcdef0123456789 详细证据"
    create_resp = client.post(
        "/incidents",
        json={"title": "t", "severity": "high", "summary": note},
    )
    assert create_resp.status_code == 200

    from server.models_db import Log

    db = SessionLocal()
    try:
        logs = (
            db.query(Log)
            .filter(Log.user_id == user.id, Log.action == "incident_create")
            .order_by(Log.id.desc())
            .all()
        )
        assert logs, "incident_create Log 缺失"
        detail = logs[0].detail
        # detail 不应含完整 note
        assert note not in detail, f"审计 detail 含完整 note: {detail[:200]}"
        # detail 不应含 fake key
        assert "sk-test-abcdef0123456789" not in detail
        _assert_no_secret_in_text(detail)
    finally:
        db.close()


def test_incident_note_accessible_via_owner_api_only(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """incident_events.note 必须可由 owner API 返回(供前端显示)。"""
    _engine, SessionLocal = tmp_db
    user, _user_db = _insert_user(SessionLocal, 7019, "note@example.com")
    client, _sl = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    create_resp = client.post(
        "/incidents",
        json={"title": "t", "severity": "high"},
    )
    incident_id = create_resp.json()["incident"]["incident_id"]

    # PATCH with note
    client.patch(
        f"/incidents/{incident_id}",
        json={"status": "investigating", "note": "owner-private-note"},
    )

    detail = client.get(f"/incidents/{incident_id}")
    events = detail.json()["events"]
    note_added = [e for e in events if e["event_type"] == "status_changed"]
    assert note_added
    assert note_added[0]["note"] == "owner-private-note"


# ---------------------------------------------------------------------------
# Tests: 字段校验
# ---------------------------------------------------------------------------


def test_post_incident_invalid_severity_returns_422(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    _engine, SessionLocal = tmp_db
    user, _user_db = _insert_user(SessionLocal, 7020, "validate@example.com")
    client, _sl = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    resp = client.post(
        "/incidents",
        json={"title": "t", "severity": "catastrophic"},
    )
    assert resp.status_code == 422


def test_post_incident_title_too_long_returns_422(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    _engine, SessionLocal = tmp_db
    user, _user_db = _insert_user(SessionLocal, 7021, "title@example.com")
    client, _sl = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    resp = client.post(
        "/incidents",
        json={"title": "x" * 121, "severity": "high"},
    )
    assert resp.status_code == 422


def test_get_incidents_limit_out_of_range_returns_422(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    _engine, SessionLocal = tmp_db
    user, _user_db = _insert_user(SessionLocal, 7022, "limit@example.com")
    client, _sl = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    assert client.get("/incidents?limit=0").status_code == 422
    assert client.get("/incidents?limit=101").status_code == 422
    assert client.get("/incidents?limit=50").status_code == 200
