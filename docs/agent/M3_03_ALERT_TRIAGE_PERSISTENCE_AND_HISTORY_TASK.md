# M3-03 告警研判持久化与历史记录 L5 超长任务

> 任务级别：L5，高风险数据库迁移 + SOC 产品能力战役。  
> 目标读者：接手本仓库的开发 agent。  
> 核心目标：把 M3-02 的告警研判状态从“当前进程内存 payload”升级为“数据库持久化 + 可查询历史 + 重启后可恢复”的 SOC 能力，同时保留现有 Dashboard 操作体验、所有权隔离和脱敏审计。

---

## 0. 背景

当前 M3-02 已经实现：

- `PATCH /alerts/{alert_id}/triage`
- 5 个研判状态：`new / investigating / contained / false_positive / resolved`
- `analyst_note` 800 字符上限
- 非 owner / 不存在统一 404
- `Log(action="alert_triage_update")` 脱敏审计
- Dashboard 研判面板、状态徽标、简报计数和 E2E 覆盖

但当前实现有明确边界：

- triage 状态保存在 `app_state.alert.backlog` 的 payload 中。
- 后端重启后 backlog 消失，triage 状态也消失。
- 多进程 / 多副本之间不共享。
- `Log` 只记录审计摘要，不是可查询的 triage 历史版本。

本任务要补上这条产品债：**安全分析员保存的研判状态和备注，重启后还应该存在；每次状态变化应该可查询。**

---

## 1. 启动前必读

执行前完整阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`
- `docs/agent/M3_02_ALERT_TRIAGE_RESPONSE_WORKBENCH_TASK.md`
- `docs/runs/2026-06-17-m3-02-alert-triage-response-workbench.md`
- `docs/ALEMBIC_MIGRATION.md`
- `docs/runs/2026-06-17-m2-01-database-url-alembic-baseline.md`

必须阅读当前实现：

- `server/models_db.py`
- `server/models/schemas.py`
- `server/core/database.py`
- `server/core/state.py`
- `server/services/alert_service.py`
- `server/routers/alerts_router.py`
- `server/tests/test_alert_triage.py`
- `server/tests/test_migrations.py`
- `migrations/env.py`
- `migrations/versions/d9af4388f20a_baseline_schema.py`
- `web-next/types/alert.ts`
- `web-next/hooks/useAlerts.ts`
- `web-next/utils/alertUtils.ts`
- `web-next/components/dashboard/AlertTriagePanel.tsx`
- `web-next/components/dashboard/AlertDetailPanel.tsx`
- `web-next/components/dashboard/AttackLogTable.tsx`
- `web-next/components/dashboard/BriefingSection.tsx`

如果实际代码与文档不一致，以当前代码和测试为准，并在运行日志记录差异。

---

## 2. 产品能力定义

作为安全分析员，我保存一条告警的研判状态和处置备注后，即使后端重启或当前内存 backlog 清空，我再次进入 Dashboard 仍能看到这条告警和它的最新研判状态；我还能查看这条告警的研判历史，知道谁在什么时候把状态从什么改成什么。

目标闭环：

```text
告警生成 -> 写入数据库 alert_records -> Dashboard 获取告警
       -> 更新 triage -> 写入最新 triage + triage history
       -> 写 Log 脱敏审计 -> 重启后 GET /alerts 仍可恢复
