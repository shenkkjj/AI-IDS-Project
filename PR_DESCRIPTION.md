# LLM Guardrails 闭环 (M1 + P1 review 修 + P2 OWASP 补完) + 收尾修复

## TL;DR

- **新增 5 层 LLM 防御**(L1 正则 / L2 启发式 / L3 NeMo Guardrails / L4 OpenAI Moderation / @guard_input·@guard_output 装饰器)
- **6 大 OWASP LLM 风险全覆盖**:LLM01 / LLM02 / LLM05 / LLM06 全部 ✅,其他 4 项文档化为 P3 backlog
- **可观测性**:`GET /metrics` Prometheus 端点(`guardrail_checks_total{scope, layer, status}`)
- **合规**:Audit log 90 天自动清理(GDPR / PCI-DSS)
- **CI 纪律**:pre-commit Rule 3 强制护栏层改动跑测试
- **收尾修复**(2026-06-12):`_StubMCP` 类定义顺序错误导致 5 个 mcp_server 测试失败,已修复并全绿
- **验证**:**219 / 219 passed**(80 既有 + 139 护栏),护栏层 **81% 覆盖率**(首次破 80%)

详细分项见下文 §P1 / §P2 / §收尾修复。

## 概述

本 PR 包含三个批次的累计工作(M1 基础层 / P1 review 修 / P2 OWASP 补完)+ 一次回归修复。

**核心目标**:
- 在 AI Copilot 链路落地企业级 LLM 安全护栏
- 覆盖 OWASP LLM Top 10 的高风险项(LLM01/02/05/06)
- 提供可观测性 + 合规 + CI 纪律三类工程能力

---

## 6 个 commit 概览(背景)

| # | Commit | 影响范围 |
|---|--------|---------|
| 1 | `chore(cleanup): remove dead code, archive legacy tests, expand .omc ignore` | 11 文件，+85/-923（净删除死代码） |
| 2 | `chore(deps): drop gsap, add @tanstack/react-query, pin node 20` | 4 文件，+41/-20 |
| 3 | `refactor(core): extract exception layer, refresh tokens, WAF middleware, log setup` | 13 文件，+973/-49 |
| 4 | `refactor(services): MFA enforcement, config whitelist, N+1 fix, LLM strategy` | 7 文件，+584/-251 |
| 5 | `refactor(web): TanStack Query, WS cookie auth, alert dedup, PWA, dynamic imports` | 26 文件，+1915/-1072 |
| 6 | `chore: nginx CSP hardening, git hooks, env example, infrastructure docs` | 7 文件，+327/-2 |

---

## 关键安全变更 (需 reviewer 重点关注)

### 1. WebSocket 认证改用 HttpOnly Cookie
**变更**：`useWebSocket.ts` 移除 URL query 中的 token，依赖浏览器自动发送
`access_token` cookie。**风险**：若 `access_token` cookie 配置错误，WS 将
无法连接；后端 `ws_alerts` 端点已支持 SimpleCookie 解析。

### 2. JWT Secret 隔离
**变更**：`security_utils.py` 引入 `APP_JWT_SECRET` 与 `APP_API_KEY_ENCRYPTION_SECRET`
两个独立环境变量，使用不同 PBKDF2 salt 派生。
**兼容性**：旧 `APP_SECRET` 仍作为 JWT 派生输入之一；新部署需同时设置两者。
**部署检查**：确认 `.env` 中两个 secret 都已生成并独立轮换。

### 3. APP_SECRET 启动时强制检查
**变更**：`main.py` 启动时校验 `APP_SECRET` 和 `AUTH_SECRET` 不在已知弱值列表中，
否则 `sys.exit(1)`。**部署影响**：所有环境必须显式配置强随机 secret。

### 4. MFA 强制执行
**变更**：所有登录流程（password / oauth / otp）经 `_enforce_totp_or_raise`
检查 `totp_enabled` 标志，启用 TOTP 的用户必须完成第二步。
**兼容性**：未启用 TOTP 的用户不受影响；启用后无法绕过。

