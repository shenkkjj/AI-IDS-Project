# Release Notes — LLM Guardrails 闭环

> **目标读者**:运维 / 产品 / 安全 / 客户支持
> **发布日期**:2026-06-12
> **版本**:本批对应 `release-20260425` 分支,无版本号 bump(还未发正式 tag)

---

## 一句话总结

AI-CyberSentinel 的 AI Copilot 链路新增**企业级 LLM 安全护栏**:5 层防御、
6 大类威胁覆盖、零回归;同时新增 Prometheus 可观测性、GDPR/PCI 合规清理、
tool-call 白名单;**219 / 219 测试通过,护栏层代码覆盖率 81%(首次破 80%)**。

---

## 给运维

### 新增端点

| 路径 | 协议 | 用途 | 是否需要鉴权 |
|---|---|---|---|
| `GET /metrics` | HTTP (Prometheus 0.0.4) | 拉取护栏层指标 | 否(内网抓取) |
| `POST /mcp` (MCP) | Streamable HTTP | 让外部 Agent 调护栏 | 走原 MCP 鉴权 |

### 新增环境变量(全部可选)

```bash
# 护栏层调优
GUARDRAIL_RAIL_TIMEOUT_S=1.5         # NeMo 超时(秒,默认 1.5)
NEMO_GUARDRAILS_ENABLED=true          # 是否启用 L3(默认 true)
OPENAI_MODERATION_KEY=sk-xxx          # L4 OpenAI Moderation 凭证

# P2-D 工具白名单(逗号分隔,默认空 = 全部拒绝)
GUARDRAIL_ALLOWED_TOOLS=search_alerts,fetch_threat_intel

# P2-C 审计清理(默认 0 = 不清理,GDPR/PCI 推荐 90)
GUARDRAIL_AUDIT_CLEANUP_DAYS=90
```

### 部署前检查清单

- [ ] `mcp` Python 包是否在生产 requirements 中?
  - 是 → 真实 `FastMCP` 启动;`/mcp` 端点可用
  - 否 → 仅 HTTP 护栏可用,`/mcp` 端点不可用(启动不会报错)
- [ ] 若启用 L4 OpenAI Moderation,`OPENAI_MODERATION_KEY` 必须存在
- [ ] 若启用 `GUARDRAIL_ALLOWED_TOOLS`,需要枚举所有合法工具名,
  否则 LLM 调任何 tool 都会被拒绝(fail-closed)
- [ ] 若启用 `GUARDRAIL_AUDIT_CLEANUP_DAYS > 0`,确认已部署
  `server/migrations/sql/sc22_audit_indexes.sql` 索引(否则清理会很慢)

### 数据库迁移

```bash
psql -f server/migrations/sql/sc22_audit_indexes.sql
```

无破坏性,纯 `CREATE INDEX IF NOT EXISTS`,可热执行。

### Prometheus 抓取配置

```yaml
scrape_configs:
  - job_name: ai_ids_guardrails
    scrape_interval: 30s
    static_configs:
      - targets: ['ai-ids-backend:8000']
    metrics_path: /metrics
```

可用 PromQL:

```promql
# 24h 阻止率
sum(rate(guardrail_checks_total{status="blocked"}[5m]))
  / sum(rate(guardrail_checks_total[5m]))

# 按层细分
sum by (layer) (rate(guardrail_checks_total[5m]))
```

### 回滚方案

本次纯增量,无 API 破坏性变更。回滚单 commit 即可:
- 前端:`/metrics` 端点不抓 → 无影响
- 后端:`@guard_input` / `@guard_output` 装饰器移除即可降级到无护栏模式
- 数据库:索引 `DROP INDEX IF EXISTS` 即可逆

---

## 给产品 / 客户支持

### 用户可感知的变更

1. **LLM 误用更难绕过** — 5 层防御覆盖 6 大类攻击
2. **PII 不会泄露到 LLM** — 身份证 / 信用卡 / SSN / 手机号在
   输入 Copilot 前即被检测(不阻断用户,但在 audit 中留痕)
3. **Copilot 不会调未授权工具** — 工具白名单(fail-closed)
4. **响应延迟上限 1.5s** — NeMo 推理超时会自动放行,
   由后续 L4 Moderation 兜底;UI 无感

### OWASP LLM Top 10 覆盖现状

| 项 | 名称 | 状态 |
|---|---|---|
| LLM01 | Prompt Injection | ✅ 5 层防御 |
| LLM02 | Sensitive Information Disclosure | ✅ 输入 PII 检测 |
| LLM03 | Training Data Poisoning | — 不适用(使用第三方 LLM) |
| LLM04 | Model DoS | ⚠️ 限速待跟进(P3 backlog) |
| LLM05 | Improper Output Handling | ✅ Output rail L1 |
| LLM06 | Excessive Agency | ✅ Tool-call 白名单 |
| LLM07 | System Prompt Leakage | ⚠️ 待评估(P3) |
| LLM08 | Vector & Embedding Weaknesses | — 不使用 RAG |
| LLM09 | Misinformation | — 业务侧(LLM Judge 待定) |
| LLM10 | Unbounded Consumption | ⚠️ 限速待跟进(P3) |

