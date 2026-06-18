# M3-04 安全事件 / 案件工作台 L5 超长任务

> 任务级别：L5，高风险数据库迁移 + 跨后端 / 前端 / 产品文档战役。  
> 目标读者：接手本仓库的开发 agent。  
> 核心目标：把当前“单条告警研判”升级为“安全事件 / 案件工作台”，让分析员能把多条相关告警归并成一个可追踪、可审计、可恢复的处置对象。

---

## 0. 背景

当前 M3-02 / M3-03 已经完成：

- `PATCH /alerts/{alert_id}/triage`：单条告警研判状态和备注。
- `GET /alerts/{alert_id}/triage/history`：单条告警研判历史。
- `alert_records`：告警快照事实来源。
- `alert_triage_events`：单条告警研判历史事实来源。
- Dashboard 中已经有告警列表、详情、研判面板、研判历史、Copilot、时间线和日报。

但产品仍停留在“单条告警处理”：

- 多条来自同一来源 IP、同一攻击类型、同一目标资产的告警无法组织成一个事件。
- 分析员无法记录“这个事件整体处置到哪一步了”。
- 安全日报和时间线只能看到零散告警，缺少可追踪的案件编号。
- Copilot 只能分析当前告警，不能获得一个案件的多告警上下文。

本任务要新增一个轻量但真实的 SOC 能力：**Incident / Case**。

---

## 1. 产品能力定义

完成后，用户应该能做到：

1. 从 Dashboard 选中一条告警，一键创建安全事件。
2. 把其他告警加入已有事件。
3. 查看事件列表、事件详情、关联告警、事件状态、严重度、负责人备注和事件时间线。
4. 推进事件状态：`open / investigating / contained / resolved / false_positive`。
5. 每次状态变化、告警加入 / 移出事件都留下可查询历史和脱敏审计。
6. 事件在后端重启、清空内存 backlog 后仍能从数据库恢复。
7. Dashboard 增加“案件”视图，但不要做成营销页；第一屏仍是可操作工作台。

一句话能力声明：

> 安全分析员可以把分散告警组织成可追踪案件，并围绕案件推进处置、查看关联证据、调用 Copilot 分析和保留审计历史。

---

## 2. 启动前必读

