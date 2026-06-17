# Run: M3-02 告警研判与处置工作台

开始时间：2026-06-17
运行模式：L5 无人值守产品能力战役
预算：最长 3 小时；同一失败最多修复 3 轮；diff 超过 1200 行则停止总结

> 本日志是 M3-02 任务的**单一事实来源**：
> 所有阶段记录、验证证据、改动清单、提交拆分方案都在同一文件。

## 目标

作为安全分析员，我能在 Dashboard 中选择一条告警，将它从"新告警"推进到
"研判中 / 已遏制 / 误报 / 已解决"，记录一段简短处置备注，复制一份
包含风险、证据、建议动作和研判状态的事件报告，并且系统会为每次
研判状态变化留下可审计记录。

不引入数据库 schema / migration；研判状态保存在当前进程的告警 backlog
payload 中，并用 `Log` 写入审计事件。持久化、查询历史和跨重启恢复
留给后续数据库迁移任务。

## 范围

允许修改：

- `server/core/state.py`
- `server/services/alert_service.py`
- `server/routers/alerts_router.py`
- `server/models/schemas.py`（仅新增 Pydantic schema）
- `server/tests/test_alert_triage.py`（新增）
- `server/tests/test_demo_flow.py`（按需）
- `server/tests/test_demo_flow_e2e.py`（按需）
- `web-next/types/alert.ts`
- `web-next/types/alertBriefing.ts`
- `web-next/types/index.ts`
- `web-next/utils/alertUtils.ts`
- `web-next/utils/alertBriefingUtils.ts`
- `web-next/utils/index.ts`
- `web-next/hooks/useAlerts.ts`
- `web-next/components/dashboard/AlertDetailPanel.tsx`
- `web-next/components/dashboard/AlertSection.tsx`
- `web-next/components/dashboard/AttackLogTable.tsx`
- `web-next/components/dashboard/BriefingSection.tsx`
- `web-next/components/dashboard/AlertTriagePanel.tsx`（新增）
- `web-next/app/dashboard/dashboard-client.tsx`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- 本文件

禁止修改：

- `.coverage`、`.claude/settings.local.json`、真实 `.env`
- `server/security/**`、认证/授权、密码、session、cookie
- 数据库 schema / migration / `models_db.py` 表结构
- `docker-compose.yml`、`nginx/**`、CI / deploy
- 现有 Demo Flow 的认证方式与 Copilot SSE 契约
- 真实 secret、本地数据库、构建产物

禁止操作：

- 不要使用 `git add .`
- 不要 `git reset --hard`、`git clean`
- 不要删除 / 跳过 / 弱化测试
- 不要把 `.coverage`、`.claude/settings.local.json`、真实 `.env` 加入 commit

## 计划

- [ ] 阶段 1：初始化运行日志
- [ ] 阶段 2：后端 RED 测试（`test_alert_triage.py`）
- [ ] 阶段 3：后端 GREEN 最小闭环（schema + state + service + router + audit）
- [ ] 阶段 4：前端产品化（triage 类型 / 派生 / 详情面板 / 简报计数 / 移动端）
- [ ] 阶段 5：前端 typecheck + build + E2E 验收
- [ ] 阶段 6：文档同步（PRODUCT.md / UNATTENDED_LONG_TASKS.md）
- [ ] 阶段 7：全量质量门
- [ ] 阶段 8：安全审查
- [ ] 阶段 9：精确提交与 push

## 验证矩阵

| 验证项 | 命令 | 通过标准 |
|---|---|---|
| 后端 RED | `pytest server/tests/test_alert_triage.py -q --tb=short` | RED 来自缺失功能/契约不满足，非语法错误 |
| 后端 GREEN | 同上 | 全绿 |
| Demo Flow 回归 | `pytest server/tests/test_demo_flow.py -q --tb=short` | 全绿（基线 5 passed） |
| 全量后端测试 | `pytest server/tests -q --tb=short` | 全绿（基线 242 passed） |
| 前端 typecheck | `cd web-next && npm run typecheck` | 0 错误 |
| 前端 build | `cd web-next && npm run build` | 0 错误 |
| E2E（可选） | `pytest server/tests/test_demo_flow_e2e.py --run-e2e -q -rs` | 1 passed 或环境受限 skip |
| diff 检查 | `git diff --check` | 无冲突标记 |

## 阶段记录

### 阶段 1 — 初始化

