# Docker Compose 本地启动指南（M2-07）

> 读者：项目 owner、新成员。
> 目的：照本文执行即可在本地拉起 AI-CyberSentinel 全栈。
> 任务：M2-07 Docker Compose 端到端验收。

---

## 0. 前置条件

- Windows 10/11 + PowerShell 5+ 或 PowerShell 7+。
- Docker Desktop 已安装并启动（Docker daemon 必须运行）。
- 仓库根目录的 `.venv/` 和 `node_modules/` 不需要在 Docker 启动时准备；容器自己装。

## 1. 准备本地 env 文件（不污染真实 `.env`）

**不要**直接用 `.env` 跑 Compose；M2-07 用一份本地专用的临时文件，git 不会跟踪：

```powershell
# 复制模板
Copy-Item .env.example .env.compose.local

# 用 Python 生成临时安全值
python -c "
import secrets
keys = ['APP_SECRET','AUTH_SECRET','ALERTS_INGEST_TOKEN','GUARDRAILS_MCP_API_KEY','POSTGRES_PASSWORD','REDIS_PASSWORD']
for k in keys:
    print(f'{k}={secrets.token_urlsafe(48)}')
"
```

把上面输出粘贴到 `.env.compose.local` 对应 key（替换占位值）。

> 安全提醒：临时 secret 仅用于本地；不要打印到终端或 commit。

## 2. 验证 Compose 语法

```powershell
docker compose --env-file .env.compose.local config
```

应输出 6 个 service：postgres / redis / migrate / backend / frontend / nginx。

## 3. 一键 build / up / smoke

我们提供 `scripts/compose_smoke.ps1`：

```powershell
.\scripts\compose_smoke.ps1 -EnvFile .env.compose.local
```

脚本会自动：

1. 验证 `docker compose config` 语法。
2. `build backend frontend nginx`。
3. `up -d`。
4. 等待后端 `/health` 返回 200（最多 60s）。
5. 等待后端 `/ready` 返回 200（最多 90s）。
6. 验证 `http://127.0.0.1/health`（nginx 入口）返回 200。
7. 验证 `http://127.0.0.1:3000`（前端首页）返回 HTML。
8. 验证 `http://127.0.0.1/api/auth/login/password`（通过 nginx 走到后端）可达。
9. 打印 `docker compose ps`。

**任何一步失败立刻停止**，并打印相应服务的日志尾部。

## 4. 手动逐步命令（适合调试）

```powershell
# build
docker compose --env-file .env.compose.local build

# up
docker compose --env-file .env.compose.local up -d

# 状态
docker compose --env-file .env.compose.local ps

# 日志（按服务）
docker compose --env-file .env.compose.local logs --tail=200 backend
docker compose --env-file .env.compose.local logs --tail=200 frontend
docker compose --env-file .env.compose.local logs --tail=200 nginx
docker compose --env-file .env.compose.local logs --tail=200 migrate

# 验证端点
Invoke-WebRequest http://127.0.0.1:8000/health
Invoke-WebRequest http://127.0.0.1:8000/ready
Invoke-WebRequest http://127.0.0.1/health       # 通过 nginx
Invoke-WebRequest http://127.0.0.1:3000          # 前端首页

# 触发 demo attack
.\scripts\demo_attack.ps1 -BaseUrl http://127.0.0.1:8000 -Email demo@example.com -Password DemoPass123! -Scenario sql_injection

# 停止（保留数据卷）
docker compose --env-file .env.compose.local down

# 完全清理（删 backend-data / postgres-data / redis-data）
docker compose --env-file .env.compose.local down -v
```

## 5. 入口方案

### 5.1 本地 HTTP 入口（默认，方案 A）

- nginx listen 80（容器内 `127.0.0.1:80` 暴露到宿主）。
- 直接 `http://127.0.0.1`、`http://127.0.0.1:3000`、`http://127.0.0.1:8000` 访问。
- `nginx/nginx.conf` 已写好；不需要证书。
- `deploy.ps1` 默认走这个方案。

### 5.2 HTTPS 入口（opt-in，方案 B）

需要：

1. 把 `fullchain.pem` + `privkey.pem` 放到 `nginx/certs/`（参考 [`nginx/certs/README.md`](../../nginx/certs/README.md)）。
2. 打开 `nginx/nginx.conf` 把 HTTPS server 块取消注释。
3. 重新 build nginx + up。
4. 通过 `https://127.0.0.1` 验证。

不要在未放证书时启用 443；nginx 会因为找不到证书退出。

## 6. 数据库与迁移

- 默认 `DATABASE_URL=postgresql+psycopg://cybersentinel:cybersentinel@postgres:5432/cybersentinel`（显式声明 driver，与 `server/core/database.py` 一致）。
- `migrate` 服务在 backend 启动前跑 `alembic upgrade head`，确保 PostgreSQL 库从 M2-01 baseline 启动。
- 旧 SQLite 路径不受影响（开发库 `data/app.db` 与容器挂载 `backend-data:/app/data` 不互相覆盖）。

## 7. 已知限制

- 沙箱或无 Docker daemon 环境跑不通 `compose_smoke.ps1`；本任务在该环境会报 `Cannot connect to the Docker daemon`，属预期内。请在有 Docker 的机器跑。
- `start_all.bat` 启动的是旧版静态 `web/`，不是当前推荐的 `web-next/`。
- 当前后端代码没有自动 `alembic upgrade head` 启动钩子；容器化路径必须显式跑 `migrate` 步骤。
- `GUARDRAILS_MCP_API_KEY` 为空时 `/mcp` 端点会 401 拒绝所有调用（fail-closed），与 `server/main.py` 行为一致。

## 8. 回滚

- 临时 env 文件不需要回滚（git 不跟踪）。
- `docker-compose.yml` / `nginx/nginx.conf` / `web-next/Dockerfile` / `server/Dockerfile` 的 M2-07 改动都在一个 commit 里，回滚直接 revert。
- `nginx/certs/README.md` 是新增文件，独立 revert。
- `.gitignore` 加了 `nginx/certs/*`，revert 后该规则会消失，**不会**误删任何已存在的证书文件。
