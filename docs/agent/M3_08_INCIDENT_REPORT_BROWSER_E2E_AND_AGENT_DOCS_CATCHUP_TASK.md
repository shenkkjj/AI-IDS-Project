# M3-08 Incident Report Browser E2E and Agent Docs Catch-up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or the local equivalent task-by-task execution workflow. This repository also requires the skill-first workflow in `AGENTS.md`: before editing, check and read the relevant skills. Reply in Chinese.

**Goal:** 把 M3-07 “案件证据报告导出”从后端契约与前端构建通过，推进到真实浏览器级验收，并顺手把遗留的 agent 任务文档归档入库。

**Architecture:** 本任务不新增产品 API，不改数据库 schema，不改认证/授权/Guardrails。主要新增或扩展可选 Playwright E2E，让浏览器走完整用户路径：注册登录 → 触发 Demo 告警 → 创建案件 → 打开案件详情 → 下载/复制案件报告 → 验证报告脱敏与页面无泄漏。文档收口只处理 agent 文档、运行日志和无人值守索引。

**Tech Stack:** FastAPI + pytest + Playwright Python + Next.js Dashboard + existing `data-testid` selectors + Git 精确分阶段提交。

---

## 0. 任务定位

这是 L5 级无人值守战役，不是“小修小补”。

M3-07 已完成：

- 后端 `GET /incidents/{incident_id}/report?format=json|markdown` 已落地。
- 后端报告契约测试 `server/tests/test_incident_report_export.py` 已 14 passed。
- 后端全量基线已到 `332 passed, 2 skipped`。
- Guardrails 专项已 `139 passed`。
- 前端 `npm run typecheck` 与 `npm run build` 已通过。
- 远端 `origin/main` 已同步到 M3-07 最新提交。

但当前仍有两个产品化缺口：

1. 浏览器级 E2E 还没有覆盖“创建案件 → 下载/复制案件报告”的真实用户路径。
2. 本地遗留 `docs/agent/M3_07_INCIDENT_EVIDENCE_REPORT_EXPORT_TASK.md` 未入库；这会让后续 agent 看不到 M3-07 的原始任务边界。

本任务要把这两个缺口一次性收口。

## 1. 启动前必读

