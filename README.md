# AI-CyberSentinel: AI 驱动的网络安全 WAF 平台

## 🚀 项目愿景

打造一个集"实时拦截、智能分析、主动防御、多模态交互"于一体的 SaaS 化安全防护平台。通过"机器学习流量过滤 + 大模型语义深探"的双引擎架构，为用户提供工业级的网址保护。

## 🛡️ 核心架构 (The Four-Layer Defense)

1. **感知层 (The Ear)**: 基于 Scapy 与反向代理技术，实时捕获流量。不再是简单的被动监听，而是作为 WAF 守住网址入口。
2. **过滤层 (The Brain - ML)**: 使用随机森林（Random Forest）算法，在毫秒级识别 SQL 注入、XSS 等传统特征码攻击。
3. **分析层 (The Soul - LLM)**: 聚合 GPT-4, Claude 3.5, Gemini, Grok 等顶级大模型，对可疑 Payload 进行深度意图溯源与风险评估。
4. **防御层 (The Sword)**: 联动系统防火墙实现秒级自动封禁，并通过邮件与语音实时告警。

## ✨ 核心功能模块

### 1. 安全态势仪表盘 (Security Dashboard)
- **专业极简设计**: 基于 Next.js + shadcn/ui 的苹果风格界面，简洁专业的视觉设计。
- **实时监测**: 攻击趋势图表、来源分布饼图、实时告警看板。
- **交互终端**: 内置黑客终端模拟器，支持命令输入交互。

### 2. SaaS 用户系统与持久化
- **多渠道登录**: 集成 NextAuth.js，支持 GitHub/Google OAuth 及邮箱验证码登录。
- **配置无感恢复**: 用户配置的模型偏好、API Keys、告警设置均存储于数据库，登录后自动同步，无需重复配置。
- **安全保障**: 密码采用 Bcrypt 哈希，敏感 API Key 采用 Fernet 对称加密存储。

### 3. Security Copilot (AI 安全副驾驶)
- **上下文交互**: 点击任一拦截记录即可呼出 AI 浮窗。AI 自动读取该 Payload 数据并给出防御建议。
- **自动化报表**: 每日凌晨由 AI 汇总昨日数据，生成打字机效果的《安全态势总结报告》。

### 4. 智能告警体系
- **多维度通知**: 发现高危攻击时，系统自动发送精美邮件报告，并触发浏览器语音预警。
- **站点监测**: 实时监测被保护网址的存活状态（Uptime），宕机立即提醒。

## 🛡️ 核心攻击防御矩阵 (Detection Matrix)

| 攻击类型 | 检测手段 | AI 处理逻辑 |
| :--- | :--- | :--- |
| **SQL 注入** | 正则匹配 + 随机森林 | 分析 Payload 中的特殊字符频率与布尔逻辑关键词 |
| **XSS 跨站脚本** | 行为指纹识别 | 识别 `<script>` 注入及编码后的恶意代码 |
| **自动化扫描** | Nmap/AWVS 指纹分析 | 识别特定的 User-Agent、请求头顺序及扫描步长 |
| **暴力破解** | 频率限制 (Rate Limiting) | 监测单 IP 对登录接口的非正常请求频率 |

## ✅ 已完成功能

- [x] 邮箱密码注册与登录
- [x] OTP 验证码邮件登录
- [x] OAuth 第三方登录（GitHub / Google）
- [x] TOTP 双因素认证
- [x] 多层速率限制
- [x] 用户角色管理（admin / analyst / viewer）
- [x] WAF 网关（12 条正则规则）
- [x] 多 LLM 后端支持（OpenAI / DeepSeek / Claude / Gemini / 自定义）
- [x] Security Copilot 流式对话
- [x] 实时 WebSocket 告警推送
- [x] 多通道通知（邮件 / 桌面通知 / Webhook）
- [x] 站点健康监测与 SSL 证书预警
- [x] 操作审计日志
- [x] 数据库自动迁移
- [x] Docker Compose 一键部署

## 📂 项目结构

```
AI-IDS-Project/
├── agent/                    # 抓包嗅探引擎与 WAF 反向代理模块
├── server/                   # FastAPI 后端核心
│   ├── core/               # 核心模块（配置、数据库、安全、限流等）
│   ├── routers/            # API 路由层
│   ├── services/           # 业务服务层
│   └── models/             # Pydantic Schema
├── web-next/                # Next.js 15 前端
├── models/                  # 机器学习模型训练脚本
├── data/                    # SQLite 数据库存储
├── simulator/               # 攻击模拟测试工具
├── nginx/                   # Nginx 反向代理配置
├── scripts/                 # 运维脚本
├── docker-compose.yml       # 容器编排
└── deploy.ps1              # Windows 一键部署脚本
```

## 🛠️ 技术栈

- **Frontend**: Next.js 15, Tailwind CSS, shadcn/ui, Framer Motion
- **Backend**: FastAPI, Uvicorn, SQLAlchemy, Pydantic
- **Security**: NextAuth.js, Bcrypt, Cryptography (Fernet), TOTP
- **AI**: Scikit-learn, OpenAI/Anthropic/Google/xAI SDKs
- **Database**: SQLite (开发) / PostgreSQL (生产)
- **Cache**: Redis 7
- **Container**: Docker Compose

## 🚀 快速开始

### 环境要求

- Python 3.12+
- Node.js 20+
- Docker & Docker Compose

### Docker Compose 部署（推荐）

```bash
# 1. 克隆项目
git clone <your-repo-url>
cd AI-IDS-Project

# 2. 复制环境变量模板
cp .env.example .env

# 3. 运行部署脚本（自动生成安全密钥）
powershell -ExecutionPolicy Bypass -File deploy.ps1

# 或手动运行 Docker Compose
docker compose up -d
```

访问地址：
- 前端: http://localhost:3000
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs

### 本地开发

```bash
# 后端
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn server.main:app --reload

# 前端
cd web-next
npm install
npm run dev
```

## 🔐 安全配置

部署前必须在 `.env` 中配置以下密钥：

```env
APP_SECRET=<至少32字符的安全密钥>
AUTH_SECRET=<NextAuth加密密钥>
POSTGRES_PASSWORD=<PostgreSQL密码>
REDIS_PASSWORD=<Redis密码>
```

运行 `deploy.ps1` 会自动生成这些密钥。

## 🐳 服务架构

```
┌─────────────────────────────────────────┐
│              nginx (反向代理)            │
│         端口: 80/443                    │
└────────────┬───────────────────────────┘
              │
    ┌─────────┴─────────┐
    ▼                   ▼
┌─────────┐         ┌─────────┐
│ frontend │         │ backend │
│ (Next.js)│         │(FastAPI)│
│ :3000    │         │ :8000   │
└────┬─────┘         └────┬─────┘
     │                   │
     │    ┌──────────────┘
     │    │
     ▼    ▼
┌─────────┐    ┌─────────┐
│ postgres │    │  redis  │
│  :5432   │    │  :6379  │
└─────────┘    └─────────┘
```

## 📄 许可证

本项目仅供学习研究使用。

## 🔒 隐私声明

本系统承诺：所有捕获的 Payload 数据在前端展示前均会经过脱敏处理；用户的 API Key 经过硬件隔离级别加密存储，仅在发起 AI 请求时在内存中临时解密。
