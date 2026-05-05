from unittest.mock import AsyncMock, patch


class TestThreatIntelService:
    def test_extract_ip_valid(self):
        from server.services.threat_intel_service import _extract_ip
        assert _extract_ip("192.168.1.1") == "192.168.1.1"

    def test_extract_ip_in_line(self):
        from server.services.threat_intel_service import _extract_ip
        assert _extract_ip("some text 10.0.0.1 more text") == "10.0.0.1"

    def test_extract_ip_comment_skip(self):
        from server.services.threat_intel_service import _extract_ip
        assert _extract_ip("# 192.168.1.1") is None

    def test_extract_ip_empty(self):
        from server.services.threat_intel_service import _extract_ip
        assert _extract_ip("") is None

    def test_extract_ip_invalid(self):
        from server.services.threat_intel_service import _extract_ip
        assert _extract_ip("999.999.999.999") is None

    def test_extract_ip_non_ip(self):
        from server.services.threat_intel_service import _extract_ip
        assert _extract_ip("not an ip address") is None

    def test_blacklist_initially_empty(self):
        from server.services import threat_intel_service
        assert threat_intel_service.get_blacklist_size() == 0

    def test_is_blacklisted_false_initially(self):
        from server.services import threat_intel_service
        assert not threat_intel_service.is_blacklisted("1.2.3.4")


class TestNotificationService:
    def test_build_generic_payload(self):
        from server.services.notification_service import build_alert_webhook_payload
        alert = {
            "raw_alert": {"source_ip": "1.2.3.4", "destination_ip": "5.6.7.8", "payload": "test", "blocked": True},
            "llm_analysis": {"risk_level": "critical", "summary": "高危攻击"},
            "alert_id": "abc123",
        }
        payload = build_alert_webhook_payload(alert, "generic")
        assert payload["risk_level"] == "critical"
        assert "1.2.3.4" in payload["text"]

    def test_build_dingtalk_payload(self):
        from server.services.notification_service import build_alert_webhook_payload
        alert = {
            "raw_alert": {"source_ip": "1.2.3.4", "destination_ip": "5.6.7.8", "payload": "test", "blocked": False},
            "llm_analysis": {"risk_level": "high", "summary": "可疑攻击"},
        }
        payload = build_alert_webhook_payload(alert, "dingtalk")
        assert payload["msgtype"] == "markdown"
        assert "HIGH" in payload["markdown"]["title"]

    def test_build_feishu_payload(self):
        from server.services.notification_service import build_alert_webhook_payload
        alert = {
            "raw_alert": {"source_ip": "1.1.1.1", "destination_ip": "2.2.2.2", "payload": "", "blocked": True},
            "llm_analysis": {"risk_level": "medium", "summary": "常规扫描"},
        }
        payload = build_alert_webhook_payload(alert, "feishu")
        assert payload["msg_type"] == "interactive"
        assert "card" in payload

    def test_build_missing_llm_analysis(self):
        from server.services.notification_service import build_alert_webhook_payload
        alert = {"raw_alert": {"source_ip": "1.2.3.4"}}
        payload = build_alert_webhook_payload(alert)
        assert payload["risk_level"] == "unknown"
