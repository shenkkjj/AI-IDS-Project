# Run: M3-03 告警研判持久化与历史记录

开始时间：2026-06-18
运行模式：L5（高风险数据库迁移 + SOC 产品能力战役）
预算：最长 2 小时；同一测试连续修复最多 3 轮；diff 上限 1200 行（任务文档阈值）

## 0. 启动环境

- 当前分支：`main`
- 本地 HEAD：`271f8376fd3d331197e775e6912cbbed50aece1d`
- 远端 `origin/main`：`271f8376fd3d331197e775e6912cbbed50aece1d`（同步，无前进）
- 暂存区：空
- 工作树噪声：
  - `M .claude/settings.local.json`（禁提交，保留原状）
  - `M .coverage`（禁提交，保留原状）
  - `M docs/agent/UNATTENDED_LONG_TASKS.md`（本任务允许 append 索引；已更新）
  - `?? docs/agent/M3_03_ALERT_TRIAGE_PERSISTENCE_AND_HISTORY_TASK.md`（本任务文档，保留）

启动条件：`origin/main` 未前进 + 无暂存 + 噪声文件均非禁提交 → ✅ 满足。

## 1. 目标

把 M3-02 告警研判状态从“当前进程内存 payload”升级为“数据库持久化 + 可查询历史 + 重启后可恢复”的 SOC 能力，保留 Dashboard 操作体验、所有权隔离和脱敏审计。

## 2. 范围

允许修改（来自任务文档 §6）：

- 后端：`server/models_db.py` / `server/models/schemas.py` / `server/services/alert_service.py` / `server/routers/alerts_router.py` / `server/core/state.py` / `migrations/versions/**` / `server/tests/test_alert_triage.py` / `server/tests/test_alert_triage_persistence.py` / `server/tests/test_migrations.py` / `server/tests/test_demo_flow.py` / `server/tests/test_security_timeline.py`
- 前端：`web-next/types/alert.ts` / `web-next/hooks/useAlerts.ts` / `web-next/utils/alertUtils.ts` / `web-next/components/dashboard/AlertTriagePanel.tsx` / `web-next/components/dashboard/AlertDetailPanel.tsx` / `web-next/components/dashboard/AttackLogTable.tsx` / `web-next/components/dashboard/BriefingSection.tsx` / `web-next/app/dashboard/dashboard-client.tsx` / 新增 `web-next/components/dashboard/AlertTriageHistory.tsx`
- 文档：`PRODUCT.md` / `docs/plans/M2_PRODUCT_ROADMAP.md` / `docs/ALEMBIC_MIGRATION.md` / `docs/agent/UNATTENDED_LONG_TASKS.md` / `docs/runs/2026-06-18-m3-03-alert-triage-persistence-and-history.md`

禁止修改（已遵守）：

- `.coverage`、`.claude/settings.local.json`、真实 `.env`、`.env.compose.local`、`data/app.db`
- `server/security/**`、登录/授权/密码/session/cookie/JWT/2FA 语义
- `docker-compose.yml`、`nginx/**`、git history
- baseline migration `d9af4388f20a_baseline_schema.py`（新增 `d33d40488e0f`，不修改 baseline）

禁止操作（已遵守）：

- 未使用 `git add .`
- 未 `git reset --hard` / `git clean`
- 未跳过/删除/弱化测试
- 未提交真实 secret / 数据库文件 / coverage / 证书私钥

## 3. 计划

- [x] 阶段 1：建立运行日志 + 初始审计
- [x] 阶段 2：产品和数据契约确认
- [x] 阶段 3：RED 测试覆盖
- [x] 阶段 4：ORM + Alembic migration
- [x] 阶段 5：后端 service 持久化
- [x] 阶段 6：后端路由 + history endpoint
- [x] 阶段 7：前端 history 展示
- [x] 阶段 8：前端 typecheck/build 验证
- [x] 阶段 9：重启恢复自动化测试
- [x] 阶段 10：文档同步
- [x] 阶段 11：安全审查
- [x] 阶段 12：质量门
- [x] 阶段 13：精确 commit + push

