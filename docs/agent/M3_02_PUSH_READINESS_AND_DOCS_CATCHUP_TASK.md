# M3-02 Push Readiness and Docs Catch-up Task

> 任务级别：L5 无人值守收口战役。
> 适用场景：M3-02 告警研判与处置工作台已经本地拆分成 5 个 commit，但尚未 push；同时原始任务文档 `docs/agent/M3_02_ALERT_TRIAGE_RESPONSE_WORKBENCH_TASK.md` 仍未纳入版本控制。
> 回复语言：中文。

---

## 0. 启动前必读

完整阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/agent/M3_02_ALERT_TRIAGE_RESPONSE_WORKBENCH_TASK.md`
- `docs/runs/2026-06-17-m3-02-alert-triage-response-workbench.md`
- 本文件

这是一个收口任务，不是新功能任务。不要继续扩大 M3-02 功能范围。

---

## 1. 当前预期状态

预期当前状态：

- 分支：`main`
- 本地 `HEAD`：在 `origin/main` 之后，领先 5 个 M3-02 commit。
- 远端 `origin/main`：仍停在 M3 push readiness 完成后的基线。
- 暂存区为空。
- 本地噪声文件可能存在：
  - `.coverage`
  - `.claude/settings.local.json`
- 未跟踪文档可能存在：
  - `docs/agent/M3_02_ALERT_TRIAGE_RESPONSE_WORKBENCH_TASK.md`
  - `docs/agent/M3_02_PUSH_READINESS_AND_DOCS_CATCHUP_TASK.md`

如果实际状态不同，先审计并写入运行日志，不要盲目 push。

---

## 2. 任务目标

把 M3-02 的本地成果收口成远端可接力基线：

1. 审查 5 个 M3-02 commit 是否符合任务拆分。
2. 确认 `.coverage`、`.claude/settings.local.json` 没有进入任何 commit。
3. 把漏掉的 agent 任务文档补进一个单独 docs commit。
4. 重跑最终质量门。
5. 确认远端未前进。
6. push `main` 到 `origin/main`。
7. push 后确认本地 HEAD 与远端 HEAD 一致。

---

## 3. 允许修改范围

只允许修改或 stage：

- `docs/agent/M3_02_ALERT_TRIAGE_RESPONSE_WORKBENCH_TASK.md`
- `docs/agent/M3_02_PUSH_READINESS_AND_DOCS_CATCHUP_TASK.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/runs/2026-06-17-m3-02-push-readiness-and-docs-catchup.md`

允许创建：

- `docs/runs/2026-06-17-m3-02-push-readiness-and-docs-catchup.md`

---

## 4. 禁止范围

禁止修改、stage、commit：

- `.coverage`
- `.claude/settings.local.json`
- 真实 `.env`
- `server/**`
- `web-next/**`
- 数据库文件
- 构建产物
- CI / deploy / Docker / nginx

禁止操作：

- 不要使用 `git add .`
- 不要 `git reset --hard`
- 不要 `git clean`
- 不要 rebase / merge，除非用户另行明确要求
- 不要为了 push 修改业务代码

---

## 5. 阶段计划

### 阶段 1：创建运行日志

创建：

```text
docs/runs/2026-06-17-m3-02-push-readiness-and-docs-catchup.md
```

记录：

- 开始时间
- 当前分支
- 当前 `HEAD`
- 远端 `origin/main`
- 初始 `git status --short --branch`
- 本任务边界

初始命令：

```powershell
git status --short --branch
git rev-parse HEAD
git ls-remote origin refs/heads/main
git diff --cached --name-only
```

### 阶段 2：M3-02 提交栈审查

运行：

```powershell
git log --oneline origin/main..HEAD
git log --name-only --format="commit %h %s" origin/main..HEAD
git log --name-only --format="commit %h %s" origin/main..HEAD -- .coverage .claude/settings.local.json
```

验收：

- 本地领先 commit 包含 M3-02 的 5 个功能/测试/文档提交。
- `.coverage` 和 `.claude/settings.local.json` 在噪声审查命令中无输出。
- 暂存区为空。

如果领先 commit 数量不是 5，先记录实际情况；只要全部属于 M3-02 且验证通过，可以继续。

### 阶段 3：补交任务文档

确认这两个任务文档内容存在且可读：

- `docs/agent/M3_02_ALERT_TRIAGE_RESPONSE_WORKBENCH_TASK.md`
- `docs/agent/M3_02_PUSH_READINESS_AND_DOCS_CATCHUP_TASK.md`

确认 `docs/agent/UNATTENDED_LONG_TASKS.md` 已列出二者；如果没有，补一条短索引。

只用精确路径 stage：

```powershell
git add -- docs/agent/M3_02_ALERT_TRIAGE_RESPONSE_WORKBENCH_TASK.md docs/agent/M3_02_PUSH_READINESS_AND_DOCS_CATCHUP_TASK.md docs/agent/UNATTENDED_LONG_TASKS.md docs/runs/2026-06-17-m3-02-push-readiness-and-docs-catchup.md
git diff --cached --name-only
```

确认 staged 只包含上述 docs 文件后 commit：

```text
docs(agent): 补齐 M3-02 长任务与推送收口文档
```

### 阶段 4：最终质量门

按顺序运行，不要并行前端 typecheck/build：

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

E2E：

```powershell
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow_e2e.py --run-e2e -q -rs --tb=short
```

如果 E2E 因本地浏览器、Next.js dev server、CSP/hydration、首编译超时等环境原因失败，可以记录为环境限制，但必须说明它是否是业务回归。不要谎称通过。

### 阶段 5：Push Gate

运行：

```powershell
git status --short --branch
git diff --cached --name-only
git log --oneline origin/main..HEAD
git log --name-only --format="commit %h %s" origin/main..HEAD -- .coverage .claude/settings.local.json
git ls-remote origin refs/heads/main
```

只有同时满足以下条件才允许 push：

- 当前分支是 `main`
- 远端 `origin/main` 未前进
- 暂存区为空
- 禁止文件未进入任何 commit
- 质量门通过
- E2E 通过，或 E2E 限制已明确记录且不是业务回归

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

本地 HEAD 必须等于远端 main。

---

## 6. 停止条件

遇到任一情况停止：

- 远端 main 已前进，需要 rebase/merge。
- 暂存区出现 `.coverage`、`.claude/settings.local.json`、真实 `.env`。
- 质量门失败且 3 轮内无法修复。
- 需要改业务代码才能继续。
- 当前领先 commit 不属于 M3-02，或包含未知大范围改动。
- push 需要额外登录/授权。

停止时输出当前 `git status --short --branch`、阻塞证据和下一条建议任务。

---

## 7. 最终报告

完成后用中文输出：

- 完成状态：完成 / 部分完成 / 阻塞
- push 状态：已 push / 未 push
- 本地 commit 列表
- 新增 docs commit hash
- 验证命令与结果
- E2E 结果
- 运行日志路径
- 最终 `git status --short --branch`
- 本地 HEAD 与远端 HEAD
- 剩余本地噪声文件