```

---

## 3. 非目标

本任务不做：

- 不做完整企业级工单系统。
- 不做 SLA、负责人分派、批量处置、通知升级、Jira/Slack 集成。
- 不改登录、授权、session、cookie、JWT、2FA 语义。
- 不改 `server/security/**` 或 LLM Guardrails 策略。
- 不引入新数据库框架。
- 不删除旧的内存 backlog；WebSocket 实时体验仍可继续使用 backlog。
- 不迁移旧本地 `data/app.db` 的历史内存告警，因为旧告警本来没有持久化来源。
- 不把审计日志当作唯一历史来源。

---

## 4. 架构决策

### 4.1 新增数据库事实来源

新增两张表：

1. `alert_records`
   - 每条告警的持久化快照。
   - 按 `user_id + alert_id` 唯一。
   - 保存 raw alert JSON、LLM analysis JSON、analysis error、processed_at、最新 triage。
   - 用于 `GET /alerts` 重启后恢复。

2. `alert_triage_events`
   - 每次 triage 状态变化的历史事件。
   - 按 alert record 关联。
   - 保存 from/to 状态、disposition、analyst_note、updated_by、created_at。
   - 用于历史查询。

推荐字段：

`alert_records`：

- `id: int primary key`
- `alert_id: string(64), nullable=false`
- `user_id: int foreign key users.id ondelete=CASCADE, nullable=false`
- `raw_alert_json: text, nullable=false`
- `llm_analysis_json: text, nullable=true`
- `analysis_error: text, nullable=true`
- `processed_at: datetime, nullable=false`
- `triage_status: string(32), nullable=false, default='new'`
- `triage_disposition: string(64), nullable=true`
- `triage_note: text, nullable=true`
- `triage_updated_at: datetime, nullable=true`
- `triage_updated_by: int foreign key users.id ondelete=SET NULL, nullable=true`
- `created_at / updated_at`

约束和索引：

- unique: `(user_id, alert_id)`
- index: `(user_id, processed_at)`
- index: `(user_id, triage_status, processed_at)`
- index: `alert_id`

`alert_triage_events`：

- `id: int primary key`
- `alert_record_id: int foreign key alert_records.id ondelete=CASCADE`
- `user_id: int foreign key users.id ondelete=CASCADE`
- `alert_id: string(64), nullable=false`
- `from_status: string(32), nullable=true`
- `to_status: string(32), nullable=false`
- `disposition: string(64), nullable=true`
- `analyst_note: text, nullable=true`
- `updated_by: int foreign key users.id ondelete=SET NULL`
- `created_at: datetime`

约束和索引：

- index: `(user_id, alert_id, created_at)`
- index: `(alert_record_id, created_at)`

### 4.2 JSON 存储策略

优先使用 `Text` 存 JSON 字符串，而不是强依赖 PostgreSQL JSONB。

原因：

- 当前默认开发库是 SQLite。
- Compose 使用 PostgreSQL。
- Alembic baseline 已走跨数据库路线。
- Text + `json.dumps(..., ensure_ascii=False)` 足够支撑本阶段。

实现要求：

- 新增小 helper：`_json_dumps` / `_json_loads_dict`。
- 反序列化失败时返回空 dict，并记录 warning，不让 `GET /alerts` 整体失败。
- 不在日志中打印完整 raw payload。

### 4.3 兼容内存实时路径

数据库是查询和持久化事实来源；内存 backlog 仍用于：

- WebSocket 实时推送。
- 当前进程短期缓存。
- 老测试或无数据库路径的兼容。

推荐行为：

- `process_alert` / `trigger_demo_attack` 创建 payload 后，写入 `alert_records`。
- `get_alerts(user_id, limit)` 优先读数据库；如果数据库读失败或没有记录，再回退内存 backlog，并记录 warning。
- `update_alert_triage` 先更新数据库和 history；成功后尝试同步内存 backlog 中对应 payload。内存同步失败不影响主请求。
- WebSocket 推送时 payload 应带最新 triage。

---

## 5. API 契约

保留：

```text
PATCH /alerts/{alert_id}/triage
GET /alerts
```

新增：

```text
GET /alerts/{alert_id}/triage/history?limit=50
```

历史响应建议：

```json
{
  "status": "ok",
  "alert_id": "<alert_id>",
  "items": [
    {
      "id": 123,
      "from_status": "new",
      "to_status": "investigating",
      "disposition": "needs_review",
      "analyst_note": "已确认 WAF 拦截生效。",
      "updated_by": 42,
      "created_at": 1781580000
    }
  ],
  "count": 1
}
```

安全要求：

- 必须 `require_auth_user`。
- 只能查当前用户自己的 alert。
- 非 owner / 不存在统一 404。
- `limit` 范围建议 1-100，默认 50。
- 历史 API 可以返回完整 `analyst_note`，因为这是用户自己的产品数据；但 Log / timeline 仍只写脱敏摘要。

---

## 6. 允许修改范围

后端：

- `server/models_db.py`
- `server/models/schemas.py`
- `server/services/alert_service.py`
- `server/routers/alerts_router.py`
- `server/core/state.py`
- `migrations/versions/**`
- `server/tests/test_alert_triage.py`
- `server/tests/test_alert_triage_persistence.py`
- `server/tests/test_migrations.py`
- `server/tests/test_demo_flow.py`
- `server/tests/test_security_timeline.py`

前端：

- `web-next/types/alert.ts`
- `web-next/hooks/useAlerts.ts`
- `web-next/utils/alertUtils.ts`
- `web-next/components/dashboard/AlertTriagePanel.tsx`
- `web-next/components/dashboard/AlertDetailPanel.tsx`
- `web-next/components/dashboard/AttackLogTable.tsx`
- `web-next/components/dashboard/BriefingSection.tsx`
- `web-next/app/dashboard/dashboard-client.tsx`
- 可新增 `web-next/components/dashboard/AlertTriageHistory.tsx`

文档：

- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`
- `docs/ALEMBIC_MIGRATION.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/runs/2026-06-18-m3-03-alert-triage-persistence-and-history.md`

---

## 7. 禁止修改范围

禁止修改：

- `.coverage`
- `.claude/settings.local.json`
- 真实 `.env`
- `.env.compose.local`
- `data/app.db`
- `server/security/**`
- 登录、授权、密码、session、cookie、JWT、2FA 语义
- `docker-compose.yml`
- `nginx/**`
- git history

禁止操作：

- 不要使用 `git add .`
- 不要 `git reset --hard`
- 不要 `git clean`
- 不要 force push
- 不要跳过、删除、弱化测试
- 不要提交真实 secret、数据库文件、coverage、证书私钥

---

## 8. 执行阶段

### 阶段 1：建立运行日志与初始审计

创建：

```text
docs/runs/2026-06-18-m3-03-alert-triage-persistence-and-history.md
```

初始命令：

```powershell
git status --short --branch
git rev-parse HEAD
git ls-remote origin refs/heads/main
git diff --cached --name-status
git log --oneline --decorate --max-count=8
```

记录：

- 当前分支。
- 本地 HEAD。
- 远端 main。
- 工作树已有噪声文件。
- 本任务允许/禁止范围。

如果远端前进、本地 ahead、或 staged 区不为空，先停止总结，不要开始改代码。

### 阶段 2：产品和数据契约确认

在运行日志写明：

- `alert_records` 是告警快照事实来源。
- `alert_triage_events` 是 triage 历史事实来源。
- `Log(action="alert_triage_update")` 继续作为 SOC 时间线审计摘要，不保存完整 note。
- `GET /alerts` 重启后来自 DB。
- 内存 backlog 只是实时缓存。

### 阶段 3：先写 RED 测试

新增或扩展：

```text
server/tests/test_alert_triage_persistence.py
```

至少覆盖：

1. `POST /alerts/demo` 后写入 `alert_records`。
2. 清空 `app_state.alert.backlog` 后，`GET /alerts` 仍能返回 DB 中的 demo alert。
3. `PATCH /alerts/{alert_id}/triage` 更新 DB 最新 triage。
4. 新 Session / 清空 backlog 后，`GET /alerts` 返回最新 triage。
5. 每次 triage 更新写入 `alert_triage_events`。
6. `GET /alerts/{alert_id}/triage/history` 返回当前用户历史。
7. 非 owner 查询 / 更新 triage 历史返回 404。
8. 审计 Log 仍不含完整 payload / 完整 note / secret。
9. DB 写入失败时主路径应明确失败或降级，不能 silent success。

迁移测试扩展：

- `server/tests/test_migrations.py` 必须验证 `alembic upgrade head` 后包含两张新表和关键索引。

运行 RED：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_alert_triage_persistence.py -q --tb=short
.venv\Scripts\python.exe -m pytest server\tests\test_migrations.py -q --tb=short
```

RED 必须来自功能缺失，不得来自语法错误或坏 fixture。

### 阶段 4：新增 ORM 模型与 Alembic migration

修改 `server/models_db.py`：

- 新增 `AlertRecord`
- 新增 `AlertTriageEvent`
- 保持字段命名清晰。
- 使用 `Text` 存 JSON。
- 添加关系可以有，但不要引入复杂 lazy loading 依赖。

新增 Alembic revision：

```powershell
.venv\Scripts\python.exe -m alembic revision -m "add alert triage persistence"
```

然后手写或调整 migration：

- create `alert_records`
- create `alert_triage_events`
- create unique constraint 和 indexes
- downgrade 必须 drop indexes / tables

运行：

```powershell
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m pytest server\tests\test_migrations.py -q --tb=short
```

不要编辑已经推送的 baseline migration。

### 阶段 5：后端服务持久化

在 `server/services/alert_service.py` 中实现：

- alert payload -> DB record 的序列化 helper。
- DB record -> backend alert payload 的反序列化 helper。
- `persist_alert_record(db, payload, user_id)`。
- `list_alert_records(user_id, limit, db)`。
- `update_alert_triage(...)` 改为 DB 事务更新 + 写 history + 写 Log 摘要。
- `get_alert_triage_history(user_id, alert_id, limit, db)`。
- `get_alerts(user_id, limit, db)` 优先从 DB 读取，必要时回退 backlog。

注意：

- 当前 `get_alerts` 路由没有注入 db，需要改为 `db: Session = Depends(get_db)`。
- demo attack 当前有 db，可直接持久化。
- worker 处理 ingest alert 时需要打开 `SessionLocal()` 持久化。
- 持久化失败不能伪装成功；对于 demo / worker，运行日志写明选择：
  - demo 主请求建议失败返回 503，因为用户期待可恢复。
  - worker ingest 可记录 error 并避免广播未持久化状态，或明确标记 degraded。

### 阶段 6：后端路由与契约

修改 `server/routers/alerts_router.py`：

- `GET /alerts` 注入 db。
- `PATCH /alerts/{alert_id}/triage` 调用 DB-backed service。
- 新增 `GET /alerts/{alert_id}/triage/history`。

错误语义：

- 未登录：401。
- 非 owner / 不存在：404。
- 无效 limit / body：422。
- DB 不可用：503 或项目现有异常约定。

后端 GREEN：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_alert_triage.py -q --tb=short
.venv\Scripts\python.exe -m pytest server\tests\test_alert_triage_persistence.py -q --tb=short
.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow.py -q --tb=short
.venv\Scripts\python.exe -m pytest server\tests\test_security_timeline.py -q --tb=short
```

### 阶段 7：前端历史展示

前端最小可用目标：

- 当前 `AlertTriagePanel` 继续可保存状态和备注。
- 保存后状态来自后端返回。
- `AlertDetailPanel` 或 `AlertTriagePanel` 显示最近 triage 历史（最多 5 条）。
- 历史加载失败时显示低调错误态，不影响保存。
- 不做大面积 UI 重构。

建议新增：

```text
web-next/components/dashboard/AlertTriageHistory.tsx
```

建议扩展：

- `web-next/types/alert.ts` 增加 `AlertTriageEvent`。
- `useAlerts` 增加 `loadTriageHistory(alertId)` 或在面板组件内部 fetch。
- API 路径：`/api/backend/alerts/{alert_id}/triage/history`。

UI 要求：

- 紧凑，不用大卡片套卡片。
- 移动端不溢出。
- 历史 note 如果很长，要截断或折行。
- 不展示后端 stack trace。

### 阶段 8：前端验证

运行：

```powershell
cd web-next
npm run typecheck
npm run build
cd ..
```

如果改动明显影响 Dashboard，尽量启动本地服务并用浏览器验证：

```text
登录 -> 触发 Demo -> 保存 triage -> 刷新页面 -> 仍看到 triage
```

如果无法浏览器验证，必须记录环境原因。

### 阶段 9：重启恢复验证

必须有自动化验证证明“不是内存假象”。

推荐测试方式：

- 创建 demo alert。
- 保存 triage。
- 清空 `app_state.alert.backlog`。
- 使用同一个临时 SQLite DB 新建 TestClient / 新 Session。
- `GET /alerts` 仍返回 alert。
- triage 状态仍是保存后的状态。
- history endpoint 返回事件。

这条测试是本任务的核心验收，不允许省略。

### 阶段 10：文档同步

更新 `PRODUCT.md`：

- M3-02 当前边界从“内存 backlog”改为“M3-03 后 DB 持久化”。
- 风险登记中说明 alert payload JSON 存储策略和当前非目标。

更新 `docs/plans/M2_PRODUCT_ROADMAP.md`：

- M3-02 边界改写。
- 新增 M3-03 交付状态或后续任务记录。

更新 `docs/ALEMBIC_MIGRATION.md`：

- 新增 migration 说明。
- 说明如何在本地和 Compose 中运行 `alembic upgrade head`。
- 说明 downgrade 仅开发/测试使用，生产回滚走 forward migration。

更新 `docs/agent/UNATTENDED_LONG_TASKS.md`：

- 添加本任务索引。

运行日志必须记录所有验证命令和结果。

### 阶段 11：安全审查

运行日志中必须回答：

- alert ownership 是否完全由 `user_id + alert_id` 限制。
- 非 owner 是否统一 404。
- history endpoint 是否也按 owner 隔离。
- `analyst_note` 是否仍有 800 字符上限。
- Log / timeline 是否仍不含完整 note、完整 payload、secret、stack trace、regex、system prompt。
- DB 是否存储完整 note；若是，说明它是用户私有产品数据，只通过认证 API 返回。
- 是否新增 env var；如果没有，明确写“无”。
- 是否触碰 `server/security/**`；如果没有，明确写“未触碰”。

### 阶段 12：质量门

按顺序运行：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_migrations.py -q --tb=short
.venv\Scripts\python.exe -m pytest server\tests\test_alert_triage.py -q --tb=short
.venv\Scripts\python.exe -m pytest server\tests\test_alert_triage_persistence.py -q --tb=short
.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow.py -q --tb=short
.venv\Scripts\python.exe -m pytest server\tests\test_copilot_contract.py -q --tb=short
.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
cd web-next
npm run typecheck
npm run build
cd ..
git diff --check
```

如果触碰 `server/security/**` 或 Guardrails，必须加跑：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

本任务原则上不应触碰这些路径。

### 阶段 13：提交与 push

允许所有质量门通过后 commit / push。

只允许精确 stage。

推荐拆分：

1. `test(alerts): 覆盖研判持久化与历史契约`
2. `feat(db): 增加告警研判持久化表`
3. `feat(alerts): 持久化告警研判状态与历史`
4. `feat(dashboard): 展示告警研判历史`
5. `docs(alerts): 记录研判持久化边界和运行日志`

每次 commit 前：

```powershell
git diff --cached --name-status
git diff --cached --check
```

push 前：

```powershell
git status --short --branch
git log --oneline origin/main..HEAD
git log --name-only --format="commit %h %s" origin/main..HEAD -- .coverage .claude/settings.local.json .env .env.compose.local data/app.db
git ls-remote origin refs/heads/main
```

满足以下条件才允许 push：

- 当前分支是 `main`。
- 远端未前进。
- 暂存区为空。
- 禁提交文件没有进入 commit。
- 质量门通过。
- 运行日志完整。

push：

```powershell
git push origin main
```

push 后：

```powershell
git rev-parse HEAD
git ls-remote origin refs/heads/main
git status --short --branch
```

---

## 9. 停止条件

遇到任一情况必须停止：

- 远端 `origin/main` 已前进，需要 merge/rebase。
- migration 需要 destructive 数据迁移。
- 需要修改认证、授权、session、cookie、JWT、2FA。
- 需要修改 `server/security/**`。
- 同一测试连续修复 3 轮仍失败。
- 重启恢复测试无法实现。
- 无法运行 Alembic 或 pytest，且不是代码内可修复问题。
- `.coverage`、`.claude/settings.local.json`、真实 `.env`、数据库文件被 staged。
- diff 超过约 1200 行且不是测试/文档/migration 合理增长。

停止时输出：

- 已完成阶段。
- 阻塞证据。
- 当前 `git status --short --branch`。
- 下一条最小工单。

---

## 10. 最终报告格式

完成后用中文输出：

```text
完成状态：完成 / 部分完成 / 阻塞
推送状态：已 push / 未 push / 阻塞未 push

核心能力：
- 告警是否持久化：
- triage 最新状态是否持久化：
- triage history 是否可查询：
- 重启/清空 backlog 后是否恢复：

提交：
- <hash> <message>

验证：
- <命令>: <结果>

安全审查：
- owner 隔离：
- 非 owner 404：
- 日志脱敏：
- secret / env：

运行日志：
- docs/runs/2026-06-18-m3-03-alert-triage-persistence-and-history.md

最终状态：
- git status:
- HEAD:
- origin/main:
- 剩余本地噪声：
```