必须按顺序阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/agent/M3_07_INCIDENT_EVIDENCE_REPORT_EXPORT_TASK.md`
- `docs/runs/2026-06-18-m3-07-incident-evidence-report-export.md`
- `server/tests/test_demo_flow_e2e.py`
- `server/tests/test_incident_report_export.py`
- `server/routers/incidents_router.py`
- `server/services/incident_report_service.py`
- `web-next/components/dashboard/AlertDetailPanel.tsx`
- `web-next/components/dashboard/IncidentDetailPanel.tsx`
- `web-next/components/dashboard/IncidentSection.tsx`
- `web-next/hooks/useIncidents.ts`
- `web-next/types/incident.ts`

如果任何必读文件缺失，不要盲改；先在运行日志里记录缺失项，再用 `rg` 查找当前等价文件。

## 2. 技能选择要求

执行前必须检查并优先使用相关 skill：

- `superpowers:executing-plans` 或等价执行计划 skill：逐项执行本任务。
- `verification-loop`：设计验证矩阵和最终证据。
- `tdd-workflow`：新增 E2E 或测试辅助前，先写失败断言或可证明缺口。
- `frontend-patterns`：如需调整 Dashboard 选择器、按钮状态或前端交互。
- `security-review`：任何报告内容、下载文件、剪贴板、页面 DOM 泄漏检查都必须走安全审查思路。
- 如无合适 skill，按 `AGENTS.md` 要求使用 `find-skills` 查找。

不要因为“只是测试”就跳过安全审查：报告导出涉及 payload、note、secret sentinel、stack trace、system prompt 等敏感面。

## 3. 运行模式与预算

- 运行模式：L5 无人值守战役。
- 预计时长：2-4 小时。
- 同一失败最多修复：3 轮。
- diff 预算：约 1200 行；如果主要是文档和 E2E 测试，可放宽到 1800 行，但必须在运行日志解释。
- 允许通过质量门后精确 commit 并 push 到 `origin/main`。
- 禁止使用 `git add .`。
- 禁止提交 `.coverage`、`.claude/settings.local.json`、真实 `.env`、数据库文件、证书、私钥、token。
- 禁止修改 git 历史。

## 4. 初始审计

先创建运行日志：

```text
docs/runs/2026-06-18-m3-08-incident-report-browser-e2e-and-agent-docs-catchup.md
```

日志必须记录：

- 当前分支。
- `git status --short --branch`。
- `git log --oneline --decorate -12`。
- 是否存在 `.coverage` 噪声。
- 是否存在未入库的 `docs/agent/M3_07_INCIDENT_EVIDENCE_REPORT_EXPORT_TASK.md`。
- 是否存在本任务文档 `docs/agent/M3_08_INCIDENT_REPORT_BROWSER_E2E_AND_AGENT_DOCS_CATCHUP_TASK.md`。
- 前后端 dev server 是否已运行。
- Playwright 是否已安装。

推荐命令：

```powershell
git status --short --branch
git log --oneline --decorate -12
Test-Path .coverage
Test-Path docs\agent\M3_07_INCIDENT_EVIDENCE_REPORT_EXPORT_TASK.md
Test-Path docs\agent\M3_08_INCIDENT_REPORT_BROWSER_E2E_AND_AGENT_DOCS_CATCHUP_TASK.md
.venv\Scripts\python.exe -c "import importlib.util; raise SystemExit(0 if importlib.util.find_spec('playwright') else 1)"
```

预期：

- `main...origin/main` 无 ahead/behind。
- `.coverage` 可能 modified，必须保留但不提交。
- M3-07 和 M3-08 任务文档应被纳入本任务的 docs commit。
- Playwright 如果缺失，可以记录为 E2E 环境阻塞；如果能安装或本地已有浏览器，则继续跑真实 E2E。

## 5. 允许修改

允许修改：

- `server/tests/test_demo_flow_e2e.py`
- 或新增 `server/tests/test_incident_report_e2e.py`
- `web-next/components/dashboard/AlertDetailPanel.tsx`（仅当选择器或状态等待有真实问题）
- `web-next/components/dashboard/IncidentDetailPanel.tsx`（仅当 E2E 暴露真实按钮、下载或状态问题）
- `web-next/hooks/useIncidents.ts`（仅当 E2E 暴露真实 API 传参问题）
- `web-next/types/incident.ts`（仅当类型与实现不一致）
- `docs/agent/M3_07_INCIDENT_EVIDENCE_REPORT_EXPORT_TASK.md`
- `docs/agent/M3_08_INCIDENT_REPORT_BROWSER_E2E_AND_AGENT_DOCS_CATCHUP_TASK.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/runs/2026-06-18-m3-08-incident-report-browser-e2e-and-agent-docs-catchup.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

如果 E2E 暴露后端报告实现真实 bug，允许最小修改：

- `server/routers/incidents_router.py`
- `server/services/incident_report_service.py`
- `server/tests/test_incident_report_export.py`

但必须先在运行日志中说明 bug、影响、最小修复方案和回归命令。

## 6. 禁止修改

禁止修改：

- `server/security/**`
- `server/core/auth*`
- `server/routers/auth*`
- `/mcp` 鉴权逻辑
- Alembic migration 或数据库 schema
- `docker-compose.yml`
- `nginx/**`
- 真实 `.env`
- `.coverage`
- `.claude/settings.local.json`
- `data/*.db`
- 任何证书、私钥、token

禁止新增：

- PDF/DOCX 导出。
- 外部报告渲染依赖。
- LLM 报告生成。
- 新环境变量。
- 新认证策略。

## 7. 产品验收目标

完成后，一个安全分析员在真实浏览器中应该能完成：

1. 通过 UI 注册或登录。
2. 进入 Dashboard。
3. 触发 Demo 攻击。
4. 在告警详情中点击“创建案件”。
5. 自动进入或切换到案件视图。
6. 看到案件详情面板。
7. 点击“下载报告”并得到 `incident-<incident_id>-report.md`。
8. 下载文件正文包含：
   - `# 案件证据报告`
   - `## 1. 案件摘要`
   - `## 2. 关联告警`
   - `## 3. 案件时间线`
   - `## 4. 安全与脱敏说明`
