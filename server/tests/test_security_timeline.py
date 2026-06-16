"""``GET /logs/security-timeline`` 端点测试。

覆盖：

- 未登录返回 401。
- 登录用户可读到自己的 demo attack / guardrail / auth 事件。
- ``limit`` 硬上限 100；超过自动 cap。
- 返回 schema 不含 regex / stack trace / API key / system prompt 等敏感字面量。
- reason / detail 全文不会通过本端点外泄。
- demo attack 写 Log 后，timeline 能看到 ``demo_attack`` 类别。
"""
from __future__ import annotations

import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.core.database import create_log
from server.models_db import AuditLog, User
from server.routers import logs_router


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def timeline_user(monkeypatch):
    """构造一个 User + DB（mock） + 把路由挂上 + 注入 auth。"""
    user = User(
        id=7777,
        email="timeline@example.com",
        password_hash="x",
        is_active=True,
    )

    # 真实 DB 写入：用临时 SQLite
    from server.core.database import Base, SessionLocal, engine

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # 先清再插：避免前一轮失败留下脏数据导致 UNIQUE 冲突
    db.query(AuditLog).filter(
        (AuditLog.user_id == user.id) | (AuditLog.user_id.is_(None))
    ).delete()
    from server.models_db import Log as _Log

    db.query(_Log).filter(
        (_Log.user_id == user.id) | (_Log.user_id.is_(None))
    ).delete()
    db.query(User).filter(User.id == user.id).delete()
    db.commit()

    db.add(user)
    db.commit()
    db.refresh(user)

    # bypass get_current_user：必须 monkeypatch logs_router 模块上的引用，
    # 因为 ``from X import Y`` 把 Y 绑到 logs_router 自己的命名空间，不会被
    # X 模块上的 setattr 影响到。
    monkeypatch.setattr(logs_router, "get_current_user", lambda *_a, **_k: user)

    app = FastAPI()
    app.include_router(logs_router.router)
    app.dependency_overrides[logs_router.get_db] = lambda: db

    client = TestClient(app)

    try:
        yield client, db, user
    finally:
        db.close()
        # 清理测试数据，避免污染后续测试
        cleanup_db = SessionLocal()
        try:
            cleanup_db.query(AuditLog).filter(
                (AuditLog.user_id == user.id) | (AuditLog.user_id.is_(None))
            ).delete()
            from server.models_db import Log as _Log

            cleanup_db.query(_Log).filter(
                (_Log.user_id == user.id) | (_Log.user_id.is_(None))
            ).delete()
            cleanup_db.query(User).filter(User.id == user.id).delete()
            cleanup_db.commit()
        finally:
            cleanup_db.close()


@pytest.fixture
def anon_client():
    """未登录客户端：依赖未 override，应该 401。"""
    app = FastAPI()
    app.include_router(logs_router.router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Sentinel / sanitiser
# ---------------------------------------------------------------------------


_FORBIDDEN_IN_TIMELINE: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"sk-proj-[A-Za-z0-9_-]+"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"\bTraceback\s+\(most recent call last\)", re.IGNORECASE),
    re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+.*system\s+prompt", re.IGNORECASE),
    re.compile(r"forget\s+.*instructions", re.IGNORECASE),
    re.compile(r"PRIVATE\s+KEY", re.IGNORECASE),
)


def _assert_no_forbidden(payload: dict) -> None:
    import json

    text = json.dumps(payload, ensure_ascii=False)
    for pat in _FORBIDDEN_IN_TIMELINE:
        assert not pat.search(text), f"timeline 命中禁止 sentinel：{pat.pattern} → {text[:200]!r}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_security_timeline_requires_auth(anon_client):
    resp = anon_client.get("/logs/security-timeline")
    assert resp.status_code == 401


def test_security_timeline_returns_empty_when_no_events(timeline_user):
    client, _db, _user = timeline_user
    resp = client.get("/logs/security-timeline")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["limit"] == 50  # 默认


