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

    # 必须用 ``staticmethod`` 包装,否则 Python 会把 ``self`` 作为第一
    # 个位置参数传入,导致 ``TypeError`` → fail-closed 把这条错误包装为
    # ``moderation_unavailable (L4: fail-closed, exc=TypeError)``。
    monkeypatch.setattr(
        client.OpenAIModerationClient, "check", staticmethod(_ok)
    )


@pytest.fixture
def mock_openai_moderation_block(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the moderation client to always return `flagged=True`."""
    from server.security.llm_guardrails.moderation import client

    async def _block(text: str) -> dict[str, Any]:
        return {
            "flagged": True,
            "categories": {"prompt_injection": True, "jailbreak": True},
        }

    monkeypatch.setattr(
        client.OpenAIModerationClient, "check", staticmethod(_block)
    )


@pytest.fixture
def mock_openai_moderation_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the moderation client to raise (simulating API outage)."""
    from server.security.llm_guardrails.moderation import client

    async def _raise(text: str) -> dict[str, Any]:
        raise RuntimeError("simulated OpenAI outage")

    monkeypatch.setattr(
        client.OpenAIModerationClient, "check", staticmethod(_raise)
    )


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


# --- 阶段 4:Colang corpus 确定性 autouse fixture ------------------------------
#
# M3-06 修复背景:
#   本任务之前,``test_colang_flows.py`` 在本地无真实 OpenAI key 时,
#   benign 样本会因为 L4 moderation client 真实发请求 → ``httpx`` 异常
#   → ``moderation_unavailable (L4: fail-closed)`` → benign 被错误阻断。
#   这与生产 fail-closed 策略无关,纯粹是测试夹具不稳定(取决于 httpx
#   连接是否被缓存)。为了使 Colang 语料测试**只**关注 L1 正则 / NeMo 语义,
#   而不依赖真实 OpenAI / 网络状态,在本 conftest 范围内为
#   ``test_colang_flows.py`` 提供 autouse pass-through fake。
#
# 作用域:
#   仅对 ``test_colang_flows.py`` 生效。其他测试(如
#   ``test_moderation_client.py`` 验证 ``OpenAIModerationClient.check`` 的
#   真实 HTTP 行为)不受影响。
#
# 优先级:
#   若某 Colang 测试显式请求 ``mock_openai_moderation_block`` / ``_fail``,
#   pytest 仍按"先 autouse 后显式"顺序应用 fixture;最后一次 ``setattr`` 生效
#   (覆盖 autouse 的 pass-through)。
@pytest.fixture(autouse=True)
def _safe_moderation_for_colang(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """让 ``test_colang_flows.py`` 在没有真实 OpenAI key / 网络时仍能确定性通过。

    行为:把 ``OpenAIModerationClient.check`` 替换为永远 ``flagged=False``
    的 fake,使 benign 样本能正常通过 L4 走到 L3/NeMo(由 L1 regex 仍按
    真实规则阻断恶意样本)。生产代码 ``core.GuardrailEngine._run_rails``
    的 fail-closed 行为**不变** —— 这里只动测试夹具。
    """
    node_path = str(request.node.fspath)
    if "test_colang_flows" not in node_path:
        return
    from server.security.llm_guardrails.moderation import client

    async def _ok(_text: str) -> dict[str, Any]:
        return {"flagged": False, "categories": {}}

    # 注意:必须用 ``staticmethod`` 包装,否则 Python 会把 ``self`` 作为
    # 第一个位置参数传给 ``_ok`` → ``TypeError: takes 1 positional
    # argument but 2 were given`` → fail-closed 把这条 TypeError 包装为
    # ``moderation_unavailable (L4: fail-closed, exc=TypeError)``。
    monkeypatch.setattr(
        client.OpenAIModerationClient, "check", staticmethod(_ok)
    )
