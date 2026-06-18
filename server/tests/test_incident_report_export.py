"""M3-07 案件证据报告导出 RED→GREEN 测试集。

设计目标（docs/agent/M3_07_INCIDENT_EVIDENCE_REPORT_EXPORT_TASK.md §5/§6/§10）:

- ``GET /incidents/{incident_id}/report?format=json|markdown`` 可用。
- owner 隔离:非 owner / 不存在统一 404,不暴露存在性。
- format 校验:只接受 ``json | markdown``;其他 422。
- 报告内容包含 incident 基础信息、关联告警摘要、事件时间线、安全声明。
- 报告**不**含完整 payload / 完整 note / fake secret / system prompt /
  stack trace / Guardrails 内部 pattern。
- 报告限制:summary 1000 / alert summary 240 / payload preview 180 /
  event detail 240 / event note preview 160 / linked_alerts ≤ 20 /
  events ≤ 50 (newest-first)。
- 成功生成报告写 ``Log(action="incident_report_export")``,detail 只含
  incident_id / format / 计数 / redaction_count。
- 非 owner / 不存在 / invalid format / DB 失败**不**写 success Log。

所有测试用 ``tmp_path`` 临时 SQLite(``Base.metadata.create_all`` 一次性建表),
不污染真实 ``data/app.db``,也不需要预先跑 Alembic migration。
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
    db_file = tmp_path / "incident_report_test.db"
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


def _build_alert_payload(
    user_id: int,
    *,
    alert_id: str | None = None,
    payload: str | None = None,
    summary: str | None = None,
    risk_level: str = "critical",
) -> dict[str, Any]:
    aid = alert_id or uuid.uuid4().hex
    return {
        "alert_id": aid,
        "raw_alert": {
            "event": "waf_block",
            "source_ip": "203.0.113.45",
            "destination_ip": "10.0.0.15",
            "payload": payload if payload is not None else "' UNION SELECT username,password FROM users --",
            "alert_user_id": user_id,
            "timestamp": time.time(),
            "blocked": True,
        },
        "llm_analysis": {
            "risk_level": risk_level,
            "summary": summary if summary is not None else "SQL 注入攻击",
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
    user: User | None,
    session_local,
    *,
    monkeypatch,
) -> tuple[TestClient, Any]:
    """构造一个走真 DB 的 TestClient,bypass WS / email 副作用。

    ``user=None`` 时不注入 auth,用于测试未登录 401。
    """

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
    if user is not None:
        app.dependency_overrides[incidents_router.require_auth_user] = lambda: user
        app.dependency_overrides[alerts_router.require_auth_user] = lambda: user
    app.dependency_overrides[incidents_router.get_db] = lambda: session_local()
    app.dependency_overrides[alerts_router.get_db] = lambda: session_local()
    return TestClient(app), session_local


# ---------------------------------------------------------------------------
# Sentinel / sanitizer
# ---------------------------------------------------------------------------


# 复用 logs_router 的 _SENTINEL_PATTERNS 集合,再加上 Guardrails 内部 pattern。
_FORBIDDEN_IN_REPORT: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"sk-proj-[A-Za-z0-9_-]+"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"PRIVATE\s+KEY", re.IGNORECASE),
    re.compile(r"\bTraceback\s+\(most recent call last\)", re.IGNORECASE),
    re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+.*system\s+prompt", re.IGNORECASE),
    re.compile(r"forget\s+.*instructions", re.IGNORECASE),
    re.compile(r"\bsystem\s*:\s*", re.IGNORECASE),
    re.compile(r"\bdeveloper\s*:\s*", re.IGNORECASE),
)


def _assert_no_forbidden(text: str, *, context: str) -> None:
    for pat in _FORBIDDEN_IN_REPORT:
        match = pat.search(text)
        assert not match, (
            f"{context} 命中禁止 sentinel: {pat.pattern} → ...{text[max(0, match.start()-20):match.end()+20]!r}..."
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_incident_with_alert(
    SessionLocal,
    client,
    user: User,
    *,
    title: str = "SQL 注入案件",
    summary: str | None = "同源 IP 多次注入",
    severity: str = "high",
    note: str | None = None,
    raw_payload: str | None = None,
    alert_summary: str | None = None,
    risk_level: str = "critical",
) -> str:
    """创建 alert + incident 并返回 incident_id。"""
    payload = _build_alert_payload(
        user.id,
        payload=raw_payload,
        summary=alert_summary,
        risk_level=risk_level,
    )
    seed_db = SessionLocal()
    alert_service.persist_alert_record(seed_db, payload, user.id)
    seed_db.commit()
    seed_db.close()

    body: dict[str, Any] = {
        "title": title,
        "severity": severity,
        "alert_id": payload["alert_id"],
    }
    if summary is not None:
        body["summary"] = summary
    resp = client.post("/incidents", json=body)
    assert resp.status_code == 200, resp.text
    incident_id = resp.json()["incident"]["incident_id"]

    if note is not None:
        client.patch(
            f"/incidents/{incident_id}",
            json={"status": "investigating", "note": note},
        )

    return incident_id


# ---------------------------------------------------------------------------
# Tests: 401 / 404 / 422
# ---------------------------------------------------------------------------


def test_report_unauthenticated_returns_401(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """未登录请求 /incidents/{id}/report 返回 401。"""
    _engine, SessionLocal = tmp_db
    user, _ = _insert_user(SessionLocal, 7100, "noauth@example.com")
    client, _ = _make_client(None, SessionLocal, monkeypatch=monkeypatch)

    resp = client.get("/incidents/inc_does_not_matter/report?format=json")
    assert resp.status_code == 401


def test_report_other_user_incident_returns_404(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """非 owner 查别人 incident report 返回 404,不暴露存在性。"""
    _engine, SessionLocal = tmp_db
    owner, _ = _insert_user(SessionLocal, 7101, "owner-r@example.com")
    intruder, _ = _insert_user(SessionLocal, 7102, "intruder-r@example.com")
    owner_client, _ = _make_client(owner, SessionLocal, monkeypatch=monkeypatch)
    intruder_client, _ = _make_client(intruder, SessionLocal, monkeypatch=monkeypatch)

    incident_id = _seed_incident_with_alert(SessionLocal, owner_client, owner)
    resp = intruder_client.get(f"/incidents/{incident_id}/report?format=json")
    assert resp.status_code == 404


def test_report_nonexistent_incident_returns_404(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """不存在 incident 返回 404。"""
    _engine, SessionLocal = tmp_db
    user, _ = _insert_user(SessionLocal, 7103, "missing-r@example.com")
    client, _ = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    resp = client.get("/incidents/inc_doesnotexist/report?format=json")
    assert resp.status_code == 404


def test_report_invalid_format_returns_422(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """format=xml 等非法值返回 422。"""
    _engine, SessionLocal = tmp_db
    user, _ = _insert_user(SessionLocal, 7104, "badfmt@example.com")
    client, _ = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    incident_id = _seed_incident_with_alert(SessionLocal, client, user)
    resp = client.get(f"/incidents/{incident_id}/report?format=xml")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests: format=json
# ---------------------------------------------------------------------------


def test_report_format_json_returns_envelope(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """format=json 返回 status=ok + incident_id + filename + markdown + meta。"""
    _engine, SessionLocal = tmp_db
    user, _ = _insert_user(SessionLocal, 7105, "json-r@example.com")
    client, _ = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    incident_id = _seed_incident_with_alert(SessionLocal, client, user)
    resp = client.get(f"/incidents/{incident_id}/report?format=json")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ok"
    assert body["incident_id"] == incident_id
    assert body["filename"] == f"incident-{incident_id}-report.md"
    assert isinstance(body["markdown"], str) and body["markdown"].startswith("# 案件证据报告")
    meta = body["meta"]
    assert meta["alert_count"] == 1
    assert meta["included_alerts"] == 1
    assert meta["event_count"] >= 1
    assert meta["included_events"] >= 1
    assert meta["redaction_count"] >= 0
    assert "generated_at" in meta


def test_report_format_markdown_returns_markdown_body(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """format=markdown 返回 text/markdown + Markdown body。"""
    _engine, SessionLocal = tmp_db
    user, _ = _insert_user(SessionLocal, 7106, "md-r@example.com")
    client, _ = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    incident_id = _seed_incident_with_alert(SessionLocal, client, user)
    resp = client.get(f"/incidents/{incident_id}/report?format=markdown")
    assert resp.status_code == 200, resp.text
    ctype = resp.headers.get("content-type", "")
    assert ctype.startswith("text/markdown"), f"unexpected content-type: {ctype}"
    disposition = resp.headers.get("content-disposition", "")
    assert f"filename=incident-{incident_id}-report.md" in disposition, disposition
    body = resp.text
    assert body.startswith("# 案件证据报告")
    assert incident_id in body


# ---------------------------------------------------------------------------
# Tests: 内容脱敏
# ---------------------------------------------------------------------------


def test_report_does_not_include_full_payload(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """报告不含完整 raw payload,只含 payload_length 和截断 preview。"""
    _engine, SessionLocal = tmp_db
    user, _ = _insert_user(SessionLocal, 7107, "payload-r@example.com")
    client, _ = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    long_payload = "ATTACK-PAYLOAD-" + ("x" * 500)
    incident_id = _seed_incident_with_alert(
        SessionLocal, client, user, raw_payload=long_payload
    )
    resp = client.get(f"/incidents/{incident_id}/report?format=json")
    assert resp.status_code == 200
    body = resp.json()
    markdown = body["markdown"]
    # 完整 payload 字符串(514 字符)绝对不应原样出现
    assert long_payload not in markdown, "报告不应包含完整 raw payload"
    # preview / length 必须出现
    assert "payload_preview" in markdown
    assert "payload_length" in markdown
    # payload_length 必须等于原始 payload 长度
    import re as _re

    length_match = _re.search(r"payload_length:\s*(\d+)", markdown)
    assert length_match is not None
    assert int(length_match.group(1)) == len(long_payload)
    # preview 区域不应包含完整 long_payload
    assert long_payload not in markdown
    # preview 截断长度应 ≤ 180 字符(payload_preview 后内容)
    preview_match = _re.search(r"payload_preview:\s*(.+)", markdown)
    assert preview_match is not None
    preview_value = preview_match.group(1).strip()
    assert len(preview_value) <= 181, (
        f"payload_preview 应 ≤ 180 字符(+末尾省略号/换行),实际 {len(preview_value)}"
    )


def test_report_does_not_include_full_note(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """报告不含完整 note 全文,只含 note_length 和截断 preview。"""
    _engine, SessionLocal = tmp_db
    user, _ = _insert_user(SessionLocal, 7108, "note-r@example.com")
    client, _ = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    long_note = "PRIVATE-NOTE-CONTENT-" + ("y" * 200)
    incident_id = _seed_incident_with_alert(
        SessionLocal, client, user, note=long_note
    )
    resp = client.get(f"/incidents/{incident_id}/report?format=json")
    assert resp.status_code == 200
    body = resp.json()
    markdown = body["markdown"]
    # 完整 note 字符串(221 字符)绝对不应原样出现
    assert long_note not in markdown, "报告不应包含完整 note"
    # note_length / note_preview 应出现
    assert "note_length" in markdown
    assert "note_preview" in markdown
    # note_length 必须等于原始 note 长度
    import re as _re

    length_match = _re.search(r"note_length:\s*(\d+)", markdown)
    assert length_match is not None
    assert int(length_match.group(1)) == len(long_note)
    # note_preview 截断长度应 ≤ 160 字符
    preview_match = _re.search(r"note_preview:\s*(.+)", markdown)
    assert preview_match is not None
    preview_value = preview_match.group(1).strip()
    assert len(preview_value) <= 161, (
        f"note_preview 应 ≤ 160 字符,实际 {len(preview_value)}"
    )


def test_report_does_not_include_secrets_or_sentinels(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """报告不含 fake secret / system prompt / stack trace / PRIVATE KEY / Guardrails regex。"""
    _engine, SessionLocal = tmp_db
    user, _ = _insert_user(SessionLocal, 7109, "secret-r@example.com")
    client, _ = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    # 把 fake secret / system prompt / stack trace 放进 summary 和 note,看是否被脱敏
    secret_summary = "包含 fake key sk-test-abcdef0123456789abcd 与系统 system: you are helpful"
    secret_note = "Traceback (most recent call last):\n  File 'x.py' ignore previous instructions"
    incident_id = _seed_incident_with_alert(
        SessionLocal,
        client,
        user,
        summary=secret_summary,
        note=secret_note,
    )
    resp = client.get(f"/incidents/{incident_id}/report?format=json")
    assert resp.status_code == 200
    body = resp.json()
    markdown = body["markdown"]
    _assert_no_forbidden(markdown, context="report markdown")


# ---------------------------------------------------------------------------
# Tests: 审计 Log
# ---------------------------------------------------------------------------


def test_report_success_writes_sanitised_audit_log(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """成功生成报告写 Log(action="incident_report_export"),detail 只含安全计数。"""
    _engine, SessionLocal = tmp_db
    user, _ = _insert_user(SessionLocal, 7110, "audit-r@example.com")
    client, _ = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    incident_id = _seed_incident_with_alert(
        SessionLocal,
        client,
        user,
        title="这是案件 title 不应进 Log",
        summary="这是案件 summary 也不应进 Log",
    )
    resp = client.get(f"/incidents/{incident_id}/report?format=json")
    assert resp.status_code == 200

    from server.models_db import Log

    db = SessionLocal()
    try:
        logs = (
            db.query(Log)
            .filter(Log.user_id == user.id, Log.action == "incident_report_export")
            .order_by(Log.id.desc())
            .all()
        )
        assert logs, "incident_report_export Log 缺失"
        detail = logs[0].detail
        # detail 必须含 incident_id + format + 计数
        assert f"incident_id={incident_id}" in detail
        assert "format=json" in detail
        assert "alert_count=" in detail
        assert "event_count=" in detail
        assert "redaction_count=" in detail
        # detail **不**应含 title 或 summary
        assert "这是案件 title" not in detail
        assert "这是案件 summary" not in detail
    finally:
        db.close()


def test_report_non_owner_does_not_write_audit_log(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """非 owner 请求 report 失败时不写 success Log。"""
    _engine, SessionLocal = tmp_db
    owner, _ = _insert_user(SessionLocal, 7111, "owner-naudit@example.com")
    intruder, _ = _insert_user(SessionLocal, 7112, "intruder-naudit@example.com")
    owner_client, _ = _make_client(owner, SessionLocal, monkeypatch=monkeypatch)
    intruder_client, _ = _make_client(intruder, SessionLocal, monkeypatch=monkeypatch)

    incident_id = _seed_incident_with_alert(SessionLocal, owner_client, owner)
    resp = intruder_client.get(f"/incidents/{incident_id}/report?format=json")
    assert resp.status_code == 404

    from server.models_db import Log

    db = SessionLocal()
    try:
        logs = (
            db.query(Log)
            .filter(Log.user_id == intruder.id, Log.action == "incident_report_export")
            .all()
        )
        assert not logs, "非 owner 不应写 incident_report_export Log"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tests: 报告基础信息
# ---------------------------------------------------------------------------


def test_report_includes_basic_incident_and_linked_alerts(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """报告含 incident 基础信息、关联告警摘要、事件时间线。"""
    _engine, SessionLocal = tmp_db
    user, _ = _insert_user(SessionLocal, 7113, "basic-r@example.com")
    client, _ = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    incident_id = _seed_incident_with_alert(
        SessionLocal,
        client,
        user,
        title="测试案件",
        summary="用于验证报告内容",
    )
    resp = client.get(f"/incidents/{incident_id}/report?format=json")
    assert resp.status_code == 200
    markdown = resp.json()["markdown"]

    # 基础信息
    assert "案件 ID:" in markdown
    assert incident_id in markdown
    assert "状态:" in markdown
    assert "严重度:" in markdown
    assert "关联告警:" in markdown
    # 案件摘要
    assert "## 1. 案件摘要" in markdown
    # 关联告警表格
    assert "## 2. 关联告警" in markdown
    # 时间线
    assert "## 3. 案件时间线" in markdown
    # 安全声明
    assert "## 4. 安全与脱敏说明" in markdown


# ---------------------------------------------------------------------------
# Tests: 大案件截断
# ---------------------------------------------------------------------------


def test_report_truncates_alerts_and_events(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """25 条 linked alerts 只展示前 20 条;60 条 events 只展示最近 50 条。"""
    _engine, SessionLocal = tmp_db
    user, _ = _insert_user(SessionLocal, 7114, "big-r@example.com")
    client, _ = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    # 创建 incident
    create = client.post("/incidents", json={"title": "big case", "severity": "high"})
    assert create.status_code == 200
    incident_id = create.json()["incident"]["incident_id"]

    # link 25 条 alert(用已有 alert,这里直接 link 不存在的 alert_id 不行,
    # 必须先 persist。改为 link 25 条真实 alert records。)
    seed_db = SessionLocal()
    try:
        for i in range(25):
            payload = _build_alert_payload(user.id, alert_id=f"big-alert-{i:03d}")
            alert_service.persist_alert_record(seed_db, payload, user.id)
        # 写 60 条事件:1 created + 59 status 变化
        # 用 update 更新 incident 状态多次
    finally:
        seed_db.commit()
        seed_db.close()

    for i in range(25):
        link_resp = client.post(
            f"/incidents/{incident_id}/alerts",
            json={"alert_id": f"big-alert-{i:03d}"},
        )
        assert link_resp.status_code == 200, link_resp.text

    # 触发 59 次 status 变化;created 事件 + 59 status_changed = 60 events total
    cycle = ["investigating", "contained", "resolved", "false_positive", "open"]
    target_statuses = (cycle * 12)[:59]  # 12*5=60,取前 59
    assert len(target_statuses) == 59
    for s in target_statuses:
        client.patch(f"/incidents/{incident_id}", json={"status": s})

    resp = client.get(f"/incidents/{incident_id}/report?format=json")
    assert resp.status_code == 200
    body = resp.json()
    meta = body["meta"]
    # alert_count 应为 25,included_alerts 应被截断到 20
    assert meta["alert_count"] == 25
    assert meta["included_alerts"] == 20
    assert meta["truncated"] is True
    markdown = body["markdown"]
    # 报告里应明确说明"仅展示前 20 条"
    assert "20" in markdown
    # 报告里应说明 events 截断
    # event_count 应 >= 60(1 created + 59 status changed),included_events 应 = 50
    assert meta["event_count"] >= 60
    assert meta["included_events"] == 50


# ---------------------------------------------------------------------------
# Tests: filename 派生
# ---------------------------------------------------------------------------


def test_report_filename_derived_only_from_incident_id(
    tmp_db, reset_app_state, monkeypatch
) -> None:
    """filename 只能由 incident_id 派生,不能使用 title(避免文件名注入和泄密)。"""
    _engine, SessionLocal = tmp_db
    user, _ = _insert_user(SessionLocal, 7115, "fname-r@example.com")
    client, _ = _make_client(user, SessionLocal, monkeypatch=monkeypatch)

    # title 中包含换行 / 引号 / 路径分隔符,绝对不能进 filename
    nasty_title = 'evil"; rm -rf /;\n#'
    incident_id = _seed_incident_with_alert(
        SessionLocal, client, user, title=nasty_title
    )
    resp = client.get(f"/incidents/{incident_id}/report?format=json")
    assert resp.status_code == 200
    body = resp.json()
    expected = f"incident-{incident_id}-report.md"
    assert body["filename"] == expected
    # 必须**不**含 title 任何字符
    for ch in [";", "rm", "/", '"', "\n"]:
        assert ch not in body["filename"], f"filename 含危险字符 {ch!r}"