执行前完整阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`
- `docs/ALEMBIC_MIGRATION.md`
- `docs/agent/M3_02_ALERT_TRIAGE_RESPONSE_WORKBENCH_TASK.md`
- `docs/agent/M3_03_ALERT_TRIAGE_PERSISTENCE_AND_HISTORY_TASK.md`
- `docs/runs/2026-06-18-m3-03-alert-triage-persistence-and-history.md`

必须阅读当前实现：

- `server/models_db.py`
- `server/models/schemas.py`
- `server/core/database.py`
- `server/core/state.py`
- `server/routers/alerts_router.py`
- `server/routers/logs_router.py`
- `server/routers/copilot_router.py`
- `server/services/alert_service.py`
- `server/services/copilot_service.py`
- `server/tests/test_alert_triage.py`
- `server/tests/test_alert_triage_persistence.py`
- `server/tests/test_migrations.py`
- `web-next/app/dashboard/dashboard-client.tsx`
- `web-next/types/alert.ts`
- `web-next/types/route.ts`
- `web-next/hooks/useAlerts.ts`
- `web-next/components/dashboard/AlertDetailPanel.tsx`
- `web-next/components/dashboard/AlertTriagePanel.tsx`
- `web-next/components/dashboard/AlertTriageHistory.tsx`
- `web-next/components/dashboard/AttackLogTable.tsx`
- `web-next/components/dashboard/BriefingSection.tsx`

建议先用 `rg incident server web-next docs` 检查是否已有遗留实现。若已存在同名概念，先记录冲突，再决定复用或更名，不要盲目新增平行系统。

---

## 3. 初始仓库审计

开始改文件前必须：

1. 创建运行日志：

   ```text
   docs/runs/2026-06-18-m3-04-incident-case-workbench.md
   ```

2. 记录：
   - 当前分支。
   - `HEAD`。
   - `origin/main`。
   - `git status --short --branch`。
   - 暂存区是否为空。
   - 本地噪声文件。

3. 如果出现以下情况，立即停止：
   - `origin/main` 比本地新，且不是 fast-forward 明确可处理。
   - 本地已有暂存文件。
   - 发现 `.coverage`、`.claude/settings.local.json`、真实 `.env`、数据库文件、密钥文件被暂存。
   - 发现上一个任务未完成的冲突或半截迁移。

允许存在但不得提交：

- `.coverage`
- `.claude/settings.local.json`
- `.env`
- `.env.compose.local`
- `data/app.db`
- `server/.pytest_cache/**`
- `**/__pycache__/**`

---

## 4. 数据模型契约

新增两个核心表，全部走 Alembic 新 revision，不修改 baseline，不修改 `d33d40488e0f`。

### 4.1 `incidents`

安全事件 / 案件事实来源。

建议字段：

- `id`：整数主键。
- `incident_id`：字符串业务 ID，建议格式 `inc_<12-16 hex>`，全局唯一。
- `user_id`：FK `users.id`，owner 隔离。
- `title`：字符串，1-120 字符。
- `summary`：文本，可为空，最多 1000 字符，由分析员或自动模板生成。
- `severity`：`critical / high / medium / low`。
- `status`：`open / investigating / contained / resolved / false_positive`。
- `assignee_user_id`：FK `users.id`，可空；M3-04 默认设为当前用户，不做多人协作权限。
- `created_from_alert_id`：字符串，可空，记录首条告警。
- `created_at`：时间。
- `updated_at`：时间。
- `closed_at`：时间，可空。

建议约束 / 索引：

- `UniqueConstraint("incident_id")`
- `Index("ix_incidents_user_updated", "user_id", "updated_at")`
- `Index("ix_incidents_user_status_updated", "user_id", "status", "updated_at")`
- `Index("ix_incidents_created_from_alert", "created_from_alert_id")`

### 4.2 `incident_alert_links`

事件与告警的关联表。

建议字段：

- `id`
- `incident_id`：FK `incidents.incident_id` 或 FK `incidents.id`，优先用整数 FK `incident_record_id`，同时冗余业务 `incident_id` 字符串便于 API。
- `user_id`：FK `users.id`，owner 隔离。
- `alert_record_id`：FK `alert_records.id`。
- `alert_id`：字符串冗余，便于查询和审计。
- `linked_by`：FK `users.id`。
- `linked_at`：时间。
- `removed_at`：时间，可空。

建议约束 / 索引：

- 唯一约束只应限制“同一 incident 下同一 alert 的 active link”，SQLite 不支持通用 partial unique 的跨库写法时，优先在 service 层做幂等检查；不要写只适配 PostgreSQL 的 partial unique。
- `Index("ix_incident_alert_links_incident_active", "incident_record_id", "removed_at")`
- `Index("ix_incident_alert_links_user_alert", "user_id", "alert_id")`
- `Index("ix_incident_alert_links_alert_record", "alert_record_id")`

### 4.3 `incident_events`

事件时间线事实来源。

建议字段：

- `id`
- `incident_record_id`：FK `incidents.id`
- `incident_id`：字符串冗余
- `user_id`：FK `users.id`
- `event_type`：`created / status_changed / alert_linked / alert_unlinked / note_added / summary_updated / severity_changed`
- `from_status`：可空
- `to_status`：可空
- `detail`：脱敏摘要，不存完整 raw payload，不存 secret。
- `note`：私有 note，可空，最多 1000 字符；只通过 owner API 返回。
- `actor_user_id`：FK `users.id`
- `created_at`

建议索引：

- `Index("ix_incident_events_incident_created", "incident_record_id", "created_at")`
- `Index("ix_incident_events_user_created", "user_id", "created_at")`

如果你判断三张表比两张表更清晰，可以按三张表实现；如果想把 event 合进 link 表，必须在运行日志里说明取舍。推荐三张表，因为它能让事件时间线干净。

---

## 5. API 契约

新增 router 优先放在：

```text
server/routers/incidents_router.py
```

并在 `server/main.py` include。注意：`main.py` 含 `/mcp` 安全段，除 include router 外不要改 MCP、安全护栏、认证逻辑。

### 5.1 `GET /incidents`

认证：`require_auth_user`。

查询参数：

- `limit`：默认 50，范围 1-100。
- `status`：可选，必须在事件状态白名单内。

返回：

```json
{
  "status": "ok",
  "items": [
    {
      "incident_id": "inc_abcd1234",
      "title": "...",
      "summary": "...",
      "severity": "high",
      "status": "investigating",
      "alert_count": 3,
      "created_from_alert_id": "...",
      "created_at": 1710000000,
      "updated_at": 1710000000,
      "closed_at": null
    }
  ],
  "count": 1,
  "limit": 50
}
```

### 5.2 `POST /incidents`

认证：`require_auth_user`。

请求：

```json
{
  "title": "来自 203.0.113.45 的 SQL 注入攻击",
  "summary": "可选",
  "severity": "high",
  "alert_id": "可选，若传入则作为首条关联告警"
}
```

行为：

- 若 `alert_id` 存在，必须验证该 alert 属于当前 user。
- 创建 incident。
- 若有 `alert_id`，创建 active link。
- 写 `incident_events(created)`。
- 写 `Log(action="incident_create")` 脱敏摘要。
- 返回 incident detail。

错误：

- 未登录 401。
- alert 不存在 / 非 owner：404。
- 字段非法：422。
- DB 写失败：503 或抛出可预测 5xx，不允许静默成功。

### 5.3 `GET /incidents/{incident_id}`

认证：`require_auth_user`。

返回：

- incident 基础信息。
- 关联告警列表，使用与 `GET /alerts` 一致的 payload 派生前端字段所需信息。
- 最近事件时间线，默认 20 条 newest-first 或 oldest-first 二选一，但必须文档和测试一致。推荐 newest-first，与 triage history 一致。

非 owner / 不存在统一 404。

### 5.4 `PATCH /incidents/{incident_id}`

认证：`require_auth_user`。

允许更新：

- `status`
- `severity`
- `title`
- `summary`
- `note`：可选，作为事件 note 写入 `incident_events`，不一定覆盖 summary。

行为：

- 更新 incident。
- 状态变更时写 `incident_events(status_changed)`。
- severity/title/summary/note 变化写对应 event。
- `status` 进入 `resolved / false_positive` 时自动设置 `closed_at`；从关闭态改回打开态时清空 `closed_at`。
- 写 `Log(action="incident_update")` 脱敏摘要，不能包含完整 note。

### 5.5 `POST /incidents/{incident_id}/alerts`

认证：`require_auth_user`。

请求：

```json
{ "alert_id": "..." }
```

行为：

- 验证 incident 属于当前 user。
- 验证 alert 属于当前 user。
- 若 active link 已存在，幂等返回 ok，不重复写 active link；是否写 `incident_events(alert_linked)` 由你决定，但测试需锁定。推荐重复 link 不写新 event。
- 新 link 写 `incident_events(alert_linked)` + `Log(action="incident_alert_link")`。

### 5.6 `DELETE /incidents/{incident_id}/alerts/{alert_id}`

认证：`require_auth_user`。

行为：

- 软删除 link：设置 `removed_at`。
- 写 `incident_events(alert_unlinked)`。
- 非 owner / incident 不存在 / alert link 不存在统一 404。
- 不删除 `alert_records`。

### 5.7 Copilot 集成

不要大改 Guardrails 或 LLM provider。

最小可接受方案：

- 在前端事件详情里提供“用 AI 分析案件”按钮。
- 点击后把案件标题、状态、严重度、关联告警摘要拼成用户消息，走现有 Copilot SSE。
- 不新增 LLM provider。
- 不绕过现有 `copilot_service` guardrails。

如果要新增后端 `incident_id` 上下文参数给 Copilot，必须同步测试，并确保：

- owner 隔离。
- 非 owner / 不存在 404 或降级，不泄露 incident 是否存在。
- SSE error 不泄露 stack trace / prompt / secret。

推荐 M3-04 先走前端拼接摘要，后续 M3-05 再做后端 incident-aware Copilot contract。

---

## 6. 前端契约

新增“案件”视图，目标是可操作工作台，不是漂亮展示页。

### 6.1 路由 / 导航

修改：

- `web-next/types/route.ts`
- `web-next/utils/routeUtils.ts`
- `web-next/app/dashboard/dashboard-client.tsx`

新增 RouteKey：

```ts
"incidents"
```

导航显示：

- label：`案件`
- index：建议 `03`

现有索引可顺延或不改，但不要造成同屏多个 `§ 03` 混乱。

### 6.2 类型和 hook

建议新增：

- `web-next/types/incident.ts`
- `web-next/hooks/useIncidents.ts`

`useIncidents` 应至少支持：

- `loadIncidents`
- `createIncidentFromAlert`
- `loadIncidentDetail`
- `updateIncident`
- `linkAlert`
- `unlinkAlert`
- 状态：`loadState / selectedIncident / incidentItems / detailState / actionState / error`

### 6.3 组件

建议新增：

- `web-next/components/dashboard/IncidentSection.tsx`
- `web-next/components/dashboard/IncidentList.tsx`
- `web-next/components/dashboard/IncidentDetailPanel.tsx`
- `web-next/components/dashboard/IncidentTimeline.tsx`
- `web-next/components/dashboard/IncidentLinkedAlerts.tsx`

复用现有视觉语言：

- 不做 landing page。
- 不把卡片套卡片。
- 不使用大 hero。
- 不新增一套设计系统。
- 组件应能在桌面和移动宽度下不重叠。

### 6.4 与告警详情集成

在 `AlertDetailPanel` 或其上层提供：

- “创建案件”按钮。
- 若已有案件列表，可选择“加入案件”。

M3-04 最小验收可以只做：

- 从当前选中告警创建新案件。
- 在案件详情里添加当前选中告警或通过 alert_id 添加。

不要在 M3-04 做复杂批量选择、拖拽、多选表格。

---

## 7. 允许修改范围

后端：

- `server/models_db.py`
- `server/models/schemas.py`
- `server/services/incident_service.py`（新增）
- `server/routers/incidents_router.py`（新增）
- `server/main.py`（仅 include 新 router）
- `server/tests/test_incidents.py`（新增）
- `server/tests/test_incident_persistence.py`（可新增）
- `server/tests/test_migrations.py`
- `migrations/versions/**`（新增 revision）

前端：

- `web-next/types/incident.ts`（新增）
- `web-next/types/route.ts`
- `web-next/utils/routeUtils.ts`
- `web-next/hooks/useIncidents.ts`（新增）
- `web-next/app/dashboard/dashboard-client.tsx`
- `web-next/components/dashboard/AlertDetailPanel.tsx`
- `web-next/components/dashboard/**Incident*.tsx`（新增）
- 必要时小改 `BriefingSection.tsx`，显示 open incident 计数。

文档：

- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`
- `docs/ALEMBIC_MIGRATION.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/runs/2026-06-18-m3-04-incident-case-workbench.md`

---

## 8. 禁止修改范围

禁止：

- `.coverage`
- `.claude/settings.local.json`
- `.env`
- `.env.compose.local`
- `data/app.db`
- 任何真实 secret / token / key / 证书私钥
- `server/security/**`
- `/mcp` 鉴权逻辑
- 登录、注册、JWT、refresh token、2FA、cookie 语义
- `docker-compose.yml`
- `nginx/**`
- 既有 Alembic baseline `d9af4388f20a_baseline_schema.py`
- 既有 M3-03 migration `d33d40488e0f_add_alert_triage_persistence.py`

除非测试证明必须，不要修改：

- `server/services/copilot_service.py`
- `server/services/llm_providers.py`
- `server/core/security.py`

不允许：

- `git add .`
- `git reset --hard`
- `git clean`
- force push
- 为了通过测试而 skip / 删除 / 弱化既有测试
- 把 DB 失败伪装成成功

---

## 9. 分阶段执行计划

### 阶段 1：运行日志和基线审计

- 建 run log。
- 记录 git 状态。
- 记录当前测试基线是否可跑。
- 停止条件见 §3。

### 阶段 2：能力契约落地

在 run log 写清：

- incident 与 alert triage 的关系。
- incident owner 隔离策略。
- incident 状态流转策略。
- 关闭态 `closed_at` 行为。
- 事件 timeline 返回顺序。
- 重复 link 的幂等策略。

### 阶段 3：RED 测试

先写失败测试，不先实现。

建议覆盖：

1. `POST /incidents` 可从 owner alert 创建 incident，并自动 link alert。
2. 非 owner alert 创建 incident 返回 404。
3. `GET /incidents` 只返回当前 user 的 incident。
4. `GET /incidents/{incident_id}` 返回 linked alerts + events。
5. `PATCH /incidents/{incident_id}` 更新 status/severity/title/summary 并写 event。
6. `resolved / false_positive` 设置 `closed_at`。
7. 从关闭态改回 `investigating` 清空 `closed_at`。
8. `POST /incidents/{incident_id}/alerts` 可 link 第二条 alert。
9. 重复 link 幂等，不重复 active link。
10. `DELETE /incidents/{incident_id}/alerts/{alert_id}` 软删除 link。
11. 非 owner incident / alert 全部 404，不泄露存在性。
12. `incident_events.note` 可由 owner API 返回，但 `Log.detail` 不含完整 note。
13. 清空 `app_state.alert.backlog` 后，incident detail 仍从 DB 返回 linked alerts。
14. Alembic `upgrade head` 建出 incident 三表和索引。
15. Alembic `downgrade base` 删除 incident 表。

测试文件建议：

- `server/tests/test_incidents.py`
- `server/tests/test_incident_persistence.py`
- 扩展 `server/tests/test_migrations.py`

### 阶段 4：ORM + Alembic

- 新增 ORM model。
- 新增 Alembic revision，`down_revision` 指向当前 head `d33d40488e0f`。
- migration 必须有 `upgrade()` 和 `downgrade()`。
- 不做数据 backfill。
- 不加 `NOT NULL` 到既有大表。
- 新表可以正常 `nullable=False`。
- SQLite / PostgreSQL 兼容优先，不使用 PostgreSQL-only JSONB / partial index。

### 阶段 5：后端 service

新增 `server/services/incident_service.py`。

建议 service API：

- `create_incident(...)`
- `list_incidents(...)`
- `get_incident_detail(...)`
- `update_incident(...)`
- `link_alert(...)`
- `unlink_alert(...)`
- `build_incident_audit_detail(...)`

service 层必须：

- 用 `user_id` 过滤所有 incident 和 alert。
- 所有非 owner / 不存在返回 `None` 或抛项目已有可控异常，由 router 映射 404。
- DB 写入失败不静默。
- 所有事件写入与主变更同事务。
- `Log` 写入由 router 层或 service 明确处理，但失败不得破坏主请求。

### 阶段 6：后端 router

新增 `server/routers/incidents_router.py` 并 include。

必须：

- 端点全部认证。
- limit 参数有上限。
- 请求体用 Pydantic schema。
- 用户可见错误不含 stack trace。
- Log detail 脱敏。

### 阶段 7：前端 hook + 类型

- 新增 incident 类型。
- 新增 `useIncidents`。
- 通过 `/api/backend/incidents...` 代理路径调用后端。
- 错误态低调展示，不弹出 raw stack。
- 不把 API response 当 any 到处传，尽量用类型收束。

### 阶段 8：前端案件工作台

- Dashboard 新增“案件”导航。
- 事件列表支持状态、严重度、告警数、更新时间。
- 事件详情支持：
  - 状态切换。
  - 严重度切换。
  - 摘要 / note 保存。
  - 关联告警列表。
  - 事件 timeline。
  - “用 AI 分析案件”按钮。
- 告警详情支持从当前告警创建案件。

### 阶段 9：Copilot 最小案件上下文

优先前端拼接消息，不改后端 LLM。

消息模板必须包括：

- incident id
- title
- severity
- status
- linked alert 数量
- 最多 5 条 alert 摘要
- 明确要求输出：风险、证据、影响、下一步处置

不得包含：

- secret
- API key
- system prompt
- stack trace
- 完整超长 payload

### 阶段 10：真实浏览器 / 前端验证

如果 dev server 可启动，必须用浏览器或 Playwright 验证：

- 登录后 Dashboard 可打开。
- 触发 Demo 告警。
- 从告警创建案件。
- 切到案件视图。
- 事件详情显示关联告警和 timeline。
- 修改事件状态后 UI 更新。

如环境无法启动，必须在 run log 写清失败原因，并至少跑 typecheck/build。

### 阶段 11：文档同步

更新：

- `PRODUCT.md`：M3-04 能力、边界、验收。
- `docs/plans/M2_PRODUCT_ROADMAP.md`：M3 路线图追加 M3-04。
- `docs/ALEMBIC_MIGRATION.md`：新增 migration 描述。
- `docs/agent/UNATTENDED_LONG_TASKS.md`：把本任务从待执行改为已交付，补 run log 路径。
- run log：全阶段证据。

### 阶段 12：安全审查

必须在 run log 写安全审查小节：

- owner 隔离。
- 非 owner 404。
- Log 脱敏。
- note 私有返回边界。
- Copilot 消息不含 secret / system prompt / stack trace。
- 未触碰 `server/security/**` 和 `/mcp`。
- 新 env var 情况，原则上本任务不应新增 env var。

### 阶段 13：质量门

至少运行：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_migrations.py server\tests\test_incidents.py server\tests\test_incident_persistence.py server\tests\test_alert_triage.py server\tests\test_alert_triage_persistence.py server\tests\test_demo_flow.py -q --tb=short
```

如果 `test_incident_persistence.py` 未独立创建，就从命令里去掉，但必须说明原因。

再运行：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests -q --tb=short --ignore=server\tests\test_e2e.py
```

前端：

```powershell
cd web-next
npm run typecheck
npm run build
```

迁移：

```powershell
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic downgrade -1
.venv\Scripts\python.exe -m alembic upgrade head
```

最终：

```powershell
git diff --check
git status --short --branch
```

如果触碰了 `server/security/**`、`server/services/copilot_service.py`、`server/services/llm_providers.py`，还必须跑：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
.venv\Scripts\python.exe -m pytest server\tests\test_copilot_contract.py -q --tb=short
```

---

## 10. 提交与推送

只有全部质量门通过后，才允许精确 commit / push。

禁止 `git add .`。

建议 commit 拆分：

1. `test(incidents): 覆盖安全事件案件契约`
2. `feat(db): 增加安全事件案件持久化表`
3. `feat(incidents): 实现案件 API 与审计时间线`
4. `feat(dashboard): 增加安全事件案件工作台`
5. `docs(incidents): 记录案件工作台边界与运行日志`

提交前必须检查 staged：

```powershell
git diff --cached --name-status
```

不得 staged：

- `.coverage`
- `.claude/settings.local.json`
- `.env*` 真实配置
- `data/app.db`
- `*.pem`
- `*.key`
- `server/.pytest_cache/**`
- `**/__pycache__/**`

push 前：

```powershell
git status --short --branch
git log --oneline origin/main..HEAD
```

如果 `origin/main` 前进，停止并报告，不要强推。

---

## 11. 停止条件

遇到以下任一情况必须停止并写 run log：

1. 同一测试失败连续修复 3 轮。
2. Alembic migration 需要修改既有已部署 revision。
3. 为实现 incident 必须修改认证 / JWT / 2FA / cookie / `server/security/**`。
4. 需要新增外部服务、真实 secret 或公网部署。
5. `git diff --stat` 超过 1600 行且不是测试 / 文档为主。
6. 前端布局出现明显重叠，但无法本地验证修复。
7. DB 写失败只能靠静默忽略才能“通过”。
8. 发现与 M3-03 alert persistence 契约冲突。

---

## 12. 完成报告模板

完成后输出：

```text
完成状态：完成 / 部分完成 / 阻塞

本次新增能力：
- ...

关键文件：
- ...

验证命令：
- ... -> 结果

数据库迁移：
- revision: ...
- upgrade/downgrade: ...

安全审查：
- owner 隔离：...
- 审计脱敏：...
- Copilot 上下文：...

提交：
- commit 列表
- push 状态

剩余风险：
- ...
```

---

## 13. 给 owner 的短启动口令

```text
请执行 docs/agent/M3_04_INCIDENT_CASE_WORKBENCH_TASK.md 里的 L5 超长任务。先完整阅读任务文档和其中列出的必读文件，创建并持续更新 run log；按 RED→GREEN→IMPROVE 推进，完成 incident/case 数据库持久化、API、owner 隔离、事件时间线、Dashboard 案件工作台、Copilot 案件摘要、测试、文档同步、质量门、精确 commit/push。不要 git add .，不要提交 .coverage、.claude/settings.local.json、真实 env、数据库文件或密钥。遇到远端前进、破坏性迁移、认证/安全护栏变更或质量门无法通过时停止并报告。
```
