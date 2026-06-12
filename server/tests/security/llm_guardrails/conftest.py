"""Adversarial test infrastructure for the LLM Guardrails layer.

Provides:
- `corpus_path` fixture pointing to the JSONL attack samples
- `load_corpus(name)` helper that yields each sample as a dict
- `mock_openai_moderation(monkeypatch, *, flagged: bool)` fixture
- `mock_nemo_rails(monkeypatch, *, allow: bool)` fixture
- `guardrail_engine` fixture that wires a real engine but bypasses external calls
- `temp_audit_db` fixture that swaps the AuditLog table for an in-memory SQLite
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import AsyncMock, MagicMock

import pytest

CORPUS_DIR = Path(__file__).resolve().parent / "corpus"


@pytest.fixture
def corpus_path() -> Path:
    """Return the directory holding the JSONL attack corpora."""
    return CORPUS_DIR


def load_corpus(name: str) -> Iterator[dict[str, Any]]:
    """Yield each sample from a named JSONL file in the corpus dir.

    Skips blank lines. Raises if the file is missing so a misnamed corpus
    name fails fast instead of silently returning an empty list.
    """
    path = CORPUS_DIR / f"{name}.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"corpus file not found: {path}")
    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


# --- 3rd-party mock fixtures ---------------------------------------------------


@pytest.fixture
def mock_openai_moderation_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the moderation client to always return `flagged=False`."""
    from server.security.llm_guardrails.moderation import client

    async def _ok(text: str) -> dict[str, Any]:
        return {"flagged": False, "categories": {}}

    monkeypatch.setattr(client.OpenAIModerationClient, "check", _ok)


@pytest.fixture
def mock_openai_moderation_block(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the moderation client to always return `flagged=True`."""
    from server.security.llm_guardrails.moderation import client

    async def _block(text: str) -> dict[str, Any]:
        return {
            "flagged": True,
            "categories": {"prompt_injection": True, "jailbreak": True},
        }

    monkeypatch.setattr(client.OpenAIModerationClient, "check", _block)


@pytest.fixture
def mock_openai_moderation_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the moderation client to raise (simulating API outage)."""
    from server.security.llm_guardrails.moderation import client

    async def _raise(text: str) -> dict[str, Any]:
        raise RuntimeError("simulated OpenAI outage")

    monkeypatch.setattr(client.OpenAIModerationClient, "check", _raise)


@pytest.fixture
def mock_nemo_rails_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub GuardrailEngine to return None (i.e. allowed)."""
    from server.security.llm_guardrails import core

    async def _check(self, *, scope: str, message: str, history: list) -> str | None:
        return None

    monkeypatch.setattr(core.GuardrailEngine, "check_input", _check)


@pytest.fixture
def mock_nemo_rails_block(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub GuardrailEngine to return a blocking reason."""
    from server.security.llm_guardrails import core

    async def _check(self, *, scope: str, message: str, history: list) -> str | None:
        return "blocked: jailbreak detected by NeMo self_check_input"

    monkeypatch.setattr(core.GuardrailEngine, "check_input", _check)