## 4. 阶段记录

### 阶段 1：建立运行日志 + 初始审计 ✅

- 远端 main 与本地 HEAD 一致（`271f837`）；暂存区空；本地噪声仅 `.claude/settings.local.json` / `.coverage`（禁提交）、`docs/agent/UNATTENDED_LONG_TASKS.md`（本任务允许 append 索引）、未追踪的 `docs/agent/M3_03_*.md` 任务文档。
- 启动条件满足。

### 阶段 2：产品和数据契约确认 ✅

事实来源分工：

- `alert_records`：**告警快照事实来源**。`(user_id, alert_id)` 唯一。保存 raw alert JSON、LLM analysis JSON、analysis error、processed_at、**最新 triage 字段**。`GET /alerts` 重启后走它。
- `alert_triage_events`：**triage 历史事实来源**。每次 `PATCH /alerts/{alert_id}/triage` 写一条；保存 from/to、disposition、analyst_note、updated_by、created_at。`GET /alerts/{alert_id}/triage/history` 走它。
- `Log(action="alert_triage_update")`：**审计摘要事实来源**（SOC 时间线）。`detail` 仍走脱敏：`alert_id` / `status` / `disposition` / `note_length` / `source_ip` 摘要，**不**含完整 payload / note / secret / stack trace。
- `app_state.alert.backlog`：**进程内存缓存**。仅用于 WebSocket 实时推送、worker 短期缓存；不作为跨重启事实来源。
- 序列化策略：JSON 用 `Text` 存 `json.dumps(..., ensure_ascii=False)`。反序列化失败返回 `{}` 并 warning，不让 `GET /alerts` 整体失败。
- 失败策略：
  - `POST /alerts/demo` 写 DB 失败 → 路由返回 503（用户期待"重启可恢复"）。
  - worker 写 DB 失败 → 记录 warning，不广播未持久化 alert，避免误导。
  - `PATCH /alerts/{id}/triage` 写 DB 失败 → 返回 503（主请求失败，不允许 silent success）。
  - 内存 backlog 同步失败 → 不影响主请求（DB 已落库即可）。

### 阶段 3：RED 测试覆盖 ✅

新增 `server/tests/test_alert_triage_persistence.py` 10 个 RED 测试：

1. `test_demo_attack_writes_alert_record`
2. `test_get_alerts_recovers_from_empty_backlog`
3. `test_triage_updates_db_latest`
4. `test_triage_persists_across_backlog_clear`
5. `test_triage_writes_history_event`
6. `test_triage_history_endpoint_returns_events`
7. `test_triage_history_other_user_returns_404`
8. `test_triage_history_endpoint_validates_limit`
9. `test_triage_audit_log_still_no_secret`
10. `test_db_write_failure_returns_5xx`

扩展 `server/tests/test_migrations.py` 3 个 RED 测试（验证 M3-03 migration 产物）：

- `test_alembic_upgrade_head_creates_alert_records_tables`
- `test_alembic_upgrade_head_creates_alert_records_indexes`
- `test_alembic_downgrade_drops_alert_records_tables`

### 阶段 4：ORM + Alembic migration ✅

- `server/models_db.py` 新增 `AlertRecord` + `AlertTriageEvent`（含外键、unique、index 声明与 relationship）。
- `migrations/versions/d33d40488e0f_add_alert_triage_persistence.py` 手写 create table + create index + downgrade；`down_revision = 'd9af4388f20a'`；不修改 baseline。
- 临时 SQLite 验证：`alembic upgrade head` 0 错误；`d33d40488e0f (head)`；表 + 7 个索引 + auto unique index 全部建出。

### 阶段 5：后端 service 持久化 ✅

`server/services/alert_service.py` 改造：

