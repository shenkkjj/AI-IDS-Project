# M2-07 Push 与运行日志最终收口 L5 超长任务

> 任务级别：L5，高风险收口任务。
> 目标读者：接手本仓库的开发 agent。
> 任务日期：2026-06-17。
> 核心目标：把本地已经完成的 M2-07 Docker Compose 端到端工作，从“本地 commit 已落地但未推送、运行日志有后续补充”推进到“证据完整、禁提交文件安全、远端已同步”，或留下明确阻塞证据。

---

## 0. 任务背景

当前仓库曾执行过 `docs/agent/M2_07_DOCKER_COMPOSE_E2E_READINESS_TASK.md`。

已知现状：

- 本地 `main` 有提交 `5e4d158 feat(deploy): M2-07 docker compose e2e readiness`。
- `main` 当前显示可能为 `origin/main: ahead 1`。
- M2-07 commit 已包含 Docker Compose、nginx、Dockerfile、smoke 脚本、部署文档等改动。
- `docs/runs/2026-06-17-m2-07-docker-compose-e2e-readiness.md` 在 commit 后又追加了“阶段 10-13”证据，当前可能仍未提交。
- `.coverage`、`.claude/settings.local.json` 是本地噪声或个人配置，禁止提交。
- 上一轮 `git push origin main` 失败原因记录为 `schannel: failed to receive handshake, SSL/TLS connection failed`，疑似本机 github.com 网络/TLS 受限。

本任务不是重做 M2-07，而是做最终收口：复核证据、补齐运行日志提交、处理远端同步。

---

## 1. 必读上下文

开始前必须完整阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/agent/M2_07_DOCKER_COMPOSE_E2E_READINESS_TASK.md`
- `docs/runs/2026-06-17-m2-07-docker-compose-e2e-readiness.md`
- `docs/deploy/COMPOSE_QUICKSTART.md`
- `docker-compose.yml`
- `nginx/nginx.conf`
- `server/Dockerfile`
- `web-next/Dockerfile`
- `scripts/compose_smoke.ps1`

如果当前环境支持 skill，先按 `AGENTS.md` 的 Skill-First Workflow 选择并阅读相关 skill。部署、Docker、git 收口、验证相关 skill 优先。

---

## 2. 运行模式与预算

运行模式：L5，无人值守超长收口。

时间预算：

- 最长连续执行 2-4 小时。
- 同一个失败最多修复 3 轮。
- push 网络失败最多重试 2 次；如果失败签名相同，不要硬刷。
- diff 超过约 500 行时停止总结，除非主要是运行日志。

停止条件：

- 远端 `origin/main` 已经前进，且本地 commit 无法直接 fast-forward 推送。
- 发现本地 commit 中包含真实 secret、真实 `.env`、`.coverage`、`.claude/settings.local.json`、数据库文件或证书私钥。
- Docker smoke 复核失败，且同一根因修复 3 轮仍失败。
- 需要改认证/授权、安全护栏核心、数据库 schema，但本任务没有授权。
- `git push` 持续因为网络、权限、认证或 TLS 失败。

---

## 3. 允许与禁止

允许修改：

- `docs/runs/2026-06-17-m2-07-docker-compose-e2e-readiness.md`
- `docs/agent/M2_07_PUSH_AND_RUNLOG_FINALIZATION_TASK.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- 如果复核发现 M2-07 部署文档和脚本之间有事实不一致，可小范围修改：
  - `docs/deploy/COMPOSE_QUICKSTART.md`
  - `README.md`
  - `scripts/compose_smoke.ps1`
  - `docker-compose.yml`
  - `nginx/nginx.conf`
  - `server/Dockerfile`
  - `web-next/Dockerfile`

禁止修改或提交：

- 真实 `.env`
- `.env.compose.local`
- `.coverage`
- `.claude/settings.local.json`
- `data/*.db` / `*.db`
- `nginx/certs/*.pem` / `*.key` / `*.crt`
- `server/security/**`
- 认证/授权业务语义
- 数据库 schema / migration 设计
- git history 重写

