import sys
import httpx

BASE = "http://127.0.0.1:8000"
TEST_EMAIL = "2762919805@qq.com"
TEST_PASSWORD = "S2762919805s"

passed = 0
failed = 0
results = []


def test(name, func):
    global passed, failed
    try:
        func()
        passed += 1
        results.append(("PASS", name))
        print(f"  PASS: {name}")
    except Exception as e:
        failed += 1
        results.append(("FAIL", name, str(e)))
        print(f"  FAIL: {name} — {e}")


def assert_status(resp, expected, msg=""):
    if resp.status_code != expected:
        detail = ""
        try:
            detail = resp.json().get("detail", "")
        except Exception:
            detail = resp.text[:200]
        raise AssertionError(f"Expected {expected}, got {resp.status_code} — {detail} {msg}")


print("\n=== AI-IDS API Test Suite ===\n")

# --- Public endpoints (no auth needed) ---

test("POST /auth/register (duplicate)", lambda: assert_status(
    httpx.post(f"{BASE}/auth/register", json={
        "email": TEST_EMAIL, "password": TEST_PASSWORD, "display_name": "Test"
    }), 409))

test("POST /auth/register (bad email)", lambda: assert_status(
    httpx.post(f"{BASE}/auth/register", json={
        "email": "not-an-email", "password": TEST_PASSWORD
    }), 422))

# --- Login ---

login_resp = None
def test_login():
    global login_resp
    login_resp = httpx.post(f"{BASE}/auth/login/password", json={
        "email": TEST_EMAIL, "password": TEST_PASSWORD
    })
    assert_status(login_resp, 200)
    data = login_resp.json()
    assert "user" in data, "Missing user in response"
    assert "config" in data, "Missing config in response"
test("POST /auth/login/password (correct)", test_login)

token = login_resp.json().get("access_token", "") if login_resp and login_resp.status_code == 200 else ""
headers = {"Authorization": f"Bearer {token}"} if token else {}

test("POST /auth/login/password (wrong)", lambda: assert_status(
    httpx.post(f"{BASE}/auth/login/password", json={
        "email": TEST_EMAIL, "password": "wrongpassword"
    }), 401))

test("POST /auth/login/password (not found)", lambda: assert_status(
    httpx.post(f"{BASE}/auth/login/password", json={
        "email": "nonexistent@test.com", "password": "whatever"
    }), 401))

# --- Authenticated endpoints ---

test("GET /site/health", lambda: assert_status(
    httpx.get(f"{BASE}/site/health", headers=headers), 200))

test("GET /auth/session", lambda: assert_status(
    httpx.get(f"{BASE}/auth/session", headers=headers), 200))

test("GET /user/config", lambda: assert_status(
    httpx.get(f"{BASE}/user/config", headers=headers), 200))

test("PUT /user/config", lambda: assert_status(
    httpx.put(f"{BASE}/user/config", headers=headers, json={
        "ai_provider": "openai", "model": "gpt-4o-mini"
    }), 200))

# --- OTP / Password reset ---

test("POST /auth/login/otp/request (bad email)", lambda: assert_status(
    httpx.post(f"{BASE}/auth/login/otp/request", json={"email": "bad"}), 422))

test("POST /auth/login/otp/verify (no code)", lambda: assert_status(
    httpx.post(f"{BASE}/auth/login/otp/verify", json={
        "email": TEST_EMAIL, "code": "000000"
    }), 400))

test("POST /auth/password/reset/request (bad email)", lambda: assert_status(
    httpx.post(f"{BASE}/auth/password/reset/request", json={"email": "bad"}), 422))

test("POST /auth/password/reset/confirm (no code)", lambda: assert_status(
    httpx.post(f"{BASE}/auth/password/reset/confirm", json={
        "email": "notfound99999@example.com", "code": "000000", "new_password": "NewPass123!"
    }), 404))

# --- OAuth ---

test("POST /auth/login/oauth (no id_token)", lambda: assert_status(
    httpx.post(f"{BASE}/auth/login/oauth", json={
        "provider": "github", "provider_user_id": "123", "email": "test@test.com"
    }), 422))

test("POST /auth/login/oauth (invalid token)", lambda: assert_status(
    httpx.post(f"{BASE}/auth/login/oauth", json={
        "provider": "google", "id_token": "fake-token", "provider_user_id": "123",
        "email": "test-oauth-99999@test.com"
    }, timeout=15.0), 401))

# --- LLM ---

test("POST /llm/test (no key)", lambda: assert_status(
    httpx.post(f"{BASE}/llm/test", headers=headers, json={
        "provider": "openai", "model": "gpt-4o-mini", "base_url": "https://api.openai.com"
    }, timeout=12.0), 400))

# --- Alerts & Logs ---

test("GET /alerts (unauthorized)", lambda: assert_status(
    httpx.get(f"{BASE}/alerts"), 401))

test("GET /alerts (authorized)", lambda: assert_status(
    httpx.get(f"{BASE}/alerts?limit=10", headers=headers), 200))

test("GET /logs", lambda: assert_status(
    httpx.get(f"{BASE}/logs?limit=10", headers=headers), 200))

# --- Site target ---

test("POST /site/target (unauthorized)", lambda: assert_status(
    httpx.post(f"{BASE}/site/target", json={"url": "https://example.com"}), 401))

test("POST /site/target (SSRF)", lambda: assert_status(
    httpx.post(f"{BASE}/site/target", headers=headers, json={"url": "http://127.0.0.1:8000"}),
    422))

test("POST /site/target (valid)", lambda: assert_status(
    httpx.post(f"{BASE}/site/target", headers=headers, json={"url": "https://httpbin.org"}, timeout=15.0),
    200))

# --- Logout ---

test("POST /auth/logout", lambda: assert_status(
    httpx.post(f"{BASE}/auth/logout", headers=headers), 200))

test("GET /auth/session (after logout)", lambda: assert_status(
    httpx.get(f"{BASE}/auth/session"), 401))


print(f"\n{'='*50}")
print(f"Results: {passed} PASS, {failed} FAIL out of {passed+failed} tests")
print(f"{'='*50}")

if failed > 0:
    print("\nFailed tests:")
    for r in results:
        if r[0] == "FAIL":
            print(f"  - {r[1]}: {r[2]}")

sys.exit(0 if failed == 0 else 1)
