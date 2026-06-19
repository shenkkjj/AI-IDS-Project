# Run: NEXT-02 E2E and SSRF Quality Gate Hardening

开始时间：2026-06-19
运行模式：L5（高风险质量门收口战役）
预算：2-4 小时；同一失败最多修复 3 轮；diff 预算 ~800 行

## 目标

- 修复 `test_demo_flow_e2e.py --run-e2e` 旧登录 / 跳转等待方式（`expect_navigation` 等待 App Router client-side route），复用 NEXT-01 已验证路径：后端 API register + NextAuth `/api/auth/callback/credentials` cookie seeding + `/dashboard` URL polling / 显式 goto。
- 让 `test_ssrf.py` 的公网域名 build-url 测试在受限 DNS / 代理环境下确定性通过：只改测试 monkeypatch `_is_url_pointing_to_internal`，严禁放宽生产 `_is_ssrf_safe` / `_is_url_pointing_to_internal`。
- 满足完整质量门：Demo Flow E2E / Auth E2E / Incident Report E2E / SSRF / 后端全量 / Guardrails / 前端 typecheck+build。

## 范围

允许修改：

- `server/tests/test_demo_flow_e2e.py`
- `server/tests/test_ssrf.py`
- `docs/runs/2026-06-19-next-02-e2e-and-ssrf-quality-gate-hardening.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

禁止修改：

- `server/analyzer.py` 的 `_is_ssrf_safe` / `build_chat_completions_url`
- `server/core/utils.py` 的 `_is_url_pointing_to_internal` / `_is_private_or_loopback_ip`
- `server/core/auth*` / `server/routers/auth*` / `server/security/**`
- `/mcp` 鉴权 / Alembic / `docker-compose.yml` / `nginx/**`
- `web-next/app/dashboard/page.tsx` / `web-next/app/layout.tsx` / `web-next/app/providers.tsx`
- 真实 `.env` / `.env.local` / `web-next/.env*`
- `.coverage` / `data/*.db`

禁止行为：把 Demo Flow 改 skip/xfail；删除 Copilot fallback / triage / DOM forbidden sentinel 断言；为 SSRF 测试绿放宽生产阻断；让公网域名测试访问真实网络；把 token 写进 storage / DOM；`git add .`。

## 初始审计

- 当前分支：`main`
- `git status --short --branch`：

  ```
  ## main...origin/main
   M .coverage
   M docs/agent/UNATTENDED_LONG_TASKS.md
  ?? docs/agent/NEXT_02_E2E_AND_SSRF_QUALITY_GATE_HARDENING_TASK.md
  ```

- `git log --oneline -15` HEAD：`b282856 docs(auth): 记录 next-auth 会话阻塞收口`，已包含 NEXT-01 的 `efaa348 fix(auth)`、`c120c40 test(e2e)`。
- `.coverage`：modified（**不会 stage**）。
- Playwright：已安装；本地 chromium binary 是 `1217`（headless shell），通过 `PLAYWRIGHT_CHROMIUM_EXECUTABLE` 环境变量指向 `chrome-headless-shell.exe` 即可跑通。
- Dev server：后端 `:8000`、前端 `:3000` 均已就绪（`/api/backend/health` 200 OK）。
- `test_demo_flow_e2e.py` 登录 helper 走 `async with page.expect_navigation(url=re.compile(r"/dashboard..."))` 等原生导航事件，与 Next.js App Router client-side `router.push("/dashboard")` 不兼容（NEXT-01 run log §未解决问题 #1 已记录此根因）。`pytestmark` 仍是单值 `pytest.mark.e2e`，与 NEXT-01 / M3-08 的 `[pytest.mark.e2e]` 列表不一致（语义等价，顺便对齐为列表风格）。
- `test_ssrf.py` 中 `test_public_domain_ok` 已用 monkeypatch；但 `test_build_url_with_ssrf_check` / `test_build_url_strips_trailing_slash` / `test_build_url_with_subpath` **没有** monkeypatch DNS，仍依赖 `api.deepseek.com` / `example.com` 的真实解析，受限 DNS 环境（如 `198.18.*` 劫持）会误红。

## 计划

- [x] 阶段 1：阅读必读上下文 + 创建 run log
- [x] 阶段 2：RED A — 跑 `test_demo_flow_e2e.py --run-e2e`，记录 `expect_navigation` 超时
- [x] 阶段 3：RED B — 跑 `test_ssrf.py`，确认公网 build-url 测试在当前 DNS 下失败
- [x] 阶段 4：GREEN A — 替换 `_register_via_ui` 为 NEXT-01 callback cookie + URL polling 路径，`_wait_for_demo_button` 提到 45s
- [x] 阶段 5：GREEN B — 给 `test_build_url_with_ssrf_check` / `test_build_url_strips_trailing_slash` / `test_build_url_with_subpath` 加 `allow_public_dns` fixture
- [x] 阶段 6：跑专项 + 回归矩阵（Auth E2E / Incident Report E2E / Demo Flow E2E / SSRF / 后端全量 / Guardrails / 前端 typecheck+build）
- [x] 阶段 7：安全审查 + 文档收口
- [ ] 阶段 8：精确 commit + push

## 阶段记录

### 阶段 1 — 上下文阅读 + 运行日志

阅读：`docs/agent/NEXT_02_E2E_AND_SSRF_QUALITY_GATE_HARDENING_TASK.md` /
`docs/runs/2026-06-19-next-01-auth-session-loading-e2e-recovery.md` /
`server/tests/test_auth_session_e2e.py` / `server/tests/test_incident_report_e2e.py` /
`server/tests/test_demo_flow_e2e.py` / `server/tests/test_ssrf.py` /
`docs/agent/UNATTENDED_LONG_TASKS.md`。

NEXT-01 已为本任务铺好路：`web-next/app/dashboard/page.tsx` 是 Server Component，`/api/auth/callback/credentials` cookie 路径已在 auth E2E 与 incident report E2E 中真实跑通。本任务只需把 demo flow 的 helper 与之对齐。

### 阶段 2 — RED A：复现 Demo Flow E2E `expect_navigation` 超时

预热 Playwright Chromium 1217（环境里已有的 headless shell）后跑：

```
PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:/Users/27629/AppData/Local/ms-playwright/chromium_headless_shell-1217/chrome-headless-shell-win64/chrome-headless-shell.exe'
pytest server/tests/test_demo_flow_e2e.py --run-e2e -q --tb=short -s
```

输出：

```
FAILED server/tests/test_demo_flow_e2e.py::test_demo_flow_e2e_browser
playwright._impl._errors.TimeoutError: Timeout 20000ms exceeded.
waiting for navigation to "re.compile('/dashboard(\\?.*)?$')" until 'domcontentloaded'
1 failed in 25.42s
```

根因确认：`async with page.expect_navigation(url=re.compile(r"/dashboard(\?.*)?$"), ...)` 等待原生 navigation 事件，App Router 的 `router.push("/dashboard")` 是客户端路由，不触发原生 navigation。NEXT-01 已用 URL polling + 显式 goto 路径解决。

### 阶段 3 — RED B：复现 SSRF 测试对真实 DNS 的依赖

```
pytest server/tests/test_ssrf.py -q --tb=short -vv
```

输出：

```
FAILED test_ssrf.py::TestSsrfProtection::test_build_url_with_ssrf_check
FAILED test_ssrf.py::TestSsrfProtection::test_build_url_strips_trailing_slash
FAILED test_ssrf.py::TestSsrfProtection::test_build_url_with_subpath
3 failed, 10 passed
ValueError: Base URL resolves to an internal or restricted address.
```

根因：当前主机 / 代理把 `api.deepseek.com` / `example.com` 解析到 `198.18.0.0/15` 等 RFC2544 / 保留地址，生产 `_is_url_pointing_to_internal` 正确阻断。生产代码合规（fail-closed），是测试没有 monkeypatch DNS。

### 阶段 4 — GREEN A：替换 `_register_via_ui` 为 NEXT-01 callback cookie + URL polling

只改 `server/tests/test_demo_flow_e2e.py`，最小 diff：

- `pytestmark = [pytest.mark.e2e]`（与 NEXT-01 / M3-08 列表风格对齐）。
- `_register_via_ui`：先 `POST /api/backend/auth/register`（409 / "已存在" / "exists" 视为已存在）；然后等 `login-email` hydration + `login-submit` 可点击；接着拉 csrf 走 `/api/auth/callback/credentials` 直接种 httpOnly cookie；再点击 `login-submit` 让 React 状态一致（失败无所谓）；最后 URL polling `window.location.pathname === '/dashboard'`，失败 fallback 显式 `page.goto("/dashboard")` 让服务端 `auth()` 接受 / redirect。
- `_wait_for_demo_button`：timeout 从 15s 提到 45s，与 NEXT-01 / M3-08 真实 dev server 编译时间对齐。

未删除：Copilot fallback 断言（`API Key` / `Base URL`）、triage 状态切换断言（`data-triage-status="investigating"`）、DOM forbidden sentinel 扫描。未抽取共享 helper（最小 diff 优先；`server/tests/e2e_helpers.py` 不新增）。

### 阶段 5 — GREEN B：SSRF 公网 build-url 测试加 `allow_public_dns` fixture

只改 `server/tests/test_ssrf.py`：

- 抽出 module 级 `allow_public_dns` fixture，monkeypatch `server.core.utils._is_url_pointing_to_internal` 返回 `False`。
- `test_public_domain_ok` / `test_build_url_with_ssrf_check` / `test_build_url_strips_trailing_slash` / `test_build_url_with_subpath` 加 fixture 参数。
- 新增 `test_allow_public_dns_fixture_does_not_bypass_literal_internal_ip`：fixture 启用时 literal IP（`127.0.0.1` / `192.168.1.1` / `169.254.169.254`）仍走生产阻断，确认 fixture 只 monkeypatch 域名解析 helper，不影响 literal IP 的生产阻断。
- `test_loopback_blocked` / `test_private_ip_blocked` / `test_link_local_blocked` / `test_cloud_metadata_blocked` / `test_build_url_rejects_internal` / `test_multicast_blocked` / `test_reserved_blocked` / `test_build_url_rejects_empty` / `test_empty_hostname` 不加 fixture，仍走生产阻断。

未改：`server/analyzer.py` / `server/core/utils.py` 的生产 SSRF 逻辑。

### 阶段 6 — 验证矩阵（详见下方"验证证据"）

注：本地 dev backend register rate limit（`REGISTER_RATE_LIMIT_MAX=5/小时`）在
连续跑 demo + auth + incident E2E 后耗尽 IP 配额。**未修改生产 rate-limit
代码**，仅在本地 dev server 端把 uvicorn 进程重启清空内存计数（PID 1492 → 2276，
命令行不变：`python -m uvicorn server.main:app --port 8000 --host 127.0.0.1`）。
后续 CI / 生产环境跑 E2E 时建议给注册 IP 白名单或在 fixture 内做 backoff，
但这超出本任务范围。

### 阶段 7 — 安全审查

| 项 | 结论 |
|---|---|
| `server/analyzer.py` 修改 | **未改**（git diff 0 行） ✅ |
| `server/core/utils.py` 修改 | **未改**（git diff 0 行） ✅ |
| 生产 `_is_ssrf_safe` 仍阻断 loopback / RFC1918 / link-local / metadata / multicast / reserved | ✅（`test_loopback_blocked` 等 7 项原断言保留 + 新增 `test_allow_public_dns_fixture_does_not_bypass_literal_internal_ip` 双保险） |
| SSRF 测试 monkeypatch 仅在 `server/tests/test_ssrf.py` | ✅ |
| Demo Flow E2E 是否绕过认证 | 否；仍通过 NextAuth callback + httpOnly cookie 进入 Dashboard，未禁用任何 auth check ✅ |
| `localStorage` / `sessionStorage` 保存 token | 未使用 ✅ |
| backend access token 写入 DOM | 未使用 ✅ |
| DOM forbidden sentinel 仍扫描 secret / stack trace / system prompt | 保留 ✅ |
| Copilot fallback / triage 断言 | 保留 ✅ |
| `server/core/auth*` / `server/routers/auth*` / `server/security/**` 修改 | 未改 ✅ |
| Alembic / 数据库 schema / `nginx/**` / `docker-compose.yml` / 部署配置修改 | 未改 ✅ |
| `web-next/app/dashboard/page.tsx` / `web-next/app/layout.tsx` / `web-next/app/providers.tsx` 修改 | 未改 ✅ |
| 真实 `.env` / `.env.local` / `web-next/.env*` stage | 未 stage ✅ |
| `.coverage` stage | 未 stage ✅ |

## 验证证据

### E2E（核心验收）

```
pytest server/tests/test_demo_flow_e2e.py --run-e2e -q --tb=short -s
[E2E 诊断] {'registered': True, 'demo': True, 'copilot': True, 'triage': True, 'forbidden': None}
1 passed in 9.89s
```

```
pytest server/tests/test_auth_session_e2e.py --run-e2e -q --tb=short -s
[E2E 诊断] {'registered': True, 'dashboard_url': True, 'trigger_demo_visible': True,
            'loading_text_persisted': False, 'session_user_email': 'e2e-auth-...@example.com',
            'forbidden': None}
1 passed in 6.41s
```

```
pytest server/tests/test_incident_report_e2e.py --run-e2e -q --tb=short -s
[E2E 诊断] alert_id='...' filename='incident-inc_...-report.md' copy_status='已复制'
{'registered': True, 'demo': True, 'create': True, 'download': True,
 'copy_status': '已复制', 'forbidden': None,
 'filename': 'incident-inc_...-report.md'}
1 passed in 4.64s
```

### SSRF 与后端 / Guardrails / 前端

| 命令 | 结果 |
|---|---|
| `pytest server/tests/test_ssrf.py` | **14 passed**（13 原 + 1 新增保护测试） |
| `pytest server/tests` | **333 passed, 4 skipped**（4 个 e2e 默认 skip，与 NEXT-01 基线一致） |
| `pytest server/tests/security/llm_guardrails` | **139 passed** |
| `npm run typecheck` (web-next) | **0 错误** |
| `npm run build` (web-next) | **通过**；`/dashboard` 43.4 kB / First Load JS 191 kB |

## 改动文件

```
server/tests/test_demo_flow_e2e.py    GREEN A: 替换登录 helper 等待方式
server/tests/test_ssrf.py             GREEN B: 抽 fixture + 公网域名测试加 monkeypatch
docs/runs/2026-06-19-next-02-e2e-and-ssrf-quality-gate-hardening.md  本文件
docs/agent/UNATTENDED_LONG_TASKS.md   NEXT-02 状态/索引补全(commit 阶段)
PRODUCT.md / docs/plans/M2_PRODUCT_ROADMAP.md  质量门状态记录(commit 阶段)
```

未改：

```
server/analyzer.py / server/core/utils.py / server/core/auth* /
server/routers/auth* / server/security/** /
web-next/app/dashboard/page.tsx / web-next/app/layout.tsx /
web-next/app/providers.tsx / web-next/lib/auth.ts / web-next/middleware.ts /
Alembic migration / docker-compose.yml / nginx/** / .env*
```

## 未解决问题（不在本任务范围）

1. **本地 dev backend register rate limit**：`REGISTER_RATE_LIMIT_MAX=5/小时`，连续跑 3 个 E2E 会触发 429。本任务通过重启 dev server 解开；建议 M3-09+ 给 E2E 加 IP 白名单或 fixture-level backoff。
2. **`IncidentSection` 与 `dashboard-client.tsx` 双 `useIncidents()` 实例不共享 state**（M3-04 / NEXT-01 遗留 bug）：建议下一条工单 M3-09 统一 incident state 单一事实源。

## 最终状态

**完成**。
