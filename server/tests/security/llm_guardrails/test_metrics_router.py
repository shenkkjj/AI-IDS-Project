"""Unit tests for the /metrics Prometheus endpoint (P2-B).

Contract:
- ``GET /metrics`` returns Prometheus text exposition format 0.0.4
- Each row from ``iter_metrics`` becomes a labelled counter sample
- Empty input emits a zero-valued sample so dashboards never see a
  missing series
- Label values are escaped per the spec (``\\``, ``"``, ``\\n``)
"""
from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.routers import metrics_router
from server.routers.metrics_router import router


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_metrics_endpoint_emits_prometheus_format(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_rows = [
        ("copilot", "input", "passed", 100),
        ("copilot", "input", "blocked", 5),
    ]

    # The router imported `iter_metrics` at module load time, so we have
    # to patch the name in the router's namespace, not the audit module.
    monkeypatch.setattr(metrics_router, "iter_metrics", lambda *, hours=24: fake_rows)

    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    assert "# HELP guardrail_checks_total" in body
    assert "# TYPE guardrail_checks_total counter" in body
    assert 'guardrail_checks_total{scope="copilot",layer="input",status="passed"} 100' in body
    assert 'guardrail_checks_total{scope="copilot",layer="input",status="blocked"} 5' in body
    # Correct content-type per the Prometheus 0.0.4 spec
    assert "text/plain" in resp.headers["content-type"]
    assert "version=0.0.4" in resp.headers["content-type"]


def test_metrics_endpoint_emits_zero_when_no_data(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(metrics_router, "iter_metrics", lambda *, hours=24: [])

    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    # The zero-valued sample is a deliberate placeholder so Grafana
    # queries never see a missing time series.
    assert 'guardrail_checks_total{scope="none",layer="none",status="none"} 0' in body


def test_metrics_endpoint_escapes_label_values(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_rows: list[tuple[str, str, str, int]] = [
        ("weird\"name", "in\\put", "pass\ned", 1),
    ]
    monkeypatch.setattr(metrics_router, "iter_metrics", lambda *, hours=24: fake_rows)

    resp = client.get("/metrics")
    body = resp.text
    # Quotes / backslashes / newlines escaped
    assert 'scope="weird\\"name"' in body
    assert 'layer="in\\\\put"' in body
    assert 'status="pass\\ned"' in body
