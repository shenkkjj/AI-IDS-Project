# NEXT-01 Auth Session Loading E2E Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or the local equivalent task-by-task execution workflow. This repository also requires the skill-first workflow in `AGENTS.md`: before editing, check and read the relevant skills. Reply in Chinese.

**Goal:** 修复 M3-08 暴露的 next-auth 5 beta + Next.js 15 dev mode 下 Dashboard `useSession()` 永远 `loading` 的阻塞，让真实浏览器 E2E 能进入 Dashboard 并跑通案件报告下载验收。

**Architecture:** 先用 E2E 复现 auth session loading 阻塞，再优先采用服务端 `auth()` 保护 `/dashboard` 的 App Router 模式，让 Dashboard 放行不依赖客户端 `useSession()` hydration。只有该路线不足时，才允许给 `SessionProvider` 注入服务端初始 session 或升级 `next-auth` / `next`，并必须保持 httpOnly cookie、JWT session、后端 access token 语义不降级。

**Tech Stack:** Next.js 15 App Router + React 19 + next-auth 5.0.0-beta.30 + Credentials provider + FastAPI backend auth + pytest Playwright E2E + existing M3-08 E2E.

---

## 0. 为什么这是下一条优先任务

M3-08 已经完成：

- `server/tests/test_incident_report_e2e.py` 已写好，默认 skip，`--run-e2e` 显式触发。
- 报告导出后端契约仍为 `14 passed`。
- 后端全量为 `332 passed, 3 skipped`。
- Guardrails 专项为 `139 passed`。
- 前端 `npm run typecheck` / `npm run build` 通过。
- M3-08 commits 已 push 到 `origin/main`，当前 `HEAD` 应是 `77f7ba8 docs(incidents): 更新 M3-08 run log push 状态为成功` 或其后续提交。

M3-08 未完成的关键点：

- `pytest server/tests/test_incident_report_e2e.py --run-e2e` 无法进入 Dashboard。
- `test_demo_flow_e2e.py` 同样在 Dashboard 阶段失败。
- 现象：`/api/auth/session` 返回 200 + user，但 `web-next/app/dashboard/page.tsx` 客户端 `useSession()` 长时间保持 `loading`，页面停在 `SYSTEM · LOADING`。
- 这导致 M3-04 / M3-05 / M3-07 的真实浏览器产品路径都没有被真正验收。

本任务不是继续加功能，而是修复产品化验收通道。

## 1. 启动前必读

