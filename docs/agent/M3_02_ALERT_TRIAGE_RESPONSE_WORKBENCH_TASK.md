# M3-02 告警研判与处置工作台超长任务

> 任务级别：L5 无人值守产品能力战役。
> 适用场景：M3 Demo-Ready SOC 工作台已推送到 `origin/main`，下一步要把“看见告警”升级为“研判告警、记录处置、复制报告、留下审计证据”。
> 回复语言：中文。

---

## 0. 启动前必读

执行前完整阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`
- `docs/runs/2026-06-16-m3-demo-ready-soc-workbench.md`
- 本文件

还必须阅读当前实现面：

- `server/core/state.py`
- `server/services/alert_service.py`
- `server/routers/alerts_router.py`
- `server/tests/test_demo_flow.py`
- `server/tests/test_demo_flow_e2e.py`
- `web-next/hooks/useAlerts.ts`
- `web-next/types/alert.ts`
- `web-next/utils/alertUtils.ts`
- `web-next/types/alertBriefing.ts`
- `web-next/utils/alertBriefingUtils.ts`
- `web-next/components/dashboard/AlertSection.tsx`
- `web-next/components/dashboard/AlertDetailPanel.tsx`
- `web-next/components/dashboard/AttackLogTable.tsx`
- `web-next/app/dashboard/dashboard-client.tsx`

如果实际代码与文档不一致，以当前代码和测试为准，并在运行日志中记录差异。

---

## 1. 产品能力定义

作为安全分析员，我能在 Dashboard 中选择一条告警，将它从“新告警”推进到“研判中 / 已遏制 / 误报 / 已解决”，记录一段简短处置备注，复制一份包含风险、证据、建议动作和研判状态的事件报告，并且系统会为每次研判状态变化留下可审计记录。

这条任务的核心不是做企业级工单系统，而是把当前 demo 告警闭环升级成一个小型 SOC 分析闭环：

```text
告警出现 -> 选中告警 -> 查看证据 -> 设置研判状态 -> 保存处置备注 -> 复制事件报告 -> 审计日志可追踪
```

---

## 2. 非目标

本任务不做：

- 不引入数据库 schema / Alembic 迁移。
- 不做多租户、SLA、工单分派、通知升级、Jira/Slack 集成。
- 不修改认证、授权、密码、session、cookie、Guardrails 核心策略。
- 不修改 `.env.example`，除非实现中确实新增环境变量；本任务原则上不应新增 env var。
- 不改变现有 Demo Flow 的认证方式和 Copilot SSE 契约。
- 不把内存状态包装成生产级持久化承诺。

重要说明：本任务允许先把研判状态保存在当前进程的告警 backlog payload 中，并用 `Log` 写入审计事件。持久化、查询历史和跨重启恢复留给后续数据库迁移任务。

---

## 3. 状态与接口契约

### 3.1 研判状态

新增稳定状态枚举：

- `new`：新告警，尚未研判。
- `investigating`：研判中。
- `contained`：已遏制。
- `false_positive`：误报。
- `resolved`：已解决。

建议字段：

```json
{
  "status": "investigating",
  "disposition": "needs_review",
  "analyst_note": "已确认 WAF 拦截生效，继续观察同源 IP。",
  "updated_at": 1781580000,
  "updated_by": 42
}
```

`analyst_note` 上限建议 800 字符。前端要限制输入，后端也必须校验。

### 3.2 API

新增或扩展后端接口：

```text
PATCH /alerts/{alert_id}/triage
```

请求体：

```json
{
  "status": "contained",
  "disposition": "blocked_at_waf",
  "analyst_note": "已确认 WAF 拦截，暂无横向扩散证据。"
}
```

响应体建议：

```json
{
  "status": "ok",
  "alert_id": "<alert_id>",
  "triage": {
    "status": "contained",
    "disposition": "blocked_at_waf",
    "analyst_note": "已确认 WAF 拦截，暂无横向扩散证据。",
    "updated_at": 1781580000,
    "updated_by": 42
  },
  "alert": { "...": "更新后的告警 payload" }
}
```

`GET /alerts` 返回的每条告警也应包含 `triage` 字段；旧告警没有 triage 时，前端映射为 `new`。

### 3.3 安全与审计

必须满足：

- `PATCH /alerts/{alert_id}/triage` 必须使用 `require_auth_user`。
- 只能更新当前用户自己的告警。
- 告警不存在或不属于当前用户时返回 404，避免通过 403 暴露告警 ID 是否存在。
- 无效状态、过长备注、错误 body 返回 422。
- 审计日志使用 `Log(action="alert_triage_update")` 或同等现有日志机制。
- 审计 detail 不得记录完整 payload、完整 analyst_note、API key、stack trace、regex、system prompt。
- 可以记录 `alert_id`、`status`、`disposition`、`note_length`、`source_ip` 的脱敏摘要。

---

## 4. 允许修改范围

后端：

- `server/core/state.py`
- `server/services/alert_service.py`
- `server/routers/alerts_router.py`
- `server/models/schemas.py`（仅新增 Pydantic schema）
- `server/tests/test_alert_triage.py`
- `server/tests/test_demo_flow.py`
- `server/tests/test_demo_flow_e2e.py`

前端：

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
- `web-next/components/dashboard/**` 中为本任务新增的小组件
- `web-next/app/dashboard/dashboard-client.tsx`

文档与运行日志：

- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/runs/2026-06-17-m3-02-alert-triage-response-workbench.md`

---

## 5. 禁止修改范围

禁止修改：

- `.coverage`
- `.claude/settings.local.json`
- 真实 `.env`
- `server/security/**`
- 认证、授权、密码、NextAuth 语义
- 数据库 schema / migration / `models_db.py` 表结构
- `docker-compose.yml`
- `nginx/**`
- CI / deploy 配置

禁止操作：

- 不要使用 `git add .`
- 不要 `git reset --hard`
- 不要 `git clean`
- 不要删除、跳过、弱化测试
- 不要提交真实 secret、本地数据库、构建产物、coverage 产物

---

## 6. 执行阶段

### 阶段 1：建立运行日志与初始审计

创建：

```text
docs/runs/2026-06-17-m3-02-alert-triage-response-workbench.md
```

记录：

- 开始时间
- 当前分支与 `git status --short --branch`
- 当前 `HEAD`
- 远端 `origin/main`
- 任务边界
- 验证矩阵

初始命令：

```powershell
git status --short --branch
git rev-parse HEAD
git ls-remote origin refs/heads/main
git diff --cached --name-only
```

如果分支不是 `main`，或远端已前进，停止并报告。

### 阶段 2：先写 RED 测试

先新增后端测试 `server/tests/test_alert_triage.py`，至少覆盖：

1. 当前用户可以更新自己的告警 triage。
2. 更新后 `GET /alerts` 能返回 triage。
3. 其他用户更新同一 `alert_id` 返回 404。
4. 未登录请求返回 401 或项目当前依赖默认错误。
5. 无效 status 返回 422。
6. 过长 `analyst_note` 返回 422。
7. 审计日志会记录状态变化，但不包含完整 payload 或完整 note。

运行并记录 RED：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_alert_triage.py -q --tb=short
```

RED 必须来自缺失功能或契约不满足，不能来自语法错误、导入错误或测试夹具坏掉。

### 阶段 3：实现后端最小闭环

建议实现方式：

- 在 `server/models/schemas.py` 新增 triage 请求/响应 schema。
- 在 `server/core/state.py` 为 `AlertState` 增加在 lock 内按 `alert_id` 更新 payload 的方法。
- 在 `server/services/alert_service.py` 增加：
  - 默认 triage 构造函数。
  - `update_alert_triage(user_id, alert_id, data, db)`。
  - `get_alerts` 返回时确保旧告警带默认 triage。
  - demo / process alert 创建时附带默认 triage。
- 在 `server/routers/alerts_router.py` 增加 `PATCH /alerts/{alert_id}/triage`。
- 日志写入失败不得破坏主请求，但必须记录 warning。

后端 GREEN：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_alert_triage.py -q --tb=short
.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow.py -q --tb=short
.venv\Scripts\python.exe -m pytest server\tests\test_security_timeline.py -q --tb=short
```

### 阶段 4：前端产品化

前端要完成一个真正可用的 SOC 工作台体验：

- 告警列表显示 triage 状态徽标。
- 详情面板显示当前研判状态、处置备注和更新时间。
- 使用图标按钮或紧凑 segmented controls 切换状态，不做营销式大卡片。
- 保存按钮有 loading / success / error 状态。
- 复制报告内容包含 triage 状态、处置备注摘要、风险、证据、影响、建议动作。
- 日/周简报增加“待研判 / 研判中 / 已闭环”计数，但必须从真实 alert triage 派生。
- 离线或保存失败时不丢失当前输入。
- 移动端不重叠、不溢出、不把按钮挤成不可读文字。

建议新增组件：

- `web-next/components/dashboard/AlertTriagePanel.tsx`
- 或把小控件拆成 `AlertTriageControls.tsx`

建议新增 data-testid：

- `alert-triage-panel`
- `triage-status-new`
- `triage-status-investigating`
- `triage-status-contained`
- `triage-status-false-positive`
- `triage-status-resolved`
- `triage-note-input`
- `triage-save`
- `triage-status-badge`

### 阶段 5：前端验证与浏览器路径

运行：

```powershell
cd web-next
npm run typecheck
npm run build
cd ..
```

不要并行运行 `npm run typecheck` 和 `npm run build`，避免 `.next/types` 竞争。

如果本地 Chrome 可用，扩展 `server/tests/test_demo_flow_e2e.py` 或新增显式 E2E 覆盖：

```text
注册/登录 -> Dashboard -> 触发 Demo -> 选中新告警 -> 切换为研判中 -> 保存备注 -> 状态徽标可见 -> 复制报告仍可用
```

显式 E2E 命令：

```powershell
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow_e2e.py --run-e2e -q -rs --tb=short
```

如果因为本地缺浏览器无法运行，记录 skip/blocked 原因。不要谎称通过。

### 阶段 6：文档同步

更新 `PRODUCT.md`：

- 在 M3 章节补充 M3-02 告警研判与处置工作台。
- 明确当前 triage 状态是进程内 backlog + 审计日志，不是跨重启持久化工单系统。
- 在下一批任务中保留数据库迁移 / Alembic 持久化作为后续。

更新 `docs/agent/UNATTENDED_LONG_TASKS.md`：

- 把本任务列入可复用超长任务文档。

运行日志必须写明：

- RED 证据
- GREEN 证据
- 前端验证结果
- E2E 是否运行
- 安全审查结果
- 提交拆分计划

### 阶段 7：全量质量门

按顺序运行：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_alert_triage.py -q --tb=short
.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow.py -q --tb=short
.venv\Scripts\python.exe -m pytest server\tests\test_copilot_contract.py -q --tb=short
.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
cd web-next
npm run typecheck
npm run build
cd ..
git diff --check
```

如果改动触及 LLM / Guardrails / `server/security/**`，还必须运行：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

本任务原则上不应触及这些路径。

### 阶段 8：安全审查

在运行日志中写一节安全审查，至少回答：

- alert ownership 是否按 user_id 限制。
- 非 owner 是否返回 404。
- analyst_note 是否有长度限制。
- 审计日志是否避免写入完整 payload / note / secret。
- 前端是否会显示后端 stack trace。
- 是否修改了认证/授权语义。
- 是否新增 env var 或 secret。

### 阶段 9：提交与 push

允许在所有验证通过后 commit 和 push。

只允许精确 stage，不允许 `git add .`。

推荐拆分：

1. `test(alerts): 增加告警研判状态契约测试`
2. `feat(alerts): 增加告警研判状态接口`
3. `feat(dashboard): 增强告警研判与处置工作台`
4. `test(e2e): 覆盖告警研判工作流`
5. `docs: 记录 M3-02 告警研判工作台`

如果最终只适合 3-4 个 commit，可以合并相近提交，但必须保持：

- 测试
- 后端能力
- 前端体验
- 文档/运行日志

每次 commit 前运行：

```powershell
git diff --cached --name-only
```

确认 staged 文件只属于当前 commit。

push 前运行：

```powershell
git status --short --branch
git log --oneline origin/main..HEAD
git log --name-only --format="commit %h %s" origin/main..HEAD -- .coverage .claude/settings.local.json
git ls-remote origin refs/heads/main
```

只有满足以下条件才允许 push：

- 当前分支是 `main`
- 远端 `origin/main` 没有前进
- 暂存区为空
- `.coverage` 和 `.claude/settings.local.json` 没有进入任何 commit
- 质量门通过
- E2E 通过，或因本地浏览器缺失而明确记录为环境限制

push：

```powershell
git push origin main
```

push 后确认：

```powershell
git rev-parse HEAD
git ls-remote origin refs/heads/main
git status --short --branch
```

---

## 7. 停止条件

遇到任一情况必须停止并报告：

- 需要数据库 schema / migration 才能继续。
- 需要修改认证、授权、session、cookie 或 Guardrails。
- 同一测试失败连续修复 3 轮仍失败。
- E2E 失败原因指向真实业务回归，且无法在授权范围内修复。
- 远端分支已前进，需要 rebase/merge。
- 发现 `.coverage`、`.claude/settings.local.json`、真实 `.env` 被 stage。
- diff 明显失控，业务代码新增超过约 1200 行且不是测试/文档。

停止时输出：

- 已完成阶段
- 阻塞证据
- 当前 `git status --short --branch`
- 下一条建议超长任务

---

## 8. 最终报告格式

完成后用中文输出：

- 完成状态：完成 / 部分完成 / 阻塞
- 推送状态：已 push / 未 push / 阻塞未 push
- commit hash 与 message
- 运行过的验证命令与结果
- E2E 结果
- 运行日志路径
- 最终 `git status --short --branch`
- 本地 HEAD 与远端 HEAD
- 剩余本地噪声文件

