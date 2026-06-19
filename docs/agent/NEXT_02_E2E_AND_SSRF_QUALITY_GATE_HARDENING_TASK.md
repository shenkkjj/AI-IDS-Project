# NEXT-02 E2E and SSRF Quality Gate Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or the local equivalent task-by-task execution workflow. This repository also requires the skill-first workflow in `AGENTS.md`: before editing, check and read the relevant skills. Reply in Chinese.

**Goal:** 把 NEXT-01 之后仍残留的质量门缺口收口：修复旧版 Demo Flow 浏览器 E2E 的登录 / 跳转等待方式，并让 SSRF 测试在受限 DNS / 代理环境下确定性通过，同时不降低生产 SSRF 防护。

**Architecture:** 复用 NEXT-01 已验证通过的后端 API register + NextAuth callback cookie seeding + `/dashboard` 服务端 `auth()` 验收路径，替换 `test_demo_flow_e2e.py` 中过时的 `expect_navigation` 登录等待。SSRF 部分只改测试隔离：把公网域名 build-url 测试改成显式 monkeypatch `_is_url_pointing_to_internal(...)=False`，避免真实 DNS 把公网域名解析到 `198.18.0.0/15` 等受限地址时误红；生产 `server/analyzer.py` / `server/core/utils.py` 的 SSRF 阻断策略必须保持原样。

**Tech Stack:** pytest + pytest-asyncio + Playwright Python + FastAPI backend + Next.js 15 App Router + next-auth 5 + existing SSRF helpers in `server.analyzer` / `server.core.utils`.

---

## 0. 为什么这是下一条优先任务

NEXT-01 已交付并 push 到 `origin/main`：

- `web-next/app/dashboard/page.tsx` 已改成 Server Component，用 `auth()` + `redirect("/")` 放行 Dashboard。
- `web-next/app/layout.tsx` 已在服务端读取 session 并传给 `Providers`。
- `web-next/app/providers.tsx` 已把服务端 session 注入 `<SessionProvider session={session}>`。
- `server/tests/test_auth_session_e2e.py --run-e2e` 已真实通过。
- `server/tests/test_incident_report_e2e.py --run-e2e` 已真实通过。

但仍有两个会影响后续无人值守质量判断的问题：

1. `server/tests/test_demo_flow_e2e.py --run-e2e` 仍使用旧登录 helper：`async with page.expect_navigation(...)` 等待 `/dashboard`。Next.js App Router 的 `router.push("/dashboard")` 是客户端路由，不稳定触发原生 navigation event，所以该测试会在注册 / 登录阶段超时。
2. `server/tests/test_ssrf.py` 的部分公网域名 build-url 测试仍依赖真实 DNS。当前环境可能把 `api.deepseek.com` / `example.com` 解析到 `198.18.*` 等保留地址，生产代码正确阻断后测试反而失败。

本任务不是加功能，而是把“后端默认基线 + 浏览器 Demo Flow + SSRF 安全测试”恢复成可重复的质量门。

## 1. 启动前必读

