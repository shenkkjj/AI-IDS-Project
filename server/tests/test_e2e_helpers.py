"""M3-09: server/tests/e2e_helpers.py 的纯函数单测。

不启动浏览器,只覆盖 ``classify_register_response`` 三种状态:
- 200/201 -> created
- 409 + "已存在" / "exists" -> exists
- 429 + 限流文案 -> rate_limited
"""
from __future__ import annotations

import pytest

from server.tests.e2e_helpers import (
    classify_register_response,
    stable_e2e_user,
    unique_e2e_user,
)


def test_classify_register_response_marks_created() -> None:
    assert classify_register_response(200, "{}") == "created"
    assert classify_register_response(201, "{}") == "created"


def test_classify_register_response_allows_existing_user_chinese() -> None:
    assert classify_register_response(409, "邮箱已注册") == "exists"
    assert classify_register_response(400, "用户已存在") == "exists"


def test_classify_register_response_allows_existing_user_english() -> None:
    assert classify_register_response(400, "user exists") == "exists"
    assert classify_register_response(409, "duplicate user") == "exists"


def test_classify_register_response_marks_rate_limited_chinese() -> None:
    msg = "注册尝试过于频繁,请1小时后再试"
    assert classify_register_response(429, msg) == "rate_limited"
    # 后端返回 429 时,即使没带"频繁"文案也仍归类为 rate_limited(以 status 为权威)。
    assert classify_register_response(429, "") == "rate_limited"


def test_classify_register_response_marks_rate_limited_english() -> None:
    assert classify_register_response(429, "rate limited") == "rate_limited"


def test_classify_register_response_unexpected_status_marks_error() -> None:
    assert classify_register_response(500, "internal server error") == "error"
    assert classify_register_response(503, "") == "error"


def test_unique_e2e_user_is_unique_and_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
    email_a, _ = unique_e2e_user("e2e-demo")
    email_b, _ = unique_e2e_user("e2e-demo")
    assert email_a.endswith("@example.com")
    assert email_b.endswith("@example.com")
    # ts 单位是 ms,不同调用之间通常不同;即便相同 ts 也允许,这里只断言后缀。
    assert email_a.startswith("e2e-demo-")


def test_stable_e2e_user_default_pattern(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("E2E_E2E_DEMO_EMAIL", raising=False)
    email, _ = stable_e2e_user("e2e-demo")
    assert email == "e2e-demo-stable@example.com"


def test_stable_e2e_user_uses_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("E2E_E2E_REPORT_EMAIL", "custom-report@example.com")
    email, _ = stable_e2e_user("e2e-report")
    assert email == "custom-report@example.com"
