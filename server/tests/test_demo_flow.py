import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.models_db import User
from server.routers import alerts_router


@pytest.fixture
def demo_client(monkeypatch):
    user = User(id=42, email="demo@example.com", is_active=True)

    async def fake_broadcast_json(user_id, payload):
        fake_broadcast_json.calls.append((user_id, payload))

    fake_broadcast_json.calls = []

    monkeypatch.setattr("server.services.alert_service.manager.broadcast_json", fake_broadcast_json)

    app = FastAPI()
    app.include_router(alerts_router.router)
    app.dependency_overrides[alerts_router.require_auth_user] = lambda: user
    app.dependency_overrides[alerts_router.get_db] = lambda: _FakeDb()
    return TestClient(app), fake_broadcast_json


def test_demo_attack_creates_alert_for_current_user(demo_client):
    client, broadcast = demo_client

    response = client.post("/alerts/demo", json={"scenario": "sql_injection"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["scenario"] == "sql_injection"
    assert payload["alert"]["raw_alert"]["alert_user_id"] == 42
    assert payload["alert"]["raw_alert"]["blocked"] is True
    assert payload["alert"]["llm_analysis"]["risk_level"] == "critical"
    assert "UNION SELECT" in payload["alert"]["raw_alert"]["payload"]
    assert broadcast.calls[-1][0] == 42
    assert payload["copilot"]["ready"] is False
    assert payload["copilot"]["fallback_reason"] == "missing_api_key_or_base_url"
    assert "配置页" in payload["copilot"]["next_action"]


def test_demo_attack_reports_copilot_ready_when_user_configured(monkeypatch):
    user = User(id=43, email="ready@example.com", is_active=True)
    user.encrypted_api_key = "encrypted"

    async def fake_broadcast_json(*_args, **_kwargs):
        return None

    monkeypatch.setattr("server.services.alert_service.manager.broadcast_json", fake_broadcast_json)
    monkeypatch.setattr("server.core.llm_utils.decrypt_api_key", lambda _value: "sk-test-ready-key")

    app = FastAPI()
    app.include_router(alerts_router.router)
    app.dependency_overrides[alerts_router.require_auth_user] = lambda: user
    app.dependency_overrides[alerts_router.get_db] = lambda: _ConfiguredFakeDb()
    client = TestClient(app)

    response = client.post("/alerts/demo", json={"scenario": "scanner"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["copilot"]["ready"] is True
    assert payload["copilot"]["fallback_reason"] is None
    assert payload["copilot"]["next_action"] == "点击 AI 助手中的“分析当前告警”获取流式分析。"


def test_demo_attack_is_visible_in_alert_list(demo_client):
    client, _broadcast = demo_client

    created = client.post("/alerts/demo", json={"scenario": "xss"}).json()
    response = client.get("/alerts?limit=5")

    assert response.status_code == 200
    payload = response.json()
    alert_ids = [item["alert_id"] for item in payload["items"]]
    assert created["alert"]["alert_id"] in alert_ids
    assert payload["items"][-1]["raw_alert"]["alert_user_id"] == 42


def test_demo_attack_rejects_unknown_scenario(demo_client):
    client, _broadcast = demo_client

    response = client.post("/alerts/demo", json={"scenario": "unknown"})

    assert response.status_code == 422


def test_demo_alert_can_drive_copilot_fallback(monkeypatch):
    from server.models.schemas import CopilotStreamIn
    from server.services import alert_service, copilot_service

    user = User(id=77, email="fallback@example.com", is_active=True)

    async def fake_broadcast_json(*_args, **_kwargs):
        return None

    monkeypatch.setattr("server.services.alert_service.manager.broadcast_json", fake_broadcast_json)

    async def run_flow():
        created = await alert_service.trigger_demo_attack(user_id=user.id, scenario="scanner")
        chunks = [
            chunk async for chunk in copilot_service.copilot_stream(
                user,
                CopilotStreamIn(message="分析这条告警", alert_id=created["alert_id"]),
                "127.0.0.1",
                db=_FakeDb(),
            )
        ]
        return created, "".join(chunks)

    import asyncio
    created, body = asyncio.run(run_flow())

    assert created["alert_id"] in body or "请先在配置页设置可用的 API Key" in body
    assert "请先在配置页设置可用的 API Key" in body


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


class _ConfiguredFakeConfig:
    ai_provider = "custom"
    model = "demo-model"
    base_url = "https://api.example.test/v1"
    timeout_seconds = 20


class _ConfiguredFakeDb(_FakeDb):
    def __init__(self):
        self.config = _ConfiguredFakeConfig()
