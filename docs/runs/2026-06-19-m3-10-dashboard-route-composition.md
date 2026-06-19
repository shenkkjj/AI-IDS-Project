# M3-10 Dashboard route composition 收口运行日志

> 任务文档：`docs/agent/M3_10_DASHBOARD_ROUTE_COMPOSITION_TASK.md`

开始时间：2026-06-19
运行模式：L5 超长任务
预算：同一失败最多修复 3 轮；禁止越界修改认证/授权/Guardrails/SSRF/DB schema。

## 目标

- 将 `dashboard-client.tsx` 从 route JSX 大文件收口为“父层持有 controller/hook + section 组件接收 props 渲染 UI + 单一路由元数据”。
- 修复顶部导航缺少 `incidents` 一等入口的问题。
- 新增 Dashboard route sections 浏览器 E2E，锁住所有核心 route tab 与核心 section wrapper。

## 启动状态

- `git status --short --branch`：

  ```text
  ## main...origin/main
   M .coverage
   M docs/agent/UNATTENDED_LONG_TASKS.md
  ?? docs/agent/M3_10_DASHBOARD_ROUTE_COMPOSITION_TASK.md
  ```

- `git log --oneline --decorate -12`：

  ```text
  7076ecb (HEAD -> main, origin/main) docs(incidents): 记录案件状态与 E2E 韧性收口
  54c771c test(e2e): 复用浏览器登录辅助工具
  061b098 fix(dashboard): 统一案件工作台状态源
  de95177 test(e2e): 复现案件详情自动选中链路并复用登录助手
  8142fa8 docs(quality): 记录 E2E 与 SSRF 质量门收口
  ecca22b test(security): 固化 SSRF 测试 DNS 隔离
  371b772 test(e2e): 稳定 demo flow 浏览器登录路径
  b282856 docs(auth): 记录 next-auth 会话阻塞收口
  efaa348 fix(auth): 使用服务端 session 放行 dashboard
  c120c40 test(e2e): 复现 dashboard 会话 loading 阻塞
  77f7ba8 docs(incidents): 更新 M3-08 run log push 状态为成功
  0e5cb74 docs(incidents): 记录案件报告浏览器验收
  ```

- `dashboard-client.tsx` 启动行数：840。
- 既有本地噪声：
  - `.coverage` modified，本任务禁止 stage / commit。
  - `docs/agent/UNATTENDED_LONG_TASKS.md` modified，后续只按本任务文档同步。
  - `docs/agent/M3_10_DASHBOARD_ROUTE_COMPOSITION_TASK.md` untracked，作为本任务输入文档读取；提交前按精确 staged set 审查。

## 范围

允许修改：

- `web-next/app/dashboard/dashboard-client.tsx`
- `web-next/components/dashboard/SystemStatusBar.tsx`
- `web-next/components/dashboard/SectionHeading.tsx`
- `web-next/components/dashboard/DashboardFields.tsx`
- `web-next/components/dashboard/DashboardRows.tsx`
- `web-next/components/dashboard/sections/*.tsx`
- `web-next/constants/dashboardRoutes.ts`
- `server/tests/test_dashboard_route_sections_e2e.py`
- 本运行日志
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

禁止修改：

- 认证/授权生产代码
- `server/security/**`
- SSRF 生产逻辑
- DB schema / migration
- 后端 API
- npm 依赖
- `.coverage` / env / 数据库 / 密钥

## 计划

- [x] RED：新增 Dashboard route sections E2E 并确认失败原因正确。
- [x] GREEN：新增单一路由元数据，修复 `SystemStatusBar` 桌面/移动导航入口。
- [x] GREEN：抽出 `SectionHeading`、表单/行原子组件和 route section 组件。
- [x] GREEN：`dashboard-client.tsx` 只保留 hook/controller、handler 和 route 组合。
- [x] 验证：新增 E2E、四条连续 E2E、后端全量、Guardrails、前端 typecheck/build。
- [x] IMPROVE：禁止模式搜索、diff 范围审查、前端安全自审。
- [x] 文档同步、精确 commit、push。

## 阶段记录

### 阶段 1：RED E2E

改动：

- 新增 `server/tests/test_dashboard_route_sections_e2e.py`。

验证：

- 待运行：

  ```powershell
  $env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
  $env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
  .venv\Scripts\python.exe -m pytest server\tests\test_dashboard_route_sections_e2e.py -q --tb=short --run-e2e -s
  ```

结果：

