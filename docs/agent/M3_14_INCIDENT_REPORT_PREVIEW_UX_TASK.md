# M3-14 Incident Report Preview UX 收口任务

> **给无人值守 Agent 的任务文档。** 本任务是 L5 超长任务：先读上下文，创建运行日志，按 TDD/E2E 红绿推进，阶段性记录证据，最后通过完整验证矩阵后精确 commit / push。不要把 skipped 当 passed。

## 0. 任务一句话

把 M3-07/M3-08 已交付的“复制 / 下载案件 Markdown 报告”升级成可演示的 **案件报告预览体验**：用户在案件详情里能先打开一个紧凑、脱敏、可关闭的报告预览面板，看到报告结构、元信息、payload preview 与脱敏/截断说明，再决定复制或下载。

## 1. 背景

已交付能力：

- M3-07：后端 `GET /incidents/{incident_id}/report?format=json|markdown` 已生成脱敏 Markdown 报告。
- M3-08：真实浏览器 E2E 已覆盖“创建案件 -> 下载报告 -> 验证 markdown 结构与脱敏 sentinel -> 复制报告”。
- M3-09：`useIncidents()` 已上提到 `dashboard-client.tsx` 父层，案件列表 / detail / report 共享同一 state。
- M3-13：Dashboard 移动端视觉 QA 已覆盖移动 viewport、截图、横向溢出和 forbidden sentinel。

当前体验缺口：

- 用户只能点“复制报告 / 下载报告”，没有预览报告内容和报告安全元信息。
- `incident-report-status` 只有短文本，不够说明报告是否经过脱敏、是否被截断、包含多少告警和事件。
- 演示时无法在 UI 内证明报告结构、payload preview、redaction count 和安全说明确实存在。

本任务目标不是重写报告生成，也不是新增后端能力，而是补齐前端预览 UX + E2E 证据。

## 2. 必读上下文

