# M3-15 SOC Timeline Drilldown / Filter UX 收口任务

> **给无人值守 Agent 的任务文档。** 本任务是 L5 超长任务：先读上下文，创建运行日志，按 TDD/E2E 红绿推进，阶段性记录证据，最后通过完整验证矩阵后精确 commit / push。不要把 skipped 当 passed。

## 0. 任务一句话

把 Dashboard 的 SOC 安全时间线从“只读列表”升级成可演示、可筛选、可展开的运营证据面板：用户能按事件类型筛选，展开单条事件查看脱敏详情，复制安全摘要，并用真实浏览器 E2E 证明不泄露 secret / system prompt / stack trace。

## 1. 背景

已交付能力：

- `GET /logs/security-timeline` 已合并 `Log` + `AuditLog`，按时间倒序返回最近事件。
- 后端 `server/tests/test_security_timeline.py` 已覆盖未登录 401、limit cap、demo attack、Guardrails event、newest-first、敏感 sentinel 不外泄。
- 前端 `SecurityTimelinePanel.tsx` 已显示时间线、loading/empty/error/degraded/offline 状态与刷新按钮。
- M3-10/M3-11 已把 Dashboard route section 拆分并加入响应式/可访问性 E2E。
- M3-14 已证明案件报告预览 UX 可以通过真实浏览器 E2E、截图和 sentinel 扫描收口。

当前体验缺口：

- 时间线事件只能浏览，不能按 `全部 / Demo / Copilot / 护栏 / 系统` 快速筛选。
- 每条事件只显示一行摘要，不能展开查看更明确的 source/category/status/time/detail 证据。
- 不能复制单条 SOC 证据摘要用于报告或排障。
- 没有真实浏览器 E2E 覆盖时间线 drilldown、筛选、复制摘要、移动端截图和 DOM sentinel。

本任务默认不改后端 API，不新增数据库字段，不改变脱敏策略；只用现有 `SecurityTimelineItem` 字段做前端 UX 收口。

## 2. 必读上下文