必须按顺序阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/agent/NEXT_01_AUTH_SESSION_LOADING_E2E_RECOVERY_TASK.md`
- `docs/runs/2026-06-19-next-01-auth-session-loading-e2e-recovery.md`
- `server/tests/test_auth_session_e2e.py`
- `server/tests/test_incident_report_e2e.py`
- `server/tests/test_demo_flow_e2e.py`
- `server/tests/test_ssrf.py`
- `server/analyzer.py`
- `server/core/utils.py`
- `web-next/app/dashboard/page.tsx`
- `web-next/app/layout.tsx`
- `web-next/app/providers.tsx`

如果任何文件路径因 Windows shell 的 `[` / `]` 通配问题读取失败，使用 `-LiteralPath`。

## 2. 必用 skill

执行前必须检查并使用：

- `superpowers:executing-plans`：按本文逐项执行。
- `tdd-workflow`：先复现 Demo E2E 与 SSRF 测试失败，再修。
- `e2e-testing`：处理 Playwright 稳定等待、locator auto-wait、失败诊断。
- `security-review`：SSRF 和认证 cookie 路径都是安全敏感面，必须确认没有放宽生产策略。
- `verification-loop`：最终质量门。

如果需要抽取共享 E2E helper，可额外参考 `frontend-patterns`，但本任务优先做小范围测试修复，不做前端结构改造。

## 3. 风险等级与预算

- 运行模式：L5 高风险质量门收口战役。
- 风险分类：认证 E2E 测试路径 + SSRF 安全测试，属于高审查要求，但默认不改生产认证 / 生产 SSRF 代码。
- 预计时长：2-4 小时。
- 同一失败最多修复：3 轮。
- diff 预算：约 800 行；如果抽取共享 E2E helper，可到 1200 行，但必须解释。
- 允许通过质量门后精确 commit 并 push 到 `origin/main`。
- 禁止 `git add .`。
- 禁止提交 `.coverage`、真实 `.env`、数据库、证书、私钥、token。

## 4. 初始审计

先创建运行日志：

```text
docs/runs/2026-06-19-next-02-e2e-and-ssrf-quality-gate-hardening.md
```

记录：

- 当前分支。
- `git status --short --branch`。
- `git log --oneline --decorate -15`。
- `.coverage` 是否 modified。
- Playwright 是否安装。
- 前后端 dev server 是否已运行。
- 当前 `server/tests/test_demo_flow_e2e.py` 登录 helper 是否仍使用 `expect_navigation`。
- 当前 `server/tests/test_ssrf.py` 哪些测试没有 monkeypatch DNS helper。

推荐命令：

```powershell
git status --short --branch
git log --oneline --decorate -15
Test-Path .coverage
.venv\Scripts\python.exe -c "import importlib.util; raise SystemExit(0 if importlib.util.find_spec('playwright') else 1)"
Select-String -Path server\tests\test_demo_flow_e2e.py -Pattern "expect_navigation|pytestmark|callback/credentials"
Select-String -Path server\tests\test_ssrf.py -Pattern "api.deepseek.com|example.com|monkeypatch|_is_url_pointing_to_internal"
```

## 5. 允许修改

优先允许修改：

- `server/tests/test_demo_flow_e2e.py`
- `server/tests/test_ssrf.py`
- `docs/runs/2026-06-19-next-02-e2e-and-ssrf-quality-gate-hardening.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

条件允许修改：

- `server/tests/e2e_helpers.py`：只有当你决定抽取 NEXT-01 / M3-08 / Demo Flow 共用登录 helper 时才新增。
- `server/tests/test_auth_session_e2e.py`：只有当抽取共享 helper 时才做 import 替换，不改变断言语义。
- `server/tests/test_incident_report_e2e.py`：只有当抽取共享 helper 时才做 import 替换，不改变报告验收断言语义。

## 6. 禁止修改

禁止修改：

- `server/analyzer.py` 的 `_is_ssrf_safe` / `build_chat_completions_url` 生产逻辑。
- `server/core/utils.py` 的 `_is_url_pointing_to_internal` / `_is_private_or_loopback_ip` 生产逻辑。
- `server/core/auth*`
- `server/routers/auth*`
- `server/security/**`
- `/mcp` 鉴权逻辑。
- Alembic migration / 数据库 schema。
- `web-next/app/dashboard/page.tsx` / `web-next/app/layout.tsx` / `web-next/app/providers.tsx`，除非 E2E 暴露 NEXT-01 真实回归；若需要改，必须停下写风险说明。
- 真实 `.env` / `.env.local` / `web-next/.env` / `web-next/.env.local`。
- `.coverage`
- `data/*.db`

禁止行为：

