# GitHub Push 连通性与凭据恢复 L5 超长任务

> 任务级别：L5，高风险 Git / 凭据 / 发布收口任务。  
> 目标读者：接手本仓库的开发 agent。  
> 任务日期：2026-06-17。  
> 核心目标：在不泄露 secret、不绕过 TLS、不 force push 的前提下，诊断并恢复本机到 GitHub 的 push 能力，把当前本地 `main` 上未推送提交安全推送到 `origin/main`；如果需要用户交互登录或网络策略调整，则留下完整证据并停止。

---

## 0. 当前背景

当前仓库在 `main` 分支上已有本地未推送提交。最近一次验收看到：

- 本地 `main` 领先 `origin/main` 约 3 个 commit。
- ahead commit 包括：
  - `5e4d158 feat(deploy): M2-07 docker compose e2e readiness`
  - `00e90d6 docs(runs): 补齐 M2-07 push 收口证据与运行日志最终状态`
  - `a685c10 docs(runs): 记录 M2-07 push 网络阻塞与最终收口状态`
- `git push origin main` 失败过，错误包括：
  - `Failed to connect to github.com port 443`
  - `schannel: AcquireCredentialsHandle failed: SEC_E_NO_CREDENTIALS`
- `.coverage` 和 `.claude/settings.local.json` 是本地噪声/个人配置，禁止提交。

这不是代码功能任务。不要继续堆产品功能。先把本地提交安全同步到远端，或者明确证明当前机器无法同步。

---

## 1. 必读上下文

