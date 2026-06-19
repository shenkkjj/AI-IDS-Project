# Run: M3-11 Dashboard section 响应式 QA 与可访问性收口

开始时间：2026-06-19
运行模式：L5
预算：单段 30-60 分钟，连续 3 轮失败必停

## 启动状态

```text
git status --short --branch
## main...origin/main
 M .coverage
 M docs/agent/UNATTENDED_LONG_TASKS.md
?? docs/agent/M3_11_DASHBOARD_SECTION_RESPONSIVE_QA_TASK.md
```

```text
git log --oneline --decorate -12
9e154de docs(dashboard): 记录 route composition 收口
4759691 refactor(dashboard): 拆分 route section 组合
d46b4fe test(e2e): 覆盖 dashboard 路由区块回归
7076ecb docs(incidents): 记录案件状态与 E2E 韧性收口
54c771c test(e2e): 复用浏览器登录辅助工具
061b098 fix(dashboard): 统一案件工作台状态源
de95177 test(e2e): 复现案件详情自动选中链路并复用登录助手
8142fa8 docs(quality): 记录 E2E 与 SSRF 质量门收口
ecca22b test(security): 固化 SSRF 测试 DNS 隔离
371b772 test(e2e): 稳定 demo flow 浏览器登录路径
b282856 docs(auth): 记录 next-auth 会话阻塞收口
efaa348 fix(auth): 使用服务端 session 放行 dashboard
```

M3-10 已交付：route composition + dashboard route E2E。
启动时 `web-next/app/dashboard/dashboard-client.tsx` 行数：406。

## 目标

- 在桌面/移动真实浏览器中验证 Dashboard route section 的布局、导航、文字溢出、aria 状态、键盘可达性、forbidden sentinel。
- 通过 RED → GREEN → IMPROVE TDD 节奏交付响应式 E2E。
- 必要的轻量 UI/可访问性修复，不重做视觉设计。

## 范围

允许修改：
- `server/tests/test_dashboard_responsive_e2e.py`（新增）
- `web-next/components/dashboard/**`
- `web-next/app/dashboard/dashboard-client.tsx`（如需）
- `docs/runs/2026-06-19-m3-11-dashboard-section-responsive-qa.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

禁止修改：
- 后端 auth / Guardrails / SSRF / DB schema / API contract
- npm 依赖
- `.env` / `.coverage` / 数据库 / 密钥

## 计划

- [ ] Task 1 RED：新增 `test_dashboard_responsive_e2e.py` 并跑出失败
- [ ] Task 2 GREEN：轻量 UI 修复
- [ ] Task 3 GREEN：响应式 E2E + 五条关键 E2E 连续通过
- [ ] Task 4：后端全量 / Guardrails / 前端 typecheck / build
- [ ] Task 5 IMPROVE：de-sloppify + 安全审查
- [ ] Task 6：文档同步
- [ ] 精确 commit + push

## 阶段记录

### 阶段 0 - 启动

dev server：后端 :8000 健康检查 200，前端 :3000 可访问；Playwright 已安装。

启动时 Next.js dev server 出现 stale chunk 缓存（`Cannot find module './745.js'` / `'./vendor-chunks/@auth.js'`），手动 kill PID 8932 + `rm -rf web-next/.next` + 重启 `npm run dev`，约 10s 后 `/api/backend/health` 与 `/api/auth/csrf` 重新返回 200。

### 阶段 1 - RED：新增响应式 E2E

新增 `server/tests/test_dashboard_responsive_e2e.py`（覆盖桌面/移动 viewport、6 个 route、aria-current、整页/按钮溢出、icon-only 命名、键盘 Enter、forbidden sentinel、截图证据）。

```text
APP_SECRET=... AUTH_SECRET=... pytest server/tests/test_dashboard_responsive_e2e.py --run-e2e -q --tb=short -s
2 failed in 16.16s
```

RED 原因（正确，是 UI 缺口而非环境问题）：
1. `SystemStatusBar.tsx` L107 主题切换按钮 (`Moon` / `Sun`) 缺 `title` / `aria-label`。
2. `CopilotPanel.tsx` L109 Copilot 提交按钮 (`Send` icon) 缺 `title` / `aria-label`。

### 阶段 2 - GREEN：轻量可访问性修复

仅修改两个文件、共 6 行 +0 行 - 改动：

- `web-next/components/dashboard/SystemStatusBar.tsx`：
  - 主题切换按钮加 `title={theme === "light" ? "切换为深色主题" : "切换为浅色主题"}` + 同等 `aria-label`。
  - 已有 `title` 的 Bell（启用桌面通知）、LogOut（退出登录）按钮顺手补 `aria-label`。
- `web-next/components/dashboard/CopilotPanel.tsx`：
  - Send 提交按钮加 `title="发送给 Copilot"` + `aria-label="发送给 Copilot"`。

未改 hook、state、prompt、props、route、CSS 视觉。

```text
APP_SECRET=... AUTH_SECRET=... pytest server/tests/test_dashboard_responsive_e2e.py --run-e2e -q --tb=short -s
2 passed in 17.40s
```

诊断 (desktop)：
```
{'viewport': 'desktop', 'registered': True,
 'routes': ['overview', 'monitor', 'incidents', 'waf', 'ai', 'report'],
 'screenshots': ['docs\\runs\\artifacts\\m3-11-dashboard-responsive\\desktop-overview.png',
                 'docs\\runs\\artifacts\\m3-11-dashboard-responsive\\desktop-incidents.png'],
 'forbidden': None}