- 不允许把 Demo Flow E2E 改成 `skip` / `xfail`。
- 不允许删除 Copilot fallback、triage、DOM forbidden sentinel 断言。
- 不允许为了 SSRF 测试绿而放宽生产 SSRF 阻断。
- 不允许让公网域名测试访问真实网络作为通过条件。
- 不允许在浏览器 storage 保存 token。
- 不允许暴露 backend access token。

## 7. RED A：复现 Demo Flow E2E 失败

先运行旧 Demo Flow E2E：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow_e2e.py -q --tb=short --run-e2e -s
```

预期：

- 如果 dev server / Playwright 未就绪，记录为环境阻塞，但不要删除测试。
- 如果测试失败在 `page.expect_navigation` / `/dashboard` 等待，记录为本任务主 RED。
- 如果测试已经通过，仍要做 SSRF 部分；并把 Demo Flow 结果记录为“无需代码修复，只做文档与质量门验证”。

不要在 RED 前改测试代码。

## 8. GREEN A：修复 Demo Flow 登录 helper

优先做最小修复：只替换 `server/tests/test_demo_flow_e2e.py` 的 `_register_via_ui` 登录实现，不抽取新文件。

把 `pytestmark` 改为列表，和 NEXT-01 / M3-08 对齐：

```python
pytestmark = [pytest.mark.e2e]
```

保留函数名 `_register_via_ui(page, email, password)`，但实现策略改为 NEXT-01 已验证路径：

```python
async def _register_via_ui(page, email: str, password: str) -> None:
    """通过后端 API 创建用户, 再用 NextAuth callback 种 cookie 并进入 Dashboard。

    Next.js App Router 的 router.push 不稳定触发原生 navigation event,
    因此不能再使用 page.expect_navigation 等待 /dashboard。
    """
    api_response = await page.request.post(
        f"{BASE}/api/backend/auth/register",
        data={"email": email, "password": password},
        headers={"Content-Type": "application/json"},
    )
    if api_response.status not in (200, 201):
        body = await api_response.text()
        if api_response.status == 409 or "已存在" in body or "exists" in body.lower():
            pass
        else:
            pytest.fail(
                f"E2E 前置失败: 无法注册测试用户 (HTTP {api_response.status})。"
                f"body: {body!r}"
            )

    await page.goto(f"{BASE}/", wait_until="domcontentloaded", timeout=15000)
    await page.wait_for_load_state("domcontentloaded", timeout=10000)
    try:
        await page.wait_for_function(
            "() => document.querySelector('[data-testid=\"login-email\"]') !== null",
            timeout=30000,
        )
    except Exception as exc:  # noqa: BLE001
        body_text = await page.evaluate(
            "() => document.body ? document.body.innerText.slice(0, 500) : ''"
        )
        pytest.fail(
            f"无法等到 login-email hydration 完成 ({exc})。body 文本: {body_text!r}"
        )

    await page.wait_for_function(
        "() => { const btn = document.querySelector('[data-testid=\"login-submit\"]'); return btn && !btn.disabled; }",
        timeout=30000,
    )
    await page.get_by_test_id("login-email").first.fill(email)
    await page.get_by_test_id("login-password").first.fill(password)

    csrf_resp = await page.request.get(f"{BASE}/api/auth/csrf", timeout=10000)
    csrf_token = (await csrf_resp.json()).get("csrfToken", "")
    if csrf_token:
        await page.request.post(
            f"{BASE}/api/auth/callback/credentials",
            form={
                "email": email,
                "password": password,
                "csrfToken": csrf_token,
                "callbackUrl": f"{BASE}/dashboard",
                "json": "true",
            },
            timeout=15000,
        )

    try:
        await page.get_by_test_id("login-submit").click(timeout=5000)
    except Exception:
        pass

    try:
        await page.wait_for_function(
            "() => window.location.pathname === '/dashboard'",
            timeout=20000,
        )
        return
    except Exception:
        pass

    try:
        await page.goto(f"{BASE}/dashboard", wait_until="domcontentloaded", timeout=15000)
    except Exception:
        pass

    try:
        await page.wait_for_function(
            "() => window.location.pathname === '/dashboard'",
            timeout=15000,
        )
    except Exception as exc:  # noqa: BLE001
        body_text = await page.evaluate(
            "() => document.body ? document.body.innerText.slice(0, 500) : ''"
        )
        pytest.fail(
            f"登录后未跳到 /dashboard ({exc})。当前 URL: {page.url!r}。"
            f"body 文本: {body_text!r}"
        )
