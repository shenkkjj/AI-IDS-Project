# M3-06 测试与安全质量门收口 L5 超长任务

> 任务级别：L5，高风险测试债务 + 安全边界 + 验证矩阵收口战役。  
> 目标读者：接手本仓库的开发 agent。  
> 核心目标：把 M3-04 / M3-05 运行日志里反复标记为“预存失败”的测试债务收口为可重复、可解释、可验证的质量门，而不是继续把失败留到下一个任务。

---

## 0. 背景

M3-03 到 M3-05 已经把告警研判、案件工作台、案件感知 Copilot 合约连续落地。当前产品能力在增长，但测试基线出现了一个危险信号：

- M3-04 run log 记录过全量 `server/tests` 有 12 个预存失败：LLM Colang flows 9 个 + SSRF 3 个。
- M3-05 run log 记录 `test_demo_alert_can_drive_copilot_fallback` 因 NeMo Guardrails `moderation_unavailable` 失败。
- `PRODUCT.md` 和部分 roadmap 仍保留更早的“默认后端测试全绿”叙述，已经可能过时。
- 如果继续让后续 agent 在这些失败上叠功能，项目会越来越难判断“这是新回归，还是旧债务”。

本任务不是新增产品功能，而是建立可持续加功能之前必须有的质量地基：

```text
复现预存失败
  -> 分类失败性质
  -> 用 TDD / 测试夹具 / 最小生产修复收口
  -> 保持 Guardrails / SSRF 真实安全策略不降级
  -> 跑通目标质量门
  -> 文档同步当前真实基线
  -> 精确 commit / push
```

---

## 1. 产品能力定义

完成后，owner 和后续 agent 应该能做到：

1. 清楚知道当前默认后端测试、Guardrails 专项、SSRF 专项、Demo Flow、Copilot contract 的真实状态。
2. 不再把 `moderation_unavailable`、Colang corpus、SSRF DNS/monkeypatch 问题含糊称作“预存失败”。
3. 本地无真实 OpenAI / NeMo 外部可用性时，相关测试仍可确定性运行。
4. SSRF 防护仍然阻断 loopback / private / link-local / metadata / multicast / reserved 地址。
5. Guardrails 生产路径仍然 fail-closed，不因为测试稳定性而放宽策略。
6. 后续 agent 可以把本任务产出的验证矩阵作为新的开发前基线。

一句话能力声明：

> 项目从“带着已知失败继续堆功能”升级为“测试失败有明确归属，核心安全质量门可重复验证”。

---

## 2. 启动前必读

