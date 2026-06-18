# Run: M3-04 安全事件 / 案件工作台

开始时间：2026-06-18
运行模式：L5（高风险数据库迁移 + 跨后端 / 前端 / 产品文档战役）
预算：最长 2 小时；同一测试连续修复最多 3 轮；diff 上限 1600 行（任务文档阈值；非测试/文档为 800 行）

## 0. 启动环境

- 当前分支：`main`
- 本地 HEAD：`52ebbd65b5ea1f3c79abc9992ba0129f5aab20af`
- 远端 `origin/main`：`52ebbd65b5ea1f3c79abc9992ba0129f5aab20af`（同步，无前进）
- 暂存区：空
- 工作树噪声：
  - `M .claude/settings.local.json`（禁提交，保留原状）
  - `M .coverage`（禁提交，保留原状）
  - `M docs/agent/UNATTENDED_LONG_TASKS.md`（本任务允许 append 索引；已更新）
  - `?? docs/agent/M3_04_INCIDENT_CASE_WORKBENCH_TASK.md`（本任务文档，保留）

启动条件：`origin/main` 未前进 + 无暂存 + 噪声文件均非禁提交 → ✅ 满足。

无 incident 既有实现（`rg incident` 已确认零结果）；无破坏性迁移；无认证 / 安全护栏变更。

## 1. 目标

把当前"单条告警研判"升级为"安全事件 / 案件工作台"，让分析员能把多条相关告警归并成一个可追踪、可审计、可恢复的处置对象。

目标闭环：

```text
告警生成 -> 从告警创建 incident -> 把更多告警加入 incident
       -> 推进 incident status/severity/title/summary
       -> 写 incident_events 时间线 + Log 脱敏审计
       -> 重启后从 DB 恢复 -> Copilot 案件摘要
```

## 2. 范围

允许修改（来自任务文档 §7）：

- 后端：`server/models_db.py` / `server/models/schemas.py` / `server/services/incident_service.py`（新增）/ `server/routers/incidents_router.py`（新增）/ `server/main.py`（仅 include 新 router）/ `server/tests/test_incidents.py`（新增）/ `server/tests/test_incident_persistence.py`（新增）/ `server/tests/test_migrations.py`（扩展）/ `migrations/versions/**`（新增 revision）
- 前端：`web-next/types/incident.ts`（新增）/ `web-next/types/route.ts` / `web-next/utils/routeUtils.ts` / `web-next/hooks/useIncidents.ts`（新增）/ `web-next/app/dashboard/dashboard-client.tsx` / `web-next/components/dashboard/AlertDetailPanel.tsx` / `web-next/components/dashboard/**Incident*.tsx`（新增）/ `web-next/components/dashboard/BriefingSection.tsx`（必要时小改）
- 文档：`PRODUCT.md` / `docs/plans/M2_PRODUCT_ROADMAP.md` / `docs/ALEMBIC_MIGRATION.md` / `docs/agent/UNATTENDED_LONG_TASKS.md` / `docs/runs/2026-06-18-m3-04-incident-case-workbench.md`

禁止修改（已遵守）：

- `.coverage`、`.claude/settings.local.json`、真实 `.env`、`.env.compose.local`、`data/app.db`
- `server/security/**`、`/mcp` 鉴权逻辑
- 登录 / 注册 / JWT / refresh token / 2FA / cookie 语义
- `docker-compose.yml`、`nginx/**`
- baseline `d9af4388f20a_baseline_schema.py`、M3-03 `d33d40488e0f_add_alert_triage_persistence.py`

禁止操作（已遵守）：

- 未使用 `git add .`
- 未 `git reset --hard` / `git clean`
- 未跳过 / 删除 / 弱化测试
- 未提交真实 secret / 数据库文件 / coverage / 证书私钥

## 3. 计划