```

如果复制上述代码后出现行宽 / lint 风格问题，只做等价拆行，不改变行为。

同时把 `_wait_for_demo_button` timeout 调整到 45s，与 NEXT-01 / M3-08 真实 dev server 编译时间对齐：

```python
async def _wait_for_demo_button(page) -> None:
    await page.wait_for_selector(
        '[data-testid="trigger-demo-attack"]',
        state="visible",
        timeout=45000,
    )
```

不要删除后续这些断言：

- `attack-log-row` 出现。
- `analyze-current-alert` 可见并可点击。
- Copilot assistant fallback 包含 `API Key` 或 `Base URL`。
- triage 保存后 `data-triage-status="investigating"`。
- DOM forbidden sentinel 扫描。

## 9. 可选：抽取共享 E2E helper

只有当你发现 `test_auth_session_e2e.py`、`test_incident_report_e2e.py`、`test_demo_flow_e2e.py` 的重复登录 helper 已经影响维护，才新增：

```text
server/tests/e2e_helpers.py
```

建议只放这些纯测试 helper：

```python
from __future__ import annotations

import os
import time
from importlib.util import find_spec

import pytest

BASE = os.getenv("E2E_BASE_URL", "http://localhost:3000")
DEFAULT_PASSWORD = os.getenv("E2E_DEFAULT_PASSWORD", "DemoE2EPass123!")


def skip_without_playwright() -> None:
    if find_spec("playwright") is None:
        pytest.skip(
            "未安装 playwright。运行 `pip install playwright && "
            "playwright install chromium` 后加 --run-e2e 显式执行。"
        )


def unique_e2e_user(prefix: str) -> tuple[str, str]:
    ts = int(time.time() * 1000)
    return f"{prefix}-{ts}@example.com", DEFAULT_PASSWORD
```

不要在本次强行抽取所有 helper。抽取会扩大 diff；如果只改 `test_demo_flow_e2e.py` 就能稳定通过，优先保持最小 diff。

## 10. RED B：复现 SSRF 测试对真实 DNS 的依赖

运行：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_ssrf.py -q --tb=short -vv
```

预期：

- 在受限 DNS / 代理环境中，`test_build_url_with_ssrf_check`、`test_build_url_strips_trailing_slash`、`test_build_url_with_subpath` 可能失败，错误来自 `build_chat_completions_url` 的内部地址阻断。
- 这不是生产 bug；生产代码正确 fail-closed。
- 这是测试没有隔离 DNS 行为。

如果本地已经 13/13 通过，也仍应检查测试是否对 DNS 依赖明确；只有在没有不稳定点时才不改。

## 11. GREEN B：让 SSRF 测试确定性通过

只改 `server/tests/test_ssrf.py`。新增测试 fixture：

```python
@pytest.fixture
def allow_public_dns(monkeypatch):
    monkeypatch.setattr(
        "server.core.utils._is_url_pointing_to_internal",
        lambda _url: False,
    )
```

给所有“公网域名应允许”的测试加 fixture：

```python
def test_public_domain_ok(self, allow_public_dns):
    assert _is_ssrf_safe("https://api.deepseek.com")
    assert _is_ssrf_safe("https://api.openai.com")
    assert _is_ssrf_safe("https://www.google.com")


def test_build_url_with_ssrf_check(self, allow_public_dns):
    url = build_chat_completions_url("https://api.deepseek.com")
    assert url == "https://api.deepseek.com/v1/chat/completions"


def test_build_url_strips_trailing_slash(self, allow_public_dns):
    url = build_chat_completions_url("https://api.deepseek.com/")
    assert url == "https://api.deepseek.com/v1/chat/completions"


def test_build_url_with_subpath(self, allow_public_dns):
    url = build_chat_completions_url("https://example.com/api")
    assert url == "https://example.com/api/v1/chat/completions"
```