开始前完整阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/agent/M2_07_PUSH_AND_RUNLOG_FINALIZATION_TASK.md`
- `docs/runs/2026-06-17-m2-07-docker-compose-e2e-readiness.md`

如当前环境支持 skill，必须优先使用并阅读与 GitHub、终端操作、验证、安全凭据相关的 skill。

---

## 2. 运行模式与预算

运行模式：L5，无人值守诊断 + 安全收口。

时间预算：

- 最长连续执行 2 小时。
- 同一网络错误最多重试 2 次。
- 同一凭据错误最多诊断 2 轮。
- 不允许进入“反复 push 碰运气”模式。

停止条件：

- 需要用户在浏览器、GitHub CLI、凭据管理器或 SSH key 页面中交互登录。
- 需要生成新 SSH key 并添加到 GitHub。
- 需要修改系统代理、防火墙、证书存储或全局 Git TLS 配置。
- 远端 `main` 已经前进，本地不能 fast-forward 推送。
- 发现任何 secret、token、私钥、真实 `.env` 可能被写入日志、暂存区或提交。
- push 连续 2 次同签名失败。

---

## 3. 安全硬规则

禁止：

- 不要 `git add .`
- 不要 force push
- 不要改 `http.sslVerify=false`
- 不要关闭 TLS 校验
- 不要把 token 写进 remote URL
- 不要打印 GitHub token、PAT、cookie、私钥内容
- 不要提交 `.coverage`
- 不要提交 `.claude/settings.local.json`
- 不要提交 `.env` / `.env.compose.local`
- 不要提交 `id_rsa`、`id_ed25519`、`*.pem`、`*.key`
- 不要运行 destructive git 命令，如 `git reset --hard`、`git clean`

允许：

- 只读诊断 Git 配置、远端、分支和凭据状态。
- 使用 `gh auth status` 查看认证状态。
- 使用 `ssh -o BatchMode=yes -T git@github.com` 检查现有 SSH key 是否可用。
- 在 SSH 已经可用时，用 SSH URL 临时 push 当前分支。
- 在 HTTPS 凭据已经可用时，正常 `git push origin main`。
- 追加运行日志，记录脱敏后的诊断证据。

---

## 4. 运行日志

本任务追加到：

```text
docs/runs/2026-06-17-m2-07-docker-compose-e2e-readiness.md
```

追加章节：

```markdown
### 阶段 15：GitHub push 连通性与凭据恢复
```

必须记录：

- 当前时间。
- 当前分支和 HEAD。
- 本地 ahead 提交列表。
- 工作树状态。
- HTTPS 远端状态。
- DNS / TCP / GitHub CLI / SSH 诊断结果。
- 是否成功 push。
- 如果失败，失败原因和需要用户做的下一步。

任何 URL、token、私钥路径、用户名如果包含敏感信息，写入日志前必须脱敏。

---

## 5. 阶段计划

### 阶段 1：确认当前工作树和提交栈

运行：

```powershell
git status --short --branch
git log --oneline --decorate --max-count=12
git log --oneline origin/main..HEAD
git diff --name-status
git diff --cached --name-status
git remote -v
```

要求：

- 确认当前分支是 `main`。
- 确认本地 ahead commit 列表。
- 确认 staged 区为空。
- 确认未提交文件只有已知禁提交噪声，或明确列出其他文件。
- 如果 `git remote -v` 输出包含 token 或密码，运行日志只写 `<redacted>` 版本。

### 阶段 2：禁提交文件和 secret 审查

运行：

```powershell
git diff --cached --name-only
git ls-files .env .coverage .claude/settings.local.json .env.compose.local
git diff --name-only
```

检查 staged 和 ahead commit 中不允许出现：

- `.env`
- `.env.compose.local`
- `.coverage`
- `.claude/settings.local.json`
- `*.db`
- `nginx/certs/*.pem`
- `nginx/certs/*.key`
- `id_rsa`
- `id_ed25519`

如果发现禁止文件已 staged：

```powershell
git restore --staged <精确路径>
```

不要使用 `git reset`。

### 阶段 3：HTTPS 网络与凭据诊断

运行只读命令：

```powershell
Resolve-DnsName github.com
Test-NetConnection github.com -Port 443
git config --show-origin --get-all credential.helper
git config --show-origin --get-all http.proxy
git config --show-origin --get-all https.proxy
git ls-remote origin refs/heads/main
```

判断：

- DNS 失败：网络/DNS 阻塞，停止。
- `Test-NetConnection` 443 失败：网络/防火墙/代理阻塞，停止。
- 443 通但 `git ls-remote` 报 `SEC_E_NO_CREDENTIALS`：凭据管理器或 GitHub 登录缺失，进入阶段 4。
- `git ls-remote` 成功：进入阶段 6。

不要修改代理配置，不要修改 TLS 配置。

### 阶段 4：GitHub CLI 认证状态

如果安装了 `gh`，运行：

```powershell
gh auth status -h github.com
```

判断：

- 如果已登录且 token 有 `repo` 权限，运行：

```powershell
gh auth setup-git -h github.com
git ls-remote origin refs/heads/main
```

`gh auth setup-git` 只允许在 `gh auth status` 已明确显示本机已有登录状态时使用；不要要求用户输入 token。

- 如果未登录，需要网页登录、设备码或 token：
  - 停止。
  - 运行日志写清楚“需要用户执行 `gh auth login -h github.com`”。
  - 不要在无人值守任务里继续。

如果没有 `gh`：

- 在运行日志记录 `gh` 不可用。
- 进入阶段 5 检查 SSH。

### 阶段 5：SSH 现有凭据诊断

只检查现有 SSH key，不生成新 key。

运行：

```powershell
ssh -o BatchMode=yes -T git@github.com
```

常见结果：

- `Hi <user>! You've successfully authenticated...`：SSH 可用，进入阶段 6，可用 SSH URL push。
- `Permission denied (publickey)`：本机没有可用 GitHub SSH key，停止并让用户配置。
- host key 交互提示或其他交互要求：停止，不要自动写 known_hosts。

不要读取或打印 `~/.ssh/id_*` 私钥内容。

### 阶段 6：远端是否可 fast-forward

如果 HTTPS 可用：

```powershell
git ls-remote origin refs/heads/main
```

如果 SSH 可用：

```powershell
git ls-remote git@github.com:shenkkjj/AI-IDS-Project.git refs/heads/main
```

比较远端 SHA 和本地 `origin/main`：

```powershell
git rev-parse origin/main
git rev-parse HEAD
git log --oneline origin/main..HEAD
```

如果远端实际 SHA 不等于本地 `origin/main`：

```powershell
git fetch origin main
git status --short --branch
```

如果 fetch 后出现需要 merge/rebase：

- 停止。
- 不要自动 merge/rebase。
- 运行日志写清楚远端已前进。

如果远端与本地 `origin/main` 一致，且本地只是 ahead，进入阶段 7。

### 阶段 7：push

HTTPS 路径：

```powershell
git push origin main
```

SSH 临时路径（不改 remote）：

```powershell
git push git@github.com:shenkkjj/AI-IDS-Project.git main:main
```

要求：

- 只 push `main:main`。
- 不要 force。
- 如果失败，不要超过 2 次同签名重试。

push 成功后运行：

```powershell
git ls-remote origin refs/heads/main
git status --short --branch
git log --oneline --decorate --max-count=8
```

如果用 SSH push 成功但 HTTPS `origin` 仍不可用：

- 不要强行改 remote。
- 运行日志记录“本次使用 SSH URL 临时推送成功；origin HTTPS 凭据仍需用户后续修复”。

### 阶段 8：提交运行日志

如果阶段 15 日志有新增内容，且没有 secret：

```powershell
git add docs/runs/2026-06-17-m2-07-docker-compose-e2e-readiness.md
git diff --cached --name-status
git diff --cached --check
git commit -m "docs(runs): 记录 GitHub push 连通性收口"
```

如果 push 已经成功但日志 commit 是 push 后才新增的：

- 再次执行阶段 6 和 7，把日志 commit 也推上去。

如果 push 失败：

- 仍可提交运行日志，但不要继续硬刷 push。

### 阶段 9：最终报告

最后运行：

```powershell
git status --short --branch
git log --oneline --decorate --max-count=10
git diff --name-status
git diff --cached --name-status
```

最终报告必须包含：

- 完成状态：完成 / 阻塞。
- 本地 HEAD。
- 远端 main SHA（如可查询）。
- push 是否成功。
- 使用的是 HTTPS 还是 SSH。
- 未提交文件。
- 禁提交文件是否仍未 staged。
- 需要用户做什么。

---

## 6. 合格交付标准

完成：

- 所有本地 ahead commit 已推送到 GitHub。
- `git status --short --branch` 不再显示 ahead。
- 运行日志记录了成功路径。
- 禁提交文件未进入 commit。

阻塞：

- 明确证明是 DNS / TCP / GitHub 凭据 / SSH key / 用户登录交互阻塞。
- 没有关闭 TLS。
- 没有 force push。
- 没有泄露 token 或私钥。
- 运行日志和最终报告都写清楚下一步。

---

## 7. 给用户的短报告模板

```text
GitHub push 收口状态：完成 / 阻塞。

本地 HEAD：
远端 main：
push 路径：HTTPS / SSH / 未执行
关键证据：
- DNS：
- TCP 443：
- gh auth：
- SSH：
- git push：

未提交文件：
- ...

需要你做：
- 如果需要登录：运行 `gh auth login -h github.com`
- 如果需要 SSH：在 GitHub 添加本机公钥后重跑本任务
- 如果网络阻塞：切换到能访问 GitHub 的网络后重跑本任务
```