执行前完整阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`
- `docs/runs/2026-06-18-m3-04-incident-case-workbench.md`
- `docs/runs/2026-06-18-m3-05-incident-aware-copilot-contract.md`

必须阅读当前实现：

- `server/tests/test_demo_flow.py`
- `server/tests/security/llm_guardrails/test_colang_flows.py`
- `server/tests/security/llm_guardrails/conftest.py`
- `server/tests/security/llm_guardrails/corpus/*.jsonl`
- `server/tests/test_ssrf.py`
- `server/security/llm_guardrails/core.py`
- `server/security/llm_guardrails/config/actions.py`
- `server/security/llm_guardrails/moderation/client.py`
- `server/security/llm_guardrails/moderation/provider.py`
- `server/analyzer.py`
- `server/core/utils.py`
- `server/services/copilot_service.py`
- `server/tests/test_copilot_contract.py`
- `server/tests/test_copilot_incident_contract.py`

必须遵守：

- Skill-First：优先使用适合的测试、安全、验证类 skill。
- TDD：先用失败命令复现，再改测试夹具或生产代码。
- Security review：任何 `server/security/**`、SSRF、Copilot SSE、外部 URL 校验相关改动都要审查。
- 不允许用 skip / xfail / 删除断言掩盖本任务列出的失败。
- 不允许为了测试通过而放宽 Guardrails 或 SSRF 真实生产策略。

---

## 3. 初始仓库审计

开始改文件前必须创建运行日志：

```text
docs/runs/2026-06-18-m3-06-test-and-security-quality-gate-closure.md
```

在运行日志记录：

- 当前分支。
- 当前 `HEAD`。
- `origin/main`。
- `git status --short --branch`。
- 暂存区是否为空。
- 禁提交噪声：
  - `.coverage`
  - `.claude/settings.local.json`
  - `data/*.db`
  - `.env`
  - `.env.*` 中真实密钥文件
  - 证书 / 私钥 / token / cookie / browser profile

停止条件：

- 本地分支落后远端且无法 fast-forward 判断。
- 暂存区已有用户改动。
- 工作树出现与本任务无关的大量业务改动。
- 发现真实 secret、真实数据库、证书私钥即将被提交。

---

## 4. 当前已知失败面

本任务至少要处理这些失败面。实际执行时必须先运行命令确认，不要只相信文档。

### 4.1 Demo Flow fallback

目标测试：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow.py::test_demo_alert_can_drive_copilot_fallback -q --tb=short
```

已知现象：

- M3-05 记录该测试可能在 Guardrails `moderation_unavailable` 上失败。
- 该测试的业务意图是证明 demo alert 可以驱动 Copilot，并在没有 API Key 时返回“请先在配置页设置可用的 API Key”降级态。

判定原则：

- 如果测试只是在验证 no-key fallback，不应依赖真实 OpenAI moderation 或 NeMo 外部可用性。
- 可通过测试夹具 stub GuardrailEngine，让测试聚焦 no-key fallback。
- 不能修改生产逻辑为“没有 key 时绕过 Guardrails”，除非先写产品和安全说明，并证明这是明确策略；默认不要这么做。

### 4.2 LLM Guardrails Colang corpus

目标测试：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails\test_colang_flows.py -q --tb=short
```

必须保持的断言：

- direct injection：100% block。
- multi-turn injection：100% block。
- role hijack：100% block。
- unicode bypass：>= 80% block。
- benign：0% block。

判定原则：

- 测试不应因为没有真实 OpenAI moderation key 或网络不可用而变成随机失败。
- 如果失败来自外部 moderation client 或 NeMo 初始化，应优先在测试层提供确定性假实现。
- 生产路径仍要保留：L4 异常 fail-closed、NeMo 超时策略、SSE error 净化、audit reason 完整保留。
- 不允许通过降低 corpus 阈值、删除样本、把 benign 改成 blocked、或新增 skip 来过关。

### 4.3 SSRF 防护

目标测试：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_ssrf.py -q --tb=short
```

必须保持的安全性质：

- 阻断 `127.0.0.1`、`localhost`、`::1`。
- 阻断 RFC1918 私网地址。
- 阻断 `169.254.169.254` 和 `metadata.google.internal`。
- 阻断 link-local、multicast、reserved。
- `build_chat_completions_url()` 仍对 base URL 做 SSRF 检查。

判定原则：

- 测试不应依赖真实外网 DNS。
- 如果 monkeypatch 目标不稳定，要修测试夹具或抽出可替换解析 seam。
- 不允许让 `_is_ssrf_safe()` 默认放行解析失败的 hostname。
- 不允许因为某个公网域名在本地解析异常就放宽生产 SSRF 策略。

---

## 5. 允许修改范围

允许修改：

- `server/tests/test_demo_flow.py`
- `server/tests/test_ssrf.py`
- `server/tests/security/llm_guardrails/**`
- `server/tests/conftest.py`（仅当需要通用测试夹具）
- `server/analyzer.py`（仅当 SSRF 可测试 seam 或真实 bug 需要）
- `server/core/utils.py`（仅当 SSRF 解析逻辑真实 bug 需要）
- `server/security/llm_guardrails/core.py`（仅当生产 bug 需要，必须安全审查）
- `server/security/llm_guardrails/config/actions.py`（仅当生产 bug 需要，必须安全审查）
- `server/services/copilot_service.py`（仅当 demo fallback contract 暴露真实 bug 需要）
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/runs/2026-06-18-m3-06-test-and-security-quality-gate-closure.md`

原则：

- 优先改测试夹具和测试隔离。
- 只有确认是生产 bug 时才改生产代码。
- 生产代码改动必须小、可解释、带回归测试。

---

## 6. 禁止修改范围

禁止修改：

- `.coverage`
- `.claude/settings.local.json`
- 真实 `.env` / `.env.local` / `.env.compose.local`
- `data/*.db`
- `server/core/auth*`
- 登录 / 注册 / JWT / refresh token / 2FA / cookie 语义
- Alembic migration 和数据库 schema（本任务默认不需要）
- `docker-compose.yml`
- `nginx/**`
- LLM provider 默认 registry 或真实 provider 选择策略，除非测试夹具局部注入
- `/mcp` 鉴权逻辑

禁止操作：

- `git add .`
- `git reset --hard`
- `git clean`
- 删除测试、跳过测试、弱化断言来制造绿色。
- 提交真实 secret、coverage、数据库、证书私钥。

---

## 7. 阶段计划

### 阶段 1：启动审计与运行日志

- 创建 run log。
- 记录 git 和远端状态。
- 记录本任务使用的 skill / 工具策略。
- 确认禁提交文件只作为噪声保留。

验收：

- run log 存在。
- 明确“可以继续 / 必须停止”的判断。

### 阶段 2：复现失败，不改代码

按顺序运行：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow.py::test_demo_alert_can_drive_copilot_fallback -q --tb=short
```

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails\test_colang_flows.py -q --tb=short
```

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_ssrf.py -q --tb=short
```

记录每条命令：

- 总数。
- 失败测试名。
- 失败原因摘要。
- 是否与 M3-04 / M3-05 记录一致。

验收：

- run log 有真实失败证据。
- 失败已被分类：测试夹具问题 / 生产 bug / 环境问题 / 文档陈旧。

### 阶段 3：Demo Flow fallback 收口

目标：

- `test_demo_alert_can_drive_copilot_fallback` 在本地无真实 moderation 服务时稳定通过。
- 测试仍证明 demo alert id 和 no-key fallback 行为。

推荐方向：

- 在测试内 stub `GuardrailEngine.instance().check_input(...)` 为 allow。
- 或注入现有测试 fake guardrails helper，如果仓库已有。
- 不触碰生产 Guardrails 策略。

必要断言：

- Copilot body 包含 no-key fallback 文案。
- provider 不应被真实外部调用。
- 测试不需要真实 OpenAI / NeMo / 网络。

验收命令：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow.py -q --tb=short
```

### 阶段 4：Guardrails corpus 确定性收口

目标：

- Colang corpus 测试不依赖真实 OpenAI moderation key、真实网络或不稳定外部服务。
- 保持 corpus 阈值和阻断语义不降级。

推荐方向：

- 阅读 `server/tests/security/llm_guardrails/conftest.py`，优先复用或新增测试级 fixture。
- 对 L4 moderation client 提供 pass-through fake，使测试聚焦 L1 / NeMo / Colang 语义。
- 如果 NeMo 本身不可确定，先把失败样本和层级写清楚，再最小修正 test harness 或 L1 规则。
- 如果确需修改 `core.py` 或 `actions.py`，先在 run log 写风险说明和回滚方案。

必须保留：

- production L4 异常 fail-closed。
- `_merge_history` role 过滤。
- SSE 用户可见错误不暴露 regex。
- audit reason 保留完整类别 / regex 供 SOC 排查。

验收命令：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails\test_colang_flows.py -q --tb=short
```

再运行：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

### 阶段 5：SSRF 测试与防护收口

目标：

- `server/tests/test_ssrf.py` 13 个测试稳定通过。
- 测试不依赖真实公网 DNS。
- 生产防护不放宽。

推荐方向：

- 检查 `_is_ssrf_safe()` 对 `server.core.utils._is_url_pointing_to_internal` 的导入时机。
- 如果测试 monkeypatch 没有命中，调整测试 patch 位置或提取可替换 helper。
- 对公网域名测试使用确定性 stub，不进行真实 DNS。
- 对 `build_chat_completions_url()` 的正常域名测试也应避免网络依赖。

验收命令：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_ssrf.py -q --tb=short
```

### 阶段 6：Copilot / Incident 回归矩阵

目标：

- M3-05 案件感知 Copilot contract 不被质量门修复误伤。
- M3-03 / M3-04 告警、案件、研判路径不回归。

运行：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_copilot_contract.py server\tests\test_copilot_incident_contract.py server\tests\test_incidents.py server\tests\test_incident_persistence.py server\tests\test_alert_triage.py server\tests\test_alert_triage_persistence.py server\tests\test_demo_flow.py server\tests\test_ssrf.py -q --tb=short
```

验收：

- 上述矩阵应全绿。
- 如失败，必须证明是新问题还是与本任务改动相关；不要继续扩大范围。

### 阶段 7：后端全量基线

先运行默认后端测试：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

如果全量仍失败：

- 不允许只写“预存失败”。
- 必须列出每个失败文件 / 测试名 / 原因 / 是否本任务引入。
- 如果剩余失败与本任务三大失败面无关，写入 run log 的“未解决问题”，并停止或请 owner 拆下一张工单。

理想验收：

- 默认 `server/tests` 全绿，或剩余失败被严格证明为本任务外部依赖且有下一步工单。

### 阶段 8：前端验证

本任务原则上不改前端，但 M3-05 之后仍要确认 Dashboard build 没被文档或依赖误伤。

```powershell
cd web-next
npm run typecheck
npm run build
```

验收：

- typecheck 0 error。
- build 成功。

### 阶段 9：文档同步

必须同步：

- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- 本任务 run log。

文档必须讲清：

- M3-06 是否把“预存失败”清零。
- 新的后端默认测试真实结果。
- Guardrails 专项真实结果。
- SSRF 专项真实结果。
- Demo Flow 真实结果。
- 如果仍有剩余失败，明确它们不是“已知失败”四个字，而是可追踪的问题列表。

### 阶段 10：安全审查

审查并记录：

- Guardrails 生产 fail-closed 是否保持。
- 测试 stub 是否只存在于测试代码。
- SSRF 生产阻断列表是否保持。
- URL 解析失败是否仍默认不安全。
- SSE error 是否仍不暴露 regex / stack trace。
- audit 是否未写入 secret / API key / payload 全文。
- 没有新增真实 env var；如新增必须同步 `.env.example` 并默认安全。
- 没有改认证 / 授权 / cookie / JWT。

### 阶段 11：最终验证矩阵

最终至少运行：

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow.py server\tests\test_ssrf.py server\tests\security\llm_guardrails -q --tb=short
```

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_copilot_contract.py server\tests\test_copilot_incident_contract.py server\tests\test_incidents.py server\tests\test_incident_persistence.py server\tests\test_alert_triage.py server\tests\test_alert_triage_persistence.py -q --tb=short
```

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

```powershell
cd web-next
npm run typecheck
npm run build
```

如果某条命令因环境问题不能运行，必须写：

- 具体错误。
- 已尝试的最小修复。
- 为什么不能继续。
- 下一步最小工单。

### 阶段 12：精确 commit / push

只有满足以下条件才允许 commit / push：

- run log 完整。
- 禁提交文件未 stage。
- 目标测试矩阵已跑。
- 安全审查已写入 run log。
- `git status --short` 已复核。

禁止 `git add .`。

建议拆分 commit：

```text
test(quality): 复现并收口预存测试失败
fix(security): 稳定 SSRF 与护栏测试边界
docs(quality): 记录 M3-06 质量门基线
```

如果实际只改测试不改生产代码，commit 名可以更保守：

```text
test(quality): 稳定安全质量门测试夹具
docs(quality): 记录测试基线收口
```

push 前：

```powershell
git status --short --branch
git log --oneline --decorate -5
git push origin main
```

---

## 8. 验收标准

最低验收：

- `test_demo_alert_can_drive_copilot_fallback` 通过。
- `server/tests/security/llm_guardrails/test_colang_flows.py` 通过。
- `server/tests/test_ssrf.py` 通过。
- 不新增 skip / xfail 来掩盖这三类失败。
- 生产 Guardrails / SSRF 策略不降级。
- run log 记录完整。

目标验收：

- `server/tests/security/llm_guardrails` 全绿。
- M3-03 / M3-04 / M3-05 回归矩阵全绿。
- `server/tests` 默认全绿，或剩余失败有严格分类和下一步工单。
- `npm run typecheck` 和 `npm run build` 通过。
- 文档同步当前真实基线。
- 精确 commit / push 到 `origin/main`。

---

## 9. 停止条件

满足任一条件必须停止并写清楚：

1. 同一个失败连续修复 3 轮仍失败。
2. 需要改认证 / 授权 / JWT / cookie / 数据库 schema，但本任务未授权。
3. 需要真实 OpenAI key、真实生产 secret、外部登录或付费服务。
4. 为修测试必须削弱 Guardrails fail-closed 或 SSRF block 策略。
5. diff 超过约 1200 行且不是文档 / 测试夹具为主。
6. 全量测试暴露大量与本任务无关失败，无法在本任务内安全收口。
7. 远端 main 前进，当前本地无法安全 fast-forward。

停止时必须交付：

- 已完成内容。
- 未完成内容。
- 阻塞原因。
- 下一条最小工单。

---

## 10. 完成时输出

最终报告必须包含：

- 完成状态：完成 / 部分完成 / 阻塞。
- 改动文件列表。
- 每个已知失败面的处理结果。
- 运行过的验证命令和结果。
- 安全审查结论。
- run log 路径。
- commit 列表和 push 状态。
- 剩余问题与下一条建议工单。

---

## 11. 给 agent 的短启动口令

```text
请执行 `docs/agent/M3_06_TEST_AND_SECURITY_QUALITY_GATE_CLOSURE_TASK.md` 中定义的 L5 超长任务。先完整阅读该文件和其中列出的必读上下文，创建运行日志，先复现再修复，按阶段推进；不要问我小问题，不要用 skip/xfail 掩盖失败，不要削弱 Guardrails 或 SSRF 生产安全策略，不要使用 git add .，不要提交 `.coverage`、`.claude/settings.local.json`、真实 env、数据库或密钥。满足质量门后可以按文档精确 commit 并 push 到 `origin/main`，完成后按任务文档输出最终报告。
```
