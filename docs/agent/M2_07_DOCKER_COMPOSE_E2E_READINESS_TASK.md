# M2-07 Docker Compose 端到端验收战役

> 任务级别：L5 无人值守超长任务
> 场景：M2 产品化进入收口阶段，Compose 现在"看起来能 build"，但本地启动、数据库接线、迁移、nginx 入口、健康检查和登录链路还没有被端到端验收。
> 回复语言：中文

---

## 0. 启动前必读

先完整阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`
- `docs/runs/2026-06-17-m2-01-database-url-alembic-baseline.md`
- `README.md`
- `docker-compose.yml`
- `server/Dockerfile`
- `web-next/Dockerfile`
- `nginx/nginx.conf`
- `server/main.py`
- `server/core/config.py`
- `server/core/database.py`
- `web-next/app/api/backend/[...path]/route.ts`
- `web-next/lib/auth.ts`
- `web-next/middleware.ts`
- `web-next/.env.example`
- `scripts/check_env_security.py`
- `scripts/daily_ops_check.sh`

如果你打算改部署行为，再补读：

- `docs/ALEMBIC_MIGRATION.md`
- `server/STRUCTURE.md`
- `web-next/scripts/smoke-auth-flow.sh`

---

## 1. 任务目标

把当前 Compose 从"能写在 README 里"推进到下面两种结果之一：

1. **本地可用**：用一套明确的本地测试环境变量，能从干净环境一键 `build -> up -> health -> 登录/回源 smoke -> clean up` 跑通。
2. **明确阻塞**：如果某个方向确实做不到，要留下可复现的证据、阻塞原因和下一步，而不是继续靠猜。

你要把项目的 Docker 路径收口成一句话：

> 新人照文档执行，就能把整套服务拉起来并验证关键链路。

---

## 2. 非目标

本任务不做：

- 不推镜像
- 不上线公网
- 不接真实生产证书
- 不改业务功能
- 不改认证/授权语义
- 不改 `server/security/**`
- 不改数据库 schema 设计
- 不引入新产品功能
- 不把 Compose 伪装成"已证明生产可用"，除非真的完成了验证

---

## 3. 已知问题

你需要优先核实这些点：

- `docker-compose.yml` 里后端数据库 URL 和实际驱动是否真的一致，别只停留在字符串看起来对。
- `nginx/nginx.conf` 现在写的是容器内 `127.0.0.1` upstream，这在 nginx 容器里通常是不对的。
- `nginx/nginx.conf` 还引用了 `fullchain.pem` / `privkey.pem`，但 compose 里目前看不到证书挂载。
- 后端启动会检查 `APP_SECRET` / `AUTH_SECRET`，Compose 必须把这些环境变量接好。
- 前端的 origin / host 白名单要和 nginx 的实际入口一致，不然登录和 API 回源会卡。
- 新数据库启动必须有明确迁移路径，不能只靠"启动时碰巧建表"。

如果你发现这里有任意一点没法在当前约束下闭环，就把它写成阻塞证据。

---

## 4. 允许修改范围

优先改配置和文档，不要乱动业务逻辑。

允许修改：

- `docker-compose.yml`
- `server/Dockerfile`
- `web-next/Dockerfile`
- `nginx/nginx.conf`
- `deploy.ps1`
- `.env.example`
- `web-next/.env.example`
- `README.md`
- `docs/deploy/**`
- `docs/runs/2026-06-17-m2-07-docker-compose-e2e-readiness.md`
- `scripts/check_env_security.py`
- `scripts/compose_smoke.ps1` 或类似的小型 smoke 辅助脚本
- `web-next/app/api/backend/[...path]/route.ts`、`web-next/middleware.ts`、`server/main.py`
  仅限于修正 compose 入口、host/origin、启动顺序这类最小问题，不许改认证语义

---

## 5. 禁止修改范围

禁止修改：

- 真正的 `.env`
- `.coverage`
- `.claude/settings.local.json`
- `data/app.db`
- `*.db`
- `server/security/**`
- 认证/授权业务规则
- 数据库 schema 设计本身
- 真实生产密钥
- git 历史
- 公网部署配置
- 镜像推送

禁止操作：

- 不要 `git add .`
- 不要 `git reset --hard`
- 不要 `git clean`
- 不要删除无关卷
- 不要把真实 secret 写进日志

---

## 6. 你必须先做的审计

先创建运行日志：

```text
docs/runs/2026-06-17-m2-07-docker-compose-e2e-readiness.md
```

写入：

- 开始时间
- 当前分支
- `git status --short --branch`
- `git rev-parse HEAD`
- `git ls-remote origin refs/heads/main`
- 你准备采用的本地 ingress 方案
- 允许修改范围
- 禁止修改范围

然后先跑一次现状审计：

```powershell
git status --short --branch
git rev-parse HEAD
git ls-remote origin refs/heads/main
docker compose config
```

如果你要用临时 env 文件，必须自己生成一个只用于本任务的文件，例如：

```text
.env.compose.local
```

这个文件不能提交，不能复用真实 `.env`，也不能把真实 secret 写进日志。

---

## 7. 建议的执行策略

### 阶段 1：RED

先证明当前 Compose 不是"虚假可用"。

建议做这些最小验证：

```powershell
docker compose --env-file .env.compose.local config
docker compose --env-file .env.compose.local build
docker compose --env-file .env.compose.local up -d
docker compose --env-file .env.compose.local ps
docker compose --env-file .env.compose.local logs --tail=100 backend
docker compose --env-file .env.compose.local logs --tail=100 frontend
docker compose --env-file .env.compose.local logs --tail=100 nginx
```

至少确认一个真实失败点，并把它写进运行日志。

### 阶段 2：数据库和迁移收口

你要把下面几件事说清楚并跑通：

- `DATABASE_URL` 在 Compose 里到底怎么传
- PostgreSQL 驱动到底用什么
- 新数据库怎么初始化
- `alembic upgrade head` 是怎么进入流程的

推荐方向：

- 用显式 `postgresql+psycopg://...`
- 为 Compose 加一个明确的 migration 步骤，别让"启动时顺便建表"成为唯一靠山
- 新数据库必须能从 0 启起来

### 阶段 3：入口和网络收口

你必须选定一种并收口：

#### 方案 A：本地 HTTP 入口

优先推荐。要求：

- nginx 走容器服务名，不要再在容器里指向 `127.0.0.1`
- 不要让 443 证书路径成为启动硬前提
- 本地访问和回源白名单要一致

#### 方案 B：保留 HTTPS

如果你坚持保留 HTTPS，必须同时补齐：

- 证书挂载
- 证书生成或放置方式
- 本地验证命令
- 文档说明

不能接受的状态：

- 443 配了但证书不存在
- nginx 起不来但 README 还假装可用
- 后端/前端能单跑，Compose 不能跑

### 阶段 4：健康检查与登录 smoke

必须验证这些路径：

- `GET /health`
- `GET /ready`
- 前端首页
- 通过 nginx 访问 API
- 至少一次登录或注册链路 smoke

如果你选的是本地 HTTP 入口，smoke 至少要覆盖：

- `http://127.0.0.1/`
- `http://127.0.0.1/health`
- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:3000`

如果你选的是 HTTPS 入口，就改成对应的 `https://...` 验证，并把证书方案写清楚。

### 阶段 5：文档和脚本

把真实可用的东西写进：

- `README.md`
- `deploy.ps1`
- `docs/deploy/**`
- `.env.example`
- `web-next/.env.example`

如果你发现需要一个小 smoke 辅助脚本，就加，但脚本要短、直白、可重复。

### 阶段 6：安全和回滚

跑一次安全审计和最终复查：

```powershell
python scripts/check_env_security.py
git diff --check
git diff --stat
git status --short --branch
```

如果你改了环境变量或入口白名单，必须确认：

- 没有把 localhost 误放进生产配置
- 没有把真实 secret 写入仓库
- `/mcp` 仍然是 fail-closed
- 任何新增 env var 都在 `.env.example` 里有明确说明

---

## 8. 验收标准

任务完成时，至少要满足：

- `docker compose build` 通过
- `docker compose up -d` 通过
- backend、frontend、postgres、redis、nginx 的状态清楚
- 至少一个完整入口可以访问
- `/health` 和 `/ready` 有可复现结果
- 前端回源和登录链路有 smoke 证据
- 运行日志写清楚所有阶段
- 文档和脚本与真实行为一致
- `git diff --check` 通过

如果没法全部满足，就输出：

- 完成到哪一步
- 卡点是什么
- 卡点的命令证据
- 下一步最小工单是什么

---

## 9. 提交要求

允许在验证通过后再考虑 commit / push。

提交前先看：

```powershell
git diff --cached --name-only
git log --oneline origin/main..HEAD
git log --name-only --format="commit %h %s" origin/main..HEAD -- .coverage .claude/settings.local.json
```

如果要清理 Compose 资源，只能清理你自己这次任务创建的独立项目，不要误伤其他环境。

---

## 10. 最终输出

完成后用中文汇报：

- 完成状态：完成 / 部分完成 / 阻塞
- 采用了哪种入口方案
- 改了哪些文件
- 跑过哪些命令
- 哪些 smoke 通过了
- 哪些还没完全确认
- 运行日志路径
- 下一条最小工单建议

