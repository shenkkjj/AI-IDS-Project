import pytest
from server.analyzer import _is_ssrf_safe, build_chat_completions_url


@pytest.fixture
def allow_public_dns(monkeypatch):
    """让公网域名测试不依赖真实 DNS。

    生产 ``_is_url_pointing_to_internal`` 会做 DNS 解析,如果当前
    主机/代理把 ``api.deepseek.com`` / ``example.com`` 解析到
    ``198.18.0.0/15`` 等 RFC2544 / 保留地址,生产代码会正确阻断,
    测试反而会误红。这里只在 "公网域名应允许" 类测试上 monkeypatch
    DNS helper,不影响 literal IP 的生产阻断 (见
    ``test_allow_public_dns_fixture_does_not_bypass_literal_internal_ip``)。
    """
    monkeypatch.setattr(
        "server.core.utils._is_url_pointing_to_internal",
        lambda _url: False,
    )


class TestSsrfProtection:
    def test_public_domain_ok(self, allow_public_dns):
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

    def test_build_url_with_ssrf_check(self, allow_public_dns):
        url = build_chat_completions_url("https://api.deepseek.com")
        assert url == "https://api.deepseek.com/v1/chat/completions"

    def test_build_url_rejects_internal(self):
        with pytest.raises(ValueError, match="internal"):
            build_chat_completions_url("http://127.0.0.1:8000")

    def test_build_url_rejects_empty(self):
        with pytest.raises(ValueError, match="Missing"):
            build_chat_completions_url("")

    def test_build_url_strips_trailing_slash(self, allow_public_dns):
        url = build_chat_completions_url("https://api.deepseek.com/")
        assert url == "https://api.deepseek.com/v1/chat/completions"

    def test_build_url_with_subpath(self, allow_public_dns):
        url = build_chat_completions_url("https://example.com/api")
        assert url == "https://example.com/api/v1/chat/completions"

    def test_multicast_blocked(self):
        assert not _is_ssrf_safe("http://224.0.0.1")

    def test_reserved_blocked(self):
        assert not _is_ssrf_safe("http://0.0.0.0")

    def test_allow_public_dns_fixture_does_not_bypass_literal_internal_ip(
        self, allow_public_dns
    ):
        """fixture 只 monkeypatch 域名解析 helper, literal IP 仍走生产阻断。"""
        assert not _is_ssrf_safe("http://127.0.0.1:8000")
        assert not _is_ssrf_safe("http://192.168.1.1")
        assert not _is_ssrf_safe("http://169.254.169.254")