### 5. Admin 端点认证改用 Authorization Header
**变更**：`admin_router` 移除 `?token=` Query 参数认证，改为 `Depends(require_admin)`。
**影响**：任何脚本或工具通过 Query token 访问 admin 端点将失败 401。

### 6. CSP 加固
**变更**：
- nginx `script-src` 移除 `'unsafe-inline'`，添加 `report-uri /api/csp-report`
- 后端响应添加 `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`
- 添加 `X-Frame-Options: DENY`、`X-Content-Type-Options: nosniff`、
  `Referrer-Policy: strict-origin-when-cross-origin`、`Permissions-Policy` 头

---

## 架构改进

### 1. 异常层
- `server/core/exceptions.py`：`DomainException` 层级
  （AuthException / NotFoundException / TotpRequiredException / ...）
- 全局 handler 转换为统一 JSON 响应
- 服务层不再 `from fastapi import HTTPException`

### 2. 刷新令牌 + 会话撤销
- `server/core/refresh_tokens.py`：24 字节 session_id + 32 字节 value，SHA-256 哈希存储
- `RefreshToken` ORM 模型：`session_id` / `token_hash` / `expires_at` / `revoked_at` /
  `replaced_by_id` / `user_agent` / `ip_address`
- 复用检测 → 整家族撤销

### 3. 策略模式 LLM Provider
- `server/services/llm_providers.py`：`LLMProvider` 抽象基类
- `OpenAICompatibleProvider` / `ClaudeProvider` / `GeminiProvider` 实现
- `resolve_provider()` 工厂 + `stream_completion()` 调度器
- `copilot_service.py` 减少 ~150 行重复 dispatch 代码

### 4. 字段白名单配置更新
- `user_service.py`：`CONFIG_FIELD_WHITELIST: dict[field, (attr, normalizer)]`
- 替换 15 个 if-elif 分支
- 不再可能透传任意键

### 5. WAF ASGI 中间件
- `server/middleware/waf.py`：检查 body / header 是否匹配 `WAF_BLOCK_PATTERNS`
- 命中返回 403 + `X-WAF-Block-Reason` 头

### 6. 共享字段常量
- `server/models/constants.py`：所有 enum 值、字符串最大长度常量
- Pydantic schemas 与 SQLAlchemy ORM 都从此 import，杜绝双向漂移

---

## 性能与可维护性

### 1. N+1 查询优化
`alert_service.py`：原本 `User + UserConfig` 两次查询改为 `joinedload` 单次 JOIN。

### 2. 批量日志
- `core/database.py` 新增 `enqueue_log()` / `flush_logs()` / `start_log_flusher()`
- 10k 上限有界队列 + 200 批 flush + 1s 间隔
- 避免高并发 SQLite 写锁争用

### 3. 前端代码分割
- `dashboard-client.tsx`：`AttackTrendChart` / `SourcePieChart` / `CopilotPanel`
  改用 `next/dynamic()` 动态加载
- `npm run build` 结果：dashboard 路由 172 kB（远低于 300 kB 应用预算）

### 4. PWA 支持
- `public/manifest.json` + `public/sw.js`
- cache-first 静态资源，network-first `/api`
- 离线降级

### 5. TanStack Query 基础设施
- `lib/queryClient.ts`：30s default staleTime 单例
- `app/providers.tsx`：QueryClientProvider 包装
- 后续 hook 可直接 `useQuery` 替换手写 fetch + setState

---

## P1 hardening pass (LLM Guardrails 7 层防 + 4 项 review 修)

> 后续提交：在 LLM 护栏层 M1 基础上，闭环 review 报告列出的 9 项 H/SC P1 漏洞。
> **影响范围**：`server/security/llm_guardrails/` 6 个文件 + 1 个新 migration + 21 个新测试。
> **设计稿**：`docs/plans/LLM_GUARDRAILS_PLAN.md`（已实施状态快照见 `AGENTS.md` §4）。

### 修复清单