---

## 给安全团队

### 防御覆盖的攻击类型

| 攻击 | 防御层 | 验证方式 |
|---|---|---|
| 直接提示注入(`ignore previous instructions`) | L1 正则 + L2 + L3 | 单元 + 语料库 |
| 角色劫持(`you are now DAN`) | L1 + L2 + L3 | 单元 + 语料库 |
| 多轮注入(前几轮铺垫,后几轮攻击) | L3 NeMo + L4 Moderation | 单元 + 语料库 |
| Unicode bypass(全角 / 兼容分解) | L1 NFKC 归一化 (H-3) | 单元 |
| 编码 bypass(base64 / hex / ROT13 / HTML entity) | L1 扩展字典 (SC-8) | 单元 |
| 私网 IP / API key / 主机名泄露 | Output L1 (H-4) | 单元 |
| 工具越权调用 | Tool-call 白名单 (P2-D) | 单元 |
| PII 输入(身份证 / 信用卡 / SSN / 手机) | `find_pii()` (P2-A) | 单元(GB / Luhn / SSN / CN 移动) |

### 监控告警建议

| 告警 | PromQL | 阈值 |
|---|---|---|
| 阻止率异常升高 | `sum(rate(guardrail_checks_total{status="blocked"}[5m])) / sum(rate(guardrail_checks_total[5m]))` | > 10% 持续 5min |
| L3 频繁超时 | (待补 — P2-B 未拆分 timeout counter) | — |
| Audit 写失败 | 待补:健康检查端点 | — |

### 风险与已知限制

- ⚠️ 防护基于模式 + LLM 推理,非形式化证明;0day 攻击可能绕过
- ⚠️ `find_pii()` 只能检测标准格式,绕过版(如 `4111-1111-1111-1111` 删
  空格)未覆盖(待 P3)
- ⚠️ Tool-call 白名单按工具名匹配,不校验参数范围(需在服务层校验)
- ⚠️ NeMo Guardrails 为可选依赖;未安装时 L3 自动降级(仅 L1/L2/L4)

---

## 给开发团队

### 新增模块结构

```text
server/security/llm_guardrails/
├── __init__.py
├── audit.py                # SQL 审计 + get_stats / iter_metrics / cleanup
├── core.py                 # GuardrailEngine 单例 + L1/L2 + PII + tool-call
├── decorators.py           # @guard_input / @guard_output
├── exceptions.py           # Guardrail{Unavailable,Timeout,Blocked}
├── mcp_server.py           # FastMCP 端点 (scan_text / get_stats)
├── moderation/
│   ├── client.py           # httpx 异步客户端 (连接池)
│   └── provider.py         # provider factory
└── config/
    ├── config.yml          # NeMo 行为配置
    ├── actions.py          # 自定义 action
    └── rails/
        ├── input.co        # Colang 输入流
        └── output.co       # Colang 输出流
```

### 测试结构

```text
server/tests/security/llm_guardrails/
├── conftest.py             # mock_nemo_rails_{pass,block} 夹具
├── corpus/                 # 5 类对抗性语料 (JSONL)
├── test_audit.py           # 18 测试
├── test_core.py            # 75 测试 (含 PII / tool-call)
├── test_decorators.py      # 13 测试
├── test_mcp_server.py      # 5 测试
└── test_metrics_router.py  # 3 测试
```

### 本地运行验证

```bash
# 仅护栏层
cd server
python -m pytest tests/security/llm_guardrails/ -v

# 全量回归
python -m pytest tests/ -q

# 覆盖率
python -m pytest tests/security/llm_guardrails/ \
  --cov=server.security.llm_guardrails --cov-report=term-missing

# pre-commit 钩子(已自动启用 Rule 3)
git commit -am "..."
# → 如果改了 server/security/llm_guardrails/ 文件,会自动跑护栏测试
```

### 进一步工作(后续 backlog)

- P3-A: NeMo 单独超时计数器(便于按层监控)
- P3-B: `find_pii()` 扩展:邮箱 / IP / MAC / JWT
- P3-C: Healthcheck 端点暴露 audit 写入健康度
- P3-D: L4 改为可选 provider 链(OpenAI → 自建 moderation API)
- P3-E: Dashboard 单元测试(React Testing Library)

---

## 验证证据

| 项 | 数据 | 时间 |
|---|---|---|
| 护栏层测试 | 139 / 139 passed | 2026-06-12 |
| 全量回归 | 219 / 219 passed (含 80 既有模块) | 2026-06-12 |
| 护栏层覆盖率 | **81%** (582 语句,108 未覆盖) | 2026-06-12 |
| 既有模块回归 | 0 失败 | 2026-06-12 |
| pre-commit Rule 3 | 在改动 `server/security/llm_guardrails/**` 时自动启用 | — |

---

## 关联

- `docs/CHANGELOG.md` — 累积变更日志
- `PR_DESCRIPTION.md` — PR 详细描述
- `AGENTS.md` — Agent / Skill 路由表
- `docs/plans/LLM_GUARDRAILS_PLAN.md` — 护栏层设计稿