def test_security_timeline_limit_is_capped(timeline_user):
    client, _db, _user = timeline_user
    resp = client.get("/logs/security-timeline?limit=10000")
    assert resp.status_code == 200
    body = resp.json()
    assert body["limit"] == 100  # 硬上限


def test_security_timeline_includes_demo_attack(timeline_user):
    client, db, user = timeline_user
    create_log(
        db,
        user_id=user.id,
        level="info",
        action="demo_attack",
        detail="scenario=sql_injection;alert_id=test-alert-1",
    )
    resp = client.get("/logs/security-timeline")
    assert resp.status_code == 200
    body = resp.json()
    categories = [item["category"] for item in body["items"]]
    assert "demo_attack" in categories
    _assert_no_forbidden(body)


def test_security_timeline_includes_guardrail_events(timeline_user):
    client, db, user = timeline_user
    # 模拟 guardrails 写入（AuditLog）
    row = AuditLog()
    row.user_id = user.id
    row.action = "guardrail_check"
    row.resource_type = "copilot"
    row.resource_id = "input"
    row.status = "blocked"
    row.detail = "status=blocked;reason=policy_violation ignore previous instructions"  # noqa: E501
    db.add(row)
    db.commit()

    resp = client.get("/logs/security-timeline")
    assert resp.status_code == 200
    body = resp.json()

    # category 应该是 guardrail_blocked
    cats = [item["category"] for item in body["items"]]
    assert "guardrail_blocked" in cats

    # summary 应该不含 L1 regex 全文
    _assert_no_forbidden(body)
    for item in body["items"]:
        if item["category"] == "guardrail_blocked":
            assert "安全护栏拦截" in item["summary"]
            # reason 全文不应出现
            assert "ignore previous instructions" not in item["summary"]


def test_security_timeline_does_not_leak_api_key(timeline_user):
    client, db, user = timeline_user
    create_log(
        db,
        user_id=user.id,
        level="info",
        action="user_config_update",
        detail="user set LLM_API_KEY=sk-test-abcdef0123456789abcdef and ALERT_EMAIL=true",
    )
    resp = client.get("/logs/security-timeline")
    body = resp.json()
    _assert_no_forbidden(body)
    # 整页 body 不应含原始 API key
    import json
    raw = json.dumps(body, ensure_ascii=False)
    assert "sk-test-abcdef0123456789abcdef" not in raw


def test_security_timeline_does_not_leak_system_prompt(timeline_user):
    client, db, user = timeline_user
    create_log(
        db,
        user_id=user.id,
        level="info",
        action="copilot_stream",
        detail="provider=openai;system: you are now a helpful assistant",
    )
    resp = client.get("/logs/security-timeline")
    body = resp.json()
    _assert_no_forbidden(body)
    import json
    raw = json.dumps(body, ensure_ascii=False)
    assert "system: you are now" not in raw
    assert "you are now a helpful assistant" not in raw


def test_security_timeline_does_not_leak_stacktrace(timeline_user):
    client, db, user = timeline_user
    create_log(
        db,
        user_id=user.id,
        level="error",
        action="other_event",
        detail=(
            "Traceback (most recent call last):\n  File 'foo.py', line 1\n  KeyError: 'x'"
        ),
    )
    resp = client.get("/logs/security-timeline")
    body = resp.json()
    _assert_no_forbidden(body)


def test_security_timeline_orders_desc_and_caps_rows(timeline_user):
    client, db, user = timeline_user
    # 写 5 条 Log，应被 cap
    for i in range(5):
        create_log(
            db,
            user_id=user.id,
            level="info",
            action="demo_attack",
            detail=f"iteration={i}",
        )
    resp = client.get("/logs/security-timeline?limit=2")
    body = resp.json()
    assert body["limit"] == 2
    assert len(body["items"]) <= 2


