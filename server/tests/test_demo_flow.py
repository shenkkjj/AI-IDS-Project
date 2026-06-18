"""``POST /alerts/demo`` 端点测试。

M3-03 改造:``trigger_demo_attack`` 现在需要 ``db: Session`` 参数,
所有测试 fixture 注入 ``tmp_db`` 临时 SQLite,DB-first 走 alert_records。

设计目标 (docs/agent/M3_03_ALERT_TRIAGE_PERSISTENCE_AND_HISTORY_TASK.md §3/§8 阶段 5):

- 触发 demo 后,DB 中应能查到 alert_record。
- 触发 demo 后,GET /alerts 仍能看到。
- copilot 准备好 / 未准备好分支行为不变。
"""
from __future__ import annotations

import asyncio
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
from server.routers import alerts_router
from server.services import alert_service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "demo_test.db"
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
def demo_client(tmp_db, monkeypatch):
    """demo 路由 + 当前用户 fixture。"""
    _engine, SessionLocal = tmp_db
    user = User(id=42, email="demo@example.com", is_active=True)
    db = SessionLocal()
    db.add(user)
    db.commit()
    db.refresh(user)

    async def fake_broadcast_json(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "server.services.alert_service.manager.broadcast_json", fake_broadcast_json
    )
    monkeypatch.setattr(
        state_module, "app_state", state_module.AppState()
    )
    app_state.alert.queue = asyncio.Queue(maxsize=ALERT_QUEUE_MAX_SIZE)
    app_state.alert.backlog = type(app_state.alert.backlog)()

    app = FastAPI()
    app.include_router(alerts_router.router)
    app.dependency_overrides[alerts_router.require_auth_user] = lambda: user
    app.dependency_overrides[alerts_router.get_db] = lambda: SessionLocal()
    return TestClient(app), user, SessionLocal


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_demo_attack_creates_alert_for_current_user(demo_client):
    client, _user, _sl = demo_client

    response = client.post("/alerts/demo", json={"scenario": "sql_injection"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["scenario"] == "sql_injection"
    assert payload["alert"]["raw_alert"]["alert_user_id"] == 42
    assert payload["alert"]["raw_alert"]["blocked"] is True
    assert payload["alert"]["llm_analysis"]["risk_level"] == "critical"
    assert "UNION SELECT" in payload["alert"]["raw_alert"]["payload"]
    assert payload["copilot"]["ready"] is False
    assert payload["copilot"]["fallback_reason"] == "missing_api_key_or_base_url"
    assert "配置页" in payload["copilot"]["next_action"]


def test_demo_attack_reports_copilot_ready_when_user_configured(tmp_db, monkeypatch):
    _engine, SessionLocal = tmp_db
    user = User(id=43, email="ready@example.com", is_active=True)
    user.encrypted_api_key = "encrypted"
    db = SessionLocal()
    db.add(user)
    db.commit()
    db.refresh(user)

    async def fake_broadcast_json(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "server.services.alert_service.manager.broadcast_json", fake_broadcast_json
    )
    monkeypatch.setattr(
        "server.core.llm_utils.decrypt_api_key", lambda _value: "sk-test-ready-key"
    )

    # 让 build_demo_copilot_state 走假 user_config 路径(返回 ready=True)
    from server.analyzer import AnalyzerConfig

    fake_runtime = AnalyzerConfig(
        api_key="sk-test-ready-key",
        base_url="https://api.example.test/v1",
        model="demo-model",
        timeout_seconds=20,
    )

    def fake_user_config_to_llm_runtime(_config, _user):
        return (fake_runtime, "custom")

    monkeypatch.setattr(
        "server.core.llm_utils.user_config_to_llm_runtime",
        fake_user_config_to_llm_runtime,
    )
    monkeypatch.setattr(
        "server.services.user_service.get_or_create_user_config",
        lambda _db, _user_id: _ConfiguredFakeConfig(),
    )

    app = FastAPI()
    app.include_router(alerts_router.router)
    app.dependency_overrides[alerts_router.require_auth_user] = lambda: user
    app.dependency_overrides[alerts_router.get_db] = lambda: SessionLocal()
    client = TestClient(app)

    response = client.post("/alerts/demo", json={"scenario": "scanner"})

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["copilot"]["ready"] is True
    assert payload["copilot"]["fallback_reason"] is None
    assert payload["copilot"]["next_action"] == "点击 AI 助手中的“分析当前告警”获取流式分析。"


def test_demo_attack_is_visible_in_alert_list(demo_client):
    client, _user, _sl = demo_client

    created = client.post("/alerts/demo", json={"scenario": "xss"}).json()
    response = client.get("/alerts?limit=5")

    assert response.status_code == 200
    payload = response.json()
    alert_ids = [item["alert_id"] for item in payload["items"]]
    assert created["alert"]["alert_id"] in alert_ids
    assert payload["items"][-1]["raw_alert"]["alert_user_id"] == 42


def test_demo_attack_rejects_unknown_scenario(demo_client):
    client, _user, _sl = demo_client

    response = client.post("/alerts/demo", json={"scenario": "unknown"})

    assert response.status_code == 422


def test_demo_alert_can_drive_copilot_fallback(tmp_db, monkeypatch):
    """service 层 trigger_demo_attack 在新签名下也仍可被 worker 之类调用。

    M3-06:该测试只验证 demo alert 能驱动 Copilot no-key fallback 路径,
    并不验证 Guardrails 决策。为避免本地无真实 OpenAI key 时
    L4 moderation fail-closed 阻断(``moderation_unavailable``),
    在测试中 stub ``GuardrailEngine.instance().check_input`` 为 allow。
    模式与 ``test_copilot_contract._stub_guardrails`` 保持一致。
    """
    _engine, SessionLocal = tmp_db
    from server.models.schemas import CopilotStreamIn
    from server.security.llm_guardrails import core as guard_core
    from server.services import alert_service, copilot_service

    user = User(id=77, email="fallback@example.com", is_active=True)
    db = SessionLocal()
    db.add(user)
    db.commit()
    db.refresh(user)

    async def fake_broadcast_json(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "server.services.alert_service.manager.broadcast_json", fake_broadcast_json
    )

    class _StubEngine:
        async def check_input(self, **_kwargs):
            return None  # allow:不验证 Guardrails,只验证 no-key fallback

    monkeypatch.setattr(
        guard_core.GuardrailEngine,
        "instance",
        staticmethod(lambda: _StubEngine()),
    )

    async def run_flow():
        created = await alert_service.trigger_demo_attack(
            db=db, user_id=user.id, scenario="scanner"
        )
        chunks = [
            chunk async for chunk in copilot_service.copilot_stream(
                user,
                CopilotStreamIn(message="分析这条告警", alert_id=created["alert_id"]),
                "127.0.0.1",
                db=_FakeDb(),
            )
        ]
        return created, "".join(chunks)

    created, body = asyncio.run(run_flow())

    assert created["alert_id"] in body or "请先在配置页设置可用的 API Key" in body
    assert "请先在配置页设置可用的 API Key" in body


# ---------------------------------------------------------------------------
# 兼容的 fake db(copilot_stream 仍走 SessionLocal 风格的 query)
# ---------------------------------------------------------------------------


class _FakeConfig:
    ai_provider = "custom"
    model = ""
    base_url = ""
    timeout_seconds = 20


class _FakeDb:
    def __init__(self):
        self.config = _FakeConfig()

    def query(self, _model):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.config

    def add(self, _item):
        return None

    def commit(self):
        return None

    def refresh(self, _item):
        return None

    def rollback(self):
        return None

    def close(self):
        return None

    def flush(self):
        return None


class _ConfiguredFakeConfig:
    ai_provider = "custom"
    model = "demo-model"
    base_url = "https://api.example.test/v1"
    timeout_seconds = 20


class _ConfiguredFakeDb(_FakeDb):
    def __init__(self):
        self.config = _ConfiguredFakeConfig()