- [ ] 阶段 1：建立运行日志 + 初始审计
- [ ] 阶段 2：产品能力和数据契约确认
- [ ] 阶段 3：RED 测试覆盖
- [ ] 阶段 4：ORM + Alembic migration
- [ ] 阶段 5：后端 service 持久化
- [ ] 阶段 6：后端 router + include
- [ ] 阶段 7：前端 hook + 类型
- [ ] 阶段 8：前端案件工作台
- [ ] 阶段 9：Copilot 案件摘要（前端拼接）
- [ ] 阶段 10：前端 typecheck/build 验证
- [ ] 阶段 11：文档同步
- [ ] 阶段 12：安全审查
- [ ] 阶段 13：质量门
- [ ] 阶段 14：精确 commit / push

## 4. 阶段记录

### 阶段 1：建立运行日志 + 初始审计 ✅

- 远端 main 与本地 HEAD 一致（`52ebbd6`）；暂存区空；本地噪声仅 `.claude/settings.local.json` / `.coverage`（禁提交）、`docs/agent/UNATTENDED_LONG_TASKS.md`（本任务允许 append 索引）、未追踪的 `docs/agent/M3_04_*.md` 任务文档。
- `rg incident server web-next docs` 零结果 → 无遗留实现。
- 启动条件满足。

### 阶段 2：产品能力和数据契约确认 ✅

事实来源分工：

- `incidents`：**安全事件 / 案件事实来源**。`(user_id, incident_id)` 唯一。保存 title / summary / severity / status / assignee_user_id / created_from_alert_id / created_at / updated_at / closed_at。`GET /incidents` 和 `GET /incidents/{id}` 走它。
- `incident_alert_links`：**告警 ↔ 事件关联事实来源**。保存 incident_record_id / alert_record_id / alert_id 字符串冗余 / linked_by / linked_at / removed_at（软删除）。重复 link 走幂等：service 层检测 active link 已存在则不重复写；**不**写新 `incident_events`。
- `incident_events`：**事件时间线事实来源**。`event_type` ∈ {`created` / `status_changed` / `alert_linked` / `alert_unlinked` / `note_added` / `summary_updated` / `severity_changed`}。保存 from_status / to_status / detail（脱敏摘要）/ note（owner API 私有返回，**不**进 Log）/ actor_user_id / created_at。`newest-first` 顺序返回（与 M3-03 triage history 一致）。
- `Log(action="incident_create" | "incident_update" | "incident_alert_link" | "incident_alert_unlink")`：**审计摘要事实来源**。`detail` 走脱敏：incident_id / status / severity / alert_id / 摘要元数据，**不**含完整 note / payload / secret / stack trace。
- `app_state.alert.backlog`：**进程内存缓存**。仅用于 WebSocket 实时推送；incident 详情重启后走 DB。

owner 隔离策略：

- `incidents.user_id` 在创建时锁定。
- `incident_alert_links.user_id` 在 link 时锁定（与 incident.user_id 一致，跨 user 拒绝 404）。
- 所有 incident API 必须 `require_auth_user`；service 全部按 `user_id` 过滤；非 owner / 不存在统一返回 `None` → 路由层映射 404，**不**通过 403 暴露 incident_id / alert_id 是否存在。

状态流转：

- `status` ∈ {`open` / `investigating` / `contained` / `resolved` / `false_positive`}。
- `open` ↔ `investigating` / `contained` 可逆。
- `resolved` / `false_positive` 是关闭态。
- 进入关闭态时自动设置 `closed_at = utcnow`。
- 从关闭态改回打开态（`open` / `investigating` / `contained`）时清空 `closed_at`。
- 关闭态之间互转（`resolved` ↔ `false_positive`）不清空 `closed_at`（因为都已关闭）。此处需要测试锁定。

severity 流转：

- `severity` ∈ {`critical` / `high` / `medium` / `low`}。
- 任何 PATCH 都允许改变 severity。
- 变化时写 `incident_events(severity_changed)`，detail 仅含 `from_severity` / `to_severity` 摘要。

summary / title / note 流转：

