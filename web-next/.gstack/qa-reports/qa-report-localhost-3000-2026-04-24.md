# QA Report — localhost:3500

- Date: 2026-04-24
- Duration: ~90m
- Mode: full (browser-based)
- Scope: 登录入口页(`/`)与鉴权保护页(`/dashboard`)；认证链路、关键接口与上线前冒烟
- Framework: Next.js + NextAuth

## Summary
- Total issues found: 3
- Fixes applied: 3 (verified: 3, best-effort: 0, reverted: 0)
- Deferred issues: 0
- Health score: 96

PR Summary: "QA found 3 issues, all fixed and verified, health score 74 → 96; real-account happy path verified on localhost:3500."

---

## Evidence
- `screenshots/home.png`
- `screenshots/home-mobile.png`
- `screenshots/issue-001-before.png`
- `screenshots/issue-001-after-click-login.png`
- `screenshots/home-3300.png`
- `screenshots/home-3400-after-auth-secret.png`
- `screenshots/home-3400-smoke.png`
- `screenshots/dashboard-redirect-3400.png`
- `screenshots/login-invalid-submit-3400.png`
- `screenshots/login-invalid-submit-3500-after-fix.png`
- `screenshots/3500-real-login-01-before-submit.png`
- `screenshots/3500-real-login-02-after-submit.png`
- `screenshots/3500-real-login-03-dashboard-attempt.png`
- `screenshots/3500-real-login-04-session-api.png`
- `screenshots/3500-real-login-success-1-before-submit.png`
- `screenshots/3500-real-login-success-2-dashboard.png`
- `screenshots/3500-real-login-success-3-post-login-home.png`

---

## Issue List

### ISSUE-001 (HIGH) 功能性
- Title: 缺少 `AUTH_SECRET` 时 NextAuth 会话接口返回 500，首页持续报错
- Repro:
  1) 打开 `http://localhost:3000/`
  2) 观察控制台错误
  3) 直接请求 `GET /api/auth/session`
- Expected: 未登录应返回 `200 + null`（或可处理响应），页面无鉴权配置错误
- Actual: 返回 `500`，错误为 `There was a problem with the server configuration`
- API evidence:
  - `curl -i http://localhost:3000/api/auth/session` -> `500`
  - `curl -i http://localhost:3500/api/auth/session`（读取 `.env.local` 后）-> `200` + `null`
- Fix Status: verified（已通过配置 `.env.local` 的 `AUTH_SECRET` 修复并复测）
- Commit SHA: N/A
- Files Changed: `.env.local`
- Before/After screenshots:
  - before: `screenshots/issue-001-before.png`
  - after: `screenshots/home-3400-after-auth-secret.png`

### ISSUE-002 (LOW) 内容/资源
- Title: 站点缺失 favicon，`/favicon.ico` 返回 404
- Repro:
  1) 打开首页
  2) 请求 `GET /favicon.ico`
- Expected: 返回 200 图标资源
- Actual (before): 返回 404
- Actual (after): 返回 200
- Evidence:
  - `curl -i http://localhost:3500/favicon.ico`（旧实例）-> `404`
  - `curl -i http://localhost:3600/favicon.ico`（新构建实例）-> `200`
- Fix Status: verified
- Commit SHA: N/A
- Files Changed: `app/favicon.ico`

### ISSUE-003 (MEDIUM) 体验/可用性
- Title: 无效凭据登录时提示技术错误码 `Configuration`，用户不可理解
- Repro:
  1) 打开 `http://localhost:3500/`
  2) 输入无效邮箱密码并提交
- Expected: 显示用户可理解的失败提示（不暴露内部错误码）
- Actual (before): 显示 `登录失败：Configuration`
- Actual (after): 显示 `登录失败：邮箱或密码错误`
- Fix Status: verified
- Commit SHA: N/A
- Files Changed: `app/page.tsx`, `auth.ts`
- Before/After screenshots:
  - before: `screenshots/login-invalid-submit-3400.png`
  - after: `screenshots/login-invalid-submit-3500-after-fix.png`

---

## Console Health Summary
- 首页与登录交互路径均无新增控制台错误
- `/favicon.ico` 噪音错误已清除（在新构建实例验证）

---

## Publish & Monitoring Acceptance

### Pre-release checks
- Frontend type check: PASS
- Frontend production build: PASS
- Backend health endpoint `/health`: PASS (200)
- OpenAPI available: PASS
- 关键路由存在: PASS
  - `/health` (GET)
  - `/site/health` (GET, 需鉴权)
  - `/alerts` (POST)
  - `/threats/confirm` (POST)
  - `/auth/session` (GET, 需鉴权)

### Monitoring-path acceptance
- `GET /site/health` 未登录返回 401，鉴权边界正常
- `/alerts` 仅允许 POST，方法约束正常（GET 返回 405）
- `POST /alerts` 与 `POST /threats/confirm` 在缺失字段时返回 422，接口校验正常
- `GET /dashboard` 未登录返回 307 重定向 `/`，前端保护正常

### Real-account integration status
- 已通过 `/auth/register` 注册并激活测试账号 `qa-user-001@example.com`
- 浏览器登录 `http://localhost:3500/` 成功，`/dashboard` 可达
- 登录态下 `GET /api/auth/session` 返回 `200`，并包含 `user.email = qa-user-001@example.com`
- 使用会话中的 `backendAccessToken` 调用 `GET /site/health` 返回 `200`
- 结论：真实账号 happy-path 已闭环，认证链路可用

### Release blockers
- 无阻塞项

---

## Top 3 Things to Keep
1. 保留 `scripts/smoke-auth-flow.sh` 作为发布前认证链路冒烟脚本
2. 预发布环境保留一组可轮换的 QA 测试账号
3. 继续在单一候选构建端口上收集上线证据，避免混端口证据漂移


