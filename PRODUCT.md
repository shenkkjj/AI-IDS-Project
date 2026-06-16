# AI-CyberSentinel 产品操作系统

> 读者：产品经理、项目 owner、AI Agent。
> 目的：把这个 vibe coding 项目从“能跑一些功能”治理成“可以持续加功能、审查、发布的产品”。
> 使用方式：任何新增功能、重构、代码审查前，先读本文件，再读 `AGENTS.md` 和相关模块文档。

---

## 1. 产品北极星

AI-CyberSentinel 不是泛泛的“安全大屏”，而是一个面向中小团队、学习型安全团队和个人实验室的 **AI 辅助 IDS / WAF / SOC Copilot**。

它的核心承诺只有三件事：

1. **Protect**：发现并拦截常见 Web 攻击，如 SQL 注入、XSS、扫描、暴力尝试。
2. **Explain**：把告警解释成人能看懂的风险、证据、影响和建议动作。
3. **Operate**：给操作者可审计、可回放、可验证的安全运营闭环。

产品成功的第一性指标不是功能数量，而是：

- 一个新用户能在 10 分钟内跑起 demo。
- 一个模拟攻击能稳定进入“检测 -> 告警 -> Copilot 分析 -> 审计记录”链路。
- 一个 AI Agent 能在明确边界内完成小功能，并通过测试、审查和安全检查。

---

## 2. 当前基线（2026-06-16 实测）

### 2.1 已验证通过

```powershell
npm run typecheck
npm run build
```

- 前端 TypeScript 检查通过。
- 前端 Next.js 生产构建通过。
- `/dashboard` 构建体积约 25.4 kB，First Load JS 约 173 kB。

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