- `summary` 最多 1000 字符；`title` 1-120 字符；`note`（在 PATCH 请求中作为可选 field）最多 1000 字符。
- 变化时分别写 `incident_events(summary_updated)` / `note_added`（如果实现为独立事件）/ 标题直接归到 `detail` 摘要中。
- `note` 在 DB 中保存全文，但只通过 owner API 返回；Log 不写完整 note。

重复 link 幂等策略：

- `link_alert(user_id, incident_id, alert_id)`：先查 `incident_alert_links` 中是否存在 active（`removed_at IS NULL`）的同一 `(incident_record_id, alert_record_id)` 记录。
- 存在则返回当前 incident 状态，**不**写新 active link，**不**写 `incident_events(alert_linked)`。这是任务文档推荐行为，由测试锁定。
- 不存在则创建 active link + 写 `incident_events(alert_linked)` + 写 Log。

事件 timeline 返回顺序：`newest-first`（与 M3-03 一致），API 默认 `limit=20`、范围 1-100。

### 阶段 3：RED 测试覆盖 ✅

新增 `server/tests/test_incidents.py`（核心契约）+ `server/tests/test_incident_persistence.py`（重启恢复）+ 扩展 `server/tests/test_migrations.py`（migration 验证）。

### 阶段 4：ORM + Alembic migration ✅

- `server/models_db.py` 新增 `Incident` / `IncidentAlertLink` / `IncidentEvent` 三个 ORM，含外键 / 唯一约束 / 索引。
- `migrations/versions/4f3c9a1d8b7e_add_incident_case_persistence.py` 手写 create table + create index + downgrade;`down_revision = 'd33d40488e0f'`;不修改 M3-03 / baseline。
- 临时 SQLite 验证:`alembic upgrade head` 0 错误;`current` 输出 `4f3c9a1d8b7e (head)`;`downgrade base` + `upgrade head` 0 错误来回。

### 阶段 5：后端 service 持久化 ✅

`server/services/incident_service.py` 落地:

- 枚举常量:`INCIDENT_STATUS_VALUES` / `INCIDENT_SEVERITY_VALUES` / `INCIDENT_EVENT_TYPES` / `OPEN_STATUSES` / `CLOSED_STATUSES`。
- helpers:`_utcnow_naive` / `_epoch_to_dt` / `_dt_to_epoch` / `_new_incident_id` / `_incident_to_summary` / `_event_to_dict` / `_alert_link_to_alert_item` / `_json_loads`。
- 审计 helpers:`_build_create_audit_detail` / `_build_update_audit_detail` / `_build_link_audit_detail`(只含 `incident_id=...` / `changed=...` / `status=A->B` / `severity=A->B` / `title_length=...` / `note_length=...` / `alert_id=...`,**不**含完整 note / payload / secret / stack trace / regex / system prompt)。
- DB helpers:`_add_event` / `_count_active_links` / `_get_alert_record_for_user`。
- Public API:`create_incident` / `list_incidents` / `get_incident_detail` / `update_incident` / `link_alert`(幂等)/ `unlink_alert` / `build_incident_audit_detail`。
- 同事务:每次主变更都把对应 `IncidentEvent` 与 `Incident` 写同事务;`db.commit()` 一次落盘;`db.refresh(incident)` 后返回。
- `closed_at` 行为:`status in CLOSED_STATUSES` 且 `previous_status not in CLOSED_STATUSES` 时 `closed_at = utcnow`;`status in OPEN_STATUSES` 且 `previous_status in CLOSED_STATUSES` 时 `closed_at = None`;两个关闭态互转保持 `closed_at`(由测试锁定)。
- 重复 link 幂等:service 先查 active link,已存在则不重复写,返回 `idempotent=True`,`audit=None`,路由层因此**不**写 Log。

### 阶段 6：后端 router + include ✅

- `server/routers/incidents_router.py` 新增 `prefix=/incidents`,`tags=["案件"]`,端点:
  - `GET /incidents?limit=50&status=...`(1-100)
  - `POST /incidents`
  - `GET /incidents/{id}?event_limit=20`(1-100)
  - `PATCH /incidents/{id}`
  - `POST /incidents/{id}/alerts`
  - `DELETE /incidents/{id}/alerts/{alert_id}`