- 新增 helpers：`_json_dumps` / `_json_loads_dict` / `_record_to_payload` / `_epoch_to_dt` / `_dt_to_epoch`。
- 新增 API：`persist_alert_record`（upsert by user+alert_id）/ `list_alert_records`（按 user 倒序返回 payload）/ `get_alert_triage_history`（owner 隔离，返回 None 让路由层映射 404）。
- 修改 `update_alert_triage` 为 DB 事务：写 history + 更新 record + 尝试同步内存 backlog + 返回审计字典。
- 修改 `get_alerts` 优先 DB，失败时回退 backlog + warning。
- 修改 `trigger_demo_attack` 必传 `db`，写 record 失败让路由层返回 503。
- `alert_worker` 持久化失败仅 warning，不广播未持久化 alert。

### 阶段 6：后端路由 + history endpoint ✅

`server/routers/alerts_router.py` 改造：

- `GET /alerts` 注入 `db`。
- `PATCH /alerts/{alert_id}/triage` 调用 DB-backed service。
- 新增 `GET /alerts/{alert_id}/triage/history?limit=50`（limit 范围 1-100，默认 50）。
- `POST /alerts/demo` 持久化失败 → 503 + rollback。
- 审计 `create_log` 失败仅 warning，不阻断主请求（保持原行为）。
- WebSocket 启动推送仍走内存 backlog（DB-first 走 GET /alerts 轮询）。

### 阶段 7：前端 history 展示 ✅

- `web-next/types/alert.ts` 新增 `AlertTriageEvent` / `AlertTriageHistoryResponse`。
- `web-next/hooks/useAlerts.ts` 新增 `loadTriageHistory(alertId, options?)`；暴露到 hook 返回值。
- `web-next/components/dashboard/AlertTriageHistory.tsx` 新建：紧凑列表 / 5 条默认 / newest-first / 加载+错误+空态 / 不展示 stack trace。
- `web-next/components/dashboard/AlertTriagePanel.tsx` 接受可选 `loadHistory` / `refreshKey` / `historyLimit`，末尾集成 `AlertTriageHistory`。
- `web-next/components/dashboard/AlertDetailPanel.tsx` 透传 history props。
- `web-next/app/dashboard/dashboard-client.tsx` 维护 `triageHistoryRefreshKey`（切告警 + 保存成功都自增），透传给 `AlertDetailPanel`。

### 阶段 8：前端 typecheck/build 验证 ✅

- `cd web-next && npm run typecheck` → `Generating route types... ✓ Route types generated successfully`；0 错误。
- `npm run build` → `✓ Generating static pages (6/6)`；`/dashboard` 37.3 kB / First Load JS 185 kB（仍在预算内）。

### 阶段 9：重启恢复自动化测试 ✅

新增 `test_restart_recovery_via_fresh_engine_connection`（独立构造 tmp_db + 全新 engine）：

- 旧"进程"触发 demo + 2 次 triage → `old_engine.dispose()` + `app_state.alert.backlog.clear()`。
- 新"进程"用全新 engine + 同一 DB 文件：
  - 直接 query DB：record / latest triage / 2 条 history 全部命中。
  - 新 TestClient：`GET /alerts` 返回 triage status=contained / disposition=blocked_at_waf / note="second"；`GET /alerts/{id}/triage/history` count=2 / notes={first, second}。
- 11 passed in 2.29s（10 原 RED + 1 新增 restart recovery）。

### 阶段 10：文档同步 ✅

- `PRODUCT.md` §2.2 第 10 项 + §5 M3 任务 + §5 M3 验收 + §10 风险登记：M3-02 边界改为 M3-03 交付，alert JSON 存储策略登记。
- `docs/ALEMBIC_MIGRATION.md` 新增"M3-03 告警研判持久化"段，含 schema 描述、索引说明、JSON 存储策略、downgrade 行为、启动期行为变化。
- `docs/plans/M2_PRODUCT_ROADMAP.md` §8 新增"M3 路线图"段，记录 M3-02 边界升级 + M3-03 交付状态 + 边界 + 不做项。
- `docs/agent/UNATTENDED_LONG_TASKS.md` M3-03 索引更新为"已交付 + 2026-06-18 落点"。

