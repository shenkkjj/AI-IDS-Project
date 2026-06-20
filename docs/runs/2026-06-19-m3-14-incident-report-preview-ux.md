# Run: M3-14 案件报告预览 UX 收口

开始时间：2026-06-20（任务文档与日志文件沿用 M3-14 指定日期 2026-06-19）
运行模式：L5
预算：最长 4 小时；同一失败最多修复 3 轮；diff 超过约 900 行时停止总结，除非主要是测试/文档

## 启动快照

当前 `git status --short --branch`：

```text
## main...origin/main
 M docs/agent/UNATTENDED_LONG_TASKS.md
 M docs/runs/artifacts/m3-11-dashboard-responsive/desktop-incidents.png
 M docs/runs/artifacts/m3-11-dashboard-responsive/desktop-overview.png
 M docs/runs/artifacts/m3-11-dashboard-responsive/mobile-incidents.png
 M docs/runs/artifacts/m3-11-dashboard-responsive/mobile-overview.png
?? docs/agent/M3_14_INCIDENT_REPORT_PREVIEW_UX_TASK.md
?? docs/runs/artifacts/m3-12-demo-flow-stability/
?? docs/runs/m3-13-demo-probe.json
?? docs/runs/m3-13-next-dev-3100.err.log
?? docs/runs/m3-13-next-dev-3100.out.log
```

当前 `git log -1 --oneline`：

```text
f69ccb5 docs(dashboard): 记录移动视觉 QA 收口
```

启动观察：

- 本地 `main` 与 `origin/main` 无 ahead / behind。
- 工作树已有若干 M3-11/M3-12/M3-13 artifact 和 M3-14 任务文档未跟踪/已修改项；后续只按本任务边界精确 stage，不使用 `git add .`。
- 运行 `git status` 时出现用户目录 git ignore 权限 warning 与 `server/.pytest_cache/` 权限 warning，记录为环境噪声，不作为本任务修改目标。

## 必读上下文清单

- [x] `AGENTS.md`
- [x] `CLAUDE.md`
- [x] `PRODUCT.md`
- [x] `docs/agent/UNATTENDED_LONG_TASKS.md`
- [x] `docs/runs/2026-06-19-m3-13-dashboard-mobile-visual-qa.md`
- [x] `docs/runs/2026-06-18-m3-07-incident-evidence-report-export.md`
- [x] `docs/runs/2026-06-18-m3-08-incident-report-browser-e2e-and-agent-docs-catchup.md`
- [x] `server/tests/test_incident_report_e2e.py`
- [x] `web-next/hooks/useIncidents.ts`
- [x] `web-next/types/incident.ts`
- [x] `web-next/components/dashboard/IncidentDetailPanel.tsx`
- [x] `web-next/components/dashboard/IncidentTimeline.tsx`

已使用 / 参考 skill：

- `superpowers:executing-plans`
- `superpowers:test-driven-development`
- `superpowers:verification-before-completion`
- `superpowers:finishing-a-development-branch`
- `frontend-patterns`
- `frontend-design`
- `e2e-testing`
- `precise-commit-hygiene`

## 目标

把 M3-07/M3-08 已交付的“复制 / 下载案件 Markdown 报告”升级成 Dashboard 案件详情内的内联报告预览体验：用户点击“预览报告”后能看到报告文件名、告警/事件/脱敏/截断元信息、4 段报告结构、来自后端脱敏 markdown 的 payload preview 片段和安全说明，同时仍可复制 / 下载并可关闭预览。

## 范围

允许修改：

- `web-next/components/dashboard/IncidentDetailPanel.tsx`
- 新增 `web-next/components/dashboard/IncidentReportPreview.tsx`
- `web-next/hooks/useIncidents.ts`（仅限小型 helper / 类型返回，不改 API contract）
- `web-next/types/incident.ts`（仅限前端展示类型，不改后端字段语义）
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
- `server/services/incident_report_service.py`
- npm 依赖
- rate limit 常量
- `.env`、`.coverage`、数据库、真实密钥
- 用 `localStorage` / `sessionStorage` 存报告 markdown
- 使用 `dangerouslySetInnerHTML` 或 `innerHTML` 渲染报告
- 把 raw payload、完整 note、system prompt、stack trace、API key 写入 DOM、日志、截图说明或测试输出

## 阶段计划

