# M3-16 Dashboard Operational Runbook / Health Checklist UX 运行日志

日期：2026-06-21
分支：`main`
起点：`86dbb7c docs(timeline): 记录 SOC 时间线 UX 收口`

## 任务边界

- 任务文档：`docs/agent/M3_16_DASHBOARD_OPERATIONAL_RUNBOOK_HEALTH_CHECKLIST_UX_TASK.md`
- 允许范围：Dashboard operational runbook / health checklist 前端 UX、真实浏览器 E2E、截图、文档同步。
- 禁止范围：认证/授权、Guardrails、SSRF、DB schema、后端 API、npm 依赖、rate limit。
- 浏览器侧禁止：不执行脚本读取真实 env，不使用 `localStorage` / `sessionStorage`，不使用 `dangerouslySetInnerHTML`。
- 提交禁止：`.coverage`、真实 env、数据库、密钥。

## 已读上下文

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/agent/M3_16_DASHBOARD_OPERATIONAL_RUNBOOK_HEALTH_CHECKLIST_UX_TASK.md`
- 近期运行日志：
  - `docs/runs/2026-06-20-m3-15-soc-timeline-drilldown-filter-ux.md`
  - `docs/runs/2026-06-19-m3-13-dashboard-mobile-visual-qa.md`
  - `docs/runs/2026-06-19-m3-11-dashboard-responsive-ux.md`
- 相邻实现：
  - `web-next/app/dashboard/dashboard-client.tsx`
  - `web-next/components/dashboard/sections/DashboardSystemStatusRouteSection.tsx`
  - `web-next/components/dashboard/SystemStatusSection.tsx`
  - `web-next/lib/dashboardRoutes.ts`
  - `web-next/types/site.ts`
  - `server/tests/e2e_helpers.py`
  - `server/tests/test_dashboard_route_sections_e2e.py`
  - `server/tests/test_dashboard_responsive_e2e.py`
  - `scripts/check_env_security.py`

## 当前工作区注意事项

启动时工作区已有非本任务脏文件：

- 已修改的旧截图：`docs/runs/artifacts/m3-11-*`、`m3-13-*`、`m3-14-*`
- 未跟踪旧日志/探针：`docs/runs/m3-13-*`、`docs/runs/m3-14-*`、`docs/runs/m3-15-*`
- 未跟踪任务文档：`docs/agent/M3_16_DASHBOARD_OPERATIONAL_RUNBOOK_HEALTH_CHECKLIST_UX_TASK.md`
- `.tmp/pytest/pytest-of-276291/` 当前存在权限提示。

提交阶段必须使用精确 pathspec，不使用 `git add .`，且不得纳入非 M3-16 旧截图/日志。

## 执行计划

1. 新增真实浏览器 E2E，先验证缺失 `operational-runbook-panel` 的 RED。
2. 实现最小 `OperationalRunbookPanel`，在 Dashboard 概览/WAF route 内渲染。
3. 跑新增 E2E 生成桌面/移动截图并检查 forbidden sentinel。
4. 跑任务要求的 Dashboard route/responsive、关键 E2E、后端全量、Guardrails、前端 typecheck/build。
5. 同步 `PRODUCT.md`、`docs/plans/M2_PRODUCT_ROADMAP.md`、`docs/agent/UNATTENDED_LONG_TASKS.md` 和本运行日志。
6. 精确拆分 3 个 commit 并 push 到 `origin/main`。

## 验证记录

### 阶段 1：新增 E2E 并确认 RED

- 新增 `server/tests/test_dashboard_operational_runbook_e2e.py`。
- 本地启动临时后端 `127.0.0.1:8120` 与前端 `127.0.0.1:3120`。
- RED 命令：
  - `.venv\Scripts\python.exe -m pytest server\tests\test_dashboard_operational_runbook_e2e.py --run-e2e -q --tb=short -s`
- RED 结果：
  - 真实浏览器登录成功。
  - 失败点：`operational-runbook-panel` 15s 内不可见。

### 阶段 2：最小 UX 实现

- 新增 `web-next/components/dashboard/OperationalRunbookPanel.tsx`。
- 修改 `DashboardSystemStatusRouteSection.tsx`，在系统状态区块下方挂载 runbook 面板。
- 修改 `dashboard-client.tsx`，只传递现有 `userEmail`。
- 面板行为：
  - 六项检查：backend health、Next API proxy、login session、demo readiness、E2E readiness、env security check。
  - 登录邮箱脱敏展示。
  - 五条命令只作为人工执行清单展示，不在浏览器执行。
  - 复制摘要使用 `navigator.clipboard.writeText`，失败时降级为 `复制失败`。
  - 不写 `localStorage` / `sessionStorage`，不使用 `dangerouslySetInnerHTML`。

### 阶段 3：新增 E2E GREEN 与截图

- 命令：
  - `.venv\Scripts\python.exe -m pytest server\tests\test_dashboard_operational_runbook_e2e.py --run-e2e -q --tb=short -s`
- 结果：
  - `1 passed in 3.67s`
  - `copy_status='已复制'`
  - `clipboard_checked=True`
  - `forbidden=None`
- 截图：
  - `docs/runs/artifacts/m3-16-dashboard-operational-runbook/operational-runbook-desktop.png`
  - `docs/runs/artifacts/m3-16-dashboard-operational-runbook/operational-runbook-mobile.png`

### 阶段 4：Dashboard 回归与关键 E2E

- Dashboard route + responsive：
  - `.venv\Scripts\python.exe -m pytest server\tests\test_dashboard_route_sections_e2e.py server\tests\test_dashboard_responsive_e2e.py --run-e2e -q --tb=short -s`
  - `3 passed in 25.42s`
- 关键 E2E 串跑：
  - `test_auth_session_e2e.py`
  - `test_demo_flow_e2e.py`
  - `test_incident_report_e2e.py`
  - `test_dashboard_route_sections_e2e.py`
  - `test_dashboard_responsive_e2e.py`
  - `test_demo_flow_stability_e2e.py`
  - `test_dashboard_mobile_visual_e2e.py`
  - `test_incident_report_preview_e2e.py`
  - `test_security_timeline_drilldown_e2e.py`
  - `test_dashboard_operational_runbook_e2e.py`
- 结果：
  - `11 passed in 80.00s`
- 说明：
  - 首轮完整关键 E2E 暴露现有 helper 每个测试优先注册唯一账号会耗尽本地 `REGISTER_RATE_LIMIT_MAX=5/hour`。
  - 本任务只修改 `server/tests/e2e_helpers.py` 的测试侧路径：显式提供 `E2E_<PREFIX>_EMAIL` 且稳定账号可登录时优先复用；不改后端 rate limit、认证 API 或生产代码。

### 阶段 5：后端、Guardrails、前端质量门

- 后端 timeline 专项：
  - `.venv\Scripts\python.exe -m pytest server\tests\test_security_timeline.py -q --tb=short`
  - `12 passed in 1.03s`
- 后端全量：
  - `.venv\Scripts\python.exe -m pytest server\tests -q --tb=short`
  - `344 passed, 12 skipped, 17 warnings in 85.19s`
- Guardrails：
  - `.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short`
  - `139 passed, 17 warnings in 19.51s`
- 前端：
  - `npm run typecheck`
  - `npm run build`
  - build 结果：`/dashboard` 49.2 kB / First Load JS 197 kB

### 阶段 6：文档同步

- 更新 `PRODUCT.md`：新增 M3-16 已交付状态。
- 更新 `docs/plans/M2_PRODUCT_ROADMAP.md`：新增 M3-16 已交付段落。
- 更新 `docs/agent/UNATTENDED_LONG_TASKS.md`：M3-16 改为已交付，并把推荐启动口令切到 M3-17。

## 安全与提交边界复核

- 未修改认证/授权、Guardrails、SSRF、DB schema、后端 API、npm 依赖或生产 rate limit。
- 未读取或提交真实 `.env`。
- 未提交 `.coverage`、数据库、密钥。
- 临时 dev server 日志 `docs/runs/m3-16-*.log` 不纳入提交。
- 启动前已有的旧截图/旧日志保持不纳入本任务提交。
