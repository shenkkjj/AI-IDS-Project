"""Unit tests for `server.security.llm_guardrails.exceptions`.

These tests cover the contract of the `GuardrailViolation` exception:
- Subclass of DomainException so the global handler emits 403 JSON
- Carries `layer` / `scope` / `status` in `extra` for client telemetry
- `status_code` is 403 (consistent with HTTP forbidden semantics)
"""
from __future__ import annotations

import pytest

from server.security.llm_guardrails.exceptions import GuardrailViolation
from server.core.exceptions import DomainException


def test_guardrail_violation_is_domain_exception() -> None:
    exc = GuardrailViolation(scope="copilot", reason="jailbreak", layer="input")
    assert isinstance(exc, DomainException)


def test_guardrail_violation_default_status_blocked() -> None:
    exc = GuardrailViolation(scope="copilot", reason="jailbreak", layer="input")
    assert exc.status_code == 403
    assert "guardrail:copilot" in exc.detail
    assert "jailbreak" in exc.detail


def test_guardrail_violation_extra_payload() -> None:
    exc = GuardrailViolation(
        scope="mcp",
        reason="role_hijack",
        layer="input",
        status="warning",
    )
    assert exc.extra == {
        "layer": "input",
        "scope": "mcp",
        "guardrail_status": "warning",
    }


def test_guardrail_violation_layer_output() -> None:
    exc = GuardrailViolation(scope="copilot", reason="pii_leak", layer="output")
    assert exc.extra["layer"] == "output"


def test_guardrail_violation_can_be_raised_and_caught() -> None:
    with pytest.raises(GuardrailViolation) as info:
        raise GuardrailViolation(scope="x", reason="y", layer="input")
    assert info.value.status_code == 403