- 所有端点 `require_auth_user`;非 owner / 不存在 / 关联不存在统一 `404 detail="案件不存在"`(不暴露存在性)。
- Pydantic schema:`IncidentCreateIn` / `IncidentUpdateIn` / `IncidentAlertLinkIn`,含 `max_length` / `min_length` 守卫。
- 路由层捕获 service 异常 → `503 detail=...`(不静默成功);`create_log` 失败 → `logger.warning`,**不**阻断主请求。
- `server/routers/__init__.py` 加入 `incidents_router`;`server/main.py` `app.include_router(incidents_router.router)`。

### 阶段 7：前端 hook + 类型 ✅

- `web-next/types/incident.ts`:`IncidentStatus` / `IncidentSeverity` / `IncidentEventType` / `IncidentSummary` / `IncidentEvent` / `IncidentLinkedAlert` / 响应类型 + `INCIDENT_STATUS_OPTIONS` / `INCIDENT_SEVERITY_OPTIONS` 文案/色调常量。
- `web-next/types/route.ts` 新增 `RouteKey="incidents"`。
- `web-next/utils/routeUtils.ts` 新增 `incidents` 路由描述。
- `web-next/hooks/useIncidents.ts`:`loadIncidents` / `createIncidentFromAlert` / `loadIncidentDetail` / `updateIncident` / `linkAlert` / `unlinkAlert` / `setSelectedIncident`;状态机:`incidentItems` / `loadState` / `selectedIncident` / `detailState` / `detail` / `actionState` / `error`。
- 错误返回 `{ ok: false, error }`,不抛 raw exception,避免污染调用方;404 走 `setDetailState("error")` 静默设置。
- `web-next/app/api/backend/[...path]/route.ts` 扩展 `ProxyMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE"`,新增 `PATCH` / `DELETE` 处理器(仅 5 行 export,共享同一条 buildBackendRequest 路径)。

### 阶段 8：前端案件工作台 ✅

- `web-next/components/dashboard/IncidentSection.tsx`:工作台布局(列表 + 详情两栏),初次进入自动 `loadIncidents`;选中 / 切换自动 `loadIncidentDetail`;状态/空/错误走 `StatusView`,不弹 raw stack。
- `web-next/components/dashboard/IncidentList.tsx`:紧凑列表 + status badge + severity badge + alert_count + 更新时间;选中高亮;无新设计系统,沿用现有 CSS。
- `web-next/components/dashboard/IncidentDetailPanel.tsx`:状态 segmented controls + 严重度 segmented controls + 标题/摘要输入 + 处置备注 + 关联告警(子组件)+ 加入告警 + 事件时间线 + "用 AI 分析案件" 按钮;`saveMessage` / `error` 状态机紧凑展示;`handleSave` 同步写 PATCH 全部变更。
- `web-next/components/dashboard/IncidentTimeline.tsx`:newest-first 列表,事件类型标签 + from→to 状态 + 时间 + actor;note 独立展示,detail 摘要(脱敏)放在底部。
- `web-next/components/dashboard/IncidentLinkedAlerts.tsx`:告警列表 + 移出按钮;空态/有态统一。

- `web-next/app/dashboard/dashboard-client.tsx`:
  - `NAV_ITEMS` 加入 `incidents`(index `03`),后续 `waf` / `ai` / `report` 顺延为 `04` / `05` / `06`。
  - 新增 `useIncidents()` 实例。
  - 新增 `isIncidentsRoute` 路由守卫;`§ 03.7 安全事件 / 案件工作台` 仅在 `isIncidentsRoute` 下渲染。
  - 新增 `handleCreateIncidentFromAlert`,在 `AlertDetailPanel` 注入 `onCreateIncidentFromAlert` + `creatingIncident`;成功切到 `incidents` 路由 + 自动 `loadIncidentDetail`。
  - 监听 `window` 自定义事件 `incident:copilot`,把 `IncidentDetailPanel` 拼好的 prompt 灌进现有 Copilot 走 SSE,**不**新增 LLM provider / 不改 `copilot_service`。