必须按顺序阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/agent/M3_08_INCIDENT_REPORT_BROWSER_E2E_AND_AGENT_DOCS_CATCHUP_TASK.md`
- `docs/runs/2026-06-18-m3-08-incident-report-browser-e2e-and-agent-docs-catchup.md`
- `web-next/package.json`
- `web-next/package-lock.json`
- `web-next/lib/auth.ts`
- `web-next/app/providers.tsx`
- `web-next/app/layout.tsx`
- `web-next/app/page.tsx`
- `web-next/app/dashboard/page.tsx`
- `web-next/app/dashboard/dashboard-client.tsx`
- `web-next/app/api/auth/[...nextauth]/route.ts`
- `web-next/middleware.ts`
- `server/tests/test_incident_report_e2e.py`
- `server/tests/test_demo_flow_e2e.py`

如果任何文件路径因 Windows shell 的 `[` / `]` 通配问题读取失败，使用 `-LiteralPath`：

```powershell
Get-Content -Raw -Encoding UTF8 -LiteralPath web-next\app\api\auth\[...nextauth]\route.ts
```

## 2. 必用 skill

执行前必须检查并使用：

- `superpowers:executing-plans`：按本文逐项执行。
- `tdd-workflow`：先复现 RED，再改认证代码。
- `frontend-patterns`：处理 App Router server/client boundary、provider、hydration。
- `security-review`：认证、cookie、token、session 属高风险面。
- `verification-loop`：最终质量门。
- 如需查库文档，使用 `context7` 查 `next-auth` / `Next.js` 当前文档，不靠记忆。

本任务已查到的官方文档方向：

- Auth.js / NextAuth v5 推荐在 App Router Server Component 中使用 `auth()` 获取 session。
- 客户端 `useSession()` 需要 `SessionProvider` 包裹，适合客户端条件渲染，但不应成为 Dashboard 真实 E2E 的唯一放行点。
- Next.js App Router 中 React Context Provider 必须是 Client Component，并从 Server Component layout 包裹 children。

## 3. 风险等级与预算

- 运行模式：L5 高风险收口战役。
- 风险分类：认证 / session / cookie / Dashboard 放行，属于 `AGENTS.md` L3 高风险区。
- 允许无人值守执行，但必须遵守硬停止条件。
- 预计时长：2-4 小时。
- 同一失败最多修复：3 轮。
- diff 预算：约 1000 行；如果包含依赖锁文件更新，可超过，但必须解释。
- 允许通过质量门后精确 commit 并 push 到 `origin/main`。
- 禁止 `git add .`。
- 禁止提交 `.coverage`、`.env`、`.env.local`、`web-next/.env`、`web-next/.env.local`、数据库、证书、私钥、token。

## 4. 初始审计

先创建运行日志：

```text
docs/runs/2026-06-19-next-01-auth-session-loading-e2e-recovery.md
```

记录：

- 当前分支。
- `git status --short --branch`。
- `git log --oneline --decorate -15`。
- `.coverage` 是否 modified。
- `web-next/.env` / `web-next/.env.local` 是否存在（只记录存在性，不打印内容）。
- 当前 `next` / `next-auth` / `react` / `react-dom` 版本。
- Playwright 是否安装。
- `PLAYWRIGHT_CHROMIUM_EXECUTABLE` 是否需要指向本地 Chromium。
- 当前 dev server 是否已运行。

推荐命令：

```powershell
git status --short --branch
git log --oneline --decorate -15
Test-Path .coverage
Test-Path web-next\.env
Test-Path web-next\.env.local
node -e "const p=require('./web-next/package.json'); console.log({next:p.dependencies.next,nextAuth:p.dependencies['next-auth'],react:p.dependencies.react,reactDom:p.dependencies['react-dom']})"
.venv\Scripts\python.exe -c "import importlib.util; raise SystemExit(0 if importlib.util.find_spec('playwright') else 1)"
```

## 5. 允许修改

优先允许修改：

- `web-next/app/dashboard/page.tsx`
- `web-next/app/providers.tsx`
- `web-next/app/layout.tsx`
- `web-next/lib/auth.ts`
- `web-next/app/page.tsx`
- `server/tests/test_auth_session_e2e.py`（建议新增）
- `server/tests/test_incident_report_e2e.py`（仅必要等待条件或诊断增强）
- `server/tests/test_demo_flow_e2e.py`（仅必要等待条件或诊断增强）
- `docs/runs/2026-06-19-next-01-auth-session-loading-e2e-recovery.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

在路线 A / B 均不足时，允许修改：

- `web-next/package.json`
- `web-next/package-lock.json`
- `web-next/next.config.js`
- `web-next/middleware.ts`

但只有在运行日志记录“为什么必须升级或配置变更”后才能改。

## 6. 禁止修改

禁止修改：

- `server/core/auth*`
- `server/routers/auth*`
- `server/security/**`
- `/mcp` 鉴权逻辑
- Alembic migration / 数据库 schema
- `docker-compose.yml`
- `nginx/**`
- 真实 `.env` / `.env.local`
- `web-next/.env` / `web-next/.env.local`
- `.coverage`
- `data/*.db`
- 证书、私钥、token

禁止行为：