开始前必须完整阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/runs/2026-06-19-m3-13-dashboard-mobile-visual-qa.md`
- `docs/runs/2026-06-18-m3-07-incident-evidence-report-export.md`
- `docs/runs/2026-06-18-m3-08-incident-report-browser-e2e-and-agent-docs-catchup.md`
- `server/tests/test_incident_report_e2e.py`
- `web-next/hooks/useIncidents.ts`
- `web-next/types/incident.ts`
- `web-next/components/dashboard/IncidentDetailPanel.tsx`
- `web-next/components/dashboard/IncidentTimeline.tsx`

必须使用或参考的 skill：

- `superpowers:executing-plans` 或 `superpowers:subagent-driven-development`
- `superpowers:test-driven-development`
- `superpowers:verification-before-completion`
- `frontend-patterns`
- `frontend-design`
- `e2e-testing`

如果当前环境没有子智能体工具，降级为 inline 执行，但仍要按阶段写运行日志。

## 3. 硬边界

允许修改：

- `web-next/components/dashboard/IncidentDetailPanel.tsx`
- 新增 `web-next/components/dashboard/IncidentReportPreview.tsx`
- `web-next/hooks/useIncidents.ts`（仅限提取小型 helper 或补充返回字段类型，不改变 API contract）
- `web-next/types/incident.ts`（仅限前端展示类型，不能改后端字段语义）
- 新增 `server/tests/test_incident_report_preview_e2e.py`
- 必要时轻量更新 `server/tests/test_incident_report_e2e.py`
- `docs/runs/2026-06-19-m3-14-incident-report-preview-ux.md`
- `docs/runs/artifacts/m3-14-incident-report-preview/**`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

禁止修改：

- 认证 / 授权
- `server/security/**` / Guardrails
- SSRF
- DB schema / Alembic migration
- 后端 report API contract
- `server/services/incident_report_service.py`，除非发现已存在测试失败且必须先停下汇报
- npm 依赖
- rate limit 常量
- `.env`、`.coverage`、数据库、真实密钥
- 用 `localStorage` / `sessionStorage` 存报告 markdown
- 把 raw payload、完整 note、system prompt、stack trace、API key 写入 DOM、日志、截图说明或测试输出

## 4. 运行预算与停止条件

预算：

- 最长运行 4 小时。
- 同一失败最多修复 3 轮。
- diff 超过约 900 行时停止总结，除非主要是测试/文档。

必须停止并写清楚阻塞：

- Playwright 浏览器无法启动，且无法用 `PLAYWRIGHT_CHROMIUM_EXECUTABLE` 指到系统 Chrome 解决。
- dev server 无法稳定返回 `/api/backend/health`。
- 需要修改认证、Guardrails、SSRF、DB schema、后端 report contract、依赖或 rate limit 常量。
- E2E 只能 skipped，无法获得真实浏览器 pass。
- 发现报告 markdown 或 DOM 中出现 secret / system prompt / stack trace sentinel。

## 5. 产品验收标准

完成后用户应该能在 Dashboard 案件详情里完成：

1. 打开某个案件详情。
2. 点击 `预览报告`。
3. 看到一个紧凑的报告预览区，包含：
   - 报告文件名。
   - 告警数、事件数、脱敏次数、是否截断。
   - 报告 4 段结构标题。
   - 一段只来自后端脱敏 markdown 的 preview。
   - 明确的“已脱敏 / 已截断”安全说明。
4. 在预览打开时继续可点击复制 / 下载。
5. 点击关闭按钮或按 `Escape` 可关闭预览。
6. 移动端不产生横向溢出，按钮文字不挤出容器。
7. 页面 DOM 和下载/预览 markdown 都不包含 forbidden sentinel。

## 6. 推荐设计

### 6.1 UI 形态

在 `IncidentDetailPanel` 的“事件时间线”工具区增加一个 `预览报告` 按钮，建议使用 lucide `Eye` 或 `FileSearch` 图标。

点击后在时间线工具区下方显示一个内联预览面板，不要使用全屏 modal，不要新增复杂路由：

- 容器 `data-testid="incident-report-preview"`
- 关闭按钮 `data-testid="incident-report-preview-close"`
- 文件名 `data-testid="incident-report-preview-filename"`
- 元信息 `data-testid="incident-report-preview-meta"`
- Markdown 片段 `data-testid="incident-report-preview-body"`
- 错误态 `data-testid="incident-report-preview-error"`

视觉要求：

- 保持当前 Dashboard 工具型、紧凑、低噪声风格。
- 不使用大 hero、营销卡片、渐变装饰。
- 面板最多占用当前详情列宽，不造成整页横向滚动。
- 移动端按钮允许换行，但文字必须在容器内。

### 6.2 数据与状态

不要把完整 markdown 长期保存在多个 state 里。推荐：

- `reportPreview` state 保存：
  - `filename`
  - `meta`
  - `previewMarkdown`：从后端 markdown 中截取前 1200-1800 字符，保留标题和 payload_preview 附近内容。
  - `loadedAt`
- 复制 / 下载按钮仍按当前实现即时调用 `onLoadReport()`，不要依赖预览 state 里的截断片段。
- 切换 incident 时清空 preview state。
- 预览请求 loading 时禁用 `预览报告` 按钮，显示 `生成中`。
- 预览失败显示短错误，不暴露 raw exception stack。

### 6.3 建议组件边界

新增：

```text
web-next/components/dashboard/IncidentReportPreview.tsx
```

职责：

- 只负责展示 `filename` / `meta` / `previewMarkdown` / `onClose`。
- 不发 fetch。
- 不保存业务 state。
- 不解析敏感 raw payload。
- 做最小 markdown 预览：按行渲染标题、列表、普通段落即可；不要引入 markdown 依赖。

`IncidentDetailPanel.tsx` 职责：

- 负责按钮、loading/error、调用 `onLoadReport()`、截取 preview、把 props 传给 `IncidentReportPreview`。
- 保留既有复制 / 下载行为。

## 7. TDD / E2E 计划

### Task 1：创建运行日志

创建：

```text
docs/runs/2026-06-19-m3-14-incident-report-preview-ux.md
```

初始内容必须包含：

- 开始时间。
- 当前 `git status --short --branch`。
- 当前 `git log -1 --oneline`。
- 必读上下文清单。
- 允许/禁止范围。
- 阶段计划。
- 停止条件。

### Task 2：RED - 新增浏览器 E2E

新增：

```text
server/tests/test_incident_report_preview_e2e.py
```

必须复用：

- `server.tests.e2e_helpers.assert_dev_server_reachable`
- `server.tests.e2e_helpers.register_or_login_for_e2e`
- `server.tests.e2e_helpers.skip_without_playwright`

测试流程：

1. 启动 Playwright chromium，支持 `PLAYWRIGHT_CHROMIUM_EXECUTABLE`。
2. `accept_downloads=True`。
3. 登录 Dashboard。
4. 触发 Demo 攻击。
5. 点击最新告警。
6. 创建案件。
7. 等待 `incident-detail-panel`。
8. 点击 `incident-preview-report`。
9. 等待 `incident-report-preview`。
10. 断言 preview filename 以 `incident-` 开头、以 `-report.md` 结尾。
11. 断言 preview body 包含：
    - `案件证据报告`
    - `案件摘要`
    - `关联告警`
    - `案件时间线`
    - `安全与脱敏说明`
    - `payload_preview`
12. 断言 meta 区域包含告警数、事件数、脱敏、截断。
13. 点击复制报告，允许 `已复制` 或剪贴板降级文案，但不能崩溃。
14. 点击下载报告，读取真实 markdown，复用现有结构/脱敏断言。
15. 按 `Escape` 或点击关闭按钮，断言 preview 消失。
16. 扫描整页 DOM，无 forbidden sentinel。
17. 保存截图到：

```text
docs/runs/artifacts/m3-14-incident-report-preview/incident-report-preview-desktop.png
docs/runs/artifacts/m3-14-incident-report-preview/incident-report-preview-mobile.png
```

RED 预期：

- 如果 `预览报告` 按钮不存在，测试应 fail 在 `incident-preview-report` selector。
- 不允许因为 selector 不存在而 skip。

### Task 3：GREEN - 实现最小 UI

实现：

- `IncidentReportPreview.tsx`
- `IncidentDetailPanel.tsx` 中的 `预览报告` 按钮与 preview state。

建议按钮：

```tsx
<button
  type="button"
  data-testid="incident-preview-report"
  onClick={() => void handlePreviewReport()}
  disabled={reportPreviewLoading || reportLoading}
  className="text-[10px] font-mono uppercase tracking-[0.15em] text-accent hover:text-accent-hover inline-flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
  aria-label="预览案件报告"
>
  {reportPreviewLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <FileSearch className="w-3 h-3" />}
  预览报告
</button>
```

注意：

- 如果 `reportAction === "loading"`，预览按钮也应避免并发，反之亦然。
- 切换 incident 时清空 preview。
- 错误文案短且净化，例如 `报告预览失败`。

### Task 4：IMPROVE - de-sloppify

检查并修复：

- 是否有重复 fetch 逻辑可以小范围抽取。
- 是否留下 `console.log`。
- 是否把 markdown 写进 `localStorage` / `sessionStorage`。
- 是否出现 `dangerouslySetInnerHTML` / `innerHTML`。
- 是否新增过度注释。
- 是否按钮没有 `aria-label` / title。
- 是否移动端按钮文字溢出或横向滚动。

扫描命令：

```powershell
rg -n "console\.log|localStorage|sessionStorage|dangerouslySetInnerHTML|innerHTML|sk-|AKIA|ghp_|PRIVATE KEY|Traceback|system:|developer:" web-next\components\dashboard server\tests\test_incident_report_preview_e2e.py
```

命中测试 sentinel 常量是允许的；命中生产组件里的真实敏感字面量必须修。

### Task 5：验证矩阵

如果本机 Chromium `spawn EPERM`，优先使用系统 Chrome：

```powershell
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
```

如需隔离 dev server，可沿用 M3-13 的 8100/3100 方案，但必须写进运行日志。

必须运行：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_incident_report_preview_e2e.py -q --tb=short --run-e2e -s -rs
```

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_incident_report_e2e.py -q --tb=short --run-e2e -s -rs
```

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_dashboard_mobile_visual_e2e.py -q --tb=short --run-e2e -s -rs
```

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_auth_session_e2e.py server\tests\test_demo_flow_e2e.py server\tests\test_incident_report_e2e.py server\tests\test_dashboard_route_sections_e2e.py server\tests\test_dashboard_responsive_e2e.py server\tests\test_demo_flow_stability_e2e.py server\tests\test_dashboard_mobile_visual_e2e.py server\tests\test_incident_report_preview_e2e.py -q --tb=short --run-e2e -s -rs
```

默认后端：

```powershell
New-Item -ItemType Directory -Force -Path '.tmp\pytest' | Out-Null
$env:TMP=(Resolve-Path '.tmp\pytest').Path
$env:TEMP=$env:TMP
.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

Guardrails：

```powershell
New-Item -ItemType Directory -Force -Path '.tmp\pytest' | Out-Null
$env:TMP=(Resolve-Path '.tmp\pytest').Path
$env:TEMP=$env:TMP
.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

前端，必须顺序执行，不要和 build 并行：

```powershell
cd web-next
npm run typecheck
npm run build
```

如果 npm shim 损坏，可使用 M3-13 已记录的本地 binary 等价命令，但必须写进运行日志。

### Task 6：文档同步

更新：

- `PRODUCT.md`：在 M3 当前状态中补 M3-14 已交付摘要。
- `docs/plans/M2_PRODUCT_ROADMAP.md`：补 M3-14 摘要。
- `docs/agent/UNATTENDED_LONG_TASKS.md`：新增 M3-14 条目，推荐口令改为下一条候选。
- `docs/runs/2026-06-19-m3-14-incident-report-preview-ux.md`：记录真实命令、结果、截图路径、commit hash、push 状态。

下一条候选建议：

- 若 owner 授权安全核心：`M3-15 Guardrails moderation httpx pool 健康监控`。
- 若继续产品体验：`M3-15 SOC timeline drilldown / filter UX`，为审计时间线补筛选、详情展开、脱敏 sentinel E2E。

默认推荐继续产品体验，除非 owner 明确授权动 Guardrails。

### Task 7：精确 commit / push

禁止 `git add .`。

建议拆分：

1. `test(e2e): 覆盖案件报告预览体验`
2. `feat(incidents): 增加案件报告预览面板`
3. `docs(incidents): 记录报告预览 UX 收口`

提交前必须运行：

```powershell
git status --short
git diff --check
git diff --cached --check
git diff --cached --name-only
```

确认未 staged：

- `.coverage`
- `.env`
- 数据库文件
- 真实密钥
- 用户本地日志
- 与本任务无关的截图/缓存

push：

```powershell
git push origin main
```

push 失败则记录远端错误和下一步，不要反复盲推。

## 8. 完成报告格式

完成后输出：

```text
完成状态：完成 / 部分完成 / 阻塞
本次 commit：
- <hash> <message>

改动文件：
- <path>：<一句话说明>

真实验证：
- <command> -> <结果>

截图证据：
- <path>

安全边界：
- 未改 auth / Guardrails / SSRF / DB schema / 后端 report contract / npm 依赖 / rate limit
- 未提交 .coverage / env / DB / 密钥
- DOM / markdown forbidden sentinel 扫描结果

运行日志：
- docs/runs/2026-06-19-m3-14-incident-report-preview-ux.md

下一条建议：
- <建议>
```

## 9. 启动口令

```text
请执行 `docs/agent/M3_14_INCIDENT_REPORT_PREVIEW_UX_TASK.md` 中定义的 L5 超长任务。先完整阅读任务文档和必读上下文，创建运行日志，新增真实浏览器 E2E 覆盖案件报告预览体验，再实现 `IncidentReportPreview` 与 `IncidentDetailPanel` 的最小 UI 改造。只允许前端报告预览 UX、E2E、截图和文档同步，不要修改认证/授权/Guardrails/SSRF/DB schema/后端 report API/npm 依赖/rate limit，不要把报告 markdown 写进 localStorage/sessionStorage，不要使用 `dangerouslySetInnerHTML`，不要提交 `.coverage`、真实 env、数据库或密钥。通过新增 preview E2E、既有 incident report E2E、mobile visual E2E、八组关键 E2E、后端全量、Guardrails、前端 typecheck/build 后，精确拆分 commit 并 push 到 `origin/main`，完成后输出最终报告。
```