```

诊断 (mobile)：
```
{'viewport': 'mobile', 'registered': True,
 'routes': ['overview', 'monitor', 'incidents', 'waf', 'ai', 'report'],
 'screenshots': ['docs\\runs\\artifacts\\m3-11-dashboard-responsive\\mobile-overview.png',
                 'docs\\runs\\artifacts\\m3-11-dashboard-responsive\\mobile-incidents.png'],
 'forbidden': None}
```

### 阶段 3 - 五条关键 E2E 连续

第一次连续运行 `auth + demo + incident + route + responsive`：1 个 demo flow 失败（Copilot fallback 15s 超时）+ 5 passed。
第二次：4 failed（demo flow 仍失败 + register rate limit 耗尽，导致后续 3 个 e2e 拿不到账号）。
排障：kill 后端 PID 3764 → `uvicorn server.main:app --host 127.0.0.1 --port 8000` 重启清空 register rate limit。

第三次（fresh backend）：

```text
APP_SECRET=... AUTH_SECRET=... pytest server/tests/test_auth_session_e2e.py server/tests/test_demo_flow_e2e.py server/tests/test_incident_report_e2e.py server/tests/test_dashboard_route_sections_e2e.py server/tests/test_dashboard_responsive_e2e.py --run-e2e -q --tb=short -s
6 passed in 46.64s
```

- Auth: `session_user_email='e2e-auth-local-1781865863888@example.com'`, `dashboard_url=True`, `forbidden=None`。
- Demo: `registered/demo/copilot/triage` 全 True, `forbidden=None`。
- Incident report: `download=True`, `copy_status='已复制'`, `forbidden=None`, filename `incident-inc_b7ceee2906fb42a6-report.md`。
- Route: 6 routes, `forbidden=None`。
- Responsive desktop + mobile：6 routes, 4 截图保存, `forbidden=None`。

> 备注：Demo Flow Copilot fallback 在串跑场景下偶发 15s 超时（与 dev backend Copilot fake provider 冷启 + 注册限流压力相关），重启 backend 后稳定 6 passed。建议下一条 M3-12 候选工单中加固 Copilot fallback E2E 的串跑稳定性。

### 阶段 4 - 全量质量门

- `pytest server/tests` → **342 passed, 7 skipped, 17 warnings**（5 个 e2e + 2 既有 skip；0 失败）。
- `pytest server/tests/security/llm_guardrails` → **139 passed, 17 warnings**（0 回归）。
- `cd web-next && npm run typecheck` → 0 错误（`next typegen` 成功）。
- `cd web-next && npm run build` → 通过；`/dashboard` 44 kB / First Load JS 191 kB。

### 阶段 5 - IMPROVE：de-sloppify 与安全审查

```text
rg "console\.log|localStorage|sessionStorage|innerHTML|dangerouslySetInnerHTML|useIncidents\(|useAlerts\(" web-next/app/dashboard web-next/components/dashboard web-next/constants server/tests/test_dashboard_responsive_e2e.py
```

仅命中：
- `web-next/app/dashboard/dashboard-client.tsx:49 const alertsCtx = useAlerts();`
- `web-next/app/dashboard/dashboard-client.tsx:64 const incidentsCtx = useIncidents();`
- `web-next/components/dashboard/IncidentSection.tsx:13` 注释（M3-09 设计说明）

—— 与 M3-09 / M3-10 设计一致，父层独占业务 hook。无新增 console.log / storage / innerHTML / dangerouslySetInnerHTML。

截图大小 `du -ch artifacts/*.png`：168 KB << 5 MB；可随 commit 提交。

`git diff --stat` 改动范围：

- `server/tests/test_dashboard_responsive_e2e.py`（新增）
- `web-next/components/dashboard/SystemStatusBar.tsx`（4 行 +0 行 - aria-label / title 补齐）
- `web-next/components/dashboard/CopilotPanel.tsx`（2 行 +0 行 - aria-label / title 补齐）
- `docs/runs/2026-06-19-m3-11-dashboard-section-responsive-qa.md`（新增 run log）
- `docs/runs/artifacts/m3-11-dashboard-responsive/*.png`（4 张截图）
- `docs/agent/M3_11_DASHBOARD_SECTION_RESPONSIVE_QA_TASK.md`（任务文档入库）
- `docs/agent/UNATTENDED_LONG_TASKS.md`（M3-11 标记已交付，启动口令更新）
- `PRODUCT.md`（§2.2 新增第 20 项 M3-11 说明）
- `docs/plans/M2_PRODUCT_ROADMAP.md`（新增 M3-11 节）

无后端 / 认证 / Guardrails / DB / state.py / config.py / utils.py / analyzer.py / migration / npm 依赖改动；无 `.coverage` / 真实 env / 数据库 / 密钥。

### 阶段 6 - 安全边界自审

- 未改 `server/services/auth_service.py` / `server/core/auth*` / `server/routers/auth*`。
- 未改 `server/security/**`（Guardrails / SSRF / WAF）。
- 未改 `server/core/state.py` / `server/core/config.py` / `server/analyzer.py` / `server/core/utils.py`。
- 未改 Alembic migration / DB schema。
- 未新增 API endpoint / npm 依赖 / env var。
- E2E helper 仍使用 httpOnly cookie path（`register_or_login_for_e2e` + NextAuth callback）；未把 token 写进 `localStorage` / `sessionStorage` / DOM。
- UI 修复仅限 `title` / `aria-label` props，无 storage / dangerous HTML / innerHTML / console.log 引入。

## 验证证据

| 命令 | 结果 |
|------|------|
| `pytest server/tests/test_dashboard_responsive_e2e.py --run-e2e` | 2 passed in 17.40s |
| `pytest server/tests/test_dashboard_route_sections_e2e.py --run-e2e` | 1 passed |
| `pytest .../test_auth_session_e2e.py + demo + incident + route + responsive --run-e2e` | 6 passed in 46.64s（fresh backend） |
| `pytest server/tests` | 342 passed, 7 skipped, 17 warnings |
| `pytest server/tests/security/llm_guardrails` | 139 passed |
| `npm run typecheck`（web-next） | 0 错误 |
| `npm run build`（web-next） | 通过；/dashboard 44 kB / 191 kB |

截图证据：
- `docs/runs/artifacts/m3-11-dashboard-responsive/desktop-overview.png`（50 KB）
- `docs/runs/artifacts/m3-11-dashboard-responsive/desktop-incidents.png`（44 KB）
- `docs/runs/artifacts/m3-11-dashboard-responsive/mobile-overview.png`（37 KB）
- `docs/runs/artifacts/m3-11-dashboard-responsive/mobile-incidents.png`（34 KB）
- 总计 168 KB << 5 MB 限额。

## 未解决问题

- Demo Flow E2E (`test_demo_flow_e2e.py`) 在串跑场景下 Copilot fallback 偶发 15s 超时，重启 backend 后稳定。建议下一条 M3-12 候选工单加固。

## 最终状态

完成。
