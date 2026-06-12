# AGENTS.md — AI-CyberSentinel 智能体路由与项目速查

> 本文件给 **AI Agent**(Claude / 其他智能体)阅读,不是给人读的产品手册。
> 目的:让 Agent 在不读完整代码库的情况下,准确定位模块、调用正确流程、遵守项目硬规则。
>
> 详细业务背景、Plan 全文、性能/覆盖率目标,见 `docs/plans/` 目录。
> 团队约束、安全规则、流程纪律,见 `CLAUDE.md`(`AGENTS.md` 不重复)。

---

## 1. 项目速查

| 项 | 值 |
|---|---|
| 业务定位 | AI 驱动的入侵检测与告警分析平台(IDS + AI Copilot) |
| 核心链路 | Sniffer → Defender → Copilot(Web UI) → LLM 推理 |
| 后端 | FastAPI + SQLAlchemy 2.0 + Pydantic v2 + httpx + loguru |
| LLM | 兼容 OpenAI 协议(默认 `gpt-4o-mini`) |
| 护栏 | NVIDIA NeMo Guardrails 0.22.x + 自研 L1/L4 双兜底 |
| 前端 | Next.js + TanStack Query(Web) / 静态 Web(legacy) |
| 测试 | pytest,目标覆盖率 ≥ 80% |
| 包管理 | `requirements.txt` + `.venv` |
| 部署 | Docker Compose + Nginx(参考 `docker-compose.yml` / `nginx/`) |

---

## 2. 目录速查(给 Agent 定位用)

```text
AI-IDS-Project/
├── server/                          # FastAPI 后端
│   ├── main.py                      # 入口 + lifespan + /mcp 挂载
│   ├── core/                        # config / database / exceptions / logging
│   ├── security/                    # 安全模块
│   │   ├── llm_guardrails/          # LLM 护栏层(本项目核心扩展)
│   │   ├── defender.py              # WAF 主动防御
│   │   └── sniffer.py               # WAF 抓包
│   ├── services/                    # 业务服务层
│   │   ├── copilot_service.py       # LLM 入口(已加护栏)
│   │   ├── alert_service.py         # 告警处理
│   │   └── llm_providers.py         # LLM Provider 注册表
│   ├── routers/                     # FastAPI 路由
│   ├── models_db.py                 # SQLAlchemy ORM
│   └── tests/                       # pytest 测试根目录
│       └── security/llm_guardrails/ # 护栏层测试 + 对抗性语料库
├── web/                             # 旧版 Web UI
├── web-next/                        # Next.js 14 新版 Web UI
├── nginx/                           # 反代配置(含 CSP)
├── docs/
│   └── plans/
│       └── LLM_GUARDRAILS_PLAN.md   # 护栏层完整设计稿(v1)
├── .env.example                     # 环境变量样例(必读)
├── CLAUDE.md                        # 硬规则 / 流程纪律
├── AGENTS.md                        # 本文件
└── README.md                        # 项目说明
```

---

## 3. Agent / Skill 路由

> 路由规则: **按当前任务目标选最合适的 Agent / Skill**,不要机械套固定顺序。
> 详细推荐组合见 `CLAUDE.md` §Skill 选择总规则;此处只补充 **本项目特有**的路由。

### 3.1 本项目特有 Agent 路由

| 场景 | 主 Agent / Skill | 辅 | 触发条件 |
|---|---|---|---|
| 修改 LLM 护栏层 | `code-reviewer` + `security-reviewer` | `tdd-guide` | 任何 `server/security/llm_guardrails/**` 改动 |
| 修改 Copilot 链路 | `code-reviewer` | `tdd-guide` | `server/services/copilot_service.py` 改动 |
| 修 WAF/IDS 规则 | `security-reviewer` | `code-reviewer` | `server/security/{defender,sniffer}.py` 改动 |
| 改数据库 / migration | `database-reviewer`(若可用) | `code-reviewer` | `server/models_db.py` / `migrations/` 改动 |
| 改认证 / 授权 | `security-reviewer`(必走) | `code-reviewer` | `server/core/auth*` / `server/routers/auth*` 改动 |
| 改 /mcp 端点 | `security-reviewer`(必走) | `code-reviewer` | `main.py` / `server/security/llm_guardrails/mcp_server.py` 改动 |
| 部署 / 迁移 / 写新 nginx | `build-error-resolver` | — | `nginx/**` / `docker-compose.yml` / `deploy.ps1` 改动 |

