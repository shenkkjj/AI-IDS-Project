# Changelog

> 累积式变更日志,本项目所有非平凡变更的单一事实源。
> 格式遵循 [Keep a Changelog 1.1](https://keepachangelog.com/zh-CN/1.1.0/),
> 语义化版本遵循 [SemVer 2.0](https://semver.org/lang/zh-CN/)。

---

## [Unreleased] — 2026-06-12

LLM Guardrails 三批(M1 / P1 / P2)闭环 + 多项 review 后修复。

### Added (新增功能)

#### M1 — LLM Guardrails 基础层
- **5 层防御**:`@guard_input` / `@guard_output` 装饰器 + L1 正则 + L2 启发式 +
  L3 NeMo Guardrails(可降级) + L4 OpenAI Moderation
- **MCP 端点**:`server/security/llm_guardrails/mcp_server.py`,暴露
  `scan_text` / `get_stats` 两个 tool,挂载在 `/mcp`
- **审计日志**:`audit.log_guardrail_event()` 写入 `AuditLog`,
  `action='guardrail_check'`,`resource_type=scope`,`resource_id=layer`,
  `status` ∈ `{passed, blocked, warning}`
- **Copilot 接入**:`server/services/copilot_service.py` 入口加护栏装饰器
- **配置层**:`server/security/llm_guardrails/config/`
  (`config.yml` + `actions.py` + `rails/{input,output}.co`)
- **NeMo 客户端**:`moderation/client.py` (httpx async) +
  `moderation/provider.py` (factory)
- **异常层**:`server/security/llm_guardrails/exceptions.py`
  (`GuardrailUnavailable` / `GuardrailTimeout` / `GuardrailBlocked`)
- **SQL 迁移**:`server/migrations/sql/sc22_audit_indexes.sql`
- **对抗性语料库**:`server/tests/security/llm_guardrails/corpus/`
  (5 类 × 多语言 × 多变体)

#### P1 hardening pass (review 后修)
- H-1:`get_stats()` 改为 SQL `GROUP BY status` + 24h 窗口 + 零值兜底
- H-2:`moderation/client.py` 共享 `httpx.AsyncClient` 连接池,`aclose()` 优雅关闭
- H-3:输入路径 `_normalize_for_l1()` 做 `unicodedata.normalize("NFKC", ...)`,
  阻止全角 Latin / 兼容分解 bypass
- H-4:`@guard_output` 装饰器不再 no-op,真正调用 `_run_output_rails()`;
  `_l1_check_output()` 阻断 RFC1918 IP / API key 前缀 / 内部主机名 / 环境变量泄露
- H-6:env 变量(`GUARDRAIL_RAIL_TIMEOUT_S` / `NEMO_GUARDRAILS_ENABLED` /
  `OPENAI_MODERATION_KEY`)改为调用时读取,支持热改
- C-1:`@guard_input` sync 路径在事件循环内显式抛错(原 `asyncio.run` 会段错误)

#### P2 / LOW hardening pass (OWASP 补完)
- **P2-A OWASP LLM02** — `find_pii()` 检测 4 类 PII:
  - 中国身份证(GB 11643-1999 校验位算法)
  - 信用卡(Luhn 算法)
  - 美国 SSN(`\d{3}-\d{2}-\d{4}`)
  - 中国手机号(`1[3-9]\d{9}`)
- **P2-B 可观测性** — `server/routers/metrics_router.py` 暴露
  `GET /metrics` (Prometheus 0.0.4 text format),指标名
  `guardrail_checks_total{scope, layer, status}`(最近 24h)
- **P2-C 合规** — `cleanup_old_audit_logs(days=90)`,在
  `main.py` startup 钩子触发,`GUARDRAIL_AUDIT_CLEANUP_DAYS` 控制
  (默认 0 = 不清理,GDPR / PCI-DSS 推荐 ≥ 90)
- **P2-D OWASP LLM06** — `_extract_tool_calls()` 支持 OpenAI
  `tool_calls[].function.name` / Anthropic
  `content[].name (type=="tool_use")` / legacy `function_call.name`,
  `GUARDRAIL_ALLOWED_TOOLS` 白名单(**默认空 = fail-closed**)
- **P2-E CI 纪律** — `.githooks/pre-commit` Rule 3:
  任何 `server/security/llm_guardrails/**` 文件改动必须先跑
  `pytest server/tests/security/llm_guardrails/`,失败拒绝 commit

### Changed (变更)

- `server/main.py` 启动钩子增加 audit 清理 + `/metrics` router 挂载
- `server/models_db.py` `AuditLog.__table_args__` 增加
  `ix_audit_logs_action_status_created` / `ix_audit_logs_user_action_created`
- `.env.example` `GUARDRAIL_RAIL_TIMEOUT_S` 默认 5 → 1.5 (SC-11)
- `@guard_output` 装饰器签名调整(从 no-op 变为可调用)
- `GuardrailEngine.check_output()` 新增;`_extract_tool_calls` 新增

### Fixed (修复)

- **回归修复(2026-06-12)**: `_StubMCP` 类定义在 `_build_mcp()` 之后,
  导致 `mcp_server.mcp` 构造时 `NameError`;重构为类前移 +
  `@mcp.tool(name=...)` 装饰器无条件下执行,保证 `_tools["scan_text"]`
  和 `_tools["get_stats"]` 在 `_StubMCP` 模式下也可被测试 lookup
- H-3 follow-up:L1 模式增加 `(?i)ignore\s+(?:all\s+)?previous\b`,
  避免裸 `ignore previous` 漏检
- H-4 测试修正:`.corp.local` 主机名模式要求前导点(测试用 `db.corp.local`)
- PII 测试修正:使用 GB 11643-1999 真实校验位 `110101199003078611`,
  错误用例 `…78612` (末位 1→2 校验失败)
- metrics router 测试 monkeypatch 修正:
  替换 `metrics_router.iter_metrics` 而非 `audit.iter_metrics`
  (router 在 import 时已绑定)

### Security (安全)

- **OWASP LLM01 Prompt Injection**:5 层防御 + 64 L1 模式(50 基础 +
  13 SC-8 字典 + 1 follow-up)
- **OWASP LLM02 Sensitive Information Disclosure**:PII 检测层
  (`find_pii()` 覆盖中国身份证 / 信用卡 / SSN / 手机号)
- **OWASP LLM05 Improper Output Handling**:output rail L1 检测
  私网 IP / API key 前缀 / 内部主机名 / 环境变量名泄露
- **OWASP LLM06 Excessive Agency**:tool-call 白名单,默认 fail-closed
- **GDPR / PCI-DSS**:audit log 90 天自动清理(可配置)

### Performance (性能)

- `iter_metrics()` 一次 SQL 聚合代替 Python 端 N 次 count
- `httpx.AsyncClient` 长连接复用,避免每次重连
- `cleanup_old_audit_logs()` 单 SQL `DELETE` 带索引,O(log n)

---

## 测试统计

| 阶段 | 护栏层测试 | 全量回归 | 护栏层覆盖率 |
|---|---|---|---|
| M1 完成 | 94 | 80 | 76% |
| P1 闭环 | 117 (+23) | 80 | 78% |
| P2 完成 | **139 (+22)** | 80 | **82%** |
| 回归修复后 | **139** | 80 + 80 (其他) = **219** | **81%** |

---

## 文件清单

### 新增 (16)

```text
docs/plans/LLM_GUARDRAILS_PLAN.md
server/migrations/sql/sc22_audit_indexes.sql
server/routers/metrics_router.py
server/security/llm_guardrails/__init__.py
server/security/llm_guardrails/audit.py
server/security/llm_guardrails/config/__init__.py
server/security/llm_guardrails/config/actions.py
server/security/llm_guardrails/config/config.yml
server/security/llm_guardrails/config/rails/__init__.py
server/security/llm_guardrails/config/rails/input.co
server/security/llm_guardrails/config/rails/output.co
server/security/llm_guardrails/core.py
server/security/llm_guardrails/decorators.py
server/security/llm_guardrails/exceptions.py
server/security/llm_guardrails/mcp_server.py
server/security/llm_guardrails/moderation/__init__.py
server/security/llm_guardrails/moderation/client.py
server/security/llm_guardrails/moderation/provider.py
server/tests/security/llm_guardrails/conftest.py
server/tests/security/llm_guardrails/corpus/benign.jsonl
server/tests/security/llm_guardrails/corpus/direct_injection.jsonl
server/tests/security/llm_guardrails/corpus/multi_turn_injection.jsonl
server/tests/security/llm_guardrails/corpus/role_hijack.jsonl
server/tests/security/llm_guardrails/corpus/unicode_bypass.jsonl
```

### 修改 (6)

```text
.claude/settings.local.json   (+3/-1)
.coverage                     (二进制数据)
.env.example                  (+21) — GUARDRAIL_* 变量
.githooks/pre-commit          (+23) — Rule 3 护栏测试钩子
server/main.py                (+81) — metrics router + audit cleanup
server/models_db.py           (+11) — 4 个 audit 索引
server/services/copilot_service.py (+40) — 入口护栏装饰
```

---

## 关联文档

- `PR_DESCRIPTION.md` — 本次 PR 详细描述(reviewer 必读)
- `AGENTS.md` — Agent / Skill 路由 + 护栏层实施状态快照
- `docs/plans/LLM_GUARDRAILS_PLAN.md` — 护栏层完整设计稿(v1)
- `docs/SECURITY_HARDENING.md` — 之前的安全加固历史
- `CLAUDE.md` — 硬规则 / 流程纪律