- 不允许把 token 放进 `localStorage` / `sessionStorage`。
- 不允许把后端 access token 暴露到页面 DOM。
- 不允许为了 E2E 跑通而绕过认证。
- 不允许把 `/dashboard` 改成未登录可访问。
- 不允许删除 M3-08 E2E 或给它加 `xfail`。
- 不允许跳过 `test_demo_flow_e2e.py` 的真实问题。

## 7. 目标用户行为

完成后真实浏览器应能：

1. 打开首页。
2. 注册或登录测试用户。
3. 进入 `/dashboard`。
4. Dashboard 不再卡在 `SYSTEM · LOADING`。
5. 能看到 `trigger-demo-attack`。
6. 能运行 M3-08 案件报告 E2E：
   - 触发 Demo 告警。
   - 创建案件。
   - 下载 Markdown 案件报告。
   - 验证报告结构与脱敏 sentinel。
   - 点击复制报告。
   - 页面 DOM 无 secret / stack / system prompt 泄漏。

## 8. RED：先复现阻塞

新增一个最小 E2E：

```text
server/tests/test_auth_session_e2e.py
```

目标：只验证“登录后 Dashboard 能解除 loading 并显示主按钮”，不掺案件报告流程。

测试要求：

- `pytestmark = [pytest.mark.e2e]`
- 默认 `pytest server/tests` skip。
- `--run-e2e` 时运行。
- 使用唯一邮箱。
- 用 `page.request.post("/api/backend/auth/register")` 创建测试用户。
- 通过 UI 登录，或用现有 login helper。
- 等待 `/dashboard`。
- 断言：
  - `SYSTEM · LOADING` 不应持续存在。
  - `[data-testid="trigger-demo-attack"]` 45s 内可见。
  - `/api/auth/session` 返回 user。
  - body 不含 stack trace / secret sentinel。

推荐命令：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_auth_session_e2e.py -q --tb=short --run-e2e
```

RED 预期：

- 当前 main 上应失败在 Dashboard loading 或 `trigger-demo-attack` 不可见。
- 如果它意外通过，必须立即运行 M3-08 E2E；若 M3-08 也通过，则说明问题已被环境或上游依赖解决，本任务改为文档收口 + 质量门。

不要在 RED 前改生产代码。

## 9. 修复路线 A：优先服务端 auth() 保护 Dashboard

这是首选路线。

当前 `web-next/app/dashboard/page.tsx` 是 Client Component：

```tsx
"use client";
import { useSession } from "next-auth/react";
```

这正是阻塞点。把 `/dashboard` 入口改为 Server Component：

```tsx
import { redirect } from "next/navigation";
import { auth } from "@/lib/auth";
import DashboardClient from "./dashboard-client";

export default async function DashboardPage() {
  const session = await auth();

  if (!session?.user) {
    redirect("/");
  }

  return <DashboardClient userEmail={String(session.user.email || "")} />;
}
```

要求：

- 删除 `useSession()` 作为 Dashboard 放行条件。
- 未登录仍然 redirect 到 `/`。
- 已登录直接渲染 `DashboardClient`。
- 不把 `backendAccessToken` 传给前端。
- 不在 DOM 输出 session 原始对象。
- 保持首页 `web-next/app/page.tsx` 的登录 UI 现有体验。

如果需要展示 401 页面，不要在本次扩展设计；先保证 Dashboard E2E 可进入。

## 10. 修复路线 B：给 SessionProvider 注入初始 session

如果路线 A 修复 Dashboard 但首页登录状态仍不稳定，或 `useSession()` 在首页继续影响自动跳转，可考虑路线 B。

`web-next/app/layout.tsx` 是 Server Component，可调用 `auth()`：

```tsx
import { auth } from "@/lib/auth";
import { Providers } from "./providers";

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  return (
    <html lang="zh-CN" className="light">
      <body className="min-h-screen bg-bg text-ink font-sans antialiased">
        <Providers session={session}>{children}</Providers>
      </body>
    </html>
  );
}
```

`web-next/app/providers.tsx` 接收 session：

```tsx
"use client";