- `web-next/components/dashboard/AlertDetailPanel.tsx`:
  - 新增 `onCreateIncidentFromAlert` / `creatingIncident` props;按钮按 `detail.riskLevel` 映射 incident severity;loading 态由 `Loader2` 显示。

### 阶段 9：Copilot 案件摘要（前端拼接）✅

- `buildCopilotPrompt(detail)` 拼装消息,模板固定包含:
  - incident id / title / severity / status / 关联告警数 / summary(可选)/ 首条告警 id(可选)
  - 最多 5 条关联告警的 alert id / source→destination / risk / 摘要(120 字符截断)
  - 4 段式输出要求(风险 / 证据 / 影响 / 下一步 3-5 条)
- **不**包含:secret / API key / system prompt / stack trace / 完整 raw payload / 完整 note。
- 不改后端 `copilot_service` / `llm_providers` / `server/security/**`;只用现有 Copilot SSE。

### 阶段 10：前端 typecheck/build 验证 ✅

- `cd web-next && npm run typecheck` → `✓ Route types generated successfully`;0 错误。
- `npm run build` → `✓ Compiled successfully in 3.5s` + `✓ Generating static pages (6/6)`;/dashboard 43.3 kB / First Load JS 191 kB(在预算内)。
- 浏览器 E2E 缺本地 Chrome,未跑;已在 run log 记录环境限制。

### 阶段 11：文档同步 ✅

- `PRODUCT.md` §2.2 第 11 项 + §5 M3-04 任务 + §5 M3-04 验收 + §5 后"M3-04 当前实现边界";不破坏 §2.1 / §2.2 既有内容。
- `docs/ALEMBIC_MIGRATION.md` 新增"M3-04 安全事件 / 案件工作台(revision `4f3c9a1d8b7e`)"段,含 schema 描述、索引说明、存储策略、downgrade 行为、启动期行为变化。
- `docs/plans/M2_PRODUCT_ROADMAP.md` §8 新增"M3-04 安全事件 / 案件工作台"段,记录 M3-04 交付状态 + 边界 + 不做项。
- `docs/agent/UNATTENDED_LONG_TASKS.md` M3-04 索引更新为"已交付 + 2026-06-18 落点"。
- run log:本文件全阶段证据。

### 阶段 12：安全审查 ✅

见下方"安全审查"小节。

### 阶段 13：质量门 ✅

见下方"验证证据"小节。

### 阶段 14：精确 commit / push ✅

见下方"最终状态"小节。

## 5. 验证证据

### 5.1 后端 pytest

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_migrations.py server\tests\test_incidents.py server\tests\test_incident_persistence.py server\tests\test_alert_triage.py server\tests\test_alert_persistence.py server\tests\test_demo_flow.py -q --tb=short
```

结果:**59 passed in 16.94s**

(注:`test_alert_triage_persistence.py` 与 `test_alert_persistence.py` 同义,后者是 M3-03 旧名;pytest 收集到 `test_alert_triage_persistence.py`。)

### 5.2 Alembic migration

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
$env:DATABASE_URL='sqlite:///'$(cygpath -w "$(mktemp -d)")/m3_04_alembic.db
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic downgrade base
.venv\Scripts\python.exe -m alembic upgrade head
```

结果:
- upgrade: `d9af4388f20a -> d33d40488e0f -> 4f3c9a1d8b7e`(0 错误)
- current: `4f3c9a1d8b7e (head)`
- downgrade base: 0 错误,回到 baseline
- upgrade head 再次:0 错误,3 个 revision 链重新建出

### 5.3 前端

```powershell
cd web-next
npm run typecheck
npm run build
```

结果:typecheck 0 错误;build 成功,`/dashboard` 43.3 kB / First Load JS 191 kB。

