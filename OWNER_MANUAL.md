# OWNER_MANUAL

> 本手册面向“站长/运维负责人”，目标是让非开发人员也能看懂并操作本平台。
> 所有命令、端口、接口、路径均来自当前仓库代码，不是模板文案。

---

## 一、平台能力地图（模块 -> 代码入口 -> 对用户的可见效果）

### 1. 认证与会话系统

- **后端入口**：`server/main.py:1319`（`/auth/register`）、`server/main.py:1346`（`/auth/login/password`）、`server/main.py:1362`（`/auth/login/oauth`）、`server/main.py:1460`（`/auth/session`）
- **前端入口**：`web-next/auth.ts:63`（NextAuth 配置）、`web-next/app/page.tsx:63`（邮箱密码登录）、`web-next/app/page.tsx:107`（OAuth 登录）
- **代理入口**：`web-next/app/api/auth/[...nextauth]/route.ts:1`
- **用户看到的效果**：
  - 可以用邮箱密码登录
  - 若配置了 OAuth 变量，可点击 GitHub/Google 登录
  - 登录成功自动跳转 `/dashboard`

#### 关键机制
- FastAPI 在登录成功后设置 `access_token` Cookie：`server/main.py:1355`
- NextAuth 会把后端 `access_token` 保存到 JWT 中：`web-next/auth.ts:144`
- 前端调用后端时通过中间代理自动带 `Authorization: Bearer ...`：`web-next/app/api/backend/[...path]/route.ts:38-40`

---

### 2. 用户配置中心（AI 模型、告警偏好、UI 偏好）

- **后端接口**：
  - 读取：`GET /user/config` -> `server/main.py:1471`
  - 更新：`PUT /user/config` -> `server/main.py:1496`
- **前端调用点**：`web-next/app/dashboard/dashboard-client.tsx:499`（读取）、`web-next/app/dashboard/dashboard-client.tsx:939`（保存）
- **数据库表**：`user_configs` -> `server/models_db.py:23`
- **用户看到的效果**：
  - 能切换 AI provider / model / base_url
  - 能保存告警语音开关
  - 下次登录后配置自动恢复

#### 注意
- API Key 加密存储（Fernet）：`server/security_utils.py:61-65`
- 数据库路径固定为：`data/app.db`，定义在 `server/db.py:12`

---

### 3. 多模型路由与连通性测试

- **后端接口（管理员令牌保护）**：
  - `GET /llm/config` -> `server/main.py:1754`
  - `PUT /llm/config` -> `server/main.py:1763`
  - `POST /llm/test` -> `server/main.py:1773`
- **管理员令牌校验**：`server/main.py:881`（`LLM_ADMIN_TOKEN`）
- **前端触发**：`web-next/app/dashboard/dashboard-client.tsx:978`（测试路由）
- **用户看到的效果**：
  - 配置模型后可点击“测试路由”验证可用性和延迟

#### 支持的 provider（后端常量）
- `openai / claude / gemini / grok / custom` -> `server/main.py:294`

---

### 4. 告警采集、分析、回放

- **采集接口**：`POST /alerts` -> `server/main.py:1872`
- **查询接口**：`GET /alerts` -> `server/main.py:1894`
- **实时推送**：`WebSocket /ws/alerts` -> `server/main.py:1909`
- **告警处理队列**：`_alert_queue` -> `server/main.py:385`
- **用户看到的效果**：
  - 看板实时出现告警
  - 告警可被 Copilot 继续分析

#### 安全边界
- 告警入站需要 `x-alerts-token`：`server/main.py:889`
- 来源 IP 还要匹配允许 CIDR：`server/main.py:123-147`

---

### 5. WAF 代理防护

- **核心接口**：`/site/proxy/{path:path}` -> `server/main.py:1811`
- **策略匹配函数**：`_payload_has_attack_signature` -> `server/main.py:150`
- **内置规则**：`WAF_BLOCK_PATTERNS` -> `server/main.py:63`
- **用户看到的效果**：
  - 命中规则请求返回 `403 blocked`
  - 被拦截事件会进入告警队列并出现在看板

#### 内置拦截范围（当前版本）
- SQLi 特征（`union select`, `or 1=1`, `sleep(` 等）
- XSS 特征（`<script`, `onerror=` 等）
- 路径穿越特征（`../`, `%2e%2e%2f`, `/etc/passwd` 等）

---

