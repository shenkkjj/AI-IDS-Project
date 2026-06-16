# Release Notes：LLM Guardrails 闭环

> 目标读者：运维、产品、安全、客户支持、开发者
> 原始发布日期：2026-06-12
> 当前整理日期：2026-06-15
> 状态：历史发布说明 + 当前待确认项

## 一句话总结

AI-CyberSentinel 的 Copilot 链路加入 LLM 安全护栏：输入检测、输出检测、审计日志、Prometheus 指标和 MCP 工具接口。它的目标是降低 prompt injection、敏感信息泄露和工具越权调用风险。

## 当前阅读方式

本文记录 Guardrails 批次的发布口径。2026-06-15 文档清理时发现，部分历史数字和当前 README 中的验证基线不完全一致，因此这里采用保守表述：

- 已确认存在的模块和端点会写成事实。
- 未在本次 M0-01 重新运行的测试数字会标为“历史记录”。
- 与当前启动路径有疑问的部署事项会标为“待确认”。

## 面向用户的变化

- Copilot 输入会经过 LLM Guardrails 检查。
- Guardrails 会记录审计事件，便于复盘被放行、拦截或告警的输入。
- `/metrics` 暴露 Prometheus 文本指标。
- `/mcp` 挂载 Guardrails MCP 工具，供外部 Agent 调用。
- `/mcp` 需要 `X-Guardrails-Key` 请求头；如果 `GUARDRAILS_MCP_API_KEY` 未配置，请求会返回 401。

## 运维说明

### 端点

| 路径 | 用途 | 当前状态 |
|---|---|---|
| `GET /health` | 存活检查 | 已确认存在 |
| `GET /ready` | 就绪检查：数据库、worker、日志 flusher | 已确认存在 |
| `GET /metrics` | Prometheus 文本指标 | 已确认存在 |
| `POST /mcp` | Guardrails MCP streamable-http | 已确认挂载逻辑存在，依赖 `mcp` 包 |

### 环境变量

| 变量 | 用途 | 默认 / 现状 |
|---|---|---|
| `APP_SECRET` | 后端主密钥 fallback | 必需，弱默认值会拒绝启动 |
| `AUTH_SECRET` | Auth / session 密钥 | 必需，弱默认值会拒绝启动 |
| `NEMO_GUARDRAILS_ENABLED` | 是否启用 NeMo Guardrails | `.env.example` 当前为 `false` |
| `NEMO_GUARDRAILS_CONFIG_PATH` | Guardrails 配置目录 | `server/security/llm_guardrails/config` |
| `GUARDRAIL_RAIL_TIMEOUT_S` | Guardrails 超时秒数 | `.env.example` 当前为 `1.5` |
| `OPENAI_API_KEY` | OpenAI Moderation 或 OpenAI provider 凭证 | 可选，按实际 provider 配置 |
| `GUARDRAILS_MCP_API_KEY` | `/mcp` 访问密钥 | 未配置时 `/mcp` 401 |
| `GUARDRAIL_AUDIT_CLEANUP_DAYS` | Guardrails 审计清理天数 | 默认 `0`，不清理 |

### 数据库迁移

历史发布说明提到：

```powershell
psql -f server/migrations/sql/sc22_audit_indexes.sql
```

当前状态：

- `server/migrations/sql/sc22_audit_indexes.sql` 确实存在。
- 后端当前数据库 engine 使用 `data/app.db` SQLite。
- PostgreSQL / Docker Compose 数据库路径待确认。

因此，在未确认数据库接线前，不要把上面的 `psql` 命令当作本地默认步骤。

## 安全说明

### 已覆盖的风险类型

| 风险 | 现有机制 |
|---|---|
| 直接 prompt injection | L1 正则 / 归一化规则 + NeMo 可选路径 |
| 角色劫持 | L1 / L3 检查 |
| 多轮注入 | history 合并后进入 Guardrails 检查 |
| Unicode bypass | NFKC 归一化相关测试 |
| 编码 bypass | 扩展字典与测试语料 |
| 敏感环境变量名泄露 | L1 / output 检查 |
| 工具越权调用 | 工具白名单逻辑 |
| PII 输入 | `find_pii()` 相关逻辑 |

注意：这是防御工程，不是形式化证明。新型绕过仍可能出现，需要持续补语料和测试。

### MCP 鉴权

`server/main.py` 中 `/mcp` 中间件会检查：

```text
X-Guardrails-Key: <GUARDRAILS_MCP_API_KEY>
```

如果 `GUARDRAILS_MCP_API_KEY` 为空，端点会 fail closed，返回 401。

## 开发者说明

### 模块结构

```text
server/security/llm_guardrails/
├── audit.py                # SQL 审计、统计、指标迭代、清理
├── core.py                 # GuardrailEngine、L1/L2/L3/L4 路径、PII、tool-call
├── decorators.py           # @guard_input / @guard_output
├── exceptions.py           # GuardrailViolation 等异常
├── mcp_server.py           # FastMCP 工具：scan_text / get_stats
├── moderation/
│   ├── client.py           # httpx 异步 moderation 客户端
│   └── provider.py         # moderation provider 策略
└── config/
    ├── config.yml
    ├── actions.py
    └── rails/
        ├── input.co
        └── output.co
```

### 测试结构

```text
server/tests/security/llm_guardrails/
├── conftest.py
├── corpus/
├── test_audit.py
├── test_colang_flows.py
├── test_core.py
├── test_decorators.py
├── test_exceptions.py
├── test_mcp_server.py
├── test_metrics_router.py
├── test_moderation_client.py
└── test_moderation_provider.py
```

### 推荐验证命令

Guardrails：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.\.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

后端非 E2E：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.\.venv\Scripts\python.exe -m pytest server\tests -q --tb=short --ignore=server\tests\test_e2e.py
```

前端：

```powershell
cd web-next
npm run typecheck
npm run build
```

## 历史验证记录

以下数字来自历史发布说明，M0-01 文档清理任务未重新运行全量测试：

| 项 | 历史记录 | 日期 |
|---|---:|---|
| 护栏层测试 | 139 / 139 passed | 2026-06-12 |
| 全量回归 | 219 / 219 passed | 2026-06-12 |
| 护栏层覆盖率 | 81% | 2026-06-12 |

当前 README 采用的验证基线更保守：

- 前端：`npm run typecheck`、`npm run build`
- 后端非 E2E：`pytest server/tests --ignore=server/tests/test_e2e.py`
- Guardrails：`pytest server/tests/security/llm_guardrails`

## 后续 backlog

- NeMo 单独超时计数器，便于按层监控。
- `find_pii()` 扩展邮箱、IP、MAC、JWT 等格式。
- Healthcheck 增加 audit 写入健康度。
- L4 moderation provider 链路可插拔。
- Dashboard 增加前端单元测试或更稳定的 smoke test。

## 关联文档

- [`README.md`](../README.md)：新手启动入口。
- [`AGENTS.md`](../AGENTS.md)：Agent / Skill 路由表。
- [`docs/plans/LLM_GUARDRAILS_PLAN.md`](plans/LLM_GUARDRAILS_PLAN.md)：护栏层设计稿。
- [`docs/CHANGELOG.md`](CHANGELOG.md)：累积变更日志。