- 后端默认测试：225 passed, 1 skipped。跳过项为可选 Playwright E2E。

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_e2e.py -q --tb=short --run-e2e
```

- 可选 E2E 入口保留；缺少 Playwright 时为 1 skipped。

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

- LLM Guardrails 测试：139 passed, 17 warnings。需作为安全护栏变更的独立验证命令保留。

### 2.2 当前明显问题

1. `README.md`、`PRODUCT.md`、`server/STRUCTURE.md` 和 `docs/agent/UNATTENDED_LONG_TASKS.md` 已作为当前入口文档；部分历史文档仍可能存在过时内容，需要按任务逐步清理。
2. Playwright E2E 仍依赖本地浏览器和前后端服务，默认 pytest 只保留 skip；2026-06-16 已用 in-app Browser 跑通过”注册/登录 -> Dashboard -> 触发 Demo -> 告警可见 -> Copilot 降级态”真实路径。`server/tests/test_demo_flow_e2e.py` 已把这条路径固化为可重复 E2E。
3. 当前没有独立 ESLint 配置；CI 已移除 `npx next lint`，前端默认验证为 `npm run typecheck` 和 `npm run build`。
4. 后端 CI 覆盖率门槛已拆分为阶段性核心口径：全量测试继续运行，80% 覆盖率门槛只统计 LLM Guardrails、RBAC、安全工具和 ORM 模型；全 `server` 包覆盖率约 52% 仍作为后续债务。
5. `web-next/app/page.tsx` 和 `web-next/app/dashboard/dashboard-client.tsx` 偏大，后续 UI 变更容易让 agent 误伤。
6. 项目有很强的安全/测试规则，但缺少稳定的产品路线、验收标准和 agent 工单模板。
7. Copilot 有 key 成功流式路径已通过 `server/tests/test_copilot_contract.py` + `FakeLLMProvider` 保护（默认 `_PROVIDERS` registry 不含 `fake_test`，生产不可达 fake）。
8. `GET /logs/security-timeline` 端点 + Dashboard § 03.5 段已上线 SOC 时间线；schema 经 sentinel 脱敏，不外泄 regex / stack trace / API key / system prompt。
9. `scripts/check_env_security.py` 覆盖生产必填 secret、placeholder、CORS、DEV_MODE、MCP 鉴权；本地开发不阻塞，生产模式有 BLOCK 项。

---

## 3. Vibe Coding 工作法

主流经验可以压缩成一句话：**让 AI 快速写代码，但不要让 AI 决定产品边界、验收标准和安全底线。**

本项目采用“规格驱动的 vibe coding”：

```text
想法 -> 产品能力说明 -> 小工单 -> 测试先行 -> 实现 -> 验证 -> 代码审查 -> 安全审查 -> 文档同步
```

外部方法论依据：

- GitHub Copilot coding agent 建议任务要清楚、范围要小、要有验收标准和需要修改的文件线索。
- GitHub Spec-Driven Development 强调先写规格，把规格作为 AI agent 生成、测试、验证代码的事实源。
- Anthropic Claude Code 团队经验强调详细的 `CLAUDE.md` / 项目说明会显著提升 agent 表现，并用测试、checkpoint、人工审查兜底。
- Vibe coding 的风险在于“看起来对但实际不完整”，所以本项目把验证和审查放在完成定义里。

---

## 4. 产品能力边界

### 4.1 必须做好的核心路径

1. 用户能启动项目并登录。
2. 用户能看到安全态势 dashboard。
3. 系统能接收或模拟攻击流量。
4. 系统能生成告警，并保留证据。
5. Copilot 能解释告警，不泄露系统 prompt、密钥或越权内容。
6. 管理员能看到关键健康状态、审计记录和护栏指标。

### 4.2 暂时不追求

- 不做完整企业级 SIEM 替代品。
- 不做多租户计费系统，除非先完成核心检测闭环。
- 不做复杂 ML 训练平台，除非已有数据集、评估指标和回归测试。
- 不引入新前端框架或后端框架。
- 不为了“看起来高级”堆更多 LLM provider。

---

## 5. 近期路线图

### M0：恢复可控性（优先级最高）

目标：让项目入口、验证命令、CI 和 agent 上下文稳定。

任务：

1. 修复主要 Markdown 文档乱码，先修 `README.md`、`server/STRUCTURE.md`、`docs/ALEMBIC_MIGRATION.md`。
2. 已完成：把 E2E 测试从默认 pytest 收集中隔离，并保留 `--run-e2e` 显式入口。
3. 已完成：CI 不再调用 `npx next lint`，改用非交互式 `npm run typecheck` 和 `npm run build`。
4. 新增 `docs/roadmap/` 或 `docs/product/` 索引，把计划、发布说明、产品能力统一入口化。
5. 更新 README 快速启动，确保小白能按步骤跑起前后端。

验收：

- `pytest server/tests -q --tb=short` 不因缺少可选 E2E 依赖而失败。
- `npm run typecheck` 和 `npm run build` 通过。
- CI 不出现交互式命令。
- README 中文可读，启动步骤可执行。

### M1：Demo 级安全闭环

目标：把产品打磨成一个能展示的完整故事。

当前状态：基础闭环已建立，并已通过真实浏览器路径验收。已新增认证态 `/alerts/demo`、Dashboard “触发 Demo 攻击”按钮、Copilot “分析当前告警”快捷动作和 `scripts/demo_attack.ps1` smoke 脚本。`/alerts/demo` 会返回 Copilot `ready` / fallback 元数据；无真实 API key 或 Base URL 时，Dashboard、终端日志和 Copilot SSE 都会清晰展示降级态。

用户故事：

> 作为安全分析员，我能启动系统，触发一次模拟攻击，在 dashboard 看到告警，点开 Copilot 获得解释和建议，并在审计日志中看到对应记录。

任务：

1. 已完成：固化攻击模拟入口，包含 dashboard 内置按钮和 `scripts/demo_attack.ps1`。
2. 已完成：补 dashboard 的“触发告警 -> 选中新告警 -> Copilot 分析/降级态”路径。
3. 已完成：LLM provider 缺失会通过 demo metadata、Dashboard 状态提示、脚本输出和 Copilot SSE 展示清晰降级态；Guardrails 拦截态沿用现有 SSE error 展示，后续仍需更细 UI 区分。
4. 已完成：给 demo 路径补 `server/tests/test_demo_flow.py` smoke test。

验收：

- 无真实 API key 时，demo 仍能通过 mock 或降级说明跑通。
- 有 API key 时，Copilot 能流式输出安全分析。
- 攻击样本、告警表、统计卡、Copilot 请求已串起来；guardrail audit 展示仍是后续债务。

### M2：安全运营化

目标：从 demo 变成可长期运行的小型 SOC 工具。

详细路线图见 `docs/plans/M2_PRODUCT_ROADMAP.md`。M2 的主题不是继续堆功能，而是把 M1 demo 闭环变成可验证、可部署、可接力维护的运营基线。

任务：

1. 已完成：建立 Demo Flow 自动化 E2E（`server/tests/test_demo_flow_e2e.py`），保护”登录 -> Dashboard -> 触发 Demo -> 告警可见 -> Copilot 降级/分析”真实路径；显式 `--run-e2e` 触发，默认 pytest 跳过。
2. 已完成：增加 Copilot fake provider / contract 测试（`server/tests/test_copilot_contract.py` + `FakeLLMProvider`），让有 key 的流式成功路径不依赖真实外部 LLM；`_PROVIDERS` 默认不含 `fake_test`，生产不可达 fake。
3. 已完成：审计时间线（`GET /logs/security-timeline` + Dashboard § 03.5 段 + `SecurityTimeline` 组件），把 demo attack、Copilot 请求、Guardrails 决策和关键操作日志变成可见运营证据；sentinel 脱敏，敏感字段不外泄。
4. 统一数据库配置和 Alembic 迁移策略，替代启动时手写 ALTER TABLE。
5. 给 `/metrics`、`/mcp`、审计清理、Guardrails 状态补运维文档和安全边界。
6. 已完成：明确生产环境最小安全配置（`scripts/check_env_security.py`）：secret、CORS、DEV_MODE、metrics/MCP 鉴权、nginx allowlist；退出码 0/1 区分通过/阻塞。

验收：

- 新增 env var 必须同步 `.env.example`。
- 安全相关改动必须跑 `server/tests/security/llm_guardrails/` 和安全审查。
- 生产部署文档能说明失败时如何回滚。
- 默认测试、Demo Flow、前端 typecheck/build 和至少一个浏览器级 Demo Flow 验收入口通过。
- `pytest server/tests -q --tb=short` 通过；`pytest server/tests/security/llm_guardrails -q --tb=short` 通过；`pytest server/tests/test_demo_flow_e2e.py --run-e2e` 至少在 skip 模式下打印清晰指引。
- `python scripts/check_env_security.py` 在本地开发返回 0；在生产模式 + 占位 secret 返回 1。

### M3：产品体验升级

目标：让它从“工程项目”变成“用户愿意反复打开的产品”。

任务：

1. 拆分 dashboard 大组件，沉淀可复用的 alert、chart、copilot、system status 组件。
2. 增强告警解释：风险等级、证据、影响范围、建议动作、复制报告。
3. 增加“日/周安全简报”，但必须可追溯到真实告警数据。
4. 统一空状态、加载态、错误态和离线态。

验收：

- 关键路径在桌面和移动端无布局错乱。
- UI 改动必须经过浏览器截图或手动验证说明。
- 不把营销落地页当作产品首页，第一屏必须可操作。

---

## 6. Agent 工单模板

以后不要只对 agent 说“帮我加功能”。用下面格式：

```markdown
你是 AI-CyberSentinel 的开发 agent。请先阅读 `PRODUCT.md`、`AGENTS.md`、`CLAUDE.md`，再执行任务。