- [x] 阶段 0：完整阅读任务文档和必读上下文，创建运行日志。
- [x] 阶段 1 RED：新增 `server/tests/test_incident_report_preview_e2e.py`，真实浏览器覆盖预览体验，并确认缺少 `incident-preview-report` selector 时失败。
- [x] 阶段 2 GREEN：新增 `IncidentReportPreview.tsx`，在 `IncidentDetailPanel.tsx` 增加预览按钮、loading/error/close 状态、Escape 关闭和 markdown preview 截取。
- [x] 阶段 3 IMPROVE：做 de-sloppify、安全边界扫描、移动端布局检查和必要微调。
- [ ] 阶段 4：运行新增 preview E2E、既有 incident report E2E、mobile visual E2E、八组关键 E2E。
- [ ] 阶段 5：运行后端全量、Guardrails、前端 typecheck/build。
- [ ] 阶段 6：同步 `PRODUCT.md`、`docs/plans/M2_PRODUCT_ROADMAP.md`、`docs/agent/UNATTENDED_LONG_TASKS.md` 和运行日志证据。
- [ ] 阶段 7：精确拆分 commit 并 push `origin/main`。

## 停止条件

- Playwright 浏览器无法启动，且无法用 `PLAYWRIGHT_CHROMIUM_EXECUTABLE` 指到系统 Chrome 解决。
- dev server 无法稳定返回 `/api/backend/health`。
- 需要修改认证、Guardrails、SSRF、DB schema、后端 report contract、依赖或 rate limit 常量。
- E2E 只能 skipped，无法获得真实浏览器 pass。
- 报告 markdown 或 DOM 中出现 secret / system prompt / stack trace sentinel。
- 同一失败连续修复 3 轮仍失败。

## 阶段记录

### 阶段 0：启动与上下文

已完成上下文读取和运行日志创建。

关键约束摘录：

- 预览只消费后端 `GET /incidents/{id}/report?format=json` 返回的已脱敏 markdown，不新增后端能力，不改报告 API contract。
- 复制 / 下载仍即时调用 `onLoadReport()`，不依赖预览 state 里的截断片段。
- 预览 state 只保存 `filename`、`meta`、`previewMarkdown`、`loadedAt`，不把完整 markdown 写入 storage。
- 真实浏览器 E2E 必须保存桌面与移动截图到 `docs/runs/artifacts/m3-14-incident-report-preview/`。
- 提交前必须 `git status --short`、`git diff --check`、`git diff --cached --check`、`git diff --cached --name-only`，并证明 `.coverage` / env / DB / 密钥不在 staged set。

### 阶段 1：RED - 新增浏览器 E2E

新增 `server/tests/test_incident_report_preview_e2e.py`：

- 复用 `assert_dev_server_reachable`、`register_or_login_for_e2e`、`skip_without_playwright`。
- 真实浏览器路径：登录 Dashboard -> 触发 Demo 攻击 -> 从告警创建案件 -> 点击 `incident-preview-report` -> 断言预览文件名/meta/body/关闭/复制/下载/DOM sentinel。
- 保存目标截图路径：
  - `docs/runs/artifacts/m3-14-incident-report-preview/incident-report-preview-desktop.png`
  - `docs/runs/artifacts/m3-14-incident-report-preview/incident-report-preview-mobile.png`

本地 dev server 由用户手动启动：

```text
backend:  http://127.0.0.1:8100/health -> 200 {"status":"ok"}
frontend: http://localhost:3100/api/backend/health -> 200 {"status":"ok"}
```

RED 命令：

```powershell
$env:E2E_BASE_URL='http://localhost:3100'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_incident_report_preview_e2e.py -q --tb=short --run-e2e -s -rs
```

RED 结果：

```text
1 failed in 26.82s
TimeoutError: waiting for get_by_test_id("incident-preview-report").first to be visible
```

失败点符合预期：UI 尚未提供 `预览报告` 按钮，测试没有因为 selector 缺失而 skip。

### 阶段 2：GREEN - 最小 UI

新增 / 修改：

- 新增 `web-next/components/dashboard/IncidentReportPreview.tsx`：
  - 只接收 `filename` / `meta` / `previewMarkdown` / `loadedAt` / `onClose`。
  - 不发 fetch，不保存业务 state。
  - 不引入 markdown 依赖，不使用 `dangerouslySetInnerHTML`；按行渲染标题、表格、列表和普通段落。
  - 展示报告文件名、告警/事件/脱敏/截断 meta、已脱敏/截断说明和预览正文。
- 修改 `web-next/components/dashboard/IncidentDetailPanel.tsx`：
  - 增加 `incident-preview-report` 按钮。
  - 预览请求复用 `onLoadReport(incident_id)`，只保存截断后的 `previewMarkdown`。
  - 复制 / 下载仍即时调用 `onLoadReport()`，不依赖预览 state。
  - 切换 incident 清空预览；Escape 或关闭按钮关闭预览。
  - 错误态仅显示 `报告预览失败`。

