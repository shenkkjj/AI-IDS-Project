# M3 Demo-Ready SOC Workbench Closing Task

> 任务级别：L4 长任务收口战役。
> 适用场景：M3-01 Dashboard 产品体验升级已经完成实现与返工，需要做完整验证、拆分提交、提交后复核，但暂不 push。
> 给 agent 的原则：这是一个长任务，不是“补一个 commit”。必须按阶段推进、留下证据、精确 stage。

---

## 0. 启动前必读

执行前必须完整阅读：

- `PRODUCT.md`
- `AGENTS.md`
- `CLAUDE.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/runs/2026-06-16-m3-demo-ready-soc-workbench.md`
- 本文件

如果上述文件与当前工作树不一致，以当前代码和测试结果为准，并在运行日志中记录差异。

---

## 1. 任务目标

把当前 M3-01 Demo-Ready SOC 工作台改造收口成可审查、可回退、可继续开发的稳定本地基线：

1. 验证 M3 工作树没有越界修改。
2. 修正或明确处理剩余小问题。
3. 跑完整质量门，包括真实浏览器 Demo Flow。
4. 用精确路径拆分提交。
5. 提交后复查，确认只剩本地覆盖率和个人配置改动。

---

## 2. 运行模式与预算

- 运行模式：L4 长任务收口战役。
- 最长运行：2 小时。
- 同一失败最多修复：3 轮。
- 如果新增代码 diff 超过约 800 行且不是文档/测试日志，停止并总结。
- 本任务允许 commit，但不允许 push。

---

## 3. 允许修改

只允许修改以下范围：

- `server/tests/test_demo_flow_e2e.py`
- `web-next/app/page.tsx`
- `web-next/app/dashboard/dashboard-client.tsx`
- `web-next/components/dashboard/**`
- `web-next/types/**`
- `web-next/utils/**`
- `docs/runs/2026-06-16-m3-demo-ready-soc-workbench.md`
- `docs/runs/2026-06-16-m3-verify-briefing-buckets.mjs`
- 必要时可新增一个更合适的验证脚本位置，例如 `web-next/scripts/**` 或 `scripts/**`，但必须同步运行命令说明

---

## 4. 禁止修改

禁止修改：

- `.coverage`
- `.claude/settings.local.json`
- 真实 `.env`
- git 历史重写
- `server/security/**`
- 认证/授权业务语义
- 数据库 schema / migration
- `web-next/app/api/**`
- 部署、nginx、CI 安全策略

禁止操作：

- 不要使用 `git add .`
- 不要 push
- 不要 reset / clean
- 不要删除数据库或清空数据
- 不要为了通过测试跳过、删除、弱化测试

---

## 5. 当前已知背景

当前 M3 改造应包含：

- Dashboard 拆分为多个子组件。
- 新增告警详情面板、简报区、状态壳。
- 修复 `deriveBriefing` 周简报 168 小时窗口不应生成 168 个桶的问题。
- 修复 Copilot WebSocket 离线时不应隐藏输入面板的问题。
- 修复 Demo Flow E2E 中 Playwright async 调用、首页 test id 可达性、注册确认密码和 hydration 等待问题。

验收基线应至少达到：

- `node docs\runs\2026-06-16-m3-verify-briefing-buckets.mjs` 通过。
- `npm run typecheck` 通过。
- `npm run build` 通过。
- `pytest server\tests -q --tb=short` 通过。
- 若本机存在 Chrome：
  - `$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'; pytest server\tests\test_demo_flow_e2e.py --run-e2e -q -rs --tb=short` 通过。
- 若没有 Chrome 或 Playwright 浏览器，必须清楚记录 skip 原因，不得伪称通过。

---

## 6. 阶段计划

### 阶段 1：工作树审计

运行：

```powershell
git status --short --branch
git diff --cached --name-only
git diff --stat
git diff --check
```

必须确认：

- 暂存区为空。
- `.coverage` 和 `.claude/settings.local.json` 未 stage。
- 除已知 M3 文件外没有无关改动。

### 阶段 2：代码审计

检查以下点：

- `deriveBriefing(alerts, 24).buckets.length === 24`
- `deriveBriefing(alerts, 168).buckets.length === 7`
- `CopilotSection` 在 `offline=true` 时仍渲染 `CopilotPanel`
- `web-next/app/page.tsx` 的 `login-email` / `login-password` / `register-confirm-password` test id 在真实 input 上
- `server/tests/test_demo_flow_e2e.py` 使用 async Playwright API 时有正确 `await`
- 原 E2E 关键选择器仍存在：
  - `trigger-demo-attack`
  - `analyze-current-alert`
  - `attack-log-row`
  - `copilot-message`
  - `security-timeline-item`