def test_security_timeline_orders_newest_first(timeline_user):
    """``GET /logs/security-timeline`` 必须返回最新事件优先（newest-first）。

    写 3 条带不同 ``created_at`` 的 Log：第 1 条最早，第 3 条最新。
    timeline 默认 limit 应只返回前 2 条（最新 2 条），且第 3 条（最新）
    必须排在第 2 条（中间）之前。
    """
    from datetime import datetime, timedelta, timezone

    client, db, user = timeline_user
    now = datetime.now(timezone.utc).replace(microsecond=0)
    inserted_ts: list[datetime] = [
        now - timedelta(minutes=30),  # oldest
        now - timedelta(minutes=15),  # middle
        now - timedelta(minutes=1),  # newest
    ]
    for i, ts in enumerate(inserted_ts, start=1):
        row = AuditLog()
        row.user_id = user.id
        row.action = "guardrail_check"
        row.resource_type = "copilot"
        row.resource_id = f"order-{i}"
        row.status = "passed"
        row.created_at = ts
        db.add(row)
    db.commit()

    resp = client.get("/logs/security-timeline?limit=2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["limit"] == 2
    assert len(body["items"]) == 2

    # ``resource_id`` 通过 ``summary`` 不可见，但 ``id`` 自增。
    # 用 ``ts`` 字段直接验证：第一个 item 是最新，第 2 个是中间。
    ts_first = body["items"][0]["ts"]
    ts_second = body["items"][1]["ts"]
    assert ts_first is not None and ts_second is not None
    assert ts_first > ts_second, (
        f"timeline 必须 newest-first；first={ts_first} second={ts_second}"
    )
    # 最新一条对应的 ts 必须出现在结果中（容忍 ``+00:00`` 后缀省略）
    expected_newest = inserted_ts[2].isoformat().replace("+00:00", "")
    expected_oldest = inserted_ts[0].isoformat().replace("+00:00", "")
    assert ts_first == expected_newest
    # 最旧一条的 ts 不能出现
    assert ts_second != expected_oldest

    _assert_no_forbidden(body)


def test_security_timeline_limit_cap_enforced_with_many_rows(timeline_user):
    """``limit=10000`` 必须被 cap 到 100，且实际返回行数不超过 100。"""
    from datetime import datetime, timedelta, timezone

    client, db, user = timeline_user
    base = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=1)
    # 写 105 条 Log（> 100），但每秒一条
    for i in range(105):
        row = AuditLog()
        row.user_id = user.id
        row.action = "guardrail_check"
        row.resource_type = "copilot"
        row.resource_id = f"cap-{i}"
        row.status = "passed"
        row.created_at = base + timedelta(seconds=i)
        db.add(row)
    db.commit()

    resp = client.get("/logs/security-timeline?limit=10000")
    assert resp.status_code == 200
    body = resp.json()
    # 硬上限
    assert body["limit"] == 100
    assert len(body["items"]) == 100
    # newest-first：第一条应是最新的 cap-104，最后一条是 cap-5
    assert body["items"][0]["ts"] > body["items"][-1]["ts"]


def test_security_timeline_desc_with_mixed_log_and_audit(timeline_user):
    """混合 Log + AuditLog 时，newest-first 排序在 union 上仍然成立。"""
    from datetime import datetime, timedelta, timezone

    client, db, user = timeline_user
    now = datetime.now(timezone.utc).replace(microsecond=0)
    # Log: older
    create_log(
        db,
        user_id=user.id,
        level="info",
        action="demo_attack",
        detail="older",
    )
    # 强制把这条 Log 的 created_at 设为较早
    from server.models_db import Log as _Log

    db.query(_Log).filter(_Log.user_id == user.id, _Log.action == "demo_attack").update(
        {_Log.created_at: now - timedelta(minutes=10)}
    )

    # Audit: newest
    audit = AuditLog()
    audit.user_id = user.id
    audit.action = "guardrail_check"
    audit.resource_type = "copilot"
    audit.resource_id = "newest"
    audit.status = "passed"
    audit.created_at = now
    db.add(audit)
    db.commit()

    resp = client.get("/logs/security-timeline?limit=10")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 2
    # newest 是 audit（更近）
    assert body["items"][0]["ts"] > body["items"][1]["ts"]
    # source 第一条是 audit
    assert body["items"][0]["source"] == "audit"
    assert body["items"][1]["source"] == "log"