- 第 1 轮未到达目标 RED：失败在 E2E 登录前置，`register_or_login_for_e2e(page, "e2e-routes")` 命中本地 dev backend 的 `REGISTER_RATE_LIMIT`，且 `e2e-routes-stable@example.com` 尚不存在，helper 明确失败。该失败不是导航/section 实现缺口。
- 调整测试账号前缀为 M3-09 已验证过的 `e2e-auth` 稳定路径，仅用于绕开本机注册窗口，不改变 Dashboard route/section 断言。
- 第 2 轮到达目标 RED：

  ```text
  FAILED server/tests/test_dashboard_route_sections_e2e.py::test_dashboard_route_tabs_render_core_sections
  Timeout 15000ms exceeded waiting for [data-testid="dashboard-section-stats"]
  ```

  说明登录路径已通过，失败来自当前 Dashboard 缺少稳定 section wrapper test id，符合任务预期。

### 阶段 2：GREEN 路由元数据与 section 拆分

改动：

- 新增 `web-next/constants/dashboardRoutes.ts`，统一 `overview / monitor / incidents / waf / ai / report` 的 label / index / description。
- `SystemStatusBar.tsx` 删除本地 nav，改读 `DASHBOARD_NAV_ITEMS`，桌面和移动按钮补 `data-testid` / `data-dashboard-route` / `aria-current`。
- 新增 `SectionHeading` / `DashboardFields` / `DashboardRows`。
- 新增 `web-next/components/dashboard/sections/*.tsx` route section。
- `dashboard-client.tsx` 保留所有 hook/controller 与跨区块 handler，route JSX 平移到 section 组件。

验证：

- `npm run typecheck`（`web-next`）通过。
- `dashboard-client.tsx` 行数：840 -> 406。

## 验证证据

- 新增 Dashboard route sections E2E：

  ```powershell
  .venv\Scripts\python.exe -m pytest server\tests\test_dashboard_route_sections_e2e.py -q --tb=short --run-e2e -s
  ```

  结果：`1 passed in 9.36s`；诊断输出 `routes=['overview','monitor','incidents','waf','ai','report']`，`forbidden=None`。

- Auth / Demo / Incident / Dashboard 四条连续 E2E：

  ```powershell
  .venv\Scripts\python.exe -m pytest server\tests\test_auth_session_e2e.py server\tests\test_demo_flow_e2e.py server\tests\test_incident_report_e2e.py server\tests\test_dashboard_route_sections_e2e.py -q --tb=short --run-e2e -s
  ```

  结果：`4 passed in 32.46s`；Auth session user 为 `e2e-auth-stable@example.com`，Demo `registered/demo/copilot/triage` 全部 True，Incident report `copy_status='已复制'`，Dashboard route `forbidden=None`。

- 后端全量：

  ```powershell
  .venv\Scripts\python.exe -m pytest server\tests -q --tb=short
  ```

  结果：`342 passed, 5 skipped, 17 warnings in 47.77s`。

- Guardrails 专项：

  ```powershell
  .venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
  ```

  结果：`139 passed, 17 warnings in 20.09s`。

- 前端：

  ```powershell
  npm run typecheck
  npm run build
  ```

  结果：均通过；`/dashboard` 构建体积 `44 kB`，First Load JS `191 kB`。

- IMPROVE 搜索：

  ```powershell
  rg -n "TODO|FIXME|console\.log|localStorage|sessionStorage|useIncidents\(" web-next\app\dashboard web-next\components\dashboard web-next\constants server\tests\test_dashboard_route_sections_e2e.py
  ```

  结果：仅命中父层 `dashboard-client.tsx` 的 `useIncidents()` 调用和 `IncidentSection.tsx` 注释说明；未发现子组件重新创建业务 hook、storage token、调试输出或遗留 TODO。

## 安全边界自审

- 本任务不触碰后端 auth / 授权生产代码。
- 本任务不触碰 Guardrails / `server/security/**`。
- 本任务不触碰 SSRF 生产逻辑。
- 本任务不触碰 DB schema / migration。
- 本任务不新增后端 API / npm 依赖。
- E2E helper 仍走 httpOnly cookie path。
- 新 section 不读写 storage。
- 新 section 不拼接危险 HTML。
- 父层继续持有 `useAlerts` / `useConfig` / `useCopilot` / `useTerminal` / `useReport` / `useSiteHealth` / `useSecurityTimeline` / `useThreatConfirm` / `useIncidents`；section 组件只接收 props 渲染 UI。

## 未解决问题

- 无阻塞问题。
- `.coverage` 是测试产生的本地噪声，按任务边界未 stage / commit。

## 最终状态

- 完成。`dashboard-client.tsx` 从 840 行收口到 406 行；Dashboard 路由元数据统一到 `web-next/constants/dashboardRoutes.ts`；`incidents` 已恢复为桌面和移动顶部导航一等入口；route JSX 已拆到 `web-next/components/dashboard/sections/*.tsx`；新增 `server/tests/test_dashboard_route_sections_e2e.py` 锁定六个 route tab 与核心 section wrapper。
- 已按精确 staged set 提交并推送到 `origin/main`。
