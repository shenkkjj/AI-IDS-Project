from server.core.config import WAF_BLOCK_PATTERNS


def _match_any(value: str) -> bool:
    for pattern in WAF_BLOCK_PATTERNS:
        if pattern.search(value):
            return True
    return False


class TestWafPatterns:
    def test_sqli_union_select(self):
        assert _match_any("1 UNION SELECT * FROM users")

    def test_sqli_comment_bypass(self):
        assert _match_any("1 UNION /*comment*/ SELECT * FROM users")

    def test_sqli_concat(self):
        assert _match_any("' || username || '")

    def test_sqli_url_injection(self):
        assert _match_any("url('http://evil.com')")
        assert _match_any("uri('internal')")

    def test_sqli_or_equal(self):
        assert _match_any("OR 1 = 1")
        assert _match_any("and 0 = 0")

    def test_sqli_drop_table(self):
        assert _match_any("'; DROP TABLE users; --")

    def test_sqli_insert_delete(self):
        assert _match_any("INSERT INTO users VALUES")
        assert _match_any("DELETE FROM users")

    def test_xss_script_tag(self):
        assert _match_any('<script>alert("XSS")</script>')
        assert _match_any('< script src="evil.js">')

    def test_xss_on_event(self):
        assert _match_any('<img src=x onerror=alert(1)>')
        assert _match_any('<div onclick=evil()>')

    def test_xss_javascript_protocol(self):
        assert _match_any('javascript:alert(1)')

    def test_command_exec_eval(self):
        assert _match_any("exec('rm -rf /')")
        assert _match_any("eval('malicious code')")

    def test_clean_input_passes(self):
        assert not _match_any("hello world 123")
        assert not _match_any("user@example.com")
        assert not _match_any("https://api.deepseek.com")
        assert not _match_any("normal text without special chars")

    def test_empty_string(self):
        assert not _match_any("")

    def test_unicode_safe(self):
        assert not _match_any("你好世界这是一个正常文本")

    def test_xss_case_insensitive(self):
        assert _match_any('<ScRiPt>alert(1)</sCrIpT>')

    def test_nested_script_attack(self):
        assert _match_any('<scr<script>ipt>alert(1)</scr</script>ipt>')
