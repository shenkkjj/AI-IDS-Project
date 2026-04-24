# AI-CyberSentinel: 下一代 AI 驱动的边缘安全 WAF 平台

## 🚀 项目愿景
打造一个集“实时拦截、智能分析、主动防御、多模态交互”于一体的 SaaS 化安全防护平台。通过“机器学习流量过滤 + 大模型语义深探”的双引擎架构，为用户提供工业级的网址保护。

## 🛡️ 核心架构 (The Four-Layer Defense)
1. **感知层 (The Ear)**: 基于 Scapy 与反向代理技术，实时捕获流量。不再是简单的被动监听，而是作为 WAF 守住网址入口。
2. **过滤层 (The Brain - ML)**: 使用随机森林（Random Forest）算法，在毫秒级识别 SQL 注入、XSS 等传统特征码攻击。
3. **分析层 (The Soul - LLM)**: 聚合 GPT-4, Claude 3.5, Gemini, Grok 等顶级大模型，对可疑 Payload 进行深度意图溯源与风险评估。
4. **防御层 (The Sword)**: 联动系统防火墙实现秒级自动封禁，并通过邮件与语音实时告警。

## ✨ 核心功能模块

### 1. 赛博指挥中心 (Visual Dashboard)
- **颜值重构**: 基于 Next.js + shadcn/ui 的深色科技感界面，配合 Framer Motion 实现丝滑动画。
- **实时监测**: 包含地理溯源地图（IP Geolocation）、实时攻击流看板。
- **黑客终端**: 内置基于 WebSocket 的交互式模拟终端，支持命令行操作。

### 2. SaaS 用户系统与持久化
- **多渠道登录**: 集成 NextAuth.js，支持 GitHub/Google OAuth 及邮箱验证码登录。
- **配置无感恢复**: 用户配置的模型偏好、API Keys、告警设置均存储于 SQLite 数据库，登录后自动同步，无需重复配置。
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

## 🗺️ 项目开发蓝图 (Roadmap)
- [x] **Phase 1**: 基础流量嗅探与 ML 二分类模型 demo。
- [ ] **Phase 2**: SaaS 架构升级，实现 JWT 鉴权与邮件验证码系统。
- [ ] **Phase 3**: 实现反向代理 WAF 核心逻辑与站点健康监测。
- [ ] **Phase 4**: 接入多模型路由引擎与 Security Copilot 对话浮窗。
- [ ] **Phase 5**: 地理溯源、模拟终端及 AI 自动化日报功能上线。

## 📂 项目结构规范
- `/agent`: 抓包嗅探引擎与 WAF 反向代理模块。
- `/server`: FastAPI 后端、JWT 鉴权、多模型路由工厂、邮件服务。
- `/web`: Next.js 14 前端（Dashboard、SaaS 门户）。
- `/models`: 机器学习模型训练脚本。
- `/data`: 存储加密用户配置与安全日志的 SQLite 数据库。
- `/simulator`: 攻击模拟测试工具包（用于 Nmap/SQLi 模拟）。

## 🛠️ 技术栈
- **Frontend**: Next.js, Tailwind CSS, shadcn/ui, Framer Motion
- **Backend**: FastAPI, SQLAlchemy, Pydantic, Python-Multipart
- **Security**: NextAuth.js, Bcrypt, Cryptography (Fernet)
- **AI**: Scikit-learn, OpenAI/Anthropic/Google/xAI SDKs

## 🔒 隐私声明
本系统承诺：所有捕获的 Payload 数据在前端展示前均会经过脱敏处理；用户的 API Key 经过硬件隔离级别加密存储，仅在发起 AI 请求时在内存中临时解密。