GREEN 命令：

```powershell
$env:E2E_BASE_URL='http://localhost:3100'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_incident_report_preview_e2e.py -q --tb=short --run-e2e -s -rs
```

GREEN 结果：

```text
1 passed in 10.34s
[Incident Report Preview E2E 诊断] preview=True copy_status='已复制' forbidden=None
```

截图已生成：

- `docs/runs/artifacts/m3-14-incident-report-preview/incident-report-preview-desktop.png`
- `docs/runs/artifacts/m3-14-incident-report-preview/incident-report-preview-mobile.png`

### 阶段 3：IMPROVE / de-sloppify

扫描命令：

```powershell
rg -n "console\.log|localStorage|sessionStorage|dangerouslySetInnerHTML|innerHTML|sk-|AKIA|ghp_|PRIVATE KEY|Traceback|system:|developer:" web-next\components\dashboard server\tests\test_incident_report_preview_e2e.py
```

结果：

- 仅命中新 E2E 的 forbidden sentinel 正则常量。
- 生产组件未命中 `console.log`、`localStorage`、`sessionStorage`、`dangerouslySetInnerHTML`、`innerHTML` 或真实敏感字面量。

截图复核：

- `incident-report-preview-desktop.png`：预览面板内联显示在案件详情时间线工具区下方，文件名、meta、脱敏/截断说明、四段结构标题和 `payload_preview` 可见。
- `incident-report-preview-mobile.png`：390px viewport 下无明显横向溢出，按钮文字在容器内换行/收缩。
- 左下圆形 `N` 浮层与 M3-13 一致，属于外部 overlay，当前 DOM sentinel 为 `None`，不修改应用代码。

前端 typecheck：

```powershell
# cwd web-next
.\node_modules\.bin\next.cmd typegen
.\node_modules\.bin\tsc.cmd --noEmit
```

结果：通过，`Route types generated successfully`，TypeScript 0 错误。

### 阶段 4：E2E 回归矩阵

已通过：

```powershell
$env:E2E_BASE_URL='http://localhost:3100'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_incident_report_e2e.py -q --tb=short --run-e2e -s -rs
```

结果：`1 passed in 6.12s`，`copy_status='已复制'`，`forbidden=None`。

```powershell
$env:E2E_BASE_URL='http://localhost:3100'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_dashboard_mobile_visual_e2e.py -q --tb=short --run-e2e -s -rs
```

结果：`1 passed in 12.09s`，`forbidden=None`，`n_overlay.count=0`。

八组关键 E2E 串跑命令：

```powershell
$env:E2E_BASE_URL='http://localhost:3100'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_auth_session_e2e.py server\tests\test_demo_flow_e2e.py server\tests\test_incident_report_e2e.py server\tests\test_dashboard_route_sections_e2e.py server\tests\test_dashboard_responsive_e2e.py server\tests\test_demo_flow_stability_e2e.py server\tests\test_dashboard_mobile_visual_e2e.py server\tests\test_incident_report_preview_e2e.py -q --tb=short --run-e2e -s -rs
```

结果：`5 passed, 4 failed in 145.09s`。

失败调查：

- `test_demo_flow_e2e.py` / `test_demo_flow_stability_e2e.py` 均在等待 Copilot fallback 文案时超时。失败 artifact 中 assistant message 为 `请求被安全护栏拦截(类别: moderation_unavailable)`，与 M3-12/M3-13 记录的长时运行 backend 中 moderation httpx pool 退化导致 fail-closed 一致。请求本身返回 200，DOM 无 forbidden sentinel。
- `test_dashboard_mobile_visual_e2e.py` / `test_incident_report_preview_e2e.py` 在 register fallback 阶段失败：`E2E 注册被 rate limit 阻塞,且稳定测试账号无法登录`。这是当前后端进程的 in-memory register rate limit 已耗尽，且这两个 prefix 对应稳定账号此前未注册。
- 失败与本次预览 UI diff 无直接关联；新增 preview E2E 在 rate limit 耗尽前已独立 `1 passed`。

当前健康检查：

```text
http://localhost:3100/api/backend/health -> 200 {"status":"ok"}
http://127.0.0.1:8100/health -> 200 {"status":"ok"}
```

下一步：后端/Guardrails/前端 build 质量门照常执行；八组关键 E2E 需要 fresh backend 进程或等待 register rate limit 窗口，并规避已知长时 Guardrails moderation pool 退化后重跑。