### 6. 站点健康监测（Uptime + SSL）

- **设置目标站点**：`POST /site/target` -> `server/main.py:1599`
- **查询健康状态**：`GET /site/health` -> `server/main.py:1646`
- **后台巡检循环**：`_ssl_monitor_loop` -> `server/main.py:1258`
- **巡检间隔**：60 秒 -> `server/main.py:55`
- **用户看到的效果**：
  - 看板显示站点在线状态
  - 证书即将到期时会给预警

---

### 7. Security Copilot（流式应答）

- **接口**：`POST /copilot/stream` -> `server/main.py:1659`
- **流式格式**：SSE（`text/event-stream`）-> `server/main.py:1691`
- **前端解析入口**：`parseSseBuffer` -> `web-next/app/dashboard/dashboard-client.tsx:154`
- **用户看到的效果**：
  - 在右侧 Copilot 面板看到逐字流式返回
  - 选中告警后，Copilot 自动带入告警上下文

---

### 8. 新威胁确认与样本沉淀

- **接口**：`POST /threats/confirm` -> `server/main.py:1694`
- **写入目标文件**：`data/new_threats.csv` -> `server/main.py:391`
- **用户看到的效果**：
  - 在 UI 点击“确认威胁入库”后，样本落地 CSV

---

### 9. 邮件验证码与密码重置

- **接口**：
  - OTP 申请：`/auth/login/otp/request` -> `server/main.py:1395`
  - OTP 校验：`/auth/login/otp/verify` -> `server/main.py:1408`
  - 重置申请：`/auth/password/reset/request` -> `server/main.py:1423`
  - 重置确认：`/auth/password/reset/confirm` -> `server/main.py:1440`
- **邮件发送实现**：`server/mailer.py:32`（OTP）、`server/mailer.py:48`（重置）
- **用户看到的效果**：
  - 能收到验证码邮件并完成登录/重置

---

### 10. 数据模型总览（最重要三张业务表）

- `users`：账号、密码哈希、OAuth 来源、加密 API Key -> `server/models_db.py:10`
- `user_configs`：模型路由、告警、UI 偏好 -> `server/models_db.py:23`
- `logs`：审计日志 -> `server/models_db.py:39`
- `auth_challenges`：OTP/重置验证码挑战 -> `server/models_db.py:51`

---

## 二、傻瓜式操作手册（从 0 到可用）

> 默认你在项目根目录：`D:/Users/27629/Desktop/Claude/AI-IDS-Project`

### A. 首次启动（推荐本地联调）

#### 步骤 1：准备后端环境变量
1. 复制 `.env.example` 为 `.env`
2. 至少填写以下项（见 `./.env.example`）：
   - `APP_SECRET`（必须是强随机，不能弱值）
   - `LLM_ADMIN_TOKEN`
   - `ALERTS_INGEST_TOKEN`
   - 如果需要邮件功能，再填 SMTP 相关变量

> `APP_SECRET` 若缺失或弱值会导致启动期安全组件报错，来源：`server/security_utils.py:26-30`

#### 步骤 2：准备前端环境变量
1. 复制 `web-next/.env.example` 为 `web-next/.env.local`
2. 最少填写：
   - `AUTH_SECRET`
   - `BACKEND_BASE_URL=http://127.0.0.1:8000`
3. 如需 OAuth，填写：
   - `AUTH_GITHUB_ID / AUTH_GITHUB_SECRET`
   - `AUTH_GOOGLE_ID / AUTH_GOOGLE_SECRET`
   - 对应 `NEXT_PUBLIC_AUTH_GITHUB_ENABLED=true`、`NEXT_PUBLIC_AUTH_GOOGLE_ENABLED=true`

#### 步骤 3：启动后端
```bash
.venv/Scripts/python.exe -m uvicorn server.main:app --host 127.0.0.1 --port 8000
```

健康检查：
```bash
curl http://127.0.0.1:8000/health
```
预期：`{"status":"ok"}`（接口定义 `server/main.py:1749`）

#### 步骤 4：启动前端
```bash
cd web-next
npm run dev
```
默认打开：`http://127.0.0.1:3000`

> 前端脚本定义：`web-next/package.json:5`

---

### B. 快速体验一条完整主流程（登录 -> 看板 -> 配置 AI -> 测试）

