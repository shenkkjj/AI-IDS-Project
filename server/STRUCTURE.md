# 后端结构速查

`server/` 是 AI-CyberSentinel 的 FastAPI 后端。它负责认证、告警、WAF 代理、Copilot 流式接口、LLM 配置、审计日志、指标和 LLM Guardrails。

```text
server/
├── main.py                  # FastAPI app 入口：中间件、路由、/health、/ready、/mcp
├── db.py                    # 兼容旧 import 的 re-export
├── security_utils.py        # JWT / Fernet 等纯安全工具，不依赖 FastAPI
├── analyzer.py              # LLM analyzer、SSRF 防护、URL 构造
├── mailer.py                # SMTP 邮件辅助：OTP、密码重置、告警邮件
├── models_db.py             # SQLAlchemy ORM：User、UserConfig、Log、AuditLog 等
├── fix_db.py                # 旧维护脚本，使用前先确认
├── container-security.json  # 容器安全扫描/配置辅助文件
├── core/                    # 基础设施层
│   ├── config.py            # 环境变量、限流常量、cookie / CORS 校验
│   ├── database.py          # SQLite engine、SessionLocal、Base、init_db、轻量迁移
│   ├── exceptions.py        # DomainException 层级
│   ├── security.py          # JWT cookie helper、认证依赖
│   ├── refresh_tokens.py    # refresh token 签发、轮换、撤销
│   ├── rbac.py              # Role enum 与 require_role
│   ├── rate_limiter.py      # 内存限流器
│   ├── state.py             # 全局 app state：告警队列、后台任务等
│   ├── websocket.py         # WebSocket 连接管理
│   ├── llm_utils.py         # LLM provider 选择与系统提示
│   ├── logging_setup.py     # loguru 日志配置
│   └── utils.py             # 通用辅助函数
├── middleware/
│   └── waf.py               # WAF 中间件
├── models/
│   ├── schemas.py           # Pydantic request / response schema
│   └── constants.py         # 字段长度、枚举等共享常量
├── routers/                 # API 路由层
│   ├── auth_router.py       # 注册、登录、OTP、TOTP、session、密码重置
│   ├── alerts_router.py     # 告警查询、接收、WebSocket
│   ├── copilot_router.py    # /copilot/stream、威胁确认
│   ├── llm_router.py        # LLM 配置与连通性测试
│   ├── user_router.py       # 用户配置
│   ├── admin_router.py      # 角色管理
│   ├── waf_router.py        # /proxy/{path}、/waf/status
│   ├── metrics_router.py    # /metrics Prometheus 文本指标
│   ├── logs_router.py       # 日志查询
│   ├── site_router.py       # 站点监控
│   ├── notify_router.py     # Webhook 测试
│   ├── export_router.py     # 告警 / 日志导出
│   ├── compliance_router.py # 合规审计报告
│   └── threat_intel_router.py
├── services/                # 业务服务层
│   ├── auth_service.py
│   ├── alert_service.py
│   ├── copilot_service.py
│   ├── user_service.py
│   ├── llm_service.py
│   ├── llm_providers.py
│   ├── site_monitor_service.py
│   ├── audit_service.py
│   ├── notification_service.py
│   ├── threat_intel_service.py
│   └── totp_service.py
├── security/
│   └── llm_guardrails/      # LLM 输入 / 输出护栏、审计、MCP 工具
├── migrations/
│   └── sql/                 # 手写 SQL 迁移，例如 guardrails audit 索引
└── tests/                   # pytest 套件；manual/legacy 为旧手工脚本
```

## 启动相关事实

- 后端入口是 `server.main:app`。
- 启动命令：

  ```powershell
  .\.venv\Scripts\python.exe -m uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload
  ```

- `server/main.py` 在 import 阶段会检查 `APP_SECRET` 和 `AUTH_SECRET`，弱默认值或空值会直接退出。
- `/health` 是进程存活检查；`/ready` 会检查数据库、告警 worker 和日志 flusher。
- `/mcp` 端点由 `GUARDRAILS_MCP_API_KEY` 保护；未配置时返回 401。

## 数据库现状

当前 `server/core/database.py` 使用硬编码 SQLite：

```text
data/app.db
```

`.env.example` 中的 `DATABASE_URL` 目前不是后端数据库 engine 的事实来源。PostgreSQL / Docker Compose 数据库接线待确认，迁移计划见 `docs/ALEMBIC_MIGRATION.md`。

## 为什么部分文件仍在 `server/` 根目录

`db.py`、`analyzer.py`、`mailer.py`、`models_db.py`、`security_utils.py` 仍放在包根目录，是为了兼容当前 import 图。它们被 `core/`、`services/`、`routers/` 多处引用，贸然移动会制造大量无业务收益的 import churn。

如果后续重构，可以按下面方向迁移：

| 当前文件 | 推荐目标 | 原因 |
|---|---|---|
| `analyzer.py` | `core/llm_analyzer.py` | LLM plumbing 更接近基础设施 |
| `mailer.py` | `services/mailer.py` | 邮件是 I/O adapter，接近服务层 |
| `models_db.py` | `models/db.py` | ORM 与 Pydantic schema 放在同域 |
| `security_utils.py` | `core/jwt_fernet.py` | 纯安全原语适合放在 core |
| `db.py` | 删除 | 当前只是兼容 re-export |

## 推荐验证命令

后端默认测试：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.\.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

Guardrails：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.\.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

`server/tests/test_e2e.py` 已标记为可选 E2E。默认基线会收集它但跳过；真实浏览器端到端验证需要显式加 `--run-e2e` 并准备 Playwright 浏览器。