任务目标：
- 用一句话说明用户完成后能做什么。

范围：
- 允许修改：
  - path/to/file
  - path/to/dir/**
- 不允许修改：
  - 安全护栏核心，除非本任务明确要求
  - 认证/授权逻辑，除非本任务明确要求

验收标准：
- 用户可见行为：
- API/数据行为：
- 错误态：
- 安全要求：

验证命令：
- 后端：`.venv\Scripts\python.exe -m pytest ...`
- 前端：`npm run typecheck && npm run build`

完成前要求：
- 列出改动文件。
- 列出已运行验证。
- 如果涉及 `server/security/**`、认证、密钥、LLM、外部调用，必须做安全审查。
```

---

## 7. 无人值守长任务

如果你想让 agent 连续工作较长时间，并且你暂时不盯着它，必须使用 `docs/agent/UNATTENDED_LONG_TASKS.md`。

默认规则：

- L1 文档/测试/小清理可以无人值守。
- L2 普通功能可以无人值守，但必须写运行日志和阶段检查点。
- L3 认证、授权、数据库、安全护栏、部署只能半自动，必须遇到风险停止。
- agent 不允许自动 commit、push、merge、deploy，除非用户明确授权。

推荐先跑：

1. `M2-02` Demo Flow 自动化 E2E。
2. `M2-06` Copilot fake provider / contract 测试。
3. `M2-03` 审计时间线与 Guardrails 可见性。

---

## 8. 代码审查模板

让 agent 审查代码时，用这个模板：

```markdown
请以代码审查模式检查当前 diff，不要直接改代码，先给 findings。

重点：
- 是否破坏 `PRODUCT.md` 的产品边界。
- 是否违反 `AGENTS.md` / `CLAUDE.md` 的测试和安全规则。
- 是否有认证、授权、密钥、用户输入、SQL、SSRF、XSS、LLM prompt injection 风险。
- 是否缺少测试或验收命令。
- 是否有文档需要同步。

输出格式：
- Findings 优先，按严重程度排序。
- 每条必须包含文件和行号。
- 没有问题时明确说“未发现阻塞问题”，并列出剩余风险。
```

---

## 9. Definition of Ready / Done

### Ready

一个任务开始编码前必须满足：

- 目标能用一句话说清。
- 修改范围能列出主要目录。
- 至少有一个可运行的验证命令。
- 涉及用户输入、认证、LLM、密钥、数据库时，安全要求已写入验收标准。

### Done

一个任务完成前必须满足：

- 代码实现完成。
- 相关测试通过，或清楚说明为什么不能运行。
- 前端改动至少通过 `npm run typecheck`，重大 UI 改动还要浏览器验证。
- 后端改动至少跑相关 pytest。
- 安全敏感改动完成安全审查。
- 文档、`.env.example`、README 在需要时同步。

---

## 10. 风险登记

| 风险 | 当前判断 | 处理策略 |
|---|---|---|
| 文档乱码 | 高 | M0 先修入口文档 |
| E2E 测试默认失败 | 低 | 已标记为可选 E2E，默认 pytest 跳过；显式入口为 `--run-e2e` |
| CI lint 交互式失败 | 低 | 已移除 `npx next lint`，CI 使用非交互 typecheck/build |
| 全 `server` 包覆盖率不足 | 中 | CI 先守核心模块 80%；另开覆盖率扩面工单补 router/service/demo/legacy 测试 |
| 前端大组件难维护 | 中 | M3 拆分，但不要在 M0 急着重构 |
| 安全边界复杂 | 高 | 任何相关改动必须按 `AGENTS.md` 路由审查 |
| 产品范围膨胀 | 高 | 每个功能必须映射 Protect / Explain / Operate |

---

## 11. 下一批推荐工单

1. `M2-02` Demo Flow 自动化 E2E。
2. `M2-06` Copilot fake provider / contract 测试。
3. `M2-03` 审计时间线与 Guardrails 可见性。
4. `M2-01` 数据库配置与 Alembic 基线。
5. `M2-04` 生产最小安全配置文档与检查。
6. `M2-05` Dashboard 状态边界拆分。
7. `M2-07` Docker Compose 端到端验收。

推荐顺序：先保护 Demo Flow，再补 Explain 路径和审计证据，最后处理迁移、部署和拆分。