1. 打开 `http://127.0.0.1:3000`
2. 使用邮箱密码登录
3. 登录后进入 `/dashboard`
4. 在 AI 配置区填写 provider / model / base_url / api_key
5. 点“测试路由”
6. 看到类似“测试成功：provider / model / latency”即为链路正常

相关代码：
- 登录页：`web-next/app/page.tsx:31`
- 看板页：`web-next/app/dashboard/page.tsx:4`
- 测试按钮逻辑：`web-next/app/dashboard/dashboard-client.tsx:978`

---

### C. 站点接入与 WAF 验证

#### 步骤 1：配置受保护站点
在看板输入目标 URL（如 `https://example.com`），点击保存。
后端接口：`POST /site/target`（`server/main.py:1599`）

#### 步骤 2：测试代理链路
UI 输入代理路径 `/` 或完整 URL，点击“测试代理链路”。
前端调用点：`web-next/app/dashboard/dashboard-client.tsx:694`

#### 步骤 3：验证拦截是否生效
可以构造带明显攻击特征的路径或 body（仅限本地安全测试）。
命中时应返回 `403`，并在告警表中看到 `waf_block` 相关记录。

---

### D. 接入外部告警源（Agent/探针）

向后端发送：
```http
POST /alerts
Header: x-alerts-token: <ALERTS_INGEST_TOKEN>
Body: AlertIn JSON
```

字段结构见 `AlertIn`：`server/main.py:204`

常见失败：
- `401 Invalid alerts token`：token 错
- `403 Alert ingest source is not allowed`：来源 IP 不在 `ALERTS_INGEST_ALLOWED_CIDRS`
- `503 Alert queue is full`：队列满

---

### E. 启动方式对照表

#### 方式 1（推荐）：手工分开启动
- 后端：uvicorn（8000）
- 前端：Next dev（3000）
- 优点：与当前 `web-next` 实际代码一致，功能最完整

#### 方式 2：`start_all.bat` 一键启动
- 文件：`start_all.bat:12-25`
- 实际行为：
  - 启后端 `8000`
  - 启 Python 静态服务器 `8080`，目录 `web/`
- 说明：这条是旧静态前端链路，不是 `web-next` NextAuth 看板链路。

---

## 三、维护与排错指南（按症状定位）

### 症状 1：页面能打开，但登录失败

#### 检查点
1. 后端是否存活：`GET /health`
2. 前端 `BACKEND_BASE_URL` 是否指向 `http://127.0.0.1:8000`
3. `AUTH_SECRET` 是否设置
4. 数据库是否可写（`data/app.db`）

#### 关键代码点
- 账号密码登录请求：`web-next/auth.ts:83`
- 登录错误映射：`web-next/app/page.tsx:6`
- 后端密码登录：`server/main.py:1346`

---

### 症状 2：OAuth 按钮灰色或点了没反应

#### 根因
按钮可用性由前端环境变量控制：
- `NEXT_PUBLIC_AUTH_GITHUB_ENABLED`
- `NEXT_PUBLIC_AUTH_GOOGLE_ENABLED`

代码位置：`web-next/app/page.tsx:43-45`

#### 处理
- `.env.local` 把对应开关设为 `true`
- 同时配置真实 `AUTH_GITHUB_*` / `AUTH_GOOGLE_*`
- 重启前端

---

### 症状 3：AI 测试失败 / Copilot 无响应

#### 排查顺序
1. 看板点击“测试路由”，确认 provider/base_url/api_key 可连通
2. 若提示 `base_url must be a valid https URL`，说明 URL 不合规
3. 若 provider 与 base_url 不匹配，会被拒绝
4. Copilot 依赖用户配置中的 API Key，未配置会报“请先设置可用的 API Key 与 Base URL”

关键代码：
- LLM 测试：`server/main.py:1773`
- Base URL 校验：`server/main.py:577`
- Copilot 流式错误回包：`server/main.py:709`

---

### 症状 4：看不到告警，或者只有历史没有实时

#### 检查项
1. 外部发送 `/alerts` 是否带 `x-alerts-token`
2. 来源 IP 是否被允许
3. 前端是否拿到登录态（未登录会拿不到 `/alerts`）
4. WebSocket 是否建立（`/ws/alerts`）

关键代码：
- 告警入站：`server/main.py:1872`
- 告警查询（按用户过滤）：`server/main.py:1894`
- WS 推送：`server/main.py:1909`

---

### 症状 5：配置保存了，但重启后丢失