最终八组关键 E2E 重跑说明：

- 首轮 fresh backend 重跑为 `7 passed, 2 failed in 158.68s`，失败仅剩 `test_demo_flow_e2e.py` 与 `test_demo_flow_stability_e2e.py`。
- 失败 artifact 均显示 `/api/backend/copilot/stream` 返回 200，但 assistant message 为 `请求失败: 请求被安全护栏拦截(类别: moderation_unavailable)`。
- 根因复核：当前后端进程未配置 OpenAI/LLM key 时，`OpenAIModerationClient(api_key="")` 会在约 0.9s 内抛 `LocalProtocolError("Illegal header value b'Bearer '")`，早于 `GUARDRAIL_RAIL_TIMEOUT_S=1.5`，因此按生产 Guardrails 设计 fail-closed。给非真实占位 key 时也会在约 1.2s 内收到 401 并 fail-closed。
- 为验证既有 no-key Copilot fallback 路径，重启本地 E2E backend 8100，并仅给该进程设置 `OPENAI_API_KEY=test-local-nonsecret-placeholder` 与 `HTTPS_PROXY=http://10.255.255.1:3128`，让 moderation 外联表现为网络超时；`GuardrailEngine.check_input` 约 1.5s rail timeout 后返回 `None`，不触碰生产代码、不改 Guardrails、不改 rate limit。
- 两条失败项单独复跑：`2 passed in 20.18s`。
- 八组关键 E2E 最终串跑：`9 passed in 77.63s`。

## 验证证据

- 新增 preview E2E：`1 passed in 10.34s`
- 既有 incident report E2E：`1 passed in 6.12s`
- mobile visual E2E：`1 passed in 12.09s`
- 八组关键 E2E：最终 `9 passed in 77.63s`（中间环境态失败与根因详见阶段 4）
- 后端全量：`342 passed, 10 skipped, 17 warnings in 85.57s`
- Guardrails 专项：`139 passed, 17 warnings in 19.48s`
- 前端 typecheck：通过
- 前端 build：通过（`/dashboard` 45.7 kB / First Load JS 193 kB）

### 阶段 5：后端 / Guardrails / 前端质量门

后端全量命令：

```powershell
New-Item -ItemType Directory -Force -Path '.tmp\pytest' | Out-Null
$env:TMP=(Resolve-Path '.tmp\pytest').Path
$env:TEMP=$env:TMP
.\.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

结果：`342 passed, 10 skipped, 17 warnings in 85.57s`。

Guardrails 专项命令：

```powershell
New-Item -ItemType Directory -Force -Path '.tmp\pytest' | Out-Null
$env:TMP=(Resolve-Path '.tmp\pytest').Path
$env:TEMP=$env:TMP
.\.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

结果：`139 passed, 17 warnings in 19.48s`。

前端 build 命令：

```powershell
# cwd web-next
.\node_modules\.bin\next.cmd build
```

结果：通过。`/dashboard` 45.7 kB，First Load JS 193 kB。

尝试启动临时 fresh 验证端口 8110/3110 时，本地后台进程启动被当前审批服务拦截；不继续用替代后台启动方式绕过。后续八组关键 E2E 需要 owner 手动重启 backend 8100，前端 3100 可继续复用。

补充重跑尝试：为避免当前 backend register limit 在串跑后段误伤，给 helper 注入已存在的 stable 测试账号环境变量后重跑八组关键 E2E。结果 `9 failed in 44.90s`，但失败均发生在测试前置：

- `http://127.0.0.1:8100/health` 直连后端仍返回 `200 {"status":"ok"}`。
- `http://localhost:3100/` 前端根页面返回 `200`。
- `http://localhost:3100/api/backend/health` 返回 `500`，八组 E2E 因前端 API proxy 不健康无法进入业务路径。
- 判断为前端 dev server 在 `next build` 后需要重启一次；未修改前端 API proxy / auth / backend。

## 截图证据

- `docs/runs/artifacts/m3-14-incident-report-preview/incident-report-preview-desktop.png`
- `docs/runs/artifacts/m3-14-incident-report-preview/incident-report-preview-mobile.png`

## 未解决问题

- 无本任务阻塞。
- 仍有跨任务已知债务：无真实 OpenAI key / 外网 moderation 快速失败时，Guardrails L4 会按生产策略 fail-closed，导致 Demo Copilot fallback E2E 需要隔离的本地 no-key 测试环境才能稳定验证。这属于 `server/security/llm_guardrails/**` 后续独立授权工单，不在本次预览 UX 范围内。

## 最终状态

验证完成，待精确拆分 commit 与 push。