9. 下载文件正文不包含：
   - `sk-...`
   - `sk-proj-...`
   - `AKIA...`
   - `ghp_...`
   - `PRIVATE KEY`
   - `Traceback (most recent call last)`
   - `ignore previous instructions`
   - `disregard ... system prompt`
   - `forget ... instructions`
   - `system:`
   - `developer:`
10. 点击“复制报告”后 UI 不崩溃，并显示 `已复制` 或可解释的降级状态。
11. 页面可见 DOM 不出现任何 forbidden sentinel。

## 8. E2E 实现方案

优先新增独立测试文件：

```text
server/tests/test_incident_report_e2e.py
```

如果复用 `test_demo_flow_e2e.py` 更少重复，也可以扩展该文件，但要保持结构清晰。

测试必须：

- 使用 `pytestmark = pytest.mark.e2e`。
- 默认在 `pytest server/tests` 中跳过，只有 `--run-e2e` 时运行。
- 缺 Playwright 时明确 skip。
- 缺 dev server 时明确 fail，并提示启动命令。
- 不依赖真实公网。
- 不依赖真实 LLM API key。
- 使用唯一邮箱，避免重复运行冲突。
- 使用 `accept_downloads=True`。
- 尝试授予剪贴板权限：`clipboard-read` / `clipboard-write`。
- 下载报告后读取真实文件内容做断言。
- 最后关闭 browser/context。

推荐测试流程：

```text
打开首页
  -> 注册唯一用户
  -> 等待 /dashboard
  -> 触发 Demo 攻击
  -> 等待 attack-log-row
  -> 点击最新 attack-log-row
  -> 点击 alert-detail-create-incident
  -> 等待 incident-section / incident-detail-panel
  -> 点击 incident-download-report 并 expect_download
  -> 读取下载文件名和正文
  -> 验证 markdown 结构与 forbidden sentinel
  -> 点击 incident-copy-report
  -> 验证 incident-report-status
  -> 扫描 body 可见文本 sentinel
```

建议复用或抽取以下 helper：

- `_skip_without_playwright`
- `_assert_dev_server_reachable`
- `_register_unique_user`
- `_register_via_ui`
- `_collect_visible_text`
- `_contains_forbidden`

如果 helper 已在 `test_demo_flow_e2e.py`，可以从该文件导入，或把公共 helper 保持在同文件避免过度抽象。不要为了一个 E2E 小范围引入大型测试工具层。

## 9. E2E 关键断言

下载文件名：

```text
incident-<incident_id>-report.md
```

至少断言：

```python
assert suggested_filename.startswith("incident-")
assert suggested_filename.endswith("-report.md")
```

下载正文至少断言：

```python
assert "# 案件证据报告" in markdown
assert "## 1. 案件摘要" in markdown
assert "## 2. 关联告警" in markdown
assert "## 3. 案件时间线" in markdown
assert "## 4. 安全与脱敏说明" in markdown
assert "payload_length" in markdown
assert "payload_preview" in markdown
```

禁止内容断言：

```python
for pattern in _FORBIDDEN_DOM_PATTERNS:
    assert not pattern.search(markdown), pattern.pattern
```

页面 DOM 禁止内容断言：

```python
body_text = await _collect_visible_text(page)
forbidden = _contains_forbidden(body_text)
assert forbidden is None
```

复制按钮断言：

```python
await page.get_by_test_id("incident-copy-report").click()
status = page.get_by_test_id("incident-report-status")
await expect(status).to_contain_text(re.compile("已复制|复制失败|报告生成失败"))
```

如果本地浏览器权限导致剪贴板不可用，允许 UI 显示 `复制失败`，但下载路径必须成功；不能因为剪贴板权限问题放弃下载报告验收。

## 10. Dev Server 策略

如果 dev server 已运行：

- 先用 `http://localhost:3000/api/backend/health` 探测。
- 健康则复用。

如果 dev server 未运行，允许 agent 自行启动，并在运行日志记录 PID 和停止方式：