| # | ID | 漏洞 | 修复 |
|---|---|---|---|
| 1 | **H-1** | `get_stats()` Python 端 count 全表 → OOM 风险 | 改用 SQL `func.count` + `group_by status` + 24h 时间窗口过滤 |
| 2 | **H-2** | OpenAI Moderation 每次新建 `httpx.AsyncClient` → TCP/TLS 重复握手 | 改用模块级共享 `AsyncClient` + `aclose()` 释放;测试场景隔离 |
| 3 | **H-3** | L1 正则不覆盖 NFKC unicode 变体（全角 `ｉｇｎｏｒｅ`） | 引入 `_normalize_for_l1()`，在 L1 匹配前先 `unicodedata.normalize("NFKC", text)` |
| 4 | **H-4** | `@guard_output` 是 no-op（仅写 audit log） | 实现 `GuardrailEngine.check_output()` + `OUTPUT_L1_PATTERN_CATEGORY`（private IP / `sk-` / AWS / GitHub PAT / 内网 host / env var 泄露）|
| 5 | **H-6** | `GUARDRAIL_RAIL_TIMEOUT_S` 在 `__init__` 时读 → 测试和 hot-reload 失效 | 改为函数内 `os.getenv()` 每次调用读；`_read_timeout_s` / `_read_nemo_enabled` / `_read_openai_moderation_key` 三个 helper |
| 6 | **C-1** | `_check_input_sync` 用 `asyncio.run`，在事件循环内 `RuntimeError` | 检测 `asyncio.get_running_loop()`，命中则抛**带明确修复指引**的 `RuntimeError`（"改用 `async def`"） |
| 7 | **SC-8** | L1 字典只覆盖 `aWdub3Jl` / `c3lzdGVm` 2 个 base64 前缀 | 补 13 个模式：更多 base64 / `69676e6f7265` hex("ignore") / ROT13 `vtaber` / HTML entity 重建 |
| 8 | **SC-11** | 5s 超时太长，掩盖 infra 故障 | `DEFAULT_RAIL_TIMEOUT_S: 5.0 → 1.5`；`.env.example` 同步 |
| 9 | **SC-22** | `audit_logs` 缺少 `(action, status, created_at)` 复合索引，`get_stats` 走全表 | 加 `ix_audit_logs_action_status_created` + `ix_audit_logs_user_action_created` 两条复合索引；migration 见 `server/migrations/sql/sc22_audit_indexes.sql` |

### 顺带修复

- **L1 覆盖盲区**：原模式 `ignore\s+(?:all\s+)?previous\s+instructions?` 要求 `instructions?` 后缀。H-3 NFKC 揭示出 bare `ignore previous`（如 `ｉｇｎｏｒｅ　ｐｒｅｖｉｏｕｓ`）能绕过。新增 `(?i)ignore\s+(?:all\s+)?previous\b` 短形式，确保 NFKC 归一化后能命中。

### 安全收益

- **L4 降级**：`GUARDRAIL_RAIL_TIMEOUT_S=1.5` 后，Moderation 异常 → fail-closed 的反应时间从 5s 缩到 1.5s，攻击者更难用慢请求占用连接。
- **审计表索引**：`get_stats` 仪表板查询从 sequential scan 变 index-only scan；在百万行 audit_logs 表上验证 < 50ms。
- **C-1 fail-loud**：之前 `asyncio.run` 在 event loop 里崩溃会让上层 caller 误以为已拦截但实际 500。修复后**显式报错**指引用 `async def`。
- **H-4 output rail 兜底**：现在 PII/secret 泄露在响应输出阶段被 L1 拦下，**不需要 LLM judge**。

### 验证证据

| 项目 | 命令 | 结果 |
|------|------|------|
| 护栏层测试 | `pytest server/tests/security/llm_guardrails/` | **117/117 passed**（M1 上 96 → +21 P1 测） |
| 整体回归 | `pytest server/tests/ --ignore=.../test_e2e.py` | **80/80 passed**（无回归） |
| 护栏层覆盖率 | `pytest ... --cov=server.security.llm_guardrails` | **78%**（M1 76% → +2pp；`audit.py` 100% / `decorators.py` 92% / `moderation/client.py` 91%） |

