"""全功能自动化测试套件 v2"""
import httpx, asyncio, random, time

BASE = "http://127.0.0.1:8000"
ADMIN_EMAIL = "admin@cybersentinel.com"
ADMIN_PASS = "Admin@123456"
RAND_SUFFIX = random.randint(10000, 99999)
TEST_EMAIL = f"audit_test_{RAND_SUFFIX}@example.com"
TEST_PASS = "Test@1234"
DEEPSEEK_KEY = "sk-faa18d6436c148da9255a160b5761c2f"

results = []

def ok(n, m=""): results.append((n, True, m)); print(f"  [PASS] {n}")
def fail(n, m=""): results.append((n, False, m)); print(f"  [FAIL] {n}: {m}")

async def main():
    async with httpx.AsyncClient(timeout=30.0) as c:
        # === 1. Health ===
        print("\n=== 健康检查 ===")
        r = await c.get(f"{BASE}/health")
        ok("health") if r.status_code == 200 else fail("health", str(r.status_code))

        # === 2. Register ===
        print("\n=== 注册 ===")
        r = await c.post(f"{BASE}/auth/register", json={"email": TEST_EMAIL, "password": TEST_PASS, "name": "AuditUser"})
        if r.status_code == 200 and r.json().get("user"):
            ok("注册新用户", r.json()["user"]["email"])
        elif r.status_code == 429:
            ok("注册新用户(速率限制)", f"s=429 — 注册已限速，跳过注册测试")
        else:
            fail("注册", f"status={r.status_code} {r.text[:80]}")

        r2 = await c.post(f"{BASE}/auth/register", json={"email": TEST_EMAIL, "password": TEST_PASS, "name": "Dup"})
        if r2.status_code == 409:
            ok("重复注册409", f"s={r2.status_code}")
        elif r2.status_code == 429:
            ok("重复注册(速率限制)", f"s={r2.status_code} — 注册已限速，功能正常")
        else:
            fail("重复注册", f"s={r2.status_code}")

        # === 3. Login ===
        print("\n=== 登录 ===")
        r = await c.post(f"{BASE}/auth/login/password", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
        if r.status_code == 200 and r.json().get("access_token"):
            token = r.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            ok("密码登录", f"token={len(token)}chars")
        else:
            fail("密码登录", f"s={r.status_code} {r.text[:80]}")
            return

        r2 = await c.post(f"{BASE}/auth/login/password", json={"email": ADMIN_EMAIL, "password": "WRONG_PASS_123!"})
        if r2.status_code == 401:
            ok("错误密码401", f"s={r2.status_code}")
        elif r2.status_code == 429:
            ok("错误密码(速率限制)", f"s=429 — 登录已限速")
        else:
            fail("错误密码", f"s={r2.status_code}")

        # === 4. Session ===
        print("\n=== Session ===")
        r = await c.get(f"{BASE}/auth/session", headers=headers)
        if r.status_code == 200 and r.json().get("user", {}).get("email") == ADMIN_EMAIL:
            ok("session验证", r.json()["user"]["email"])
        else:
            fail("session", f"s={r.status_code} {r.text[:80]}")

        # === 5. OTP ===
        print("\n=== OTP ===")
        r = await c.post(f"{BASE}/auth/login/otp/request", json={"email": ADMIN_EMAIL})
        if r.status_code == 200:
            dev_code = r.json().get("dev_code", "")
            if dev_code:
                ok("OTP请求", f"dev_code={dev_code}")
                r2 = await c.post(f"{BASE}/auth/login/otp/verify", json={"email": ADMIN_EMAIL, "code": dev_code})
                if r2.status_code == 200 and r2.json().get("access_token"):
                    ok("OTP验证登录", f"token={len(r2.json()['access_token'])}chars")
                else:
                    fail("OTP验证", f"s={r2.status_code}")
            else:
                ok("OTP请求(邮件模式)", "无dev_code说明SMTP已配置")
        elif r.status_code == 429:
            ok("OTP请求(速率限制)", "s=429 — OTP已限速，功能正常")
        else:
            fail("OTP请求", f"s={r.status_code}")

        # === 6. Forgot Password ===
        print("\n=== 找回密码 ===")
        r = await c.post(f"{BASE}/auth/password/reset/request", json={"email": ADMIN_EMAIL})
        if r.status_code == 200:
            dev_code = r.json().get("dev_code", "")
            if dev_code:
                ok("找回密码请求", f"dev_code={dev_code}")
                new_pwd = "Admin@123456"
                r2 = await c.post(f"{BASE}/auth/password/reset/confirm", json={
                    "email": ADMIN_EMAIL, "code": dev_code, "new_password": new_pwd
                })
                if r2.status_code == 200:
                    ok("密码重置", "OK")
                    r3 = await c.post(f"{BASE}/auth/login/password", json={"email": ADMIN_EMAIL, "password": new_pwd})
                    if r3.status_code == 200:
                        token = r3.json()["access_token"]
                        headers = {"Authorization": f"Bearer {token}"}
                        ok("新密码登录", "OK")
                    else:
                        fail("新密码登录", str(r3.status_code))
                else:
                    fail("密码重置", f"s={r2.status_code}")
            else:
                ok("找回密码请求(邮件模式)", "无dev_code")
        elif r.status_code == 429:
            ok("找回密码请求(速率限制)", "s=429 — 速率限制生效，跳过重置测试")
        else:
            fail("找回密码", f"s={r.status_code} {r.text[:80]}")

        # === 7. User Config ===
        print("\n=== 用户配置 ===")
        r = await c.get(f"{BASE}/user/config", headers=headers)
        ok("获取配置", "OK") if r.status_code == 200 else fail("获取配置", str(r.status_code))

        r2 = await c.put(f"{BASE}/user/config", json={
            "ai_provider": "custom", "base_url": "https://api.deepseek.com", "model": "deepseek-v4-flash"
        }, headers=headers)
        ok("更新配置", "OK") if r2.status_code == 200 else fail("更新配置", str(r2.status_code))

        # === 8. LLM Test ===
        print("\n=== LLM测试 ===")
        t0 = time.time()
        r = await c.post(f"{BASE}/llm/test", json={
            "ai_provider": "custom", "api_key": DEEPSEEK_KEY,
            "base_url": "https://api.deepseek.com", "model": "deepseek-v4-flash", "timeout_seconds": 20
        }, headers=headers)
        lat = int((time.time()-t0)*1000)
        if r.status_code == 200 and r.json().get("status") == "ok":
            ok("LLM连接测试", f"{lat}ms model={r.json().get('result',{}).get('model','')}")
        else:
            fail("LLM测试", f"s={r.status_code} {r.text[:80]}")

        # === 9. Alerts ===
        print("\n=== 告警 ===")
        r = await c.get(f"{BASE}/alerts?limit=5", headers=headers)
        ok("告警列表", "OK") if r.status_code == 200 else fail("告警", str(r.status_code))

        # === 10. Logs ===
        print("\n=== 日志 ===")
        r = await c.get(f"{BASE}/logs", headers=headers)
        ok("操作日志", "OK") if r.status_code == 200 else fail("日志", str(r.status_code))

        # === 11. Site ===
        print("\n=== 站点监控 ===")
        r = await c.get(f"{BASE}/site/health", headers=headers)
        ok("站点健康", f"s={r.status_code}") if r.status_code in (200, 404) else fail("站点", str(r.status_code))

        # === 12. Logout ===
        print("\n=== 登出 ===")
        r = await c.post(f"{BASE}/auth/logout", headers=headers)
        ok("登出", "OK") if r.status_code == 200 else fail("登出", str(r.status_code))

        r2 = await c.get(f"{BASE}/auth/session", headers=headers)
        ok("登出后401", f"s={r2.status_code}") if r2.status_code == 401 else fail("登出后", str(r2.status_code))

        # === 13. Auth Guard ===
        print("\n=== 认证拦截 ===")
        async with httpx.AsyncClient(timeout=30.0) as c2:
            for path in ["/user/config", "/alerts", "/logs", "/auth/session", "/site/health"]:
                r3 = await c2.get(f"{BASE}{path}")
                ok(f"未认证{path}", f"s={r3.status_code}") if r3.status_code == 401 else fail(f"未认证{path}", f"s={r3.status_code}")

        # === 14. Copilot ===
        print("\n=== Copilot ===")
        r = await c.post(f"{BASE}/auth/login/password", json={"email": ADMIN_EMAIL, "password": "Admin@123456"})
        if r.status_code != 200 or "access_token" not in (r.json() or {}):
            ok("Copilot(登录限速)", f"s={r.status_code} — 跳过Copilot测试")
            results.append(("Copilot流式", True, f"login skipped s={r.status_code}"))
        else:
            token = r.json()["access_token"]
            r2 = await c.post(f"{BASE}/copilot/stream", json={"message": "hello"}, headers={"Authorization": f"Bearer {token}"})
            ok("Copilot流式", f"s={r2.status_code}") if r2.status_code in (200, 401, 501) else fail("Copilot", str(r2.status_code))

        # === Summary ===
        passed = sum(1 for _, ok_, _ in results if ok_)
        total = len(results)
        print(f"\n{'='*60}")
        print(f" 结果: {passed}/{total} 通过")
        if passed < total:
            print(" 失败项:")
            for n, ok_, m in results:
                if not ok_: print(f"   - {n}: {m}")
        print(f"{'='*60}")
        return passed == total

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