后端：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m uvicorn server.main:app --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd web-next
npm run dev
```

要求：

- 不要把 dev server 留在无人看管的前台卡死最终总结。
- 如果以后台进程启动，必须在运行日志写清 PID。
- 任务结束前停止本任务启动的后台进程。
- 如果端口被占用，优先确认是否是已有 dev server；不要强杀未知进程。

## 11. 前端修复边界

只有当 E2E 暴露真实问题时才改前端。

允许的最小修复：

- 增加或稳定 `data-testid`。
- 修复按钮 disabled / loading 状态导致 E2E 无法可靠等待。
- 修复下载文件名或 Blob 释放问题。
- 修复 `loadIncidentReport` 调用错误。
- 修复复制失败时无状态反馈。

禁止的前端扩大化：

- 不重做 Dashboard 布局。
- 不新增大卡片或营销式 Hero。
- 不把报告 markdown 长期塞入 React 全局状态。
- 不在前端重新组装 raw payload、note 或事件全文。
- 不把完整报告正文显示在页面上。

## 12. 后端修复边界

只有 E2E 或回归测试证明 M3-07 实现有真实 bug 时才改后端。

允许的最小修复：

- `format=json` response 字段与类型对齐。
- `format=markdown` header 或 filename 修正。
- 报告内容缺少必要结构时补齐。
- 脱敏 sentinel 漏洞修正。
- audit detail 过宽时收窄。

禁止的后端扩大化：

- 不新增报告表。
- 不新增 migration。
- 不改 incident owner 隔离语义。
- 不把 non-owner 从 404 改成 403。
- 不调用 LLM。
- 不引入外部渲染服务。

## 13. 文档收口

必须更新：

- `docs/agent/UNATTENDED_LONG_TASKS.md`
  - 添加 M3-08 条目。
  - 把推荐启动口令更新为下一条合理任务，或明确 M3-08 已执行完成后的建议。
- `docs/runs/2026-06-18-m3-08-incident-report-browser-e2e-and-agent-docs-catchup.md`
  - 每阶段记录改动、验证、结果。

如果本任务真实完成浏览器验收，建议更新：

- `PRODUCT.md`
  - 在 M3 交付或案件报告能力处补一句“浏览器级下载验收已覆盖”。
- `docs/plans/M2_PRODUCT_ROADMAP.md`
  - 如果该文档已有 M3 进度表，补 M3-08 验收状态。

必须把以下任务文档纳入精确 stage：

- `docs/agent/M3_07_INCIDENT_EVIDENCE_REPORT_EXPORT_TASK.md`
- `docs/agent/M3_08_INCIDENT_REPORT_BROWSER_E2E_AND_AGENT_DOCS_CATCHUP_TASK.md`

如果它们已被其他人提交，则只记录现状，不重复改。

## 14. 验证矩阵

基础命令：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_incident_report_export.py -q --tb=short
```

预期：

```text
14 passed
```

E2E 命令：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_incident_report_e2e.py -q --tb=short --run-e2e
```

如果扩展的是现有文件，则运行：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow_e2e.py -q --tb=short --run-e2e
```

