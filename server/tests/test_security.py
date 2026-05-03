import pytest
from server.security_utils import (
    issue_access_token,
    decode_access_token,
)


class TestJwtTokens:
    def test_issue_access_token_success(self):
        token = issue_access_token(
            subject="1",
            password_changed_at=0.0,
            token_version=1,
        )
        assert isinstance(token, str)
        assert len(token) > 20
        payload = decode_access_token(token)
        assert payload["sub"] == "1"
        assert payload["pwd_iat"] == 0.0
        assert payload["tv"] == 1
        assert "exp" in payload

    def test_token_contains_expiry(self):
        token = issue_access_token(
            subject="42",
            password_changed_at=100.0,
            token_version=3,
        )
        payload = decode_access_token(token)
        assert payload["exp"] > payload["iat"]
        assert payload["sub"] == "42"

    def test_decode_invalid_token(self):
        with pytest.raises(Exception):
            decode_access_token("not.a.valid.token")

    def test_decode_tampered_token(self):
        token = issue_access_token(subject="1")
        parts = token.split(".")
        tampered = parts[0] + "." + parts[1] + "." + "AAAA"
        with pytest.raises(Exception):
            decode_access_token(tampered)

    def test_token_version_preserved(self):
        token = issue_access_token(
            subject="5",
            password_changed_at=1234567890.0,
            token_version=5,
        )
        payload = decode_access_token(token)
        assert payload["pwd_iat"] == 1234567890.0
        assert payload["tv"] == 5

    def test_default_args(self):
        token = issue_access_token(subject="99")
        payload = decode_access_token(token)
        assert payload["sub"] == "99"
        assert payload["tv"] == 0
        assert "exp" in payload

    def test_different_subjects_produce_different_tokens(self):
        t1 = issue_access_token(subject="1")
        t2 = issue_access_token(subject="2")
        assert t1 != t2

    def test_different_versions_produce_different_tokens(self):
        t1 = issue_access_token(subject="1", token_version=1)
        t2 = issue_access_token(subject="1", token_version=2)
        assert t1 != t2