保持这些测试不加 fixture，确认内部地址仍走生产阻断：

- `test_loopback_blocked`
- `test_private_ip_blocked`
- `test_link_local_blocked`
- `test_cloud_metadata_blocked`
- `test_build_url_rejects_internal`
- `test_multicast_blocked`
- `test_reserved_blocked`

如果想增加一个保护测试，可以加：

```python
def test_allow_public_dns_fixture_does_not_bypass_literal_internal_ip(self, allow_public_dns):
    assert not _is_ssrf_safe("http://127.0.0.1:8000")
```

这条测试确认 fixture 只影响域名解析 helper，不影响 literal IP 的生产阻断。

## 12. GREEN 验证

先跑专项：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_ssrf.py -q --tb=short
```

期望：

- `13 passed`；如果新增保护测试，则 `14 passed`。

再跑 Demo Flow E2E：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow_e2e.py -q --tb=short --run-e2e -s
```

期望：

- `1 passed`。
- `diag["registered"] == True`。
- `diag["demo"] == True`。
- `diag["copilot"] == True`。
- `diag["triage"] == True` 或如果 triage panel 不存在，要有明确记录。
- `diag["forbidden"] is None`。

如果 Copilot fallback 文案不再包含 `API Key` / `Base URL`：

- 先检查当前后端 no-key 降级文案是否确实变更。
- 可以把断言扩展到当前产品认可的 no-key fallback marker，但必须在 run log 写明原因。
- 不允许删掉 fallback 断言。

## 13. 回归矩阵

完整质量门：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_auth_session_e2e.py -q --tb=short --run-e2e -s
```

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_incident_report_e2e.py -q --tb=short --run-e2e -s
```

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow_e2e.py -q --tb=short --run-e2e -s
```

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_ssrf.py -q --tb=short
```

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

前端：

```powershell
cd web-next
npm run typecheck
npm run build
```

注意：不要并行跑 `npm run typecheck` 和 `npm run build`，避免 `.next/types` 竞争。

## 14. 安全审查

运行日志必须逐项记录：

- `server/analyzer.py` 未修改。
- `server/core/utils.py` 未修改。
- 生产 `_is_ssrf_safe` 仍阻断 loopback / RFC1918 / link-local / metadata / multicast / reserved。
- SSRF 测试 monkeypatch 只存在于 `server/tests/test_ssrf.py`。
- Demo Flow E2E 没有绕过认证；仍通过 NextAuth callback + httpOnly cookie 进入 Dashboard。
- 没有使用 `localStorage` / `sessionStorage` 保存 token。
- 没有把 backend access token 写入 DOM。
- DOM forbidden sentinel 仍检查 secret / stack trace / system prompt。
- `.coverage` 未 stage。
- 真实 `.env` / `.env.local` 未 stage。

## 15. 文档收口

必须更新：

- `docs/runs/2026-06-19-next-02-e2e-and-ssrf-quality-gate-hardening.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`

如果真实修复并跑通质量门，更新：

- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

文档要写清：

- NEXT-01 已把 Dashboard session loading 阻塞修好。
- NEXT-02 已把旧 Demo Flow E2E 的 `expect_navigation` 迁移到 URL polling / explicit goto。
- SSRF 生产策略未降级，只有测试公网域名路径去真实 DNS 依赖。
- 后续建议工单：M3-09 统一 Dashboard incident state，修复 `dashboard-client.tsx` 和 `IncidentSection` 各自独立 `useIncidents()` 带来的状态 race。

