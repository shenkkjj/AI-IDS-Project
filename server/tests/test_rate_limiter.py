import time
from server.core.state import RateLimitState


class TestRateLimitState:
    def test_first_login_allowed(self):
        state = RateLimitState()
        assert state._check_rate_limit(state.login_attempts, "test@x.com", 60, 5) is True

    def test_within_login_limit(self):
        state = RateLimitState()
        for _i in range(5):
            assert state._check_rate_limit(state.login_attempts, "user@x.com", 60, 5) is True

    def test_exceeds_login_limit(self):
        state = RateLimitState()
        for _i in range(3):
            state._check_rate_limit(state.login_attempts, "user@x.com", 60, 3)
        assert state._check_rate_limit(state.login_attempts, "user@x.com", 60, 3) is False

    def test_independent_keys(self):
        state = RateLimitState()
        assert state._check_rate_limit(state.login_attempts, "a@x.com", 60, 2) is True
        assert state._check_rate_limit(state.login_attempts, "b@x.com", 60, 2) is True
        assert state._check_rate_limit(state.login_attempts, "a@x.com", 60, 2) is True
        assert state._check_rate_limit(state.login_attempts, "b@x.com", 60, 2) is True
        assert state._check_rate_limit(state.login_attempts, "a@x.com", 60, 2) is False
        assert state._check_rate_limit(state.login_attempts, "b@x.com", 60, 2) is False
        assert state._check_rate_limit(state.login_attempts, "c@x.com", 60, 2) is True

    def test_window_expiry(self):
        state = RateLimitState()
        key = "expire-test@x.com"
        assert state._check_rate_limit(state.login_attempts, key, 1, 2) is True
        assert state._check_rate_limit(state.login_attempts, key, 1, 2) is True
        assert state._check_rate_limit(state.login_attempts, key, 1, 2) is False
        time.sleep(1.2)
        assert state._check_rate_limit(state.login_attempts, key, 1, 2) is True

    def test_zero_max_no_limit(self):
        state = RateLimitState()
        assert state._check_rate_limit(state.login_attempts, "nolimit@x.com", 60, 0) is True

    def test_different_window_types(self):
        state = RateLimitState()
        key = "multi@x.com"
        assert state._check_rate_limit(state.login_attempts, key, 60, 5) is True
        assert state._check_rate_limit(state.register_attempts, key, 3600, 2) is True
        assert state._check_rate_limit(state.otp_attempts, key, 300, 3) is True

    def test_raw_key_case_sensitive(self):
        state = RateLimitState()
        assert state._check_rate_limit(state.login_attempts, "User@X.COM", 60, 2) is True
        assert state._check_rate_limit(state.login_attempts, "user@x.com", 60, 2) is True
        assert state._check_rate_limit(state.login_attempts, "USER@x.com", 60, 2) is True

    def test_otp_verify_failures_count(self):
        state = RateLimitState()
        assert "test@x.com" not in state.otp_verify_failures
        state.otp_verify_failures["test@x.com"] = 1
        state.otp_verify_failures["test@x.com"] += 1
        assert state.otp_verify_failures["test@x.com"] == 2