### 3.2 Skill 降级映射(本项目已确认可用版本)

| superpowers Skill | 降级路径 |
|---|---|
| `superpowers:brainstorming` | `planner` Agent 或直接 AskUserQuestion |
| `superpowers:test-driven-development` | `tdd-guide` Agent + pytest 严格红绿重构 |
| `superpowers:systematic-debugging` | 查日志 + `grep` + `Read` + 最小复现脚本 |
| `superpowers:verification-before-completion` | 跑 `pytest` + 跑 curl 自测 + 列出验证证据 |
| `superpowers:finishing-a-development-branch` | `git status` / `git diff` 复查后请用户确认再 commit |

### 3.3 不允许的 Agent 误用

- ❌ 用 `general-purpose` Agent 改护栏层核心代码(应走 `code-reviewer` 独立审查)
- ❌ 用 `Explore` Agent 写代码(只读)
- ❌ 不读 plan.md 就改 LLM 护栏层
- ❌ 跳过 `code-reviewer` / `security-reviewer` 直接 commit 安全相关代码

---

## 4. 关键模块实施状态(M1 完成)

### 4.1 LLM Guardrails 层(`server/security/llm_guardrails/`)

**状态**: ✅ M1 P0 全部完成(94 tests passed / 覆盖率 76%)

| 文件 | 职责 | Agent 必读 |
|---|---|---|
| `core.py` | `GuardrailEngine` 单例 + L1 正则 + L2/L3 NeMo + L4 Moderation + 5s timeout | ✅ |
| `decorators.py` | `@guard_input(scope=...)` / `@guard_output(scope=...)` | ✅ |
| `exceptions.py` | `GuardrailViolation`(继承 `ForbiddenException`,HTTP 403) | ✅ |
| `audit.py` | `log_guardrail_event(..., user_id)` + `get_stats` | ✅ |
| `moderation/client.py` | `OpenAIModerationClient`(独立 httpx,L4 路径) | ⚠ 看 `MAX_INPUT_CHARS=8000` |
| `moderation/provider.py` | `OpenAIModerationProvider`(策略模式,可选路径) | ⚠ |
| `mcp_server.py` | FastMCP("AI-CyberSentinel Guardrails") + `scan_text` / `get_stats` | ✅ |
| `config/config.yml` | NeMo 模型 + rails 声明 | ⚠ |
| `config/rails/input.co` | Colang 1.0 input flow | ⚠ |
| `config/rails/output.co` | Colang 1.0 output flow(留空占位) | ⚠ |
| `config/actions.py` | Python action:`openai_moderation_check`(L4 兜底,fail-closed) | ✅ |

### 4.2 护栏层 4 层防御(Agent 理解顺序)

```
用户输入 ──▶ L1 正则(同形字/角色/system: 等)──── 命中 ──▶ block
            │
            │  未命中
            ▼
        L2 NeMo `openai_moderation_check` (L4 Moderation)
            │
            │  未命中
            ▼
        L3 NeMo `self_check_input` (LLM-as-judge)
            │
            │  放行
            ▼
        LLM 主调用
            │
            ▼
        L3' NeMo `self_check_output` (输出 PII/越界检测)
            │
            ▼
        返回 Copilot
```

**关键约束**(Agent 改动时必须保留):

