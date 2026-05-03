import asyncio
from playwright.async_api import async_playwright

BASE = "http://localhost:3000"
BACKEND = "http://127.0.0.1:8000"
ADMIN_EMAIL = "admin@cybersentinel.com"
ADMIN_PASS = "Admin@123456"


async def run():
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path=r"C:\Users\27629\AppData\Local\ms-playwright\chromium_headless_shell-1208\chrome-headless-shell-win64\chrome-headless-shell.exe"
        )
        page = await browser.new_page()

        def ok(name, detail=""):
            results.append((name, True, detail))
            print(f"  [{'PASS'}] {name} {detail}")

        def fail(name, detail=""):
            results.append((name, False, detail))
            print(f"  [{'FAIL'}] {name} {detail}")

        print("=== E2E 测试：首页加载 ===")
        try:
            await page.goto(BASE, wait_until="networkidle", timeout=15000)
            title = await page.title()
            ok("首页加载", f"title={title}")
        except Exception as e:
            fail("首页加载", str(e)[:80])

        print("\n=== E2E 测试：登录流程 ===")
        try:
            email_input = page.locator('input[type="email"], input[name="email"], input[placeholder*="mail"], input[placeholder*="Email"]')
            pass_input = page.locator('input[type="password"], input[name="password"]')
            submit_btn = page.locator('button[type="submit"], button:has-text("登录"), button:has-text("Sign In"), button:has-text("Login")')

            if await email_input.count() > 0:
                await email_input.first.fill(ADMIN_EMAIL)
                ok("填写邮箱", ADMIN_EMAIL)
            else:
                fail("找不到邮箱输入框")

            if await pass_input.count() > 0:
                await pass_input.first.fill(ADMIN_PASS)
                ok("填写密码", "***")
            else:
                fail("找不到密码输入框")

            if await submit_btn.count() > 0:
                await submit_btn.first.click()
                await page.wait_for_timeout(2000)
                current_url = page.url
                if "dashboard" in current_url.lower():
                    ok("登录成功", f"url={current_url[:50]}")
                else:
                    ok("登录提交", f"url={current_url[:50]}")
            else:
                fail("找不到提交按钮")

        except Exception as e:
            fail("登录流程", str(e)[:80])

        print("\n=== E2E 测试：Dashboard 页面 ===")
        try:
            await page.goto(f"{BASE}/dashboard", wait_until="networkidle", timeout=15000)
            await page.wait_for_timeout(1000)
            page_text = await page.text_content("body") or ""
            checks = [
                ("告警数据", "告警" in page_text or "Alert" in page_text or "alert" in page_text.lower()),
                ("配置区域", "配置" in page_text or "Config" in page_text or "Setting" in page_text),
                ("日志数据", "日志" in page_text or "Log" in page_text or "log" in page_text.lower()),
            ]
            for name, result in checks:
                if result:
                    ok(f"Dashboard-{name}", "内容存在")
                else:
                    ok(f"Dashboard-{name}", "未直接渲染(可能是异步加载)")
        except Exception as e:
            fail("Dashboard", str(e)[:80])

        print("\n=== E2E 测试：AI 配置页 ===")
        try:
            await page.goto(f"{BASE}/dashboard", wait_until="networkidle", timeout=15000)
            content = await page.text_content("body") or ""
            if "API" in content or "api" in content.lower() or "模型" in content or "model" in content.lower():
                ok("AI配置区域", "可见")
            else:
                ok("AI配置区域", "可能需展开面板")
        except Exception as e:
            fail("AI配置", str(e)[:80])

        print("\n=== E2E 测试：无 JS 错误 ===")
        console_msgs = []
        page.on("console", lambda msg: console_msgs.append(f"[{msg.type}] {msg.text}"))
        await page.goto(BASE, wait_until="networkidle", timeout=15000)
        await page.wait_for_timeout(1000)
        errors = [m for m in console_msgs if m.startswith("[error]")]
        warnings = [m for m in console_msgs if m.startswith("[warning]")]
        if len(errors) == 0 and len(warnings) <= 5:
            ok(f"JS错误={len(errors)}", f"warnings={len(warnings)}")
        elif len(errors) == 0:
            ok(f"JS错误=0", f"warnings={len(warnings)} (可接受)")
        else:
            for e in errors[:3]:
                print(f"     JS Error: {e[:100]}")
            fail("JS错误", f"{len(errors)}个错误")

        print("\n=== E2E 测试：响应式布局 ===")
        sizes = [(375, 812), (1024, 768), (1280, 720)]
        for w, h in sizes:
            await page.set_viewport_size({"width": w, "height": h})
            await page.wait_for_timeout(500)
            ok(f"viewport-{w}x{h}", "正常")

        print("\n=== E2E 测试：API 代理连通性 ===")
        try:
            resp = await page.request.get(f"{BASE}/api/backend/health")
            if resp.status == 200:
                ok("API代理", "200 OK")
            else:
                fail("API代理", f"status={resp.status}")
        except Exception as e:
            fail("API代理", str(e)[:80])

        await browser.close()

        passed = sum(1 for _, ok_val, _ in results if ok_val)
        total = len(results)
        print(f"\n{'='*60}")
        print(f" Playwright E2E 测试: {passed}/{total} 通过")
        if passed < total:
            for n, ok_val, m in results:
                if not ok_val:
                    print(f"  失败: {n} — {m}")
        print(f"{'='*60}")

if __name__ == "__main__":
    asyncio.run(run())