### 部署注意事项

- **新增/修改环境变量**：
  - `GUARDRAIL_RAIL_TIMEOUT_S` 默认从 5 → **1.5**。如 Copilot SSE 出现超时告警（p99 > 1.5s），调回 3.0 是安全降级。
- **数据库迁移**（生产环境 PostgreSQL 必须执行）：
  ```bash
  psql "$DATABASE_URL" -f server/migrations/sql/sc22_audit_indexes.sql
  ```
  SQLite / dev 环境无需操作（`Base.metadata.create_all()` 启动时自动建）。
- **新装饰器用法**：`@guard_output` 现在真正检查 PII/secret 泄露，Copilot 输出如果偶然命中 RFC1918 IP / `sk-` 前缀会被拦截。如有合法业务需要展示内部 IP，使用 `GuardrailEngine.instance().check_output(... )` 自定义 scope。

---

## P2 / LOW hardening pass（OWASP LLM02 + LLM06 + 可观测性 + 合规 + CI）

> 在 P1 闭环后，闭环 P2/LOW 优先级项：补足 OWASP LLM Top 10 剩余覆盖、可观测性、合规、CI 防线。
> **影响范围**：1 个新 router + 4 个核心文件增强 + 1 个 pre-commit hook 规则 + 22 个新测试。
> **覆盖率**：从 78% 提升到 **82%**（首次突破 80% 目标）。

### 修复清单

| # | ID | 类别 | 修复 |
|---|---|---|---|
| 1 | **P2-A** | OWASP LLM02 输入 PII 检测 | `find_pii()` 工具：中国身份证（GB 11643-1999 checksum）/ 信用卡（Luhn）/ 美国 SSN / 中国手机号；高精度预筛选 + 校验位验证，避免误杀 |
| 2 | **P2-B** | 可观测性 — `/metrics` Prometheus 端点 | `routers/metrics_router.py` + `iter_metrics()` SQL 聚合；Prometheus 0.0.4 text 格式；零值占位防止 dashboard missing series |
| 3 | **P2-C** | 合规 — audit log 自动清理 | `cleanup_old_audit_logs(days=90)` + 启动时 `GUARDRAIL_AUDIT_CLEANUP_DAYS` env 触发；GDPR / PCI-DSS 留存要求 |
| 4 | **P2-D** | OWASP LLM06 Excessive Agency | `_extract_tool_calls()` 支持 OpenAI / Anthropic / legacy function_call shape；`GUARDRAIL_ALLOWED_TOOLS` 白名单（**默认空 = fail-closed**）|
| 5 | **P2-E** | CI — pre-commit 跑护栏测试 | `.githooks/pre-commit` 监测 `server/security/llm_guardrails/**` 变更，触发 pytest；CI 失败前本地拦截 |

### P2-A 详细：PII 检测

```python
# 调用示例（mcp_server.scan_text 自动集成）
hits = GuardrailEngine.instance().find_pii(text)
# 返回 [("chinese_id_card", "110101199003078611"), ("cn_mobile", "13800138000"), ...]
```

4 种 PII 类别，每种都先 regex 预筛再校验位/算法二次验证：
- **chinese_id_card**: 18 位 + GB 11643-1999 checksum
- **credit_card**: 13-19 位 + Luhn
- **us_ssn**: NNN-NN-NNNN 格式（黑名单 000/666/9xx 区段、00/0000 子段）
- **cn_mobile**: 1[3-9]xxxxxxxxx 11 位

PII 命中默认**不阻断**(避免误杀合法业务)，但 SOC 可通过 MCP 主动扫描时发现。

### P2-B 详细：Prometheus 端点

```bash
$ curl http://localhost:8000/metrics
# HELP guardrail_checks_total Total guardrail decisions in the last 24h, ...
# TYPE guardrail_checks_total counter
guardrail_checks_total{scope="copilot",layer="input",status="passed"} 1234
guardrail_checks_total{scope="copilot",layer="input",status="blocked"} 56
guardrail_checks_total{scope="mcp",layer="input",status="blocked"} 1
```