禁止操作：

- 不要使用 `git add .`
- 不要使用 `git reset --hard`
- 不要使用 `git clean`
- 不要 force push
- 不要绕过 hook
- 不要打印真实 secret

---

## 4. 必须创建或更新运行日志

本任务不新建新的 run log，直接追加到：

```text
docs/runs/2026-06-17-m2-07-docker-compose-e2e-readiness.md
```

追加一个新章节：

```markdown
### 阶段 14：push 与运行日志最终收口
```

章节必须记录：

- 当前时间。
- 当前分支、HEAD、`origin/main`。
- 工作树状态。
- 未提交文件列表。
- 禁提交文件是否未 staged。
- M2-07 smoke 是否复核。
- push 是否成功。
- 如果失败，失败命令、错误摘要、下一步。

---

## 5. 阶段计划

### 阶段 1：读取上下文和确认工作面

运行：

```powershell
git status --short --branch
git log --oneline --decorate --max-count=8
git diff --name-status
git diff --cached --name-status
git branch -vv
```

要求：

- 确认当前分支是 `main`。
- 确认是否 `ahead 1`。
- 确认 staged 区为空，或只包含本任务允许文件。
- 明确 `.coverage`、`.claude/settings.local.json` 是否存在本地改动。

### 阶段 2：复核 M2-07 commit 内容

运行：

```powershell
git show --stat --name-status --max-count=1 HEAD
git show --format=fuller --max-count=1 HEAD
```

检查：

- HEAD 是否为 `5e4d158 feat(deploy): M2-07 docker compose e2e readiness` 或同等 M2-07 commit。
- commit 是否包含 `server/Dockerfile`、`scripts/compose_smoke.ps1`、`nginx/nginx.conf` 等真实修复。
- commit message 的验证证据与运行日志是否一致。

如果 HEAD 不是 M2-07 commit：

- 不要 push。
- 在 run log 写清楚实际 HEAD。
- 停止并输出阻塞。

### 阶段 3：禁提交文件审查

运行：

```powershell
git ls-files .env
git check-ignore -v .env.compose.local
git check-ignore -v nginx/certs/fullchain.pem
git check-ignore -v nginx/certs/README.md
git diff --cached --name-only
```

还要人工检查 staged 文件名，不允许出现：

- `.coverage`
- `.claude/settings.local.json`
- `.env`
- `.env.compose.local`
- `*.db`
- `nginx/certs/*.pem`
- `nginx/certs/*.key`
- `nginx/certs/*.crt`

如果已经 staged 了禁止文件：

- 用精确路径执行 `git restore --staged <path>`，不要用 `git reset`。
- 在 run log 记录原因。

### 阶段 4：运行日志后续补充提交

当前 `docs/runs/2026-06-17-m2-07-docker-compose-e2e-readiness.md` 可能在 M2-07 commit 后又补了 smoke 和 push 阻塞证据。

检查：

```powershell
git diff -- docs/runs/2026-06-17-m2-07-docker-compose-e2e-readiness.md
```

如果 diff 只是运行日志证据补充：

```powershell
git add docs/runs/2026-06-17-m2-07-docker-compose-e2e-readiness.md
git commit -m "docs(runs): 补齐 M2-07 push 收口证据"
```

如果还有本任务文档或索引改动，也可以精确 stage：

```powershell
git add docs/agent/M2_07_PUSH_AND_RUNLOG_FINALIZATION_TASK.md
git add docs/agent/UNATTENDED_LONG_TASKS.md
```

提交前必须再次运行：

```powershell
git diff --cached --name-status
git diff --cached --check
```

不要 stage `.coverage` 或 `.claude/settings.local.json`。

### 阶段 5：静态验证矩阵

至少运行：

