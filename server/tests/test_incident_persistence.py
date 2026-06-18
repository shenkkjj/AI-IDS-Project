"""M3-04 安全事件 / 案件持久化重启恢复测试。

设计目标（docs/agent/M3_04_INCIDENT_CASE_WORKBENCH_TASK.md §9 阶段 9）:

- 清空 ``app_state.alert.backlog`` 并使用全新 SQLAlchemy engine + 同一 DB 文件,
  仍能读出 incident / linked_alerts / incident_events。
- 本测试独立构造 tmp_db,不走 ``tmp_db`` fixture,直接用 ``tmp_path`` 传 ``db_file``。
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import server.core.database as db_module
from server.core.database import Base
from server.models_db import User
from server.routers import alerts_router, incidents_router
from server.services import alert_service


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


def test_incident_detail_recovers_from_fresh_engine(tmp_path, monkeypatch) -> None:
    """同一 DB 文件 + 全新 engine,``GET /incidents/{id}`` 仍能从 DB 恢复 incident + linked alerts + events。"""
    db_file = tmp_path / "incident_restart.db"
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
    monkeypatch.setattr(incidents_router, "SessionLocal", OldSessionLocal, raising=False)

    user = User(id=7200, email="incident-restart@example.com", is_active=True)
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

    app_a = FastAPI()
    app_a.include_router(alerts_router.router)
    app_a.include_router(incidents_router.router)
    app_a.dependency_overrides[incidents_router.require_auth_user] = lambda: user
    app_a.dependency_overrides[alerts_router.require_auth_user] = lambda: user
    app_a.dependency_overrides[incidents_router.get_db] = lambda: OldSessionLocal()
    app_a.dependency_overrides[alerts_router.get_db] = lambda: OldSessionLocal()
    client_a = TestClient(app_a)

    # 准备 alert + 创建 incident + 多次 PATCH
    payload = _build_alert_payload(user.id)
    seed_db = OldSessionLocal()
    alert_service.persist_alert_record(seed_db, payload, user.id)
    seed_db.commit()
    seed_db.close()

    create = client_a.post(
        "/incidents",
        json={"title": "restart test", "severity": "high", "alert_id": payload["alert_id"]},
    )
    assert create.status_code == 200
    incident_id = create.json()["incident"]["incident_id"]

    client_a.patch(
        f"/incidents/{incident_id}",
        json={"status": "investigating", "note": "first note"},
    )
    client_a.patch(
        f"/incidents/{incident_id}",
        json={"status": "contained", "note": "second note"},
    )

    # 关闭旧连接
    old_engine.dispose()

    # ---- 阶段 B:新"进程"(全新 engine, 同一 DB 文件) ----
    new_engine = create_engine(db_url, connect_args={"check_same_thread": False})
    NewSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=new_engine)
    monkeypatch.setattr(db_module, "engine", new_engine, raising=False)
    monkeypatch.setattr(db_module, "SessionLocal", NewSessionLocal, raising=False)
    monkeypatch.setattr(alert_service, "SessionLocal", NewSessionLocal, raising=False)
    monkeypatch.setattr(alerts_router, "SessionLocal", NewSessionLocal, raising=False)
    monkeypatch.setattr(incidents_router, "SessionLocal", NewSessionLocal, raising=False)

    # 1. 直接 query DB 验证数据落盘
    from server.models_db import (
        Incident,
        IncidentAlertLink,
        IncidentEvent,
    )

    new_db = NewSessionLocal()
    try:
        inc = (
            new_db.query(Incident)
            .filter(Incident.user_id == 7200, Incident.incident_id == incident_id)
            .first()
        )
        assert inc is not None, "重启后 incident 记录丢失"
        assert inc.title == "restart test"
        assert inc.severity == "high"
        assert inc.status == "contained"
        assert inc.closed_at is None  # contained 是中间态,不应设 closed_at

        links = (
            new_db.query(IncidentAlertLink)
            .filter(IncidentAlertLink.incident_record_id == inc.id, IncidentAlertLink.removed_at.is_(None))
            .all()
        )
        assert len(links) == 1
        assert links[0].alert_id == payload["alert_id"]

        events = (
            new_db.query(IncidentEvent)
            .filter(IncidentEvent.incident_record_id == inc.id)
            .order_by(IncidentEvent.id.asc())
            .all()
        )
        # 至少: created + 2 次 status_changed
        assert len(events) >= 3
        assert events[0].event_type == "created"
        assert any(e.event_type == "status_changed" and e.to_status == "investigating" for e in events)
        assert any(e.event_type == "status_changed" and e.to_status == "contained" for e in events)
    finally:
        new_db.close()

    # 2. 用新 TestClient 验证 API
    user_reload = NewSessionLocal().query(User).filter(User.id == 7200).first()
    app_b = FastAPI()
    app_b.include_router(alerts_router.router)
    app_b.include_router(incidents_router.router)
    app_b.dependency_overrides[incidents_router.require_auth_user] = lambda: user_reload
    app_b.dependency_overrides[alerts_router.require_auth_user] = lambda: user_reload
    app_b.dependency_overrides[incidents_router.get_db] = lambda: NewSessionLocal()
    app_b.dependency_overrides[alerts_router.get_db] = lambda: NewSessionLocal()
    client_b = TestClient(app_b)

    list_resp = client_b.get("/incidents")
    assert list_resp.status_code == 200
    assert list_resp.json()["count"] == 1
    assert list_resp.json()["items"][0]["incident_id"] == incident_id

    detail_resp = client_b.get(f"/incidents/{incident_id}")
    assert detail_resp.status_code == 200
    body = detail_resp.json()
    assert body["incident"]["status"] == "contained"
    assert body["incident"]["title"] == "restart test"
    assert len(body["linked_alerts"]) == 1
    assert body["linked_alerts"][0]["alert_id"] == payload["alert_id"]
    # events 必须含 status_changed + note
    event_types = {e["event_type"] for e in body["events"]}
    assert "status_changed" in event_types

    new_engine.dispose()