开始前必须完整阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/runs/2026-06-19-m3-14-incident-report-preview-ux.md`
- `docs/runs/2026-06-19-m3-13-dashboard-mobile-visual-qa.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md` 中 M2-03 审计时间线段落
- `server/routers/logs_router.py`
- `server/tests/test_security_timeline.py`
- `web-next/components/dashboard/SecurityTimelinePanel.tsx`
- `web-next/components/dashboard/sections/DashboardSecurityTimelineSection.tsx`
- `web-next/hooks/useSecurityTimeline.ts`
- `web-next/types/securityTimeline.ts`
- `server/tests/e2e_helpers.py`
- `server/tests/test_dashboard_responsive_e2e.py`

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

- `web-next/components/dashboard/SecurityTimelinePanel.tsx`
- 可新增 `web-next/components/dashboard/SecurityTimelineDetail.tsx`
- 可新增 `web-next/components/dashboard/SecurityTimelineFilters.tsx`
- `web-next/types/securityTimeline.ts`（仅限前端展示辅助类型，不改变后端字段语义）
- `web-next/hooks/useSecurityTimeline.ts`（仅限保留现有请求、必要小型 helper，不改 API path）
- 新增 `server/tests/test_security_timeline_drilldown_e2e.py`
- 必要时轻量更新 `server/tests/test_dashboard_responsive_e2e.py`
- `docs/runs/2026-06-20-m3-15-soc-timeline-drilldown-filter-ux.md`
- `docs/runs/artifacts/m3-15-soc-timeline-drilldown/**`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

禁止修改：

- 认证 / 授权
- `server/security/**` / Guardrails
- SSRF
- DB schema / Alembic migration
- `server/routers/logs_router.py` 和 timeline API contract，除非发现现有测试失败且必须先停下汇报
- `server/models_db.py`
- npm 依赖
- rate limit 常量
- `.env`、`.coverage`、数据库、真实密钥
- 用 `localStorage` / `sessionStorage` 存 timeline 内容
- 使用 `dangerouslySetInnerHTML` 或 `innerHTML`
- 把 regex、stack trace、system prompt、API key、raw guardrail reason 写入 DOM、截图说明、运行日志或测试输出

## 4. 运行预算与停止条件

预算：

- 最长运行 4 小时。
- 同一失败最多修复 3 轮。
- diff 超过约 900 行时停止总结，除非主要是测试/文档。

必须停止并写清楚阻塞：

- 真实浏览器 E2E 无法启动，且不能通过 `PLAYWRIGHT_CHROMIUM_EXECUTABLE` 指到系统 Chrome 解决。
- dev server 无法稳定返回 `/api/backend/health`。
- 需要修改认证、Guardrails、SSRF、DB schema、后端 timeline API、依赖或 rate limit 常量。
- E2E 只能 skipped，无法获得真实浏览器 pass。
- 时间线 DOM 或复制文本中出现 forbidden sentinel。
- 筛选 UX 需要后端新增 query 参数才能完成。

## 5. 产品验收标准

完成后用户应该能在 Dashboard 的 SOC 时间线里完成：

1. 看到筛选控件：
   - 全部
   - Demo
   - Copilot
   - 护栏
   - 系统
2. 点击筛选后列表只显示对应类别，并显示筛选后的数量。
3. 点击任一事件可展开详情：
   - 时间
   - 来源 `LOG` / `AUD`
   - 类别中文名
   - 状态
   - 脱敏摘要
   - 安全说明：`已隐藏敏感字段`
4. 再次点击或按 `Escape` 可收起详情。
5. 点击复制摘要可复制一条不含 secret 的 SOC 证据摘要；剪贴板不可用时显示可接受降级文案。
6. 桌面和移动端不产生横向溢出，筛选按钮文字不挤出容器。
7. DOM、复制文本、截图说明均不包含 forbidden sentinel。

## 6. 推荐设计

### 6.1 UI 形态

在 `SecurityTimelinePanel` 顶部标题行下方加入紧凑筛选条：

- `data-testid="security-timeline-filter-all"`
- `data-testid="security-timeline-filter-demo"`
- `data-testid="security-timeline-filter-copilot"`
- `data-testid="security-timeline-filter-guardrails"`
- `data-testid="security-timeline-filter-system"`
- 当前 filter 用 `aria-pressed="true"`。

每条事件保留行式密度，但变成 button-like 可展开项：

- `data-testid="security-timeline-item"`
- `data-expanded="true"` 只出现在展开项。
- 展开详情容器 `data-testid="security-timeline-detail"`。
- 复制按钮 `data-testid="security-timeline-copy-summary"`。
- 复制状态 `data-testid="security-timeline-copy-status"`。

视觉要求：

- 保持当前 SOC 工具风格：紧凑、信息密集、低噪声。
- 不使用 modal，不做大卡片堆叠，不重做视觉系统。
- 移动端允许筛选条横向滚动或换行，但不能让整页横向溢出。
- 展开详情应像“证据抽屉”，不遮挡后续内容。

### 6.2 前端分类逻辑

不要改后端 category。前端按现有字段归组：

```text
all: 所有
demo: category === "demo_attack"
copilot: category === "copilot_stream"
guardrails: category startsWith "guardrail_"
system: 其他 category
```

计数使用当前已加载 `items` 计算，不向后端发新请求。

### 6.3 复制摘要

复制文本只由当前脱敏字段组成，建议格式：

```text
[SOC] <time> <source>/<categoryLabel> <status> - <summary>
```

禁止把 raw backend detail、regex、stack trace、system prompt、API key、完整 guardrail reason 放进复制文本。

### 6.4 建议组件边界

可新增：

```text
web-next/components/dashboard/SecurityTimelineFilters.tsx
web-next/components/dashboard/SecurityTimelineDetail.tsx
```

`SecurityTimelinePanel.tsx` 负责：

- filter state
- expanded item key state
- copy status state
- 列表筛选和渲染组合

新增组件只负责展示，不 fetch。

## 7. TDD / E2E 计划

### Task 1：创建运行日志

创建：

```text
docs/runs/2026-06-20-m3-15-soc-timeline-drilldown-filter-ux.md
```

初始内容必须包含：

- 开始时间。
- 当前 `git status --short --branch`。
- 当前 `git log -1 --oneline`。
- 必读上下文清单。
- 允许/禁止范围。
- 阶段计划。
- 停止条件。
- 当前工作区已有跨任务 artifact 脏文件，不允许 broad stage。

### Task 2：RED - 新增真实浏览器 E2E

新增：

```text
server/tests/test_security_timeline_drilldown_e2e.py
```

必须复用：

- `server.tests.e2e_helpers.assert_dev_server_reachable`
- `server.tests.e2e_helpers.register_or_login_for_e2e`
- `server.tests.e2e_helpers.skip_without_playwright`

测试流程：

1. 启动 Playwright chromium，支持 `PLAYWRIGHT_CHROMIUM_EXECUTABLE`。
2. 登录 Dashboard。
3. 等待 `security-timeline` 可见。
4. 触发 Demo 攻击，必要时点击刷新时间线。
5. 等待至少一条 `security-timeline-item`。
6. 断言筛选按钮存在。
7. 点击 Demo 筛选，断言可见项 `data-category="demo_attack"` 或列表为空时显示明确筛选空态。
8. 点击全部。
9. 点击第一条事件展开，等待 `security-timeline-detail`。
10. 断言 detail 中有 source/category/status/time/summary 和 `已隐藏敏感字段`。
11. 点击复制摘要，断言状态为 `已复制` 或 `复制失败`，但页面不崩溃。
12. 按 Escape，断言 detail 收起。
13. 扫描整页 DOM forbidden sentinel。
14. 桌面截图：

```text
docs/runs/artifacts/m3-15-soc-timeline-drilldown/security-timeline-desktop.png
```

15. 设置移动 viewport 390x844，重复打开 timeline 和展开详情，保存：

```text
docs/runs/artifacts/m3-15-soc-timeline-drilldown/security-timeline-mobile.png
```

RED 预期：

- 当前 UI 没有筛选按钮和 detail 容器，测试应 fail 在 `security-timeline-filter-demo` 或 `security-timeline-detail` selector。
- 不允许 skip 掉缺失 selector。

### Task 3：GREEN - 实现最小 UX

实现：

- 筛选 state 与筛选条。
- 列表按 filter 显示。
- 展开详情。
- Escape 收起。
- 复制摘要。
- 筛选空态。

可接受的最小组件：

- 直接在 `SecurityTimelinePanel.tsx` 内实现，如果文件增长过大再拆 `SecurityTimelineFilters.tsx` / `SecurityTimelineDetail.tsx`。
- 如果拆组件，组件必须无 fetch、无 storage。

### Task 4：IMPROVE - de-sloppify

检查并修复：

- 是否留下 `console.log`。
- 是否用了 `localStorage` / `sessionStorage`。
- 是否用了 `dangerouslySetInnerHTML` / `innerHTML`。
- 是否复制了 raw detail / raw reason。
- 筛选按钮是否有 `aria-pressed`。
- 展开项是否有可识别的 `aria-expanded`。
- `Escape` 是否只影响 timeline 展开详情，不误伤全局。
- 移动端是否横向溢出。

扫描命令：

```powershell
rg -n "console\.log|localStorage|sessionStorage|dangerouslySetInnerHTML|innerHTML|sk-|AKIA|ghp_|PRIVATE KEY|Traceback|system:|developer:" web-next\components\dashboard server\tests\test_security_timeline_drilldown_e2e.py
```

命中测试 sentinel 常量允许；生产组件命中敏感字面量必须修。

### Task 5：验证矩阵

如果本机 Chromium `spawn EPERM`，优先使用系统 Chrome：

```powershell
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
```

如需隔离 dev server，可沿用 M3-14 的 8100/3100 方案，但必须写进运行日志。

必须运行：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_security_timeline_drilldown_e2e.py -q --tb=short --run-e2e -s -rs
```

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_security_timeline.py -q --tb=short
```

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_dashboard_responsive_e2e.py -q --tb=short --run-e2e -s -rs
```

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_auth_session_e2e.py server\tests\test_demo_flow_e2e.py server\tests\test_incident_report_e2e.py server\tests\test_dashboard_route_sections_e2e.py server\tests\test_dashboard_responsive_e2e.py server\tests\test_demo_flow_stability_e2e.py server\tests\test_dashboard_mobile_visual_e2e.py server\tests\test_incident_report_preview_e2e.py server\tests\test_security_timeline_drilldown_e2e.py -q --tb=short --run-e2e -s -rs
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

如果 npm shim 损坏，可使用本地 binary 等价命令，但必须写进运行日志。

### Task 6：文档同步

更新：

- `PRODUCT.md`：在 M3 当前状态中补 M3-15 已交付摘要。
- `docs/plans/M2_PRODUCT_ROADMAP.md`：补 M3-15 摘要。
- `docs/agent/UNATTENDED_LONG_TASKS.md`：新增 M3-15 条目，推荐口令改为下一条候选。
- `docs/runs/2026-06-20-m3-15-soc-timeline-drilldown-filter-ux.md`：记录真实命令、结果、截图路径、commit hash、push 状态。

下一条候选建议：

- 若 owner 授权安全核心：`M3-16 Guardrails moderation httpx pool 健康监控`。
- 若继续产品体验：`M3-16 Dashboard operational runbook / health checklist UX`，把 `/health`、env security check、demo readiness 和 E2E readiness 汇总成运维检查面板。

默认推荐继续产品体验，除非 owner 明确授权动 Guardrails。

### Task 7：精确 commit / push

禁止 `git add .`。

建议拆分：

1. `test(e2e): 覆盖 SOC 时间线筛选与展开`
2. `feat(dashboard): 增强 SOC 时间线筛选与详情`
3. `docs(timeline): 记录 SOC 时间线 UX 收口`

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
- 与本任务无关的 M3-11/M3-12/M3-13/M3-14 artifact 或缓存

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
- 未改 auth / Guardrails / SSRF / DB schema / 后端 timeline API / npm 依赖 / rate limit
- 未提交 .coverage / env / DB / 密钥
- DOM / copy text forbidden sentinel 扫描结果

运行日志：
- docs/runs/2026-06-20-m3-15-soc-timeline-drilldown-filter-ux.md

下一条建议：
- <建议>
```

## 9. 启动口令

```text
请执行 `docs/agent/M3_15_SOC_TIMELINE_DRILLDOWN_FILTER_UX_TASK.md` 中定义的 L5 超长任务。先完整阅读任务文档和必读上下文，创建运行日志，新增真实浏览器 E2E 覆盖 SOC 时间线筛选、展开详情、复制摘要、桌面/移动截图和 forbidden sentinel，再实现 `SecurityTimelinePanel` 的最小筛选/详情 UX。只允许前端 timeline UX、E2E、截图和文档同步，不要修改认证/授权/Guardrails/SSRF/DB schema/后端 timeline API/npm 依赖/rate limit，不要使用 localStorage/sessionStorage 或 `dangerouslySetInnerHTML`，不要提交 `.coverage`、真实 env、数据库或密钥。通过新增 timeline drilldown E2E、后端 timeline 测试、Dashboard responsive E2E、九组关键 E2E、后端全量、Guardrails、前端 typecheck/build 后，精确拆分 commit 并 push 到 `origin/main`，完成后输出最终报告。
```