#### 正常行为
- 配置默认持久化在 SQLite：`data/app.db`（`server/db.py:12`）
- 表结构：`user_configs`（`server/models_db.py:23`）

#### 异常排查
1. 是否误删 `data/app.db`
2. 是否多个环境启动到了不同目录
3. 是否有权限问题导致写库失败

---

### 症状 6：站点健康状态总是离线

#### 检查项
1. 先确认目标 URL 可从本机访问
2. `POST /site/target` 是否返回成功
3. `GET /site/health` 是否为 `idle`（说明没配置成功）
4. 若 HTTPS 站点证书异常，会出现 warning/critical

关键代码：
- Uptime 检查：`server/main.py:1189`
- SSL 检查：`server/main.py:1216`
- 巡检循环：`server/main.py:1258`

---

### 症状 7：WAF 没有拦截攻击样本

#### 检查项
1. 请求是否真的走 `/site/proxy/...`
2. 载荷是否命中当前正则规则
3. 是否在 UI 中配置了目标站点

关键代码：
- 规则表：`server/main.py:63`
- 匹配函数：`server/main.py:150`
- 拦截响应：`server/main.py:1846`

---

### 症状 8：验证码邮件发不出去

#### 根因常见
- SMTP 变量未配置
- SMTP 账号/密码不对
- 端口与 TLS 组合不对

配置项见：`.env.example:13-21`
发送逻辑见：`server/mailer.py:17-29`

---

## 四、运维安全基线（必须项）

1. `APP_SECRET` 必须强随机，不可使用默认弱值
2. `LLM_ADMIN_TOKEN` 与 `ALERTS_INGEST_TOKEN` 必须设置且定期轮换
3. `.env` 与 `web-next/.env.local` 不入库
4. `data/app.db` 属于运行时数据，不要纳入 Git
5. 数据库备份默认写到仓库外目录（`../ai-ids-backups`），不要放在仓库内
6. 对外部署时将 Cookie 安全策略配置为 HTTPS 生产值：`APP_COOKIE_SECURE=true`，并按跨站需求设置 `APP_COOKIE_SAMESITE`（本地默认 `true/lax`）

---

## 五、常用命令清单

### 后端
```bash
.venv/Scripts/python.exe -m uvicorn server.main:app --host 127.0.0.1 --port 8000
```

### 前端
```bash
cd web-next
npm install
npm run dev
```

### 前端类型检查
```bash
cd web-next
npm run typecheck
```

### 日常健康检查
```bash
bash scripts/daily_ops_check.sh
```

### SQLite 备份
```bash
bash scripts/backup_db.sh
# 可选：自定义目录（推荐仓库外）
BACKUP_DIR="D:/ai-ids-backups" bash scripts/backup_db.sh
```

### 认证链路冒烟
```bash
cd web-next
npm run smoke:auth
```

---

## 六、升级/变更时的最小回归清单

每次改动后至少做以下 8 项：

1. `GET /health` 返回 ok
2. 邮箱密码登录成功并进入 `/dashboard`
3. （若启用）OAuth 登录成功
4. `PUT /user/config` 后刷新页面配置仍存在
5. `POST /llm/test` 返回成功
6. `POST /site/target` + `GET /site/health` 正常
7. `/site/proxy/...` 普通请求通过、攻击样本 403
8. `/alerts` 入站后，UI 表格和 Copilot 能看到对应上下文

---

## 七、附录：关键文件索引

- 后端总入口：`server/main.py`
- LLM 分析器：`server/analyzer.py`
- 安全工具（JWT/加密）：`server/security_utils.py`
- DB 与引擎：`server/db.py`
- DB 模型：`server/models_db.py`
- 邮件发送：`server/mailer.py`
- 登录页：`web-next/app/page.tsx`
- 仪表盘主逻辑：`web-next/app/dashboard/dashboard-client.tsx`
- NextAuth 配置：`web-next/auth.ts`
- 前后端代理：`web-next/app/api/backend/[...path]/route.ts`
- 根环境模板：`.env.example`
- 前端环境模板：`web-next/.env.example`

---

## 八、给站长的最后建议（非代码）

如果你只记三件事：

1. 先保证登录链路和 AI 测试链路通，再谈告警质量。
2. 所有“看不到数据”的问题，优先检查 token、登录态、用户隔离（本系统按用户分流告警）。
3. 每次发布前跑一遍“最小回归清单”，能拦住大多数线上事故。