## 16. 提交策略

通过质量门后精确 commit。

推荐 commit 1：

```text
test(e2e): 稳定 demo flow 浏览器登录路径
```

包含：

- `server/tests/test_demo_flow_e2e.py`
- 如抽取 helper，则包含 `server/tests/e2e_helpers.py` 以及必要 import 替换。

推荐 commit 2：

```text
test(security): 固化 SSRF 测试 DNS 隔离
```

包含：

- `server/tests/test_ssrf.py`

推荐 commit 3：

```text
docs(quality): 记录 E2E 与 SSRF 质量门收口
```

包含：

- `docs/runs/2026-06-19-next-02-e2e-and-ssrf-quality-gate-hardening.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

精确 stage 示例：

```powershell
git add server\tests\test_demo_flow_e2e.py
git commit -m "test(e2e): 稳定 demo flow 浏览器登录路径"

git add server\tests\test_ssrf.py
git commit -m "test(security): 固化 SSRF 测试 DNS 隔离"

git add docs\runs\2026-06-19-next-02-e2e-and-ssrf-quality-gate-hardening.md docs\agent\UNATTENDED_LONG_TASKS.md PRODUCT.md docs\plans\M2_PRODUCT_ROADMAP.md
git commit -m "docs(quality): 记录 E2E 与 SSRF 质量门收口"
```

不要 stage 示例里未实际修改的文件。不要使用 `git add .`。

## 17. Push 策略

提交前：

```powershell
git status --short --branch
git diff --cached --check
git diff --cached --name-only
git log --oneline --decorate -10
```

确认：

- `.coverage` 未 stage。
- `.env` / `.env.local` 未 stage。
- `web-next/.env` / `web-next/.env.local` 未 stage。
- 数据库 / 证书 / 私钥未 stage。

然后：

```powershell
git push origin main
```

如果 push 失败：

- 最多重试 3 次。
- 记录错误摘要。
- 不要无限重试。
- 本地 commit 完成但 push 阻塞时，最终状态写“本地完成，push 阻塞”。

## 18. 停止条件

任一条件满足必须停止：

- `test_demo_flow_e2e.py --run-e2e` 失败原因不是旧登录等待，且需要改生产认证代码。
- 需要修改 `server/analyzer.py` / `server/core/utils.py` 才能让 SSRF 测试通过。
- 需要放宽生产 SSRF 阻断。
- 需要真实生产 secret 或外部账号。
- 同一个 E2E 失败连续修复 3 轮仍失败。
- Playwright / dev server 环境不可用且无法在本地修复。
- 后端全量或 Guardrails 出现大面积无关失败。
- 需要把 token 放入浏览器 storage 才能跑通。

停止时必须给出：

- 已完成内容。
- 未完成内容。
- 阻塞证据。
- 下一条最小工单。

## 19. 最终报告格式

完成后中文输出：

```text
完成状态：完成 / 部分完成 / 阻塞

根因：
- ...

改动文件：
- ...

验证命令：
- pytest server/tests/test_demo_flow_e2e.py --run-e2e -> ...
- pytest server/tests/test_ssrf.py -> ...
- pytest server/tests/test_auth_session_e2e.py --run-e2e -> ...
- pytest server/tests/test_incident_report_e2e.py --run-e2e -> ...
- pytest server/tests -> ...
- pytest server/tests/security/llm_guardrails -> ...
- npm run typecheck -> ...
- npm run build -> ...

安全审查：
- ...

提交与推送：
- commit: ...
- push: 成功 / 阻塞

运行日志：
- docs/runs/2026-06-19-next-02-e2e-and-ssrf-quality-gate-hardening.md

剩余本地噪声：
- .coverage（如仍存在，说明未提交）

下一条建议工单：
- M3-09 Dashboard incident state 单一事实源收口
```

不要只说“好了”。必须写清真实 E2E、SSRF、后端全量、Guardrails、前端 typecheck/build 是否通过。
