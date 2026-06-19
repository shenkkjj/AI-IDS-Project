# M3-09 案件状态单一事实源 + E2E 注册韧性 收口运行日志

> 任务文档：`docs/agent/M3_09_INCIDENT_STATE_AND_E2E_RESILIENCE_TASK.md`

## 0. 启动状态（2026-06-19）

- 当前分支：`main`（与 `origin/main` 对齐）。
- `git status --short --branch`：

  ```text
  ## main...origin/main
   M .coverage
   M docs/agent/UNATTENDED_LONG_TASKS.md
  ?? docs/agent/M3_09_INCIDENT_STATE_AND_E2E_RESILIENCE_TASK.md
  ```

- `git log --oneline --decorate -15` 顶部 5 条：

  ```text
  8142fa8 (HEAD -> main, origin/main) docs(quality): 记录 E2E 与 SSRF 质量门收口
  ecca22b test(security): 固化 SSRF 测试 DNS 隔离
  371b772 test(e2e): 稳定 demo flow 浏览器登录路径
  b282856 docs(auth): 记录 next-auth 会话阻塞收口
  efaa348 fix(auth): 使用服务端 session 放行 dashboard
  ```

- `.coverage`：本地仍有 modify（不会被 stage，commit 时严格忽略）。
- `dashboard-client.tsx`：`const incidentsCtx = useIncidents()` 位于 `useThreatConfirm(...)` 之后（line 142）。
  - 同时 `<IncidentSection />` 没有把 `incidentsCtx` 传下去（line 468）。
- `IncidentSection.tsx`：`const incidents = useIncidents()`（line 39），即 **第二个 `useIncidents()` 实例**，与父层完全隔离。
- `test_incident_report_e2e.py`：仍包含 `incident-list-item` 兼容点击（line 410-420），代码注释明确写到“NEXT-01 IncidentSection 自己持有 useIncidents hook，与 dashboard-client 的实例隔离”。
- 三条 E2E 都各自复制了 `_register_unique_user` / `_register_via_ui|_register_and_login` / `_skip_without_playwright` / `_assert_dev_server_reachable` / `_collect_visible_text` / `_contains_forbidden`。
- `server/core/config.py`：

  ```text
  REGISTER_RATE_LIMIT_WINDOW = 3600
  REGISTER_RATE_LIMIT_MAX = 5
  ```

  默认值不变，本任务严禁修改。

## 1. 改造目标 vs 必读上下文要点

- 双 `useIncidents()` race：父层创建案件后 `IncidentSection` 内部 hook 不知道 selectedIncident 已经存在，必须靠点击列表兜底（M3-08 / NEXT-01 旧 workaround）。
- 三条 E2E 共用同一份 register helper，运行多次会撞 `REGISTER_RATE_LIMIT_MAX=5/hour`，需要重启 dev server。
- 红线：不放宽生产 register 限流；不改 cookie/token/auth 语义；不改 Guardrails / SSRF / DB schema；token 不进 storage / DOM。

## 2. 计划阶段

1. **RED A**：修改 `test_incident_report_e2e.py`，把列表点击改成纯等待 `incident-detail-panel` + 强制断言列表项 `data-incident-id`。当前实现下应失败。
2. **GREEN A**：导出 `IncidentsController` 类型；`IncidentSection` 改成接收 `incidents` controller props；`dashboard-client.tsx` 把 `incidentsCtx` 注入。
3. **GREEN A 验收**：跑 incident report E2E，期望直接看到 detail-panel，不再点击列表项。
4. **RED B**：新建 `server/tests/test_e2e_helpers.py`，对 `classify_register_response` 写纯函数单测；运行期望 ImportError → fail。
5. **GREEN B**：新建 `server/tests/e2e_helpers.py`，统一 register/login/dashboard URL helper。运行单测期望 pass。
6. **替换三条 E2E**：删除三处重复 helper，改成 import 共用 helper。验证三条 E2E 单跑、连续跑都通过且不依赖列表点击。
7. **质量门**：helper 单测 → 三条 E2E 单跑 → 三条 E2E 连续跑 → 后端全量 → Guardrails → 前端 typecheck/build。
8. **文档收口**：本 run log + UNATTENDED_LONG_TASKS + PRODUCT + Roadmap。
9. **commit & push**：四个精确 commit；`origin/main`；不放 `.coverage`。