```powershell
git diff --check
git diff --cached --check
powershell -NoProfile -ExecutionPolicy Bypass -Command "$errors=$null; [System.Management.Automation.PSParser]::Tokenize((Get-Content -Raw 'scripts\compose_smoke.ps1'), [ref]$errors) | Out-Null; if ($errors) { $errors; exit 1 }"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$errors=$null; [System.Management.Automation.PSParser]::Tokenize((Get-Content -Raw 'deploy.ps1'), [ref]$errors) | Out-Null; if ($errors) { $errors; exit 1 }"
```

如果 Docker daemon 可用，再运行：

```powershell
docker compose --env-file .env.compose.local config
.\scripts\compose_smoke.ps1 -EnvFile .env.compose.local
```

如果 Docker daemon 不可用：

- 不要声称 smoke 新鲜通过。
- 引用已有 commit message 和 run log 的历史 smoke 证据。
- 在 run log 明确“本阶段未能复跑 Docker smoke，原因是 daemon 不可用”。

### 阶段 6：远端状态审查

运行：

```powershell
git ls-remote origin refs/heads/main
git rev-parse HEAD
git rev-parse origin/main
git log --oneline origin/main..HEAD
```

判断：

- 如果 `git ls-remote` 失败但错误是网络/TLS/认证，记录阻塞，不要反复重试超过 2 次。
- 如果远端 HEAD 和本地 `origin/main` 一致，且本地只是 ahead，可以 push。
- 如果远端 HEAD 已经前进，先 `git fetch origin main`。如果 fetch 失败，停止。不要盲推。
- 如果 fetch 后需要 merge/rebase，停止并总结，不要在本任务中做复杂历史处理。

### 阶段 7：push

只有满足以下条件才允许 push：

- 工作树没有未解释的业务代码改动。
- staged 区为空，或刚刚 commit 完毕。
- 禁提交文件未 staged 且未出现在待推提交中。
- 本地 `main` 只是在远端基础上 ahead。
- 远端没有未知前进。

执行：

```powershell
git push origin main
```

push 成功后运行：

```powershell
git status --short --branch
git ls-remote origin refs/heads/main
git log --oneline --decorate --max-count=5
```

在 run log 记录：

- push 成功时间。
- 远端 main 新 SHA。
- 本地状态是否不再 ahead。

### 阶段 8：失败处理

如果 push 失败：

- 记录完整命令和错误摘要。
- 不要 force push。
- 不要修改 git config 绕过 TLS。
- 不要删除证书校验。
- 如果是网络/TLS，最终状态写“阻塞：本机无法访问 github.com 或 TLS 握手失败”。
- 下一步建议写：“在能访问 GitHub 的网络中执行 `git push origin main`，或修复本机 Git/TLS 代理配置后重试”。

### 阶段 9：最终复核

完成前运行：

```powershell
git status --short --branch
git diff --name-status
git diff --cached --name-status
git log --oneline --decorate --max-count=8
```

最终报告必须包含：

- 完成状态：完成 / 部分完成 / 阻塞。
- 是否 push 成功。
- 本地 HEAD。
- 远端 main SHA。
- 仍未提交的文件。
- 禁提交文件是否保持未 staged。
- 运行过的验证命令和结果。
- 运行日志路径。

---

## 6. 验收标准

完成标准：

- `docs/runs/2026-06-17-m2-07-docker-compose-e2e-readiness.md` 已记录阶段 14。
- M2-07 commit 和运行日志补充都已提交，或运行日志补充明确无需提交。
- `.coverage` 和 `.claude/settings.local.json` 未提交。
- 真实 `.env`、`.env.compose.local`、证书私钥、数据库文件未提交。
- `git push origin main` 成功，或失败原因被清晰记录。
- 如果 push 成功，`git status --short --branch` 不再显示 ahead。

阻塞也算合格交付，但必须证据清楚。

---

## 7. 给用户的短报告模板

```text
M2-07 收口状态：完成 / 阻塞。

本地 HEAD：
远端 main：
push：
验证：
- ...

未提交文件：
- ...

运行日志：
- docs/runs/2026-06-17-m2-07-docker-compose-e2e-readiness.md

下一步：
- ...
```
