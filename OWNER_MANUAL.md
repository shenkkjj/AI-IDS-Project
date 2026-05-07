# AI-CyberSentinel 拥有者手册

> 赛博朋克风格 AI 入侵检测与防御平台 —— 从流量嗅探、AI 分析、自动拦截到邮件告警的一体化防护系统。

---

## 目录

1. [项目愿景](#1-项目愿景)
2. [架构全景](#2-架构全景)
3. [技术栈](#3-技术栈)
4. [功能清单](#4-功能清单)
5. [项目结构](#5-项目结构)
6. [本地启动指南](#6-本地启动指南)
7. [完整 API 参考](#7-完整-api-参考)
8. [部署与运维](#8-部署与运维)
9. [安全配置说明](#9-安全配置说明)
10. [故障排查](#10-故障排查)

---

## 1. 项目愿景

**AI-CyberSentinel** 是一句：用 AI 替代传统规则引擎，实现从"流量抓取 → 智能分析 → 自动防御"全链路的零延迟网络入侵检测系统。

---

## 2. 架构全景

```
┌─────────────────────────────────────────────────────┐
│                     互联网流量                        │
└─────────────────┬───────────────────────────────────┘
                  ▼
┌─────────────────────────────────────────────────────┐
│              agent/sniffer.py（Scapy 抓包引擎）        │
│  混杂模式抓取 TCP/UDP/ICMP 包 → 提取特征向量           │
└─────────────────┬───────────────────────────────────┘
                  ▼
┌─────────────────────────────────────────────────────┐
│         agent/defender.py（防火墙执行器）             │
│  收到阻断指令 → 调用 netsh(Win) / iptables(Linux)     │
│  添加/移除 IP 黑名单规则                              │
└─────────────────┬───────────────────────────────────┘
                  ▼
┌─────────────────────────────────────────────────────┐
│         server/（FastAPI 后端 · 核心处理中枢）         │
│  ┌─────────────────────────────────────────────┐    │
│  │ routers/waf_router.py → WAF 网关              │    │
│  │  拦截 SQLi / XSS / 路径穿越 / 命令注入        │    │
│  │  12 条正则规则 + 响应头注入                     │    │
│  └─────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────┐    │
│  │ services/auth_service.py → 认证中枢           │    │
│  │  密码 / OTP / OAuth 登录 + 注册 + 密码重置    │    │
│  │  JWT 签发 + bcrypt 哈希 + Fernet 加密存储    │    │
│  └─────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────┐    │
│  │ services/llm_service.py → AI 分析引擎         │    │
│  │  支持 5 种 LLM 后端 + 自定义 Provider         │    │
│  │  攻击载荷智能分类 + Security Copilot 对话     │    │
│  └─────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────┐    │
│  │ services/alert_service.py → 告警引擎          │    │
│  │  4 线程 Worker 池 + 实时 WebSocket 推送       │    │
│  │  邮件/桌面通知/Slack Webhook 多通道分发        │    │
│  └─────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────┐    │
│  │ services/totp_service.py → TOTP 双因素认证    │    │
│  │  基于时间的一次性密码 + 备用码支持              │    │
│  └─────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────┐    │
│  │ services/threat_intel_service.py → 威胁情报   │    │
│  │  IP 黑名单管理 + AbuseIPDB 集成              │    │
│  └─────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────┐    │
│  │ core/rate_limiter.py → 速率限制器             │    │
│  │  注册限流 / 登录限流 / IP 通用限流             │    │
│  └─────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────┐    │
│  │ core/state.py → 全局状态管理器                 │    │
│  │  Redis 连接 / 限流器实例 / 蜜罐开关 / SSL 监控 │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────┬───────────────────────────────────┘
                  ▼
┌─────────────────────────────────────────────────────┐
│              SQLite + PostgreSQL（数据层）              │
│  SQLite: 用户/告警/日志/配置持久化（开发环境）           │
│  PostgreSQL: 生产环境高并发支持                         │
│  Redis:  速率限制计数 / 会话缓存 / 热点数据             │
└─────────────────────────────────────────────────────┘
                  ▼
┌─────────────────────────────────────────────────────┐
│          web-next/（Next.js 15 前端）                 │
│  ┌─────────────────────────────────────────────┐    │
│  │ app/page.tsx → 赛博朋克登录/注册页            │    │
│  │  矩阵雨 + 电路板背景 + 光斑扫描动画            │    │
│  └─────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────┐    │
│  │ app/dashboard/ → 实时安全态势看板              │    │
│  │  StatsCards / AttackLogTable / CopilotPanel │    │
│  │  HackerTerminal / CyberSidebar / LLM配置     │    │
│  │  AttackTrendChart / SourcePieChart          │    │
│  └─────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────┐    │
│  │ app/api/backend/[...path]/route.ts → 代理层  │    │
│  │  请求转发 → 后端 127.0.0.1:8000               │    │
│  │  Session JWT 解码提取 access_token            │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

**数据流向**：流量 → Scapy 抓包 → 特征提取 → WAF 过滤 → AI 分析（LLM） → 告警引擎 → 通知分发 → 防火墙阻断。前端通过 Next.js API 代理层调用后端，Session 由自定义 JWT 管理。

---

## 3. 技术栈

### 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| Next.js | 15.5.16 | React 全栈框架（App Router） |
| React | 19.1 | UI 渲染 |
| TypeScript | 5.9 | 类型安全 |
| Tailwind CSS | 3.4 | 原子化样式 |
| GSAP | 3.15 | 高性能动画引擎 |
| Framer Motion | 12.11 | 声明式动画 |
| Lucide React | 0.544 | SVG 图标库 |

### 后端

| 技术 | 版本 | 用途 |
|------|------|------|
| FastAPI | 0.136 | Python 异步 Web 框架 |
| Uvicorn | 0.45 | ASGI 服务器 |
| SQLAlchemy | 2.0 | ORM 数据库访问 |
| Loguru | 0.7 | 结构化日志 |
| bcrypt | 4.3 | 密码哈希 |
| python-jose | 3.4 | JWT 签发/验证 |
| cryptography | 46.0 | Fernet 加密（API Key） |
| fastapi-mail | 2.1 | 邮件发送 |
| Scapy | 2.7 | 网络包抓取/构造 |
| scikit-learn | 1.8 | 机器学习（攻击分类） |
| pandas | 3.0 | 数据预处理 |
| httpx | 0.28 | 异步 HTTP 客户端 |

### 基础设施

| 组件 | 用途 |
|------|------|
| SQLite | 主数据库（开发环境：用户/告警/日志/配置） |
| PostgreSQL | 生产环境数据库 |
| Redis 7 | 限流计数 / 会话缓存 |
| Docker Compose | 容器化编排 |

---

## 4. 功能清单

### 认证与用户

- [x] 邮箱密码注册（密码强度校验：8位+大小写+数字+符号）
- [x] 邮箱密码登录 → JWT 令牌签发（TV 机制防旧令牌复用）
- [x] OTP 验证码邮件登录（6 位数字，10 分钟过期，hmac 时序安全比较）
- [x] 忘记密码（邮件验证码重置，10 分钟过期）
- [x] OAuth 第三方登录（GitHub / Google）
- [x] TOTP 双因素认证（基于时间的一次性密码 + 备用码）
- [x] 安全登出（令牌版本号自增，旧令牌立即失效）
- [x] Session 验证（Bearer Token + Cookie 双通道）
- [x] 多层速率限制（注册 / 登录 / OTP / 通用 IP）
- [x] 用户角色管理（admin / analyst / viewer）

### AI 智能分析

- [x] 多 LLM 后端支持（OpenAI / DeepSeek / Claude / Gemini / 自定义 Provider）
- [x] LLM 连通性测试（支持 5 种 Provider 端点自动适配）
- [x] 攻击载荷智能分类（SQLi / XSS / 命令注入 / 路径穿越）
- [x] Security Copilot 流式对话（SSE 实时返回）
- [x] API Key Fernet 加密存储（DB 中不存明文）
- [x] AI 模型训练与重训练（RandomForest 分类器）

### 安全防护

- [x] WAF 网关（12 条正则规则拦截 SQLi / XSS / 命令注入 / 路径穿越）
- [x] WAF 响应安全头注入（X-Content-Type-Options 等）
- [x] WAF 状态监控（`GET /waf/status`）
- [x] 威胁情报黑名单（IP 黑名单管理）
- [x] AbuseIPDB 威胁情报查询
- [x] 自动防火墙阻断（IP 临时封禁 10 分钟）
- [x] 全局 CSP 安全策略（开发/生产环境分离）

### 监控与告警

- [x] 实时告警采集（4 线程 Worker 池）
- [x] WebSocket 实时推送告警
- [x] 多通道通知（邮件 / 桌面 Toast / Slack Webhook / DingTalk / 飞书）
- [x] 站点健康监测（Uptime 监控）
- [x] SSL 证书到期预警
- [x] 操作审计日志（200 条/用户隔离）

### 数据管理

- [x] 新威胁确认入库（CSV 沉淀至 `data/new_threats.csv`）
- [x] 用户配置中心（AI / 告警 / UI 偏好持久化）
- [x] 数据库自动迁移（列级验证 + ALTER TABLE 自动修补）
- [x] 审计日志导出（CSV 格式）
- [x] 合规审计报告生成

### 前端交互

- [x] 赛博朋克风格矩阵雨背景
- [x] 电路板 + 光斑扫描动画
- [x] 实时攻防态势看板 Dashboard
- [x] 攻击日志表格（分页 / 级别筛选）
- [x] 攻击趋势图表（AttackTrendChart）
- [x] 来源分布饼图（SourcePieChart）
- [x] 7 块统计卡片（流量 / 威胁 / 拦载率）
- [x] 黑客终端模拟器（命令输入交互）
- [x] 网络安全侧边栏导航
- [x] LLM 配置面板（Provider 选择 / 模型切换 / Base URL）
- [x] 桌面通知支持（useDesktopNotify）
- [x] 多语言支持（en.json / zh.json）
- [x] 主题切换（light / dark）
- [x] 全局错误边界 + 加载态

---

## 5. 项目结构

```
AI-IDS-Project/
├── agent/                          # 抓包与防御引擎
│   ├── sniffer.py                  # Scapy 网络包抓取 + 特征提取
│   └── defender.py                 # 防火墙规则管理（IP 封禁/解封）
│
├── server/                         # FastAPI 后端
│   ├── main.py                     # 应用入口（CORS / 中间件 / 路由注册）
│   ├── security_utils.py           # JWT / bcrypt / Fernet 加密工具
│   ├── mailer.py                   # 邮件发送（OTP / 重置 / 告警）
│   ├── analyzer.py                 # AI 分析引擎
│   ├── models_db.py                # SQLAlchemy ORM 模型
│   ├── core/                       # 核心模块
│   │   ├── config.py               # 环境变量加载 & WAF 规则定义
│   │   ├── database.py             # SQLite 连接 & 自动迁移
│   │   ├── security.py             # 认证依赖（require_auth_user）
│   │   ├── rbac.py                 # 角色权限控制
│   │   ├── state.py                # 全局状态（Redis / 限流器 / 开关）
│   │   ├── rate_limiter.py         # 多层速率限制实现
│   │   ├── llm_utils.py            # LLM 端点适配 & 测试请求构造
│   │   ├── websocket.py            # WebSocket 连接管理器
│   │   └── utils.py                # 通用工具（IP 提取等）
│   ├── models/                     # Pydantic 请求/响应 Schema
│   │   └── schemas.py
│   ├── routers/                    # API 路由层
│   │   ├── auth_router.py          # /auth/*（注册/登录/OTP/重置/登出/TOTP）
│   │   ├── user_router.py          # /user/config（用户配置）
│   │   ├── alerts_router.py        # /alerts/*（告警查询/WebSocket）
│   │   ├── logs_router.py          # /logs（操作日志）
│   │   ├── llm_router.py           # /llm/*（配置/测试）
│   │   ├── site_router.py          # /site/*（目标/健康）
│   │   ├── copilot_router.py       # /copilot/*（AI 对话）
│   │   ├── waf_router.py           # /waf/*（WAF 代理/状态）
│   │   ├── admin_router.py         # /admin/roles/*（角色管理）
│   │   ├── notify_router.py        # /notify/*（通知/Webhook 测试）
│   │   ├── export_router.py        # /export/*（数据导出）
│   │   ├── threat_intel_router.py  # /threat-intel/*（威胁情报）
│   │   └── compliance_router.py    # /compliance/*（合规审计）
│   └── services/                   # 业务服务层
│       ├── auth_service.py         # 认证核心逻辑
│       ├── user_service.py         # 配置读写逻辑
│       ├── llm_service.py          # LLM 测试/调用逻辑
│       ├── alert_service.py        # 告警 Worker 池
│       ├── totp_service.py         # TOTP 双因素认证
│       ├── notification_service.py # 多通道通知
│       ├── threat_intel_service.py # 威胁情报管理
│       ├── site_monitor_service.py # 站点监控
│       ├── audit_service.py       # 审计日志服务
│       └── copilot_service.py     # AI Copilot 服务
│
├── models/                         # 机器学习模型
│   ├── train.py                    # 模型训练脚本
│   ├── retrain.py                  # 模型重训练脚本
│   ├── rf_model.pkl               # RandomForest 模型
│   └── scaler.pkl                  # 特征标准化器
│
├── simulator/                      # 攻击模拟器
│   └── attacker.py                 # 自动化攻击测试
│
├── web-next/                       # Next.js 15 前端
│   ├── app/
│   │   ├── layout.tsx              # 全局布局 + 元数据
│   │   ├── page.tsx                # 赛博朋克登录/注册页
│   │   ├── providers.tsx           # SessionProvider 配置
│   │   ├── error.tsx               # 全局错误边界
│   │   ├── dashboard/              # Dashboard 仪表盘
│   │   │   ├── page.tsx            # 认证守卫 + 数据加载
│   │   │   └── dashboard-client.tsx# 看板主组件
│   │   ├── api/
│   │   │   ├── auth/[...nextauth]/ # NextAuth 路由
│   │   │   └── backend/[...path]/  # 后端 API 代理
│   │   ├── components/
│   │   │   └── animated-characters/# 动画角色组件
│   │   ├── contexts/               # React Context
│   │   │   ├── LocaleContext.tsx  # 多语言上下文
│   │   │   └── ThemeContext.tsx   # 主题上下文
│   │   └── hooks/                 # 自定义 Hooks
│   │       ├── useDesktopNotify.ts # 桌面通知
│   │       └── useWebSocket.ts    # WebSocket 连接
│   ├── components/
│   │   ├── dashboard/              # Dashboard 组件库
│   │   │   ├── AttackLogTable.tsx
│   │   │   ├── AttackTrendChart.tsx
│   │   │   ├── CopilotPanel.tsx
│   │   │   ├── CyberSidebar.tsx
│   │   │   ├── HackerTerminal.tsx
│   │   │   ├── SourcePieChart.tsx
│   │   │   └── StatsCards.tsx
│   │   └── ui/                     # 基础 UI 组件
│   │       ├── button.tsx
│   │       └── card.tsx
│   ├── locales/                    # i18n 翻译文件
│   │   ├── en.json                # 英文
│   │   └── zh.json                # 中文
│   ├── lib/
│   │   ├── auth.ts                 # NextAuth 配置
│   │   └── utils.ts                # 工具函数
│   ├── middleware.ts               # 安全头注入
│   ├── next.config.js              # Next.js 配置
│   ├── package.json
│   └── tsconfig.json
│
├── scripts/                        # 运维脚本
│   ├── backup_db.sh                # 数据库备份
│   └── daily_ops_check.sh          # 日检脚本
│
├── nginx/                          # Nginx 配置
│   └── nginx.conf                  # 反向代理配置
│
├── docker-compose.yml              # 容器编排
├── .env                            # 当前环境变量（gitignore）
├── .env.example                    # 环境变量模板
├── requirements.txt                # Python 依赖
└── OWNER_MANUAL.md                 # 本文档
```

---

## 6. 本地启动指南

### 前置条件

- Python 3.12+
- Node.js 20+
- Redis 7（可选，限流功能需要）
- Windows: Npcap（Scapy 抓包需要）

### 6.1 后端启动

```bash
# 1. 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate     # Windows
# source .venv/bin/activate # Linux/macOS

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量（复制模板）
cp .env.example .env
# 编辑 .env 填入：APP_SECRET、SMTP 配置、LLM_API_KEY 等

# 4. 初始化数据库（首次自动创建 SQLite）
python -c "from server.core.database import init_db; init_db()"

# 5. 启动后端（开发模式）
python -m uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload
```

### 6.2 前端启动

```bash
# 1. 进入前端目录
cd web-next

# 2. 安装依赖
npm install

# 3. 启动开发服务器
npm run dev
# → http://localhost:3000
```

### 6.3 关键环境变量（`.env`）

```env
# ---------- 安全核心 ----------
APP_SECRET=your-secret-at-least-32-chars  # JWT 签名密钥（必填）
AUTH_SECRET=your-auth-secret              # NextAuth 加密密钥（必填）
APP_JWT_ALG=HS256                         # JWT 算法
APP_FERNET_KEY=                           # API Key 加密密钥（自动生成）

# ---------- 数据库 ----------
DATABASE_URL=sqlite:///./data/app.db      # 开发环境
# DATABASE_URL=postgresql://user:pass@host:5432/db  # 生产环境
REDIS_URL=redis://localhost:6379/0

# ---------- SMTP 邮件 ----------
MAIL_USERNAME=your@email.com
MAIL_PASSWORD=your_smtp_auth_code
MAIL_FROM=your@email.com
MAIL_SERVER=smtp.qq.com
MAIL_PORT=465
MAIL_STARTTLS=false
MAIL_SSL_TLS=true

# ---------- AI 模型 ----------
LLM_API_KEY=sk-your-key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
LLM_ADMIN_TOKEN=internal-token-for-admin

# ---------- 威胁情报 ----------
ABUSEIPDB_API_KEY=
SHODAN_API_KEY=
```

---

## 7. 完整 API 参考

### 认证 `/auth`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `POST` | `/auth/register` | 无 | 邮箱密码注册 |
| `POST` | `/auth/login/password` | 无 | 密码登录 → JWT |
| `POST` | `/auth/login/otp/request` | 无 | 请求 OTP 验证码邮件 |
| `POST` | `/auth/login/otp/verify` | 无 | OTP 验证码登录 |
| `POST` | `/auth/password/reset/request` | 无 | 请求密码重置验证码 |
| `POST` | `/auth/password/reset/confirm` | 无 | 验证码 + 新密码重置 |
| `GET` | `/auth/session` | Bearer/Cookie | 验证当前令牌有效性 |
| `POST` | `/auth/logout` | Bearer/Cookie | 登出（令牌版本号自增） |
| `POST` | `/auth/login/oauth` | 无 | OAuth 登录（GitHub/Google） |
| `POST` | `/auth/totp/setup` | Bearer/Cookie | 设置 TOTP 双因素认证 |
| `POST` | `/auth/totp/enable` | Bearer/Cookie | 启用 TOTP |
| `POST` | `/auth/totp/disable` | Bearer/Cookie | 禁用 TOTP |
| `POST` | `/auth/totp/verify` | Bearer/Cookie | 验证 TOTP 码 |

### 用户配置 `/user`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/user/config` | Bearer/Cookie | 获取用户偏好配置 |
| `PUT` | `/user/config` | Bearer/Cookie | 更新用户偏好配置 |

### LLM 配置 `/llm`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/llm/config` | Admin Token | 获取运行时 LLM 配置 |
| `PUT` | `/llm/config` | Admin Token | 更新运行时 LLM 配置 |
| `POST` | `/llm/test` | Bearer/Cookie | 测试 LLM 连通性（支持 5 种 Provider） |

### 告警 `/alerts`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/alerts` | Bearer/Cookie | 查询告警列表（`?limit=100`） |
| `WS` | `/alerts/ws/alerts` | Token/Header | WebSocket 实时告警推送 |

### 日志 `/logs`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/logs` | Bearer/Cookie | 查询操作日志（隔离到当前用户） |

### 站点监控 `/site`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `POST` | `/site/target` | Bearer/Cookie | 设置监控站点 URL |
| `GET` | `/site/health` | Bearer/Cookie | 查询站点健康状态 |

### Copilot `/copilot`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `POST` | `/copilot/stream` | Bearer/Cookie | Security Copilot AI 流式对话（SSE） |
| `POST` | `/copilot/threats/confirm` | Bearer/Cookie | 确认威胁并入库 |

### WAF `/waf`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/waf/status` | 无 | WAF 状态监控 |
| `*` | `/waf/proxy/{path}` | 无 | WAF 网关代理（GET/POST/PUT/DELETE/PATCH） |

### 威胁情报 `/threat-intel`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/threat-intel/check/{ip}` | 无 | 检查 IP 是否在黑名单 |
| `GET` | `/threat-intel/status` | 无 | 威胁情报状态 |
| `POST` | `/threat-intel/refresh` | Admin | 刷新威胁情报黑名单 |

### 合规审计 `/compliance`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/compliance/audit-report` | Admin | 下载合规审计报告（CSV） |

### 通知 `/notify`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `POST` | `/notify/webhook/test` | Bearer/Cookie | 测试 Webhook 连通性 |

### 导出 `/export`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/export/alerts` | Bearer/Cookie | 导出告警（CSV/JSON） |

### 角色管理 `/admin/roles`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/admin/roles/list` | Admin | 列出所有角色 |
| `POST` | `/admin/roles/create` | Admin | 创建角色 |
| `PUT` | `/admin/roles/{role}/permissions` | Admin | 更新角色权限 |

### 健康检查

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/health` | 无 | 服务健康检查 |

---

## 8. 部署与运维

### 8.1 Docker Compose 部署

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 填入生产环境配置

# 2. 构建并启动
docker-compose up -d --build

# 3. 查看日志
docker-compose logs -f backend
docker-compose logs -f frontend

# 4. 停止
docker-compose down
```

服务分布：
- **backend**: `server/Dockerfile` → Python slim 镜像，非 root 用户运行
- **frontend**: `web-next/Dockerfile` → 多阶段构建，standalone 模式
- **nginx**: `nginx:1.27-alpine` → 反向代理
- **postgres**: `postgres:16-alpine` → 生产数据库
- **redis**: `redis:7-alpine` → 限流缓存

### 8.2 后台运行（生产环境）

```bash
# Linux: systemd 服务
sudo tee /etc/systemd/system/cybersentinel-backend.service << 'EOF'
[Unit]
Description=AI-CyberSentinel Backend
After=network.target redis.service

[Service]
Type=simple
User=app
WorkingDirectory=/opt/cybersentinel
EnvironmentFile=/opt/cybersentinel/.env
ExecStart=/opt/cybersentinel/.venv/bin/uvicorn server.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable --now cybersentinel-backend
```

```bash
# Linux: Nginx 反向代理前端
# 构建后使用 pm2 管理
cd web-next && npm run build
pm2 start npm --name "cybersentinel-frontend" -- start
```

### 8.3 数据库备份

```bash
# 使用自带的备份脚本
bash scripts/backup_db.sh

# 或手动备份
cp data/app.db data/backups/app_$(date +%Y%m%d_%H%M%S).db
```

### 8.4 日常巡检

```bash
bash scripts/daily_ops_check.sh
# 检查项：服务存活 / 磁盘空间 / 近期告警数 / SSL 证书有效期
```

---

## 9. 安全配置说明

### 密钥管理

| 密钥 | 位置 | 要求 |
|------|------|------|
| `APP_SECRET` | `.env` | 至少 32 字符，生产环境使用随机生成 |
| `AUTH_SECRET` | `.env` | NextAuth 加密密钥，生产环境使用 `openssl rand -base64 32` |
| `APP_FERNET_KEY` | `.env` | 留空则首次启动自动生成，用于 API Key 加密 |
| `LLM_ADMIN_TOKEN` | `.env` | 访问 `/llm/config` 的管理令牌 |

### WAF 防护规则（12 条）

```
[1] UNION SELECT          → 联合查询注入
[2] UNION /**/ SELECT     → SQL 注释绕过注入
[3] 1=1 / OR 1=1          → 永真条件注入
[4] <script>              → XSS 脚本注入
[5] javascript:           → JS 伪协议注入
[6] exec(                 → 命令执行
[7] eval(                 → 代码执行
[8] DROP TABLE            → 表删除
[9] INSERT INTO           → 数据插入
[10] DELETE FROM          → 数据删除
[11] SQL 注释事件绑定      → 事件属性注入
[12] SQL 字符串拼接       → 字符串拼接注入
```

### 速率限制

| 类型 | 限制 | 窗口 |
|------|------|------|
| 注册 | 3 次 | 1 小时 |
| 登录 | 5 次 | 15 分钟 |
| OTP 请求 | 3 次 | 10 分钟 |
| 通用 IP | 100 次 | 1 分钟 |

### CSP 策略

| 环境 | script-src | connect-src |
|------|-----------|-------------|
| 开发 | `'unsafe-inline' 'unsafe-eval'` | WebSocket + localhost |
| 生产 | `'self'` | `'self'` |

### 角色权限

| 角色 | 权限 |
|------|------|
| admin | 所有操作 |
| analyst | 查看、分析、配置 AI |
| viewer | 仅查看 |

---

## 10. 故障排查

| 症状 | 可能原因 | 排查步骤 |
|------|----------|----------|
| 登录返回 401 | `APP_SECRET` 不匹配 / 密码已重置 | 检查 `.env` → 重启后端 |
| 找回密码显示 dev_code | SMTP 未配置（开发模式降级） | 填入真实 MAIL_USERNAME/PASSWORD/SERVER |
| LLM 测试失败 | API Key 无效 / 网络不通 / 缺少 `import time` | `curl https://api.deepseek.com/v1/models -H "Authorization: Bearer $KEY"` |
| 注册永久挂起 | `register_lock` 死锁 | 已修复：检查 `auth_service.py` 中无外层锁 |
| 前端 ERR_ABORTED | 旧 Session Cookie 签名不匹配 | 清除浏览器 Cookie 或使用无痕模式 |
| 中间件报错 | 旧 `auth()` 类型断言失败 | 已移除中间件中的 `auth()` 调用 |
| Redis 连接失败 | Redis 未启动 / 地址错误 | `redis-cli ping` → 检查 `REDIS_URL` |
| 端口占用 | 旧进程未杀掉 | `netstat -ano \| findstr ":8000"` → `taskkill /PID xxx /F` |
| 数据库列缺失 | 模型更新后未迁移 | 重启后端会自动 ALTER TABLE 添加缺失列 |

---

## 11. 测试

### 运行单元测试

```bash
# 运行所有测试
python -m pytest server/tests/ -v

# 运行特定测试
python -m pytest server/tests/test_auth.py -v

# 带覆盖率
python -m pytest server/tests/ -v --cov=server --cov-report=html
```

### 测试端点

```bash
# 健康检查
curl http://localhost:8000/health

# 用户注册
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test123456!","display_name":"Test"}'

# 用户登录
curl -X POST http://localhost:8000/auth/login/password \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test123456!"}'
```

---

*文档版本：v5.0 | 更新日期：2026-05-07 | 基于代码扫描生成，反映最新项目状态*