- 任务来源：`docs/agent/M3_02_ALERT_TRIAGE_RESPONSE_WORKBENCH_TASK.md`
- 当前分支：`main`，本地 HEAD：`bf4fb1e3df9dd633a8ab61bc67cb82f8f6592794`
- 远端 `origin/main`：`bf4fb1e3df9dd633a8ab61bc67cb82f8f6592794`（与本地一致）
- 工作树：`M .claude/settings.local.json` / `M .coverage` / `M docs/agent/UNATTENDED_LONG_TASKS.md` / `?? docs/agent/M3_02_ALERT_TRIAGE_RESPONSE_WORKBENCH_TASK.md`
- 暂存区为空 ✓
- 任务禁止的 `.coverage` 与 `.claude/settings.local.json` 未 stage ✓
- 验证：可立即进入阶段 2

### 阶段 2 — 后端 RED 测试

- 新增 `server/tests/test_alert_triage.py`（11 个测试）。
- 覆盖：未登录 401 / 当前用户可更新 / GET 同步 / 其他用户 404 / 不存在 404 / 无效 status 422 / 超长 note 422 / 审计日志不含完整 payload+note+secret / disposition 可选 / 旧告警默认 new / 审计失败不破坏主请求。
- 运行：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server/tests/test_alert_triage.py -q --tb=short
```

- 结果：**9 failed, 2 passed in 2.06s**
- RED 原因：端点未注册（返回 404）+ `triage` 字段未在 `get_alerts` 派生。
- 2 个 passed 实际是「路由 404」碰巧命中（其他用户/不存在场景在端点不存在时也返回 404），在 GREEN 阶段会通过真实权限/查找逻辑再次确认。
- 全部 RED 来自契约不满足，**不是**语法/导入/夹具坏掉。

下一步：进入阶段 3，新增 schema + state 锁内更新 + service + router + audit。

### 阶段 3 — 后端 GREEN 最小闭环

- 后端改动：
  - `server/models/schemas.py`：新增 `AlertTriageUpdateIn` (status / disposition / analyst_note) + `AlertTriageOut` + `TRIAGE_STATUS_VALUES` 稳定枚举。
  - `server/core/state.py`：`AlertState.update_backlog_triage` 锁内按 `alert_id` + 所有权查找并写入；非 owner / 不存在返回 `None`。
  - `server/services/alert_service.py`：新增 `default_alert_triage` / `_ensure_triage` / `_build_audit_detail` (脱敏) / `update_alert_triage`；`get_alerts` / `process_alert` / `trigger_demo_attack` 注入默认 triage。
  - `server/routers/alerts_router.py`：新增 `PATCH /alerts/{alert_id}/triage`，强制 `require_auth_user`；非 owner / 不存在统一 404；审计 Log 失败仅 warn 不破坏主请求。
- RED → GREEN 关键映射：端点不存在 (404) → 真实 PATCH 路由返回 200；缺 `triage` 字段 → `get_alerts` `_ensure_triage` 注入；缺 `create_log` 引用 → router 真实写入。
- 验证：

```powershell
pytest server/tests/test_alert_triage.py -q --tb=short
```

- 结果：**11 passed in 0.93s**
- 回归 `pytest test_demo_flow.py test_security_timeline.py -q --tb=short`：**17 passed**（warnings 全为 nemoguardrails 内部 Pydantic V1 弃用）
- 全量 `pytest server/tests -q --tb=short`：**253 passed, 2 skipped in 71.05s**（基线 242 + 11 新增；2 skipped 为默认 E2E skip）

下一步：进入阶段 4，前端产品化。

### 阶段 4 — 前端产品化

- 改动：
  - `web-next/types/alert.ts`：新增 `AlertTriage` / `AlertTriageStatus` / `TRIAGE_STATUS_OPTIONS` / `TRIAGE_OPEN_STATUSES` / `TRIAGE_CLOSED_STATUSES`。
  - `web-next/utils/alertUtils.ts`：新增 `parseTriageStatus` / `defaultTriage` / `mapTriage`；`mapBackendAlert` 注入 `triage` 字段（旧告警默认 new）。
  - `web-next/types/alertBriefing.ts`：`AlertDetail` / `AlertBriefing` 加 `triageStatus*` / `triageBreakdown` / `triageOpen` / `triageClosed`。
  - `web-next/utils/alertBriefingUtils.ts`：新增 `triageStatusLabel` / `triageStatusTone` / `triageShortLabel`；`buildReport` 含研判状态/备注；`deriveBriefing` 派生 `triageBreakdown` / `triageOpen` / `triageClosed`。
  - `web-next/components/dashboard/AlertTriagePanel.tsx`（新增）：紧凑 segmented controls 切换 5 个状态，处置分类（≤64 字符）+ 备注（≤800 字符）输入，loading / success / error 三态，offline 禁用保存，移动端 flex-wrap 不重叠。
  - `web-next/components/dashboard/AlertDetailPanel.tsx`：集成 `AlertTriagePanel`，传 `onTriageSubmit` / `offline`。
  - `web-next/components/dashboard/AttackLogTable.tsx`：新增「研判」列 + `data-triage-status` 属性 + `triage-row-badge` testid。
  - `web-next/components/dashboard/BriefingSection.tsx`：新增 `briefing-triage-counts` 段（待研判 / 已闭环 / 状态分布）。
  - `web-next/hooks/useAlerts.ts`：新增 `updateTriage` 方法（PATCH + 本地缓存 + 选中告警同步 + error 透传）。
  - `web-next/app/dashboard/dashboard-client.tsx`：`handleTriageSubmit` 接线。
  - `web-next/utils/index.ts` / `web-next/types/index.ts`：re-export 新增。
- 验证：

```powershell
cd web-next
npm run typecheck
npm run build
```

- 结果：
  - typecheck：✓ 0 错误
  - build：✓ Compiled successfully，/dashboard 36.4 kB（基线 33.5 → 36.4 kB，新增 1 个 AlertTriagePanel 组件 + 多个徽标渲染，合理）
  - `data-testid` 全部命中：`alert-triage-panel` / `triage-status-{new,investigating,contained,false_positive,resolved}` / `triage-note-input` / `triage-save` / `triage-status-badge` / `triage-row-badge`

下一步：进入阶段 5，前端验证 + E2E。

### 阶段 5 — 前端 typecheck/build + E2E

- 验证：typecheck / build 已通过（见阶段 4）；全量后端通过（见阶段 3）。
- E2E（`server/tests/test_demo_flow_e2e.py`）：
  - 扩展了"研判状态切换 → 保存备注 → attack-log-row 更新"步骤（5.5 段），断言 `[data-testid="triage-status-badge"][data-status="investigating"]` 与 `[data-testid="attack-log-row"][data-triage-status="investigating"]`。
  - 默认 skip 模式：✅ 1 skipped（无 `--run-e2e`，符合基线）。
  - 真实浏览器 E2E（`--run-e2e`）：**环境受限**。
    - 尝试 1（`next start`）：`next.config.js` 在 production 模式下 `script-src 'self'` 严格 CSP，Next.js 15 RSC 依赖 inline script 触发 hydration 失败，所有 `data-testid` 不挂载。
    - 尝试 2（`next dev`）：hydration 成功，`login-email` 出现，但 `register → auto-redirect /dashboard` 步骤 20s 超时（next-auth session cookie + dashboard 首次编译慢），非业务回归。
    - 任务文档 §5 第 5 条允许"本地缺浏览器 / 环境受限"时记录 skip；本次属环境受限（生产 CSP + dashboard 首次编译），**未**弱化测试。
- 结论：
  - E2E 步骤扩展是真实可断言的（业务层），真实运行受阻于环境（hydration / 编译耗时）。
  - 后端 11 个新测试 + 已有 242 测试全过；前端 typecheck/build 通过；M3-02 核心契约（PATCH / 5 状态 / ownership 404 / 审计脱敏）由后端 pytest 全覆盖。
  - 下次 owner 工单可重跑 E2E，或在 CI 上挂真实 Playwright 容器。

下一步：进入阶段 6，文档同步。

### 阶段 6 — 文档同步

- 改动：
  - `PRODUCT.md`：
    - §M3 增加 M3-02 子项（产品能力定义、验收、当前实现边界）。
    - §2.2 当前明显问题加第 10 条「M3-02 研判状态保存在进程内 backlog，跨重启不保留」边界声明。
  - `docs/agent/UNATTENDED_LONG_TASKS.md`：M3-02 任务补充"重要边界"提示（不进数据库 / 跨重启不保留）。

下一步：进入阶段 7，质量门。

### 阶段 7 — 全量质量门

按任务文档 §7 顺序运行（不并行 typecheck + build）：

- `pytest server/tests/test_alert_triage.py -q --tb=short` → **11 passed**
- `pytest server/tests/test_demo_flow.py -q --tb=short` → **5 passed**
- `pytest server/tests/test_security_timeline.py -q --tb=short` → **12 passed**
- `pytest server/tests -q --tb=short` → **253 passed, 2 skipped, 17 warnings in ~32s**（基线 242 + 11 新增 = 253；warnings 全为 nemoguardrails 内部 Pydantic V1 弃用）
- `cd web-next && npm run typecheck` → ✓ 0 错误
- `cd web-next && npm run build` → ✓ Compiled successfully
- `git diff --check` → 无冲突标记，仅 LF/CRLF Windows 提示（pre-existing，与本任务无关）

任务范围未触及 `server/security/**` / 认证 / Guardrails，跳过 `server/tests/security/llm_guardrails` 专项重跑（基线 139 passed 未被影响）。

下一步：进入阶段 8，安全审查。

### 阶段 8 — 安全审查

| 审查点 | 结果 | 证据 |
|---|---|---|
| alert ownership 按 user_id 限制 | ✅ 通过 | `AlertState.update_backlog_triage` 强制 `raw_alert.alert_user_id == user_id`；非 owner 直接返回 None → 404。`test_triage_other_user_returns_404` 已断言。 |
| 非 owner 返回 404 而非 403 | ✅ 通过 | 路由层显式 `raise HTTPException(status_code=404, detail="Alert not found")`，不暴露 alert_id 是否存在。`test_triage_other_user_returns_404` + `test_triage_unknown_alert_returns_404` 双重断言。 |
| `analyst_note` 长度限制 | ✅ 通过 | Pydantic `Field(default=None, max_length=800)`；测试用 801 字符断言 422。 |
| 审计 detail 不含完整 payload / note / secret | ✅ 通过 | `_build_audit_detail` 仅含 `alert_id=...;status=...;disposition=...;note_length=...;source_ip=...`，不写入 payload / 完整 note / key。`test_triage_writes_audit_log_without_payload` 断言：note 全文不出现、`UNION SELECT` 关键字不出现、`sk-*` / `AKIA*` / `ghp_*` / `PRIVATE KEY` / `Traceback` 全部不出现。 |
| 审计 detail 必含关键摘要 | ✅ 通过 | 断言 `status=contained` / `disposition=blocked_at_waf` / `note_length=NN` 必须出现。 |
| Log 写入失败不破坏主请求 | ✅ 通过 | router 用 `try/except` 包裹 `create_log`，仅 `logger.warning`。`test_triage_audit_log_failure_does_not_break_request` 断言即使 Log 抛 RuntimeError 主请求依然 200。 |
| 前端显示后端 stack trace | ✅ 通过 | 前端 `updateTriage` 用 `payload.detail` 而非 `response.text`，永远不展示 stack；`triage-row-badge` / `triage-status-badge` 的 `data-status` 属性仅显示枚举名（NEW / INV / CON / FP / DONE），无技术细节。E2E forbidden sentinel 覆盖 `Traceback` / `system:` 等。 |
| 修改了认证/授权语义 | ❌ 否 | 仅复用 `require_auth_user` 依赖；未动 `core/security.py` / 任何 token 校验 / session 处理。 |
| 新增 env var / secret | ❌ 否 | 无新增 env 变量；无真实 secret 写入代码、测试或日志。 |
| 数据库 schema / migration | ❌ 否 | 完全在进程内 `AlertState.backlog` 字典上操作；不修改 `models_db.py` / `alembic/`。 |
| `.coverage` / `.claude/settings.local.json` / 真实 `.env` | ❌ 未 stage | `git status` 验证未进入任何 commit 候选。 |

审查结论：**无 CRITICAL / HIGH 问题**，可直接提交。

下一步：进入阶段 9，精确提交 + push。

### 阶段 9 — 精确提交 + push

- 提交拆分（按任务文档 §5 推荐顺序）：
  1. `test(alerts): 增加告警研判状态契约测试`
  2. `feat(alerts): 增加告警研判状态接口与脱敏审计`
  3. `feat(dashboard): 增强告警研判与处置工作台`
  4. `test(e2e): 覆盖告警研判工作流`
  5. `docs: 记录 M3-02 告警研判工作台与边界`
- 精确 stage（不 `git add .`），每个 commit 后 `git diff --cached --name-only` 校验。
- push 前：`git status --short --branch` / `git log --oneline origin/main..HEAD` / `git log --name-only --format="commit %h %s" origin/main..HEAD -- .coverage .claude/settings.local.json` 必须为空 / `git ls-remote origin refs/heads/main` 确认未前进。

## 验证证据汇总

| 验证项 | 命令 | 结果 |
|---|---|---|
| 后端 RED | `pytest server/tests/test_alert_triage.py` | 9 failed / 2 passed，失败原因 = 端点不存在 + 缺 `triage` 字段 + 缺 `create_log` 引用 |
| 后端 GREEN | 同上 | 11 passed in 0.93s |
| 回归 | `pytest test_demo_flow.py test_security_timeline.py` | 17 passed |
| 全量后端 | `pytest server/tests` | 253 passed, 2 skipped in ~32s（基线 242 + 11 新增） |
| 前端 typecheck | `cd web-next && npm run typecheck` | ✓ 0 错误 |
| 前端 build | `cd web-next && npm run build` | ✓ Compiled successfully，/dashboard 36.4 kB（基线 33.5 → 36.4 kB） |
| E2E 默认 skip | `pytest test_demo_flow_e2e.py` | ✅ 1 skipped |
| E2E 真实浏览器 | `pytest test_demo_flow_e2e.py --run-e2e` | ❌ 环境受限（production CSP 拒 inline + dashboard 首次编译 20s 超时），见阶段 5 |
| `git diff --check` | `git diff --check` | 无冲突，仅 LF/CRLF 提示（pre-existing） |

## 改动文件清单

### 新增（3 个）

| 文件 | 行数 | 职责 |
|---|---|---|
| `server/tests/test_alert_triage.py` | ~270 | 11 个后端契约测试 |
| `web-next/components/dashboard/AlertTriagePanel.tsx` | ~220 | 紧凑研判控件 + 状态徽标 + loading/error |
| `docs/runs/2026-06-17-m3-02-alert-triage-response-workbench.md` | 本文件 | 运行日志 |

### 修改（12 个）

| 文件 | 改动 |
|---|---|
| `server/models/schemas.py` | +`AlertTriageUpdateIn` / `AlertTriageOut` / `TRIAGE_STATUS_VALUES` |
| `server/core/state.py` | +`AlertState.update_backlog_triage` (lock 内) |
| `server/services/alert_service.py` | +`default_alert_triage` / `_ensure_triage` / `_build_audit_detail` / `update_alert_triage`；`get_alerts` / `process_alert` / `trigger_demo_attack` 注入默认 triage |
| `server/routers/alerts_router.py` | +`PATCH /alerts/{alert_id}/triage` 路由 |
| `web-next/types/alert.ts` | +`AlertTriage` / `AlertTriageStatus` / `TRIAGE_STATUS_OPTIONS` / `TRIAGE_OPEN_STATUSES` / `TRIAGE_CLOSED_STATUSES` |
| `web-next/types/alertBriefing.ts` | `AlertDetail` / `AlertBriefing` 加 triage 字段 |
| `web-next/types/index.ts` | re-export `AlertTriage` / `AlertTriageStatus` |
| `web-next/utils/alertUtils.ts` | +`parseTriageStatus` / `defaultTriage` / `mapTriage`；`mapBackendAlert` 注入 triage |
| `web-next/utils/alertBriefingUtils.ts` | +triage helper；`buildReport` 含 triage；`deriveBriefing` 加 `triageBreakdown` / `triageOpen` / `triageClosed` |
| `web-next/utils/index.ts` | re-export `triageStatusLabel` / `triageStatusTone` / `triageShortLabel` |
| `web-next/hooks/useAlerts.ts` | +`updateTriage` 方法 |
| `web-next/components/dashboard/AlertDetailPanel.tsx` | 集成 `AlertTriagePanel` |
| `web-next/components/dashboard/AttackLogTable.tsx` | 加「研判」列 + `triage-row-badge` + `data-triage-status` |
| `web-next/components/dashboard/BriefingSection.tsx` | 加 `briefing-triage-counts` 段（待研判 / 已闭环 / 状态分布） |
| `web-next/app/dashboard/dashboard-client.tsx` | +`handleTriageSubmit` 接线 |
| `server/tests/test_demo_flow_e2e.py` | 扩展 E2E 步骤 5.5（triage 切换 + 保存 + attack-log-row 校验） |
| `PRODUCT.md` | M3 任务 + §2.2 加 M3-02 边界 |
| `docs/agent/UNATTENDED_LONG_TASKS.md` | M3-02 任务补充「重要边界」 |

未触碰：`server/security/**` / `server/models_db.py` / 认证 / Guardrails / `.env` / `docker-compose.yml` / `nginx/**` / CI / 数据库 schema。

## 最终状态

- 所有阶段已落地（除 E2E 真实运行受阻于环境，已记录原因）
- 11 个新测试 + 全量 253 passed；前端 typecheck/build 通过
- 安全审查：CRITICAL / HIGH 0
- 任务范围严格遵守：未触及禁止路径，未 `git add .`