执行进度将在下方按时间戳追加。

## 3. 执行进度

### 3.1 RED A：incident report E2E 删除列表点击规避（待运行）

修改 `server/tests/test_incident_report_e2e.py`：

- 移除“先等 incident-list-item，再点第一个”的 try/except 兼容段。
- 创建后直接 `wait_for_selector('[data-testid="incident-detail-panel"]')`，timeout 30s。
- 增加“列表项必须自动选中且包含 `data-incident-id`”的强制断言。

预期当前 main 实现下：列表点击被去掉后，`IncidentSection` 内部 hook 仍是空状态，detail-panel 永不出现 → RED。

### 3.2 GREEN A：useIncidents 提升到父层

- `web-next/hooks/useIncidents.ts`：导出 `IncidentsController` 类型。
- `web-next/components/dashboard/IncidentSection.tsx`：从内部 hook 改成接收 `incidents: IncidentsController` props，保留 `initialIncidentId` / `renderCreateShortcut`。
- `web-next/app/dashboard/dashboard-client.tsx`：`<IncidentSection incidents={incidentsCtx} />`。

`createIncidentFromAlert` 已在父层走，乐观更新 + `setSelectedIncident` 立刻把列表与详情面板绑定到同一份 state；`loadIncidentDetail` 触发 ready 状态。

### 3.3 GREEN B：e2e_helpers + 替换三条 E2E

- 新增 `server/tests/e2e_helpers.py`：`classify_register_response` / `unique_e2e_user` / `stable_e2e_user` / `ensure_registered_or_rate_limited` / `login_with_nextauth_callback` / `ensure_dashboard_url` / `register_or_login_for_e2e` / `skip_without_playwright`。
- 新增 `server/tests/test_e2e_helpers.py`：纯函数单测覆盖 `classify_register_response` 三种状态。
- `test_auth_session_e2e.py` / `test_demo_flow_e2e.py` / `test_incident_report_e2e.py`：删除本地重复 helper，改 import 共用 helper。

### 3.4 质量门验证

- helper 单测 → 三条 E2E 单跑 → 三条 E2E 连续跑 → 后端全量 → Guardrails → 前端 typecheck/build。

（具体命令输出在执行后填入。）

## 4. 安全审查

- `server/services/auth_service.py` / `server/core/state.py` / `server/core/config.py` 未改。
- `REGISTER_RATE_LIMIT_MAX` / `REGISTER_RATE_LIMIT_WINDOW` 保持默认 `5 / 3600`。
- helper 仅使用 `page.request.post /api/backend/auth/register` + NextAuth `/api/auth/callback/credentials` 种 httpOnly cookie。
- 不写 `localStorage` / `sessionStorage` / DOM。
- 429 时 helper 仅 fallback 到稳定测试账号路径；无法绕过时直接 `pytest.fail`，提示等待限流窗口或重启本地 dev backend。

## 5. 提交策略

- commit 1 `test(e2e): 复现案件详情自动选中链路`：`server/tests/test_incident_report_e2e.py`。
- commit 2 `fix(dashboard): 统一案件工作台状态源`：`web-next/app/dashboard/dashboard-client.tsx` + `web-next/components/dashboard/IncidentSection.tsx` + `web-next/hooks/useIncidents.ts`。
- commit 3 `test(e2e): 复用浏览器登录辅助工具`：`server/tests/e2e_helpers.py` + `server/tests/test_e2e_helpers.py` + 三条 E2E 替换。
- commit 4 `docs(incidents): 记录案件状态与 E2E 韧性收口`：本 run log + `docs/agent/UNATTENDED_LONG_TASKS.md` + `PRODUCT.md` + `docs/plans/M2_PRODUCT_ROADMAP.md`。

## 6. 风险与停止条件

- 同一 E2E 失败 ≥ 3 轮立即停止，记录证据并写下一条最小工单。
- 若需要改后端 auth / Guardrails / SSRF / DB schema 才能跑通 → 停止。
- 若 `IncidentSection` 状态提升导致大面积 dashboard 重构 → 停止。
- Playwright / dev server 不可用且无法本地修复 → 停止并提供下一条最小工单。