import type { Session } from "next-auth";
import { SessionProvider } from "next-auth/react";

export function Providers({
  children,
  session,
}: {
  children: React.ReactNode;
  session?: Session | null;
}) {
  return (
    <SessionProvider session={session} refetchOnWindowFocus={false} refetchInterval={0}>
      {children}
    </SessionProvider>
  );
}
```

注意：

- 这会让 root layout 动态化；本项目 Dashboard 是登录态应用，可以接受。
- 如果引入类型错误，必须修好 `npm run typecheck`。
- 不要把 session 扩展成包含后端 access token 的客户端字段。

## 11. 修复路线 C：Auth.js 配置最小调整

只有 A / B 不足时才考虑。

可审查方向：

- `trustHost` 是否应在 E2E/dev 下稳定为 `true`。
- 是否需要显式设置 Auth.js `basePath` 与 route handler 一致。
- callbacks 是否应把必要字段写入 `session.user`，但不能写 access token。
- `AUTH_SECRET` / `NEXTAUTH_SECRET` 缺失或长度不足时是否有清晰错误。
- `AUTH_URL` / `NEXTAUTH_URL` 是否因 localhost / 127.0.0.1 不一致导致 cookie 域问题。

禁止：

- 禁止关闭 CSRF。
- 禁止把 session strategy 改成不安全存储。
- 禁止把 `backendAccessToken` 直接挂到 `session.user` 传给客户端，除非已有业务强依赖并经过安全审查；本任务默认不需要。

## 12. 修复路线 D：依赖升级

只有 A / B / C 均无法解决，且 Context7 / 官方 release notes 指向已知兼容问题时才允许。

允许：

- 升级 `next-auth` 到同一主线更高 beta / stable（如可用）。
- 必要时升级 `next` 到当前 15.x patch。
- 同步更新 `package-lock.json`。

要求：

- 先记录当前版本。
- 运行 `npm view next-auth version` / `npm view next version` 或查官方文档。
- 不能盲升 major。
- 不能移除 lockfile。
- 升级后必须运行完整前端 typecheck/build 和 E2E。

## 13. GREEN：验证最小 auth E2E

修复后先跑：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_auth_session_e2e.py -q --tb=short --run-e2e
```

GREEN 标准：

- 测试通过。
- Dashboard 45s 内出现 `trigger-demo-attack`。
- 页面没有 `SYSTEM · LOADING` 卡住。
- `/api/auth/session` 返回 user。
- 无 secret / stack trace sentinel。

## 14. 回归：跑 M3-08 完整 E2E

随后跑：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_incident_report_e2e.py -q --tb=short --run-e2e
```

必须真实通过，不能只默认 skip。

如果它失败在非 auth 问题：

- 允许修最小 E2E 等待条件。
- 允许修 M3-07 前端报告按钮真实 bug。
- 不允许扩大到新功能。
- 同一失败最多修 3 轮。

建议再跑历史 Demo E2E：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow_e2e.py -q --tb=short --run-e2e
```

如果 `test_demo_flow_e2e.py` 因 Copilot 无 API key 降级文案变化失败，必须确认是预期降级还是 bug，并在运行日志说明；不要静默跳过。

## 15. 质量门