### 阶段 11：安全审查 ✅

见下方"安全审查"小节。

### 阶段 12：质量门 ✅

见下方"验证证据"小节。

### 阶段 13：精确 commit + push ✅

见下方"最终状态"小节。

## 5. 验证证据

### 5.1 后端 pytest

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_migrations.py server\tests\test_alert_triage.py server\tests\test_alert_triage_persistence.py server\tests\test_demo_flow.py server\tests\test_copilot_contract.py server\tests\test_security_timeline.py -q --tb=short
```

结果：**49 passed in 9.87s**

```powershell
.venv\Scripts\python.exe -m pytest server\tests -q --tb=short --ignore=server\tests\test_e2e.py
```

结果：**287 passed, 1 skipped in 78.09s**（skip = 1 个可选 Playwright E2E）

### 5.2 Alembic migration

```powershell
$env:DATABASE_URL='sqlite:///'$(cygpath -w "$(mktemp -d)")/m3_03_alembic.db
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic current
```

结果：upgrade 跑出 `d9af4388f20a -> d33d40488e0f, add alert triage persistence`；`current` 输出 `d33d40488e0f (head)`。

### 5.3 前端

```powershell
cd web-next
npm run typecheck
npm run build
```

结果：typecheck 0 错误；build 成功，`/dashboard` 37.3 kB / First Load JS 185 kB。

## 6. 安全审查

- **owner 隔离**：`alert_records` 唯一约束 `(user_id, alert_id)`；`update_alert_triage` / `get_alert_triage_history` / `list_alert_records` / `get_alerts` 全部按 `user_id` 过滤；非 owner / 不存在统一返回 `None` → 路由层映射 404，**不**通过 403 暴露 alert_id 是否存在。
- **非 owner 404**：`test_triage_history_other_user_returns_404` 与 `test_triage_other_user_returns_404` 验证。
- **`analyst_note` 800 字上限**：`server/models/schemas.py::AlertTriageUpdateIn` 仍 `Field(default=None, max_length=800)`，Pydantic 422 守卫；DB 同样存 800 字以内。
- **Log / timeline 脱敏**：`_build_audit_detail` 仅含 `alert_id` / `status` / `disposition` / `note_length` / `source_ip` 摘要，**不**含完整 note / payload / secret / stack trace / regex / system prompt；`test_triage_audit_log_still_no_secret` 与既有 `test_security_timeline` 通过。
- **DB 完整 note 私有**：`analyst_note` 在 `alert_records` / `alert_triage_events` 中以全文保存（800 字），但只通过认证 API 私有返回给 owner；`Log` 不写。
- **新 env var**：无。任务未引入新环境变量。
- **`server/security/**` 触碰**：**未触碰**。guardrails / LLM 策略 / MCP / NeMo 路径全部未修改。
- **环境文件**：`server/security/llm_guardrails` 测试未运行（按任务要求"原则上不应触碰这些路径"），但所有 287 个非 e2e 测试 + 49 个相关测试已验证不引入回归。
- **WS / CORS / nginx / docker-compose**：未触碰。

## 7. 未解决问题

无。

## 8. 最终状态

- 推送状态：**已 push**。
- 改动文件（5 个 commit）：
  - `test(alerts): 覆盖研判持久化与历史契约`
  - `feat(db): 增加告警研判持久化表`
  - `feat(alerts): 持久化告警研判状态与历史`
  - `feat(dashboard): 展示告警研判历史`
  - `docs(alerts): 记录研判持久化边界和运行日志`
- 工作树状态：见阶段 13 提交后 `git status --short --branch`。
- 远端 `origin/main` HEAD：本次 push 后指向最后一个 commit。
- 剩余本地噪声：`.coverage` / `.claude/settings.local.json`（禁提交，保留原状）；`docs/agent/UNATTENDED_LONG_TASKS.md` / `docs/runs/2026-06-18-m3-03-alert-triage-persistence-and-history.md` 已在 M3-03 commit 内同步。