### 阶段 3：验证矩阵

按顺序运行，不要并行运行 `npm run typecheck` 和 `npm run build`，避免 `.next/types` 竞争。

```powershell
node docs\runs\2026-06-16-m3-verify-briefing-buckets.mjs
cd web-next
npm run typecheck
npm run build
cd ..
pytest server\tests -q --tb=short
pytest server\tests\test_demo_flow_e2e.py -q -rs --tb=short
```

然后启动本地服务并跑显式 E2E：

```powershell
.\.venv\Scripts\python.exe -m uvicorn server.main:app --host 127.0.0.1 --port 8000
cd web-next
npm run dev
```

另一个终端运行：

```powershell
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
pytest server\tests\test_demo_flow_e2e.py --run-e2e -q -rs --tb=short
```

完成后必须停止本地 dev server。

### 阶段 4：运行日志同步

更新 `docs/runs/2026-06-16-m3-demo-ready-soc-workbench.md`：

- 增加返工记录。
- 增加真实浏览器 E2E 结果。
- 修正过时描述，例如“offline 时整面板降级为 StatusView”如果已不准确，必须改成最新行为。
- 修正新增文件数量、验证结果和残留风险。

### 阶段 5：拆分提交

只使用精确路径 stage。推荐提交：

1. `test(e2e): 修复 Demo Flow 浏览器验收链路`
   - `server/tests/test_demo_flow_e2e.py`
   - `web-next/app/page.tsx`

2. `chore(dashboard): 增加简报派生类型与状态壳`
   - `web-next/types/alertBriefing.ts`
   - `web-next/utils/alertBriefingUtils.ts`
   - `web-next/types/index.ts`
   - `web-next/utils/index.ts`
   - `web-next/components/dashboard/StatusView.tsx`
   - `docs/runs/2026-06-16-m3-verify-briefing-buckets.mjs`

3. `feat(dashboard): 拆分 SOC 工作台组件并增强告警体验`
   - `web-next/app/dashboard/dashboard-client.tsx`
   - `web-next/components/dashboard/AlertDetailPanel.tsx`
   - `web-next/components/dashboard/AlertSection.tsx`
   - `web-next/components/dashboard/BriefingSection.tsx`
   - `web-next/components/dashboard/CopilotSection.tsx`
   - `web-next/components/dashboard/DemoFlowControls.tsx`
   - `web-next/components/dashboard/SecurityTimelinePanel.tsx`
   - `web-next/components/dashboard/SystemStatusBar.tsx`
   - `web-next/components/dashboard/SystemStatusSection.tsx`

4. `docs: 记录 M3 Demo-Ready SOC 工作台收口`
   - `docs/runs/2026-06-16-m3-demo-ready-soc-workbench.md`

每个 commit 前必须运行：

```powershell
git diff --cached --name-only
```

确认 staged 文件只属于当前 commit。

### 阶段 6：提交后复核

运行：

```powershell
git status --short --branch
git log --oneline -8
git diff --cached --name-only
git log --name-only --format="commit %h %s" HEAD~4..HEAD
```

必须确认：

- 新增 4 个 commit。
- `.coverage` 和 `.claude/settings.local.json` 没有进入提交。
- 暂存区为空。
- 当前不 push。

---

## 7. 停止条件

遇到以下任一情况必须停止：

- 显式 E2E 真实业务失败，且连续修复 3 轮仍失败。
- 需要修改认证/授权业务语义才能继续。
- 发现 M3 改造泄漏 secret、stack trace、regex 或 system prompt。
- 需要改后端 API 契约才能让前端通过。
- 任何命令需要真实生产 secret。
- stage 时发现 `.coverage` 或 `.claude/settings.local.json` 被误加入。

停止时必须输出：

- 已完成阶段。
- 阻塞证据。
- 当前 `git status --short --branch`。
- 下一条建议长任务文档。

---

## 8. 最终输出

完成后输出：

- 完成状态：完成 / 部分完成 / 阻塞。
- 4 个 commit hash 与 message。
- 运行过的验证命令和结果。
- 运行日志路径。
- 最终 `git status --short --branch`。
- 是否建议进入 push 前总审查。