后端契约：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_incident_report_export.py -q --tb=short
```

后端全量：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

Guardrails：

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

如修改依赖，还要：

```powershell
cd web-next
npm ls next next-auth react react-dom
```

## 16. 安全审查

运行日志必须逐项记录：

- 未登录访问 `/dashboard` 仍不能看到 Dashboard 数据。
- 登录后 `/dashboard` 不再依赖客户端 `useSession()` loading 放行。
- session cookie 仍由 NextAuth 管理。
- 没有使用 `localStorage` / `sessionStorage` 保存 token。
- 没有把后端 access token 写入 DOM。
- 没有把密码、token、secret 打印进 console / run log。
- `AUTH_SECRET` 缺失仍 fail fast，不 silent fallback。
- `.env` / `.env.local` / `web-next/.env` / `web-next/.env.local` 未 stage。
- `server/security/**` 未修改。
- M3-08 报告 E2E 的 forbidden sentinel 仍覆盖页面 DOM 和下载报告。

## 17. 文档收口

必须更新：

- `docs/runs/2026-06-19-next-01-auth-session-loading-e2e-recovery.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`

如果真实修复并跑通 E2E，更新：

- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

需要同步修正 M3-08 run log 的状态一致性：

- 当前 `git log` 显示 `77f7ba8 docs(incidents): 更新 M3-08 run log push 状态为成功` 已在 `origin/main`。
- 如果 `docs/runs/2026-06-18-m3-08-incident-report-browser-e2e-and-agent-docs-catchup.md` 仍残留“push 阻塞”为最终状态，允许本任务文档 commit 中补一段“历史阻塞，后续已成功 push”说明。
- 不要删除历史失败记录；只要最终状态不互相矛盾。

## 18. 提交策略

通过质量门后精确 commit。

推荐 commit 1：

```text
test(e2e): 复现 dashboard 会话 loading 阻塞
```

包含：

- `server/tests/test_auth_session_e2e.py`

推荐 commit 2：

```text
fix(auth): 使用服务端 session 放行 dashboard
```

包含实际修复文件，例如：

- `web-next/app/dashboard/page.tsx`
- `web-next/app/providers.tsx`
- `web-next/app/layout.tsx`
- `web-next/lib/auth.ts`
- 如升级依赖，包含 `web-next/package.json` / `web-next/package-lock.json`

推荐 commit 3：

```text
docs(auth): 记录 next-auth 会话阻塞收口
```

包含：

- run log
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

如果只需路线 A 且 diff 很小，可以合并为 2 个 commit，但必须保证测试和修复可审查。

精确 stage 示例：

```powershell
git add server\tests\test_auth_session_e2e.py
git commit -m "test(e2e): 复现 dashboard 会话 loading 阻塞"

git add web-next\app\dashboard\page.tsx web-next\app\providers.tsx web-next\app\layout.tsx web-next\lib\auth.ts
git commit -m "fix(auth): 使用服务端 session 放行 dashboard"

git add docs\runs\2026-06-19-next-01-auth-session-loading-e2e-recovery.md docs\agent\UNATTENDED_LONG_TASKS.md PRODUCT.md docs\plans\M2_PRODUCT_ROADMAP.md
git commit -m "docs(auth): 记录 next-auth 会话阻塞收口"
```

不要 stage 示例里未实际修改的文件。

## 19. Push 策略

提交前：

```powershell
git status --short --branch
git diff --cached --stat
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

## 20. 停止条件

任一条件满足必须停止：

- RED 无法复现且 M3-08 E2E 仍失败，原因不明。
- 服务端 `auth()` 路线、Provider 初始 session 路线、配置路线各尝试后仍同一失败超过 3 轮。
- 需要改后端 auth API、数据库 schema、Guardrails，但本任务未授权。
- 需要真实生产 secret 或外部账号。
- 依赖升级引入大量 breaking change。
- `npm run build` 或 `pytest server/tests` 出现大面积无关失败。
- 需要把 token 放到浏览器 storage 才能跑通。

停止时必须给出：

- 已完成内容。
- 未完成内容。
- 阻塞证据。
- 下一条最小工单。

## 21. 最终报告格式

完成后中文输出：

```text
完成状态：完成 / 部分完成 / 阻塞

根因：
- ...

改动文件：
- ...

验证命令：
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
- docs/runs/2026-06-19-next-01-auth-session-loading-e2e-recovery.md

剩余本地噪声：
- .coverage（如仍存在，说明未提交）
```

不要只说“好了”。必须给出真实 E2E 是否通过。