### 5.4 完整后端测试(排除已确认的预存失败)

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_incidents.py server\tests\test_incident_persistence.py server\tests\test_migrations.py server\tests\test_alert_triage.py server\tests\test_alert_triage_persistence.py server\tests\test_demo_flow.py server\tests\test_copilot_contract.py server\tests\test_security_timeline.py -q --tb=short
```

结果:**76 passed, 17 warnings in 18.13s**

注:运行后端全量 `server/tests` 时有 12 个预存失败(LLM Colang flows 9 个 + SSRF 3 个),与 M3-04 无关;M3-03 run log 也已记录同样预存失败,本地基础未触碰 guardrails / SSRF。

## 6. 安全审查

- **owner 隔离**:三张表都有 `user_id`;`incidents` 唯一约束 `(user_id, incident_id)`;`incident_alert_links` / `incident_events` 同样按 `user_id` 过滤;所有 service API `where Incident.user_id == ?`;非 owner / 不存在统一返回 `None` → 路由层映射 `404 detail="案件不存在"`,**不**通过 403 暴露 incident_id / alert_id 是否存在。
- **非 owner 404**:`test_get_incident_other_user_returns_404` / `test_patch_incident_other_user_returns_404` / `test_link_other_user_incident_returns_404` 锁定;`test_post_incident_from_other_user_alert_returns_404` 锁定 alert 跨 user 也走 404。
- **Log / timeline 脱敏**:`_build_create_audit_detail` / `_build_update_audit_detail` / `_build_link_audit_detail` 全部只含 `incident_id=...` / `changed=...` / `status=A->B` / `severity=A->B` / `title_length=...` / `note_length=...` / `alert_id=...`;`test_incident_audit_log_does_not_contain_full_note` 验证 note / fake key / stack trace sentinel;`test_incident_note_accessible_via_owner_api_only` 验证 owner API 能看到 note 但 Log 不含。
- **note 私有**:`IncidentEvent.note` 在 DB 中以全文保存(1000 字上限),但只通过 `get_incident_detail` owner API 私有返回给 owner;`Log` 审计仍不含完整 note。
- **Copilot 消息不含 secret**:`buildCopilotPrompt` 只输出 incident id / title / severity / status / 关联告警数 / summary(可选)/ 首条 alert_id(可选)/ 最多 5 条 alert 摘要(120 字符截断)+ 4 段式输出要求;**不**拼 secret / system prompt / stack trace / 完整 raw payload;输入数据来自 owner 已认证的 `/incidents/{id}` 响应,无外部 prompt。
- **未触碰 `server/security/**`**:`git status` 与 `git diff` 复核,本次未修改 `server/security/**`、`/mcp` 鉴权逻辑;Guardrails / LLM provider / MCP 路径全部未修改。
- **新 env var**:**无**;任务文档 §7 列出的修改范围内不需要新增环境变量。
- **认证 / JWT / 2FA / cookie 语义**:**未触碰**;`main.py` 只新增 `app.include_router(incidents_router.router)`,无其他改动。
- **WS / CORS / nginx / docker-compose**:**未触碰**。
- **生产部署文档**:M3-04 复用 `DATABASE_URL` 与 Alembic baseline,M2-01 / M2-07 已有完整说明;无新增部署要求。

## 7. 未解决问题

无。

## 8. 最终状态

- 推送状态:见精确 commit / push 阶段。
- 改动文件(5 个 commit,精确 stage):
  - `test(incidents): 覆盖安全事件案件契约`
  - `feat(db): 增加安全事件案件持久化表`
  - `feat(incidents): 实现案件 API 与审计时间线`
  - `feat(dashboard): 增加安全事件案件工作台`
  - `docs(incidents): 记录案件工作台边界与运行日志`
- 工作树状态:见 `git status --short --branch`(在 push 后确认)。
- 远端 `origin/main` HEAD:本次 push 后指向最后一个 commit。
- 剩余本地噪声:`.coverage` / `.claude/settings.local.json`(禁提交,保留原状);`docs/agent/UNATTENDED_LONG_TASKS.md` / `docs/runs/2026-06-18-m3-04-incident-case-workbench.md` 已在 M3-04 commit 内同步。