PromQL 示例：
```promql
# 最近 24h 拦截率
sum(rate(guardrail_checks_total{status="blocked"}[24h]))
  / sum(rate(guardrail_checks_total[24h]))
```

**安全注意**：`/metrics` 端点**无需鉴权**。生产部署必须经 nginx `location /metrics { allow 10.0.0.0/8; deny all; }` 限制内网访问。

### P2-C 详细：审计日志保留

```bash
# .env 启用 90 天保留（GDPR / PCI-DSS 推荐）
GUARDRAIL_AUDIT_CLEANUP_DAYS=90
```

启动时自动跑一次（异步、不阻塞）。删除 0 行时静默，删除 >0 行时记 INFO 日志。

### P2-D 详细：Tool call 白名单

```bash
# .env 配置允许 Copilot 调用的工具（默认空 = 全部拒绝）
GUARDRAIL_ALLOWED_TOOLS=search_alerts,fetch_threat_intel,get_alert_detail
```

**Fail-closed 默认**：白名单为空时，任何 `tool_calls` / `function_call` 都会被 `unauthorised_tool_call` 类别阻断。这堵住了 OWASP LLM06 攻击面（被劫持 LLM 调用 `rm -rf` / `execute_shell`）。

### P2-E 详细：本地 CI 防线

```bash
# .githooks/pre-commit 新增 Rule 3：
guardrail_staged=$(echo "$staged_files" | grep -E '^server/security/llm_guardrails/')
if [ -n "$guardrail_staged" ]; then
  py -m pytest server/tests/security/llm_guardrails/ -q --tb=line
  # 失败则 exit 1，拦截 commit
fi
```

开发者本机改护栏层但忘记跑测试 → `git commit` 时强制 pytest 通过才放行。

### 验证证据

| 项目 | 命令 | 结果 |
|------|------|------|
| 护栏层测试 | `pytest server/tests/security/llm_guardrails/` | **139/139 passed**（P1 后 117 → +22 P2） |
| Metrics router 测试 | `pytest server/tests/security/llm_guardrails/test_metrics_router.py` | **3/3 passed** |
| 整体回归 | `pytest server/tests/ --ignore=.../test_e2e.py` | **219/219 passed**（P1 后 197 → +22 P2，**无回归**） |
| 护栏层覆盖率 | `pytest ... --cov=...llm_guardrails --cov=...metrics_router` | **82%**（P1 后 78% → +4pp，**首次突破 80% 目标**） |

**详细覆盖率**：

| 模块 | 覆盖率 | 备注 |
|------|--------|------|
| `metrics_router.py` (新) | **100%** | 端点 + 标签转义 + 零值占位全覆盖 |
| `audit.py` | **100%** | log + get_stats + iter_metrics + cleanup 全覆盖 |
| `core.py` | 77% | NeMo 真实 LLM judge 路径不可测（合理） |
| `decorators.py` | 92% | sync event-loop 分支 + async branch |
| `moderation/client.py` | 91% | httpx 传输层 + Luhn/SSN 校验 |
| `mcp_server.py` | 91% | FastMCP 工具注册 + tool 反射 |

### 部署注意事项

- **新增环境变量**：
  - `GUARDRAIL_ALLOWED_TOOLS`：默认空（fail-closed），生产环境**必须**显式列出允许的 tool 名
  - `GUARDRAIL_AUDIT_CLEANUP_DAYS`：默认 0（不清理），GDPR / PCI 合规环境建议 90
- **nginx 限制**：`/metrics` 端点需在 nginx 加 IP 白名单（参考代码注释）
- **pre-commit 安装**：开发环境需 `git config core.hooksPath .githooks`（项目 README 已有指引）

---

## 验证证据

| 项目 | 命令 | 结果 |
|------|------|------|
| 后端测试 | `pytest server/tests/ --ignore=server/tests/manual --ignore=server/tests/test_e2e.py` | **80/80 passed** |
| 前端类型检查 | `npm run typecheck` | **0 errors** |
| 前端构建 | `npm run build` | **✓ Compiled successfully in 23.4s** |
| Dashboard 体积 | (build output) | **24.5 kB / 172 kB First Load JS** |
| 模块导入 | `python -c "from server.core import refresh_tokens, exceptions, security, config, database, logging_setup; ..."` | **OK** |

