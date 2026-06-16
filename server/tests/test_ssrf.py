import pytest
from server.analyzer import _is_ssrf_safe, build_chat_completions_url


class TestSsrfProtection:
    def test_public_domain_ok(self, monkeypatch):
        monkeypatch.setattr(
            "server.core.utils._is_url_pointing_to_internal",
            lambda _url: False,
        )
        assert _is_ssrf_safe("https://api.deepseek.com")
        assert _is_ssrf_safe("https://api.openai.com")
        assert _is_ssrf_safe("https://www.google.com")

    def test_loopback_blocked(self):
        assert not _is_ssrf_safe("http://127.0.0.1:8000")
        assert not _is_ssrf_safe("http://localhost")
        assert not _is_ssrf_safe("http://[::1]")

    def test_private_ip_blocked(self):
        assert not _is_ssrf_safe("http://192.168.1.1")
        assert not _is_ssrf_safe("http://10.0.0.1")
        assert not _is_ssrf_safe("http://172.16.0.1")

    def test_link_local_blocked(self):
        assert not _is_ssrf_safe("http://169.254.169.254")

    def test_cloud_metadata_blocked(self):
        assert not _is_ssrf_safe("http://metadata.google.internal")

    def test_empty_hostname(self):
        assert not _is_ssrf_safe("http://")

    def test_build_url_with_ssrf_check(self):
        url = build_chat_completions_url("https://api.deepseek.com")
        assert url == "https://api.deepseek.com/v1/chat/completions"

    def test_build_url_rejects_internal(self):
        with pytest.raises(ValueError, match="internal"):
            build_chat_completions_url("http://127.0.0.1:8000")

    def test_build_url_rejects_empty(self):
        with pytest.raises(ValueError, match="Missing"):
            build_chat_completions_url("")

    def test_build_url_strips_trailing_slash(self):
        url = build_chat_completions_url("https://api.deepseek.com/")
        assert url == "https://api.deepseek.com/v1/chat/completions"

    def test_build_url_with_subpath(self):
        url = build_chat_completions_url("https://example.com/api")
        assert url == "https://example.com/api/v1/chat/completions"

    def test_multicast_blocked(self):
        assert not _is_ssrf_safe("http://224.0.0.1")

    def test_reserved_blocked(self):
        assert not _is_ssrf_safe("http://0.0.0.0")