- L4 异常 → **fail-closed**(返回 `moderation_unavailable` 原因,记 audit warn)
- L1/L2/L3 总耗时 → `asyncio.wait_for(timeout=5.0)`,超时 → 放行 + audit warn
- `_merge_history` → 只接受 `role ∈ {user, assistant, system}` 三种,其他丢弃
- SSE error 事件 → **只显示 category 名,不暴露 regex 模式**
- Audit log `reason` 字段 → **保留完整 regex/类别**(供 SOC 排查)
- `/mcp` 端点 → 强制 `X-Guardrails-Key` 头(`GUARDRAILS_MCP_API_KEY` env,未配置则 401)
- 5s 超时 + 紧急关闭开关 → `NEMO_GUARDRAILS_ENABLED=false` 一键回退

### 4.3 Copilot 接入点

- **文件**: `server/services/copilot_service.py`
- **方法**: `CopilotService.stream_user_chat_completion` (SSE)
- **改造**: 显式调用 `GuardrailEngine.instance().check_input(...)`,**未使用装饰器**(避免 `asyncio.run` 在事件循环里崩溃的已知问题 C-1)
- **失败响应**: 抛 `GuardrailViolation` → SSE `error` 事件 + `log_guardrail_event(status=blocked, user_id=...)`

### 4.4 MCP 暴露(供外部 SIEM/SOAR 接入)

- **端点**: `POST /mcp`(streamable-http)
- **鉴权**: 请求头 `X-Guardrails-Key: <GUARDRAILS_MCP_API_KEY>`
- **Tools**:
  - `guardrail.scan_text(text, history=None) -> {allowed, reason, layer}`
  - `guardrail.get_stats() -> {total, blocked, passed, warning, by_layer, by_scope}`

---

## 5. Plan 与决策记录

| 文档 | 路径 | 状态 |
|---|---|---|
| LLM Guardrails 完整设计 | `docs/plans/LLM_GUARDRAILS_PLAN.md` | v1 已实施(本文件 §4 即其实施状态快照) |
| PR 描述 | `PR_DESCRIPTION.md` | 与本次 M1 配套 |
| Owner 手册 | `OWNER_MANUAL.md` | 给人看的运营手册 |
| 项目 README | `README.md` | 项目门面 |

**改动 plan 之前**:先在 `AGENTS.md` §4 同步实施状态,再改 plan.md(避免双向不一致)。

---

## 6. 硬规则摘录(Agent 必须遵守,完整版见 CLAUDE.md)

1. **输出语言**:所有回复、注释、AGENTS.md、commit message **必须中文**(代码标识符除外)。
2. **测试**: TDD 流程:RED → GREEN → IMPROVE,改护栏层后必跑 `pytest server/tests/security/llm_guardrails/`。
3. **安全审查**: 改 `server/security/**` / `main.py` 的 `/mcp` 段 / 认证代码 → **必须**经过 `security-reviewer`。
4. **不可降级**: 不允许删除/弱化测试通过检查;不允许 `asyncio.run` 包装已被装饰的协程(若必须,先改为显式调用)。
5. **fail-closed**: 任何护栏层异常 → 阻断 + audit warn,默认拒绝而不是默认放行。
6. **SSE error 净化**: 用户可见信息只含 category 名;regex / stack trace 只能进 audit log。
7. **环境变量**: 新增 env var 必须同步 `.env.example`,默认值要安全(缺失 key → 401,不是 200)。

---

## 7. 改动本文件(AGENTS.md)的时机

- ✅ 实施完 M1 后已建立本节 §4 的"实施状态快照"。
- 🔄 每次新增 plan / 实施完新里程碑时:在 §4 加新模块段落,§5 加 plan 索引。
- 🚫 **不要**把代码细节、Colang DSL 完整 YAML 复制到本文件(去 `docs/plans/` 看)。
- 🚫 **不要**把 CLAUDE.md 全部规则复制到本文件(用链接代替)。
