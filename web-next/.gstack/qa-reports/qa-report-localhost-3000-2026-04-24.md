# QA Report — localhost:3000

- Date: 2026-04-24
- Duration: ~35m
- Mode: full (browser-based)
- Scope: 登录入口页(`/`)与鉴权保护页(`/dashboard`)；认证链路与基础资源
- Framework: Next.js + NextAuth

## Summary
- Total issues found: 2
- Fixes applied: 1 (verified: 1, best-effort: 0, reverted: 0)
- Deferred issues: 1
- Health score: 90

PR Summary: "QA found 2 issues, fixed 1, health score 74 → 90."

---

## Evidence
- `screenshots/home.png`
- `screenshots/home-mobile.png`
- `screenshots/issue-001-before.png`
- `screenshots/issue-001-after-click-login.png`
- `screenshots/home-3300.png`
- `screenshots/home-3400-after-auth-secret.png`

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
  - `curl -i http://localhost:3400/api/auth/session`（读取 `.env.local` 后）-> `200` + `null`
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
- Actual: 返回 404
- Evidence:
  - `curl -i http://localhost:3000/favicon.ico` -> `404`
  - `curl -i http://localhost:3300/favicon.ico` -> `404`
- Fix Status: deferred（低优先级，可在后续UI完善中补齐）
- Commit SHA: N/A
- Files Changed: N/A

---

## Console Health Summary
- 主要错误集中在鉴权：已通过配置 `AUTH_SECRET` 解除（3400实例控制台无错误）
- 资源错误：`/favicon.ico` 404

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
- `/alerts` 仅允许 POST，方法约束正常
- 监控链路可用性结论：接口层可达且行为正确，业务层需登录态/真实告警上下文再做生产前冒烟

### Release blockers
1) 无阻塞项（`AUTH_SECRET` 已在 `.env.local` 配置并复测通过）
2) 建议补齐 `favicon.ico`（非阻塞）

---

## Top 3 Things to Fix
1. 生产/预发布环境注入与 `.env.local` 一致的 `AUTH_SECRET`
2. 用真实账号跑一次登录后 `/dashboard` 与 `/site/health` 联动回归
3. 补 favicon，清理噪音 404