后端回归矩阵：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_incident_report_export.py server\tests\test_incidents.py server\tests\test_incident_persistence.py server\tests\test_security_timeline.py -q --tb=short
```

后端全量：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

Guardrails 专项：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

前端：

```powershell
cd web-next
npm run typecheck
npm run build
```

最终 Git 审查：

```powershell
git status --short --branch
git diff --stat
git diff --cached --stat
git log --oneline --decorate -12
```

## 15. E2E 环境阻塞处理

如果 Playwright 未安装、Chromium 不可用、dev server 无法启动，不能假装 E2E 已通过。

必须交付：

- 运行日志中记录阻塞命令和错误摘要。
- 保留已写好的 E2E 测试。
- 默认测试必须仍跳过而不是失败。
- 后端契约、全量后端、Guardrails、前端 typecheck/build 必须照跑。
- 最终状态写“部分完成 / E2E 环境阻塞”，并给下一条最小工单。

只有真实运行 `--run-e2e` 并通过，才允许写“浏览器级验收完成”。

## 16. 安全审查清单

完成前必须逐条检查并写入运行日志：

- 报告下载文件不含 fake secret。
- 页面 DOM 不含 fake secret。
- 页面 DOM 不含 stack trace。
- 页面 DOM 不含 Guardrails regex 或 system prompt。
- report markdown 不含完整 raw payload。
- report markdown 不含完整 note。
- audit log 不含 report markdown 全文。
- non-owner 仍然 404。
- unauthenticated 仍然 401。
- `format=xml` 仍然 422。
- `server/security/**` 没有改动。
- 真实 env、数据库、coverage 没有被 stage。

## 17. 提交策略

通过质量门后，按精确文件拆分 commit。

推荐 commit 1：

```text
test(e2e): 覆盖案件报告浏览器验收
```

包含：

- `server/tests/test_incident_report_e2e.py`
- 或 `server/tests/test_demo_flow_e2e.py`
- 如确有必要，包含最小前端选择器修复。

推荐 commit 2：

```text
docs(agent): 归档 M3-07 与 M3-08 长任务
```

包含：

- `docs/agent/M3_07_INCIDENT_EVIDENCE_REPORT_EXPORT_TASK.md`
- `docs/agent/M3_08_INCIDENT_REPORT_BROWSER_E2E_AND_AGENT_DOCS_CATCHUP_TASK.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`

推荐 commit 3：

```text
docs(incidents): 记录案件报告浏览器验收
```

包含：

- `docs/runs/2026-06-18-m3-08-incident-report-browser-e2e-and-agent-docs-catchup.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

如果实际 diff 更适合合并为 2 个 commit，也可以合并，但必须保持：

- 测试改动与文档归档可审查。
- 禁提交文件不进入任何 commit。
- 不使用 `git add .`。

精确 stage 示例：

```powershell
git add server\tests\test_incident_report_e2e.py
git commit -m "test(e2e): 覆盖案件报告浏览器验收"

git add docs\agent\M3_07_INCIDENT_EVIDENCE_REPORT_EXPORT_TASK.md docs\agent\M3_08_INCIDENT_REPORT_BROWSER_E2E_AND_AGENT_DOCS_CATCHUP_TASK.md docs\agent\UNATTENDED_LONG_TASKS.md
git commit -m "docs(agent): 归档 M3-07 与 M3-08 长任务"

git add docs\runs\2026-06-18-m3-08-incident-report-browser-e2e-and-agent-docs-catchup.md PRODUCT.md docs\plans\M2_PRODUCT_ROADMAP.md
git commit -m "docs(incidents): 记录案件报告浏览器验收"
```

如果修改的是 `test_demo_flow_e2e.py` 或前端选择器文件，必须替换示例中的文件路径，仍然精确 stage。

## 18. Push 策略

提交前：

```powershell
git status --short --branch
git log --oneline --decorate -8
```

确认：

- 没有 `.coverage` staged。
- 没有 `.claude/settings.local.json` staged。
- 没有真实 `.env` staged。
- 没有数据库文件 staged。
- 没有证书或 key staged。

然后：

```powershell
git push origin main
```

如果 push 因网络失败：

- 不要反复无限重试。
- 最多重试 3 次。
- 记录 DNS/TCP/HTTPS 错误摘要。
- 如果本地 commit 已完成但 push 阻塞，最终状态写“本地完成，push 阻塞”。

## 19. 停止条件

满足任一条件必须停止：

- 同一个 E2E 失败连续修复 3 轮仍失败。
- 需要改认证、授权、Guardrails、schema，但本任务未授权。
- 下载报告验收需要真实 secret 或外部服务。
- dev server 无法启动且无法确认原因。
- Playwright 环境无法安装或浏览器不可用。
- diff 超过 1800 行且不是文档或测试为主。
- `server/tests` 全量出现与本任务无关的大面积失败。
- `server/security/**` 出现意外 diff。

停止时必须输出：

- 完成了什么。
- 未完成什么。
- 阻塞证据。
- 下一条最小工单。

## 20. 最终报告格式

任务完成后，用中文输出：

```text
完成状态：完成 / 部分完成 / 阻塞

改动文件：
- ...

验证命令：
- <命令> -> <结果>

安全审查：
- ...

提交与推送：
- commit: ...
- push: 成功 / 阻塞

运行日志：
- docs/runs/2026-06-18-m3-08-incident-report-browser-e2e-and-agent-docs-catchup.md

剩余本地噪声：
- .coverage（如仍存在，说明未提交）
```

不要只说“好了”。必须给出可审查证据。