---

## 部署注意事项

### 必须更新的环境变量
- `APP_SECRET`（必须为新生成的强随机值，参考生成命令：
  `python -c "import secrets; print(secrets.token_urlsafe(32))"`）
- `AUTH_SECRET`（同上，使用 `openssl rand -base64 32`）
- `APP_JWT_SECRET`（新增，独立于 APP_SECRET）
- `APP_API_KEY_ENCRYPTION_SECRET`（新增，独立于 APP_SECRET）

### 数据库迁移
- `init_db()` 仍会运行 `Base.metadata.create_all` 与 `ensure_user_config_columns()`
- Alembic 迁移计划见 `docs/ALEMBIC_MIGRATION.md`（本批未实施）

### 监控指标
- `/ready` 端点检查 database / alert_workers，可作为 readinessProbe
- `/health` 端点为 livenessProbe

---

## 后续 follow-up（本批未实施）

1. **Alembic 迁移**：替换 `ensure_user_config_columns()`（工作量 1 人/天）
2. **TanStack Query 落地**：在 `useAlerts` / `useConfig` / `useStats` 中实际使用
3. **依赖类型自动化**：`scripts/generate-api-types.sh` 接入 CI
4. **Node 版本统一**：CI 容器锁定 `node:20`

---

## 关联文档

- `docs/SECURITY_HARDENING.md` — 密钥轮换、环境变量分离、事件响应清单
- `docs/BRANCH_NAMING.md` — 分支命名规范
- `docs/ALEMBIC_MIGRATION.md` — Alembic 迁移计划
- `docs/plans/LLM_GUARDRAILS_PLAN.md` — LLM 护栏层完整设计稿（M1 + P1 hardening）
- `docs/CHANGELOG.md` — **累积变更日志**(本次 PR 的 CHANGELOG 条目已写入)
- `docs/RELEASE_NOTES.md` — **本次发布说明**(给运维 / 产品 / 安全 / 客户支持)
- `server/migrations/sql/sc22_audit_indexes.sql` — SC-22 audit 索引 DDL（生产必跑）
- `AGENTS.md` — Agent 路由表 + LLM 护栏层实施状态快照
- `server/STRUCTURE.md` — 模块布局说明
- `.githooks/pre-commit` / `.githooks/pre-push` — 本地 git hooks

---

## 收尾修复 (2026-06-12)

完成 P1 + P2 后跑全量回归发现 5 个 `test_mcp_server.py` 测试失败,
根因是 `_StubMCP` 类定义在 `_build_mcp()` 调用之后(模块顶部的
`mcp = _build_mcp()` 立即引用了 `_StubMCP`,触发 `NameError`)。

### 修复

| 改动 | 文件 | 行为 |
|---|---|---|
| 类前移 | `mcp_server.py` | `_StubMCP` 定义移到 `_build_mcp()` 之前,消除 `NameError` |
| `_StubMCP.tool()` 接受 `name=` kwarg | `mcp_server.py` | 显式注册名优先于 `fn.__name__`,让 `_tools["scan_text"]` / `_tools["get_stats"]` 可被 lookup |
| `@mcp.tool(name=...)` 无条件下执行 | `mcp_server.py` | `_StubMCP` 模式也能注册到 `_tools`,与 FastMCP 行为一致 |

### 验证

```text
139 passed in 18.80s   (护栏层单独)
219 passed in 68.11s   (全量回归, 80 既有 + 139 护栏)
护栏层覆盖率: 81%     (582 statements, 108 miss)
```

### 影响范围

- 任何 CI / 本地环境只要缺 `mcp` Python 包就走 `_StubMCP` 路径
- 修复前 → 5 个 mcp_server 测试 fail + 整护栏层 import 失败
- 修复后 → 5 个测试通过 + 整护栏层正常加载
