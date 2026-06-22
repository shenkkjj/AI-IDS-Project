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
2. Playwright E2E 仍依赖本地浏览器和前后端服务，默认 pytest 只保留 skip；2026-06-16 已用 in-app Browser 跑通过”注册/登录 -> Dashboard -> 触发 Demo -> 告警可见 -> Copilot 降级态”真实路径。`server/tests/test_demo_flow_e2e.py` 已把这条路径固化为可重复 E2E。M3-02 阶段在 E2E 中扩展了"研判状态切换 -> 保存备注 -> 攻击日志行更新"步骤。
3. 当前没有独立 ESLint 配置；CI 已移除 `npx next lint`，前端默认验证为 `npm run typecheck` 和 `npm run build`。
4. 后端 CI 覆盖率门槛已拆分为阶段性核心口径：全量测试继续运行，80% 覆盖率门槛只统计 LLM Guardrails、RBAC、安全工具和 ORM 模型；全 `server` 包覆盖率约 52% 仍作为后续债务。
5. **M2-01 已交付**：`server/core/database.py` 现在按 `DATABASE_URL` 选数据库（`load_database_url` / `normalize_database_url` / `build_engine_kwargs` / `create_app_engine`），未设置时回退到默认 SQLite；Alembic baseline revision `d9af4388f20a_baseline_schema.py` 已建立；新增 `test_database_config.py`（13 通过）和 `test_migrations.py`（8 通过）；`docs/ALEMBIC_MIGRATION.md` 已从"计划"转为"已建立 baseline"。PostgreSQL 端到端验收仍属 M2-07。
5. `web-next/app/page.tsx` 仍偏大；`web-next/app/dashboard/dashboard-client.tsx` 已在 M3-10 从 840 行收口到 406 行，后续 Dashboard 风险主要转为 section 响应式 QA、可访问性和浏览器截图证据。
6. 项目有很强的安全/测试规则，但缺少稳定的产品路线、验收标准和 agent 工单模板。
7. Copilot 有 key 成功流式路径已通过 `server/tests/test_copilot_contract.py` + `FakeLLMProvider` 保护（默认 `_PROVIDERS` registry 不含 `fake_test`，生产不可达 fake）。
8. `GET /logs/security-timeline` 端点 + Dashboard § 03.5 段已上线 SOC 时间线；schema 经 sentinel 脱敏，不外泄 regex / stack trace / API key / system prompt。
9. `scripts/check_env_security.py` 覆盖生产必填 secret、placeholder、CORS、DEV_MODE、MCP 鉴权；本地开发不阻塞，生产模式有 BLOCK 项。
10. **M3-03 告警研判持久化与历史**已交付：`alert_records` / `alert_triage_events` 两张表 + Alembic migration `d33d40488e0f` 已建出；`PATCH /alerts/{alert_id}/triage` 现在写最新 triage 到 `alert_records` + 写一条 `alert_triage_events`；`GET /alerts/{alert_id}/triage/history?limit=50` 返回 owner 隔离的 newest-first 历史；`GET /alerts` 重启后从 DB 恢复；内存 `app_state.alert.backlog` 仍用于 WebSocket 实时推送与 worker 短期缓存。`M3-02` 的内存边界已升级为 DB 持久化边界；`Log(action="alert_triage_update")` 继续只写脱敏摘要。
11. **M3-04 安全事件 / 案件工作台**已交付：`incidents` / `incident_alert_links` / `incident_events` 三表 + Alembic migration `4f3c9a1d8b7e`（基于 `d33d40488e0f`）落地；`GET / POST / PATCH /incidents` + `POST /incidents/{id}/alerts` + `DELETE /incidents/{id}/alerts/{alert_id}` 全套端点 + 5 状态白名单 (`open / investigating / contained / resolved / false_positive`) + `closed_at` 进入关闭态自动设置 / 改回打开态清空 + 重复 link 幂等 (不重复写 active link / `IncidentEvent` / Log) + owner 404 统一；`Log(action=incident_create / incident_update / incident_alert_link / incident_alert_unlink)` 只写脱敏摘要；前端 `useIncidents` + `IncidentSection / IncidentList / IncidentDetailPanel / IncidentTimeline / IncidentLinkedAlerts` 5 个新组件 + `RouteKey="incidents"` + 案件 Copilot 前端拼接消息（incident id / title / severity / status / 告警数 / 最多 5 条告警摘要 + 风险/证据/影响/下一步处置四段式要求,不含 secret / system prompt / stack trace）。
12. **M3-05 案件感知 Copilot 合约**已交付：`CopilotStreamIn` 增 `incident_id` (max_length=64)，与 `alert_id` 同时存在时 incident 优先；后端 `server/services/copilot_service._load_incident_context` 走 M3-04 owner 隔离 (`incident_service.get_incident_detail` with `event_limit=5`)，`_build_context_from_incident` 构造受控 context_block（最多 5 alerts + 5 events；summary 截断 500 字符；alert summary / event detail 截断 160 字符；event note 只放 `note_length`；alert payload 只放 `payload_length`；不放 secret / system prompt / stack trace）。SSE 错误净化：incident 不可用返回 `案件上下文不可用或不存在`（不区分 owner/不存在，不暴露 incident_id），与 Guardrails block 错误独立。Guardrails 仍在 provider 前执行，incident 路径不绕过。audit `Log(action="copilot_stream")` detail 增 `incident_id=...` 维度（仅在提供时出现），不写 title / summary / note / fake key / stack trace。fake provider 合约测试 `test_copilot_incident_contract.py` 9 通过。前端 `useCopilot.sendMessage(text, { incidentId })` 透传；`IncidentDetailPanel` 不再调用 `buildCopilotPrompt`，只发短意图 + incidentId，删 `sessionStorage` 中间态；`dashboard-client` 把 `incidentId` 灌进 `sendMessage` options。`npm run typecheck` 0 错误；`npm run build` 通过 (`/dashboard` 42.9 kB / First Load JS 190 kB)。运行日志：`docs/runs/2026-06-18-m3-05-incident-aware-copilot-contract.md`。
13. **M3-06 测试与安全质量门收口**已交付：M3-04 / M3-05 反复标记的"预存失败"已**全部清零**且不靠 skip/xfail/删除断言 —— `test_demo_alert_can_drive_copilot_fallback` 在 `test_demo_flow.py` 内 stub `GuardrailEngine.instance().check_input` 为 allow（与 `test_copilot_contract._stub_guardrails` 同模式），仅测试 no-key fallback 行为；`test_colang_flows.py` 9 个 benign 失败（httpx `ConnectError` / `LocalProtocolError` → fail-closed `moderation_unavailable`）的根因是测试夹具依赖真实 OpenAI / 网络，在 `server/tests/security/llm_guardrails/conftest.py` 增加 `_safe_moderation_for_colang` autouse fixture 把 `OpenAIModerationClient.check` 改为 pass-through fake（`staticmethod` 包装规避 self 绑定 TypeError），并同步修同 bug 的 `mock_openai_moderation_pass/block/fail` fixtures；SSRF 13/13 已稳定通过（M3-04 记录已过时，monkeypatch 命中 `_is_url_pointing_to_internal` 内部导入路径）。后端默认基线 `318 passed, 2 skipped`（0 失败），Guardrails 专项 `139 passed`（与 M2-06 一致），Demo Flow `5 passed`，SSRF `13 passed`，M3-03/M3-04/M3-05 回归矩阵 `72 passed`，前端 `npm run typecheck` 0 错误 + `npm run build` 通过（`/dashboard` 42.9 kB / 190 kB）。**生产安全策略不降级**：`GuardrailEngine._run_rails` fail-closed / `_l1_check` SSE error 净化（只暴露 category，不暴露 regex）/ SSRF 阻断（loopback / RFC1918 / link-local / metadata / multicast / reserved 全部维持）/ `audit` 脱敏（不写 secret / API key / 完整 note / payload / system prompt）全部保持原样；测试 stub 只在 `server/tests/` 目录，未触碰 `server/security/**` 任何生产代码。运行日志：`docs/runs/2026-06-18-m3-06-test-and-security-quality-gate-closure.md`。
14. **M3-07 案件证据报告导出**已交付：`GET /incidents/{incident_id}/report?format=json|markdown` 落地（`format=json` 返回 `{status, incident_id, filename, markdown, meta}` envelope；`format=markdown` 返回 `text/markdown` + `Content-Disposition`）；复用 M3-04 owner 隔离 + `incident_service.get_incident_detail`；非 owner / 不存在统一 404，不区分；invalid format 422；DB 失败 503。`server/services/incident_report_service.py` 纯函数 `sanitize_report_text` / `build_incident_report` 派生 Markdown 报告：固定 4 段结构（案件摘要 / 关联告警 / 案件时间线 / 安全与脱敏说明），限制 summary 1000 / alert summary 240 / payload preview 180 / event detail 240 / event note preview 160 / linked_alerts ≤ 20 / events ≤ 50 newest-first。脱敏复用 `logs_router._SENTINEL_PATTERNS` + 新增 `developer:` 触发；**报告正文不包含完整 raw payload / 完整 note / fake secret / system prompt / stack trace / Guardrails regex**；filename 只由 `incident_id` 派生，非法字符降级为 `_`。audit `Log(action="incident_report_export")` 仅在成功生成时写，detail 只含 `incident_id / format / alert_count / included_alerts / event_count / included_events / redaction_count`；非 owner / 不存在 / invalid format / DB 失败**不**写 success Log。前端 `IncidentDetailPanel` 事件时间线工具区加 `复制报告` / `下载报告` 按钮（`Clipboard` / `ClipboardCheck` / `Download` / `Loader2` icon；`data-testid="incident-copy-report" / "incident-download-report" / "incident-report-status"`），状态文案 `生成中 / 已复制 / 已下载 / 报告生成失败`；复制走 `navigator.clipboard.writeText`（不可用降级提示 `复制失败`），下载走 `Blob` + `URL.createObjectURL` + `anchor.click()`。前端不拼报告 / 不读 payload / note 全文。**不调用 LLM / 不引入 PDF/DOCX/外部渲染 / 不新增 schema / 不引入 env var / 不触碰 `server/security/**`**。后端 `pytest` `test_incident_report_export.py` 14 passed；后端全量 `332 passed, 2 skipped`（M3-06 baseline 318 + M3-07 新增 14；0 失败）；Guardrails 专项 `139 passed` 0 回归；前端 `npm run typecheck` 0 错误 + `npm run build` 通过（`/dashboard` 43.7 kB / First Load JS 191 kB）。运行日志：`docs/runs/2026-06-18-m3-07-incident-evidence-report-export.md`。
15. **M3-08 案件报告浏览器验收与 Agent 文档归档**已交付（**E2E dev 环境阻塞，按 M3-08 任务 §15 处理**）：`server/tests/test_incident_report_e2e.py` Playwright 真实浏览器 E2E 写好（`pytestmark = [pytest.mark.e2e]` + `@pytest.mark.e2e` 显式双层 marker，默认 `pytest server/tests` 跳过；`--run-e2e` 显式触发），覆盖：唯一邮箱 → 后端 API 预 register → UI login → 触发 Demo 攻击 → 点击告警 → 点击"从此告警创建案件" → 等待 `incident-detail-panel` → 点击"下载报告"（`accept_downloads=True` + `expect_download`） → 读取真实 markdown 文件 → 验证 4 段固定结构（`# 案件证据报告` / `## 1. 案件摘要` / `## 2. 关联告警` / `## 3. 案件时间线` / `## 4. 安全与脱敏说明`） + `payload_length` / `payload_preview` 字段 → 12 条 forbidden sentinel 脱敏断言（`sk-` / `sk-proj-` / `AKIA` / `ghp_` / `xox` / `PRIVATE KEY` / `Traceback` / `ignore previous instructions` / `disregard system prompt` / `forget instructions` / `system:` / `developer:`）→ 点击"复制报告" → 验证 `incident-report-status` 命中 `已复制` / `复制失败` / `报告生成失败` / `已下载` / `下载失败` 任一降级 marker → 整页 DOM 扫描 forbidden 文本。`accept_downloads=True` + `context.grant_permissions(["clipboard-read", "clipboard-write"], origin=BASE)`。M3-07 / M3-08 agent 任务文档归档入库；`UNATTENDED_LONG_TASKS.md` M3-08 条目 + 推荐启动口令更新为下一条 NEXT-01 工单。最小后端修复 1 行：`server/main.py:36-51` `from server.routers import (...)` 漏导 `incidents_router`（M3-04 commit 引入时的回归，本任务首次启动 dev server 触发 `NameError`），随本任务 commit 修复。
   - **E2E 阻塞摘要**：`--run-e2e` 显式触发时，E2E 在 dashboard 客户端 `wait_for_selector('[data-testid="trigger-demo-attack"]')` 45s 超时。根因：next-auth 5.0.0-beta.30 + Next.js 15 dev mode 下，`useSession()` 在 dashboard 客户端 `status` 永为 `loading`；`/api/auth/session` 客户端 fetch 返回 200 + user，但 React 状态不同步；`SYSTEM · LOADING` 60s 不消失。`test_demo_flow_e2e.py` 同样 fail 在 dashboard navigation（M3-08 之前未真跑过）。
   - **影响**：M3-04 / M3-05 / M3-07 报告导出 UI 实际**未**在真实浏览器中跑通；E2E 验收缺失。
   - **下一条工单**：NEXT-01（授权修改 `web-next/lib/auth.ts` / `web-next/app/providers.tsx` / 升级 `next-auth` / `Next.js` 解决 dev mode hydration 阻塞），独立工单不与 M3-08 任务边界冲突。
   - **质量门**：`pytest server/tests` 默认基线 332 passed, 3 skipped（M3-07 baseline 318 + M3-07 新增 14 + 1 E2E skip = 3 skip；0 失败）；`test_incident_report_export.py` 14 passed；Guardrails 专项 139 passed；前端 `npm run typecheck` 0 错误 + `npm run build` 通过（`/dashboard` 43.7 kB / First Load JS 191 kB）。运行日志：`docs/runs/2026-06-18-m3-08-incident-report-browser-e2e-and-agent-docs-catchup.md`。
16. **NEXT-01 next-auth 会话 loading 阻塞收口**已交付（2026-06-19）：`web-next/app/dashboard/page.tsx` 改为 Server Component，用 `auth()` + `redirect("/")` 决定放行，不再依赖客户端 `useSession()` 的 hydration；`web-next/app/layout.tsx` 在服务端调 `auth()` 把 session 透传给 `Providers`；`web-next/app/providers.tsx` 接受 `session?: Session | null` 并喂给 `<SessionProvider session=...>`。不升级 next-auth / next，不改后端 auth/security/Guardrails。新增 `server/tests/test_auth_session_e2e.py` 最小 E2E（注册 → UI 登录 + `/api/auth/callback/credentials` 兜底 → 等 dashboard URL → 断言 `trigger-demo-attack` 45s 内可见 / `SYSTEM · LOADING` 消失 / `/api/auth/session` 返回 user / DOM 无 sentinel）；M3-08 `test_incident_report_e2e.py` helper 同步加 callback 兜底 + 列表点击等待。`pytest server/tests/test_auth_session_e2e.py --run-e2e` 1 passed；`pytest server/tests/test_incident_report_e2e.py --run-e2e` 1 passed。运行日志：`docs/runs/2026-06-19-next-01-auth-session-loading-e2e-recovery.md`。
17. **NEXT-02 E2E 与 SSRF 质量门硬化**已交付（2026-06-19）：`server/tests/test_demo_flow_e2e.py` 的 `_register_via_ui` 重写为 NEXT-01 已验证路径——后端 API `/api/backend/auth/register`（409/"已存在"/"exists" 视为已存在）→ 等 `login-email` hydration + `login-submit` 可点击 → `/api/auth/csrf` + `/api/auth/callback/credentials` 直接种 httpOnly cookie → 点击 `login-submit` 兜底 → URL polling `window.location.pathname === '/dashboard'`，失败 fallback 显式 `page.goto("/dashboard")` 让服务端 `auth()` 决定接受/redirect；`pytestmark` 改成 `[pytest.mark.e2e]` 列表风格；`_wait_for_demo_button` timeout 从 15s 提到 45s。`server/tests/test_ssrf.py` 抽出 module 级 `allow_public_dns` fixture（monkeypatch `_is_url_pointing_to_internal -> False`）只在 `test_public_domain_ok` / `test_build_url_with_ssrf_check` / `test_build_url_strips_trailing_slash` / `test_build_url_with_subpath` 4 个公网域名测试上启用；新增 `test_allow_public_dns_fixture_does_not_bypass_literal_internal_ip` 双保险，确认 fixture 启用时 literal IP 仍走生产阻断；保留 `test_loopback_blocked` / `test_private_ip_blocked` / `test_link_local_blocked` / `test_cloud_metadata_blocked` / `test_build_url_rejects_internal` / `test_multicast_blocked` / `test_reserved_blocked` / `test_build_url_rejects_empty` / `test_empty_hostname` 不加 fixture。**未改**生产 `server/analyzer.py` / `server/core/utils.py` SSRF 逻辑，未改 `web-next/app/{dashboard,layout,providers}` / 后端认证/Guardrails/数据库/部署。Copilot fallback `API Key`/`Base URL`、triage `data-triage-status="investigating"`、DOM forbidden sentinel 断言全部保留。**真实验证**：`pytest server/tests/test_demo_flow_e2e.py --run-e2e` 1 passed (`registered/demo/copilot/triage` 全部 True / `forbidden=None`)；`pytest server/tests/test_auth_session_e2e.py --run-e2e` 1 passed；`pytest server/tests/test_incident_report_e2e.py --run-e2e` 1 passed (`copy_status='已复制'`)；`pytest server/tests/test_ssrf.py` 14 passed（13 原 + 1 新增保护测试，正常解开本地 DNS 环境失败）；`pytest server/tests` 333 passed, 4 skipped（4 个 e2e 默认 skip）；Guardrails 139 passed；前端 `npm run typecheck` 0 错误 + `npm run build` 通过（`/dashboard` 43.4 kB / First Load JS 191 kB）。运行日志：`docs/runs/2026-06-19-next-02-e2e-and-ssrf-quality-gate-hardening.md`。
18. **M3-09 案件状态单一事实源与 E2E 韧性**已交付（2026-06-19）：`useIncidents()` 提升到 `dashboard-client.tsx` 父层并传给 `IncidentSection`，案件列表 / selected / detail / report 共享同一 state；`IncidentSection` 不再创建第二个 `useIncidents()` 实例；`server/tests/e2e_helpers.py` 复用注册、NextAuth callback、稳定账号 fallback，三条 E2E 连续运行不再依赖重启 dev server。真实验证：E2E helper 9 passed；Auth/Demo/Incident 三条 E2E 连续 `3 passed`；后端全量 `342 passed, 4 skipped`；Guardrails `139 passed`；前端 typecheck/build 通过（`/dashboard` 43.4 kB / 191 kB）。运行日志：`docs/runs/2026-06-19-m3-09-incident-state-and-e2e-resilience.md`。
19. **M3-10 Dashboard route composition**已交付（2026-06-19）：新增 `web-next/constants/dashboardRoutes.ts` 作为 `overview / monitor / incidents / waf / ai / report` 的单一路由元数据；`SystemStatusBar.tsx` 桌面与移动导航恢复 `incidents` 一等入口并补 `data-testid` / `data-dashboard-route` / `aria-current`；`dashboard-client.tsx` 从 840 行降到 406 行，只保留业务 hook/controller、handler 与 route 组合；route JSX 拆到 `SectionHeading`、`DashboardFields`、`DashboardRows` 和 `web-next/components/dashboard/sections/*.tsx`。新增 `server/tests/test_dashboard_route_sections_e2e.py`，先跑出目标 RED，再 GREEN 锁住六个 route tab 与核心 section wrapper。真实验证：Dashboard route E2E `1 passed`；Auth/Demo/Incident/Dashboard 四条连续 E2E `4 passed`；后端全量 `342 passed, 5 skipped, 17 warnings`；Guardrails `139 passed, 17 warnings`；前端 typecheck/build 通过（`/dashboard` 44 kB / 191 kB）。未改认证/授权、Guardrails、SSRF、DB schema、后端 API 或 npm 依赖。运行日志：`docs/runs/2026-06-19-m3-10-dashboard-route-composition.md`。
20. **M3-11 Dashboard section 响应式 QA 与可访问性收口**已交付（2026-06-19）：新增 `server/tests/test_dashboard_responsive_e2e.py`（默认 skip，需 `--run-e2e`），覆盖桌面 1366×900 与移动 390×844 viewport 下六个 Dashboard route（`overview / monitor / incidents / waf / ai / report`）、`aria-current=page`、核心 section wrapper、整页横向溢出（`scrollWidth ≤ clientWidth + 4`）、按钮文字溢出、icon-only 按钮 `title` / `aria-label`、键盘 Tab+Enter 切换路由以及 DOM forbidden sentinel（`sk-...` / `AKIA...` / `ghp_...` / `Traceback` / `ignore previous instructions` / `system:` / `developer:` / `PRIVATE KEY` 等）。RED 暴露 `SystemStatusBar.tsx` 主题切换按钮（`Moon` / `Sun`）与 `CopilotPanel.tsx` Copilot 提交按钮（`Send` icon）属于 icon-only 但缺 `title` / `aria-label`，GREEN 仅在 `SystemStatusBar.tsx`（顺手把 Bell / LogOut 已有 `title` 的按钮补上 `aria-label`）和 `CopilotPanel.tsx` 加 `title` + `aria-label`，未改业务语义。截图证据保留 `docs/runs/artifacts/m3-11-dashboard-responsive/desktop-overview.png` / `desktop-incidents.png` / `mobile-overview.png` / `mobile-incidents.png`，共 168 KB。**真实验证**：Responsive E2E `2 passed in 17.40s`（桌面 + 移动）；M3-10 Dashboard route E2E `1 passed`；Auth / Demo / Incident / Dashboard route / Dashboard responsive 五条 E2E 连续 `6 passed in 46.64s`（重启 backend 清空 register rate limit 后）；后端全量 `342 passed, 7 skipped, 17 warnings`；Guardrails `139 passed`；前端 `npm run typecheck` 0 错误 + `npm run build` 通过（`/dashboard` 44 kB / First Load JS 191 kB）。**未改**认证/授权、Guardrails、SSRF、DB schema、后端 API 或 npm 依赖；未把 token 写进 `localStorage` / `sessionStorage` / DOM；未提交 `.coverage` / 真实 env / 数据库 / 密钥。运行日志：`docs/runs/2026-06-19-m3-11-dashboard-section-responsive-qa.md`。
21. **M3-12 Demo Flow E2E 稳定性收口**已交付（2026-06-19）：新增 `server/tests/e2e_copilot_helpers.py` 提供 sanitized 诊断 helper（`ARTIFACT_DIR=docs/runs/artifacts/m3-12-demo-flow-stability` + sk-/AKIA/ghp_/xox- 正则脱敏 + `wait_for_copilot_fallback_message` 通过 `page.wait_for_function` 在 DOM 内扫 `[data-testid="copilot-message"][data-role="assistant"]` 是否含 `API Key`/`Base URL`、默认 45s + `install_network_diagnostics` 仅记录 `/api/backend/{copilot/stream,alerts/demo,health}` 与 `/api/auth/session` 的 method/path/status + `save_copilot_failure_artifacts` 失败时 full-page screenshot + sanitized JSON）；修改 `server/tests/test_demo_flow_e2e.py` 把 30×500ms 手写轮询替换为 `wait_for_copilot_fallback_message(page, timeout_ms=45000)` + 失败 artifact 落盘，保留 `assert "API Key" in assistant_text or "Base URL" in assistant_text` 严格断言；新增 `server/tests/test_demo_flow_stability_e2e.py` 同一 chromium context + page 连续两次 `trigger-demo-attack → analyze-current-alert → wait_for_copilot_fallback_message`，第二次 `attack-log-row` 数量 ≥ 2，整体跑完做 forbidden sentinel 扫描。**真实验证**：单条 Demo Flow E2E ×3 不重启 backend 全部 passed（10.38s/10.53s/10.51s）；Stability ×2 不重启 backend 全部 passed（10.28s/6.63s）；六组关键 E2E 连续（Auth / Demo / Incident / Route / Responsive / Stability）`7 passed in 58.27s`；后端全量 `342 passed, 8 skipped, 17 warnings`；Guardrails `139 passed`；前端 `npm run typecheck` 0 错误 + `npm run build` 通过（`/dashboard` 44 kB / First Load JS 191 kB 不变）。**根因排查**：本机环境 `curl https://api.openai.com` exit 28（5s 超时不可达）；fresh backend 时 `GuardrailEngine.check_input` 1.5s rail timeout 优先于 `OpenAIModerationClient` 5s ConnectTimeout 触发 → return None → 放行 Copilot；长时运行 backend 中 moderation httpx pool 退化后 < 1.5s 立即抛 exc → fail-closed 拦截 Copilot；本任务在 fresh backend 状态下行为正确，未动 Guardrails 代码。**未改**认证/授权、Guardrails、SSRF、DB schema、后端 API、npm 依赖、`REGISTER_RATE_LIMIT_*` / `COPILOT_RATE_LIMIT_*` 常量；未把 token 写进 `localStorage` / `sessionStorage` / DOM；未提交 `.coverage` / 真实 env / 数据库 / 密钥。运行日志：`docs/runs/2026-06-19-m3-12-demo-flow-e2e-stability.md`。
22. **M3-13 Dashboard 移动视觉 QA 收口**已交付（2026-06-19）：新增 `server/tests/test_dashboard_mobile_visual_e2e.py`，覆盖 390×844 与 430×932 下 `overview` / `incidents` 的 stats 卡片密度、section 间距、移动 nav active tab 可见性、整页横向溢出、forbidden sentinel 和圆形 `N` 浮层 DOM 来源判断，并保存 `docs/runs/artifacts/m3-13-dashboard-mobile-visual/{mobile-390,mobile-430}-{overview,incidents}.png` 4 张截图。轻量修复仅限 `StatsCards.tsx`、`SystemStatusBar.tsx`、`DashboardBriefingSection.tsx`、`DashboardIncidentWorkspaceSection.tsx` 的 Tailwind/layout class：移动端 stats padding/高度/文字换行收口、mobile nav gap/tracking/横向滚动体验收紧、overview/incidents section 顶距改为 `mt-8 sm:mt-14`。`N` 浮层截图可见但 DOM 候选 count 为 0，判定为浏览器/外部 overlay，不改应用代码。**真实验证**：移动视觉 E2E `1 passed in 13.82s`；M3-11 responsive E2E `2 passed in 20.08s`；M3-12 Demo stability E2E `1 passed in 6.32s`；七组关键 E2E 连续 `8 passed in 69.21s`；后端全量 `342 passed, 9 skipped, 17 warnings`；Guardrails `139 passed, 17 warnings`；前端 typecheck/build 通过（`/dashboard` 44.1 kB / First Load JS 191 kB）。**未改**认证/授权、Guardrails、SSRF、DB schema、后端 API、npm 依赖或 rate limit 常量；未提交 `.coverage` / 真实 env / 数据库 / 密钥。运行日志：`docs/runs/2026-06-19-m3-13-dashboard-mobile-visual-qa.md`。
23. **M3-14 案件报告预览 UX 收口**已交付（2026-06-20）：新增 `web-next/components/dashboard/IncidentReportPreview.tsx`，在案件详情时间线工具区补 `预览报告` 内联入口，展示后端已脱敏报告的文件名、告警/事件/脱敏/截断 meta、四段报告结构、`payload_preview` 片段和安全说明；`IncidentDetailPanel.tsx` 复用现有 `onLoadReport()`，只保存截断后的 `previewMarkdown`、`filename`、`meta` 与 `loadedAt` 到组件 state，复制/下载仍重新拉取完整脱敏报告，不把报告 markdown 写进 `localStorage` / `sessionStorage`，不使用 `dangerouslySetInnerHTML` / `innerHTML`。新增 `server/tests/test_incident_report_preview_e2e.py`，真实浏览器覆盖登录 → Demo 告警 → 创建案件 → 预览报告 → 桌面/移动截图 → 复制/下载回归 → Escape/关闭按钮 → DOM/markdown forbidden sentinel。截图证据：`docs/runs/artifacts/m3-14-incident-report-preview/incident-report-preview-desktop.png` / `incident-report-preview-mobile.png`。**真实验证**：新增 preview E2E `1 passed in 10.34s`；既有 incident report E2E `1 passed in 6.12s`；mobile visual E2E `1 passed in 12.09s`；八组关键 E2E 最终 `9 passed in 77.63s`；后端全量 `342 passed, 10 skipped, 17 warnings`；Guardrails `139 passed, 17 warnings`；前端 typecheck 通过，build 通过（`/dashboard` 45.7 kB / First Load JS 193 kB）。**未改**认证/授权、Guardrails、SSRF、DB schema、后端 report API、npm 依赖或 rate limit 常量；未提交 `.coverage` / 真实 env / 数据库 / 密钥。运行日志：`docs/runs/2026-06-19-m3-14-incident-report-preview-ux.md`。
24. **M3-15 SOC 时间线筛选与详情展开 UX 收口**已交付（2026-06-20）：`SecurityTimelinePanel.tsx` 增加 `全部 / Demo / Copilot / 护栏 / 系统` 筛选、筛选计数、单条事件展开详情、Escape 收起和脱敏 SOC 摘要复制；详情只展示时间、来源、类别、状态、脱敏摘要和安全说明，不写 `localStorage` / `sessionStorage`，不使用 `dangerouslySetInnerHTML` / `innerHTML`。新增 `server/tests/test_security_timeline_drilldown_e2e.py`，真实浏览器覆盖登录、Demo 时间线事件、筛选、展开详情、复制摘要、桌面/移动截图和 DOM/copy forbidden sentinel。截图证据：`docs/runs/artifacts/m3-15-soc-timeline-drilldown/security-timeline-desktop.png` / `security-timeline-mobile.png`。**真实验证**：新增 timeline drilldown E2E `1 passed in 18.51s`；后端 timeline 契约 `12 passed in 2.88s`；Dashboard responsive E2E `2 passed in 30.06s`；九组关键 E2E 最终 `10 passed in 144.89s`；后端全量 `342 passed, 11 skipped, 17 warnings`；Guardrails `139 passed, 17 warnings`；前端 typecheck 通过，build 通过（`/dashboard` 47.1 kB / First Load JS 194 kB）。**未改**认证/授权、Guardrails、SSRF、DB schema、后端 timeline API、npm 依赖或 rate limit 常量；未提交 `.coverage` / 真实 env / 数据库 / 密钥。运行日志：`docs/runs/2026-06-20-m3-15-soc-timeline-drilldown-filter-ux.md`。
25. **M3-16 Dashboard Operational Runbook / Health Checklist UX 收口**已交付（2026-06-21）：新增 `OperationalRunbookPanel.tsx`，在 Dashboard 概览与 `WAF 管理` route 的系统状态区块内展示后端健康、Next API proxy 探针、登录会话、Demo readiness、E2E readiness 与 env security check 六项检查；登录身份只显示脱敏邮箱，命令只作为人工执行清单展示，复制摘要只包含安全诊断字段，不读真实 env、不执行浏览器侧脚本、不写 `localStorage` / `sessionStorage`，不使用 `dangerouslySetInnerHTML`。新增 `server/tests/test_dashboard_operational_runbook_e2e.py`，真实浏览器覆盖面板、六项 checklist、五条关键命令、复制状态、桌面/移动截图和 DOM/copy forbidden sentinel；并增强 `server/tests/e2e_helpers.py` 的测试侧稳定账号 env 复用，避免长串 E2E 被本地注册限流误挡，不改后端 rate limit。截图证据：`docs/runs/artifacts/m3-16-dashboard-operational-runbook/operational-runbook-desktop.png` / `operational-runbook-mobile.png`。**真实验证**：新增 runbook E2E `1 passed in 3.67s`；Dashboard route + responsive E2E `3 passed in 25.42s`；关键 E2E 串跑最终 `11 passed in 80.00s`；后端 timeline 专项 `12 passed in 1.03s`；后端全量 `344 passed, 12 skipped, 17 warnings`；Guardrails `139 passed, 17 warnings`；前端 `npm run typecheck` 与 `npm run build` 通过（`/dashboard` 49.2 kB / First Load JS 197 kB）。**未改**认证/授权、Guardrails、SSRF、DB schema、后端 API、npm 依赖或生产 rate limit；未提交 `.coverage` / 真实 env / 数据库 / 密钥。运行日志：`docs/runs/2026-06-21-m3-16-dashboard-operational-runbook-health-checklist-ux.md`。
26. **M3-17 Incident / Alert Evidence Pack Checklist UX 收口**已交付（2026-06-21）：新增 `IncidentEvidencePackChecklist.tsx`，在案件详情的关联告警与事件时间线之间展示只读证据包清单，覆盖报告可生成、关联告警、案件时间线、研判覆盖、脱敏/截断状态和缺失项六类检查；面板只通过既有 `onLoadReport(incidentId)` 读取报告 `filename/meta`，不保存报告 markdown，并提供不含 payload / secret / 原始 timeline note 的安全证据包摘要复制。`IncidentDetailPanel.tsx` 仅挂载该面板并复用现有 incident detail、linked alerts、events 与 report loader。新增 `server/tests/test_incident_evidence_pack_checklist_e2e.py`，真实浏览器覆盖登录、Demo 告警、创建案件、证据包 checklist、报告 meta 刷新、复制摘要、下载 markdown、桌面/移动截图和 DOM/clipboard/markdown forbidden sentinel。截图证据：`docs/runs/artifacts/m3-17-incident-alert-evidence-pack-checklist/evidence-pack-desktop.png` / `evidence-pack-mobile.png`。**真实验证**：新增 evidence pack E2E `1 passed in 9.26s`；既有 incident report / preview / security timeline / Dashboard responsive E2E `5 passed in 37.49s`；关键 E2E 串跑最终 `12 passed in 104.30s`；后端全量 `344 passed, 13 skipped, 17 warnings`；Guardrails `139 passed, 17 warnings`；前端 `npm run typecheck` 与 `npm run build` 通过（`/dashboard` 51.5 kB / First Load JS 199 kB）。**未改**认证/授权、Guardrails、SSRF、DB schema、后端 incident/report API、npm 依赖或 rate limit；未调用 LLM；未使用 `localStorage` / `sessionStorage` / `dangerouslySetInnerHTML` / `innerHTML`；未提交 `.coverage` / 真实 env / 数据库 / 密钥。运行日志：`docs/runs/2026-06-21-m3-17-incident-alert-evidence-pack-checklist-ux.md`。
27. **M3-18 Incident Closure / Post-Incident Review Checklist UX 收口**已交付（2026-06-21）：新增 `IncidentClosureReviewChecklist.tsx`，在案件详情中放在 Evidence Pack Checklist 之后、事件时间线之前，展示只读关闭前复盘清单，覆盖状态可复核、证据包基础材料、报告元信息、关联告警、研判覆盖、时间线事件、复盘备注和关闭缺失项；面板只从既有 incident detail、linked alerts、events 和 `onLoadReport(incidentId)` 返回的 `filename/meta` 推导，不保存完整报告 markdown，不自动关闭案件，不改变 `closed_at` 语义，并提供不含 payload / note 正文 / secret / 报告正文的 Closure Review 摘要复制。新增 `server/tests/test_incident_closure_review_checklist_e2e.py`，真实浏览器覆盖登录、Demo 告警、创建案件、M3-17 evidence checklist 仍可见、closure checklist、报告 meta 刷新、复制摘要、保存 `contained` + 复盘备注后仍不自动关闭、下载 markdown 回归、桌面/移动截图和 DOM/clipboard/markdown forbidden sentinel。截图证据：`docs/runs/artifacts/m3-18-incident-closure-post-incident-review-checklist/closure-review-desktop.png` / `closure-review-mobile.png`。**真实验证**：新增 closure E2E `1 passed in 12.07s`；M3-17 evidence pack + incident report + preview + security timeline + Dashboard responsive E2E `6 passed in 52.10s`；关键 E2E 串跑最终 `13 passed in 99.18s`；后端 timeline 专项 `12 passed in 1.13s`；后端全量 `344 passed, 14 skipped, 17 warnings`；Guardrails `139 passed, 17 warnings`；前端 `npm run typecheck` 与 `npm run build` 通过（`/dashboard` 53.4 kB / First Load JS 201 kB）。**未改**认证/授权、Guardrails、SSRF、DB schema、后端 incident/report API、npm 依赖或 rate limit；未调用 LLM；未使用 `localStorage` / `sessionStorage` / `dangerouslySetInnerHTML` / `innerHTML`；未提交 `.coverage` / 真实 env / 数据库 / 密钥。运行日志：`docs/runs/2026-06-21-m3-18-incident-closure-post-incident-review-checklist-ux.md`。
28. **M3-19 Closed Incident Archive / Status Filter UX 收口**已交付（2026-06-21）：新增 `IncidentStatusFilterBar.tsx`，在案件列表上方提供 `全部 / 活跃 / 已开启 / 调查中 / 已遏制 / 已解决 / 误报 / 已关闭归档` 八类筛选；`IncidentSection.tsx` 复用既有 `GET /incidents?status=` 单状态接口，前端聚合 `active` 与 `closed` 复合筛选，并用 request sequence + `AbortController` 避免筛选 race；筛选后当前 selected 不在列表中会清空详情，防止 stale incident。`IncidentList.tsx` 新增关闭态归档模式，关闭态列表项结构化展示 `incident-closed-at` 与状态 badge，活跃列表保留更新时间；筛选 state 只在 React 内存中，不写 `localStorage` / `sessionStorage`。新增 `server/tests/test_incident_status_filter_archive_e2e.py`，真实浏览器覆盖登录、Demo 告警、创建 open / contained / resolved / false_positive 样本、八组筛选、关闭归档 `closed_at` 可见、关闭态详情仍显示 M3-18 closure checklist、刷新后筛选回到默认、桌面/移动截图和 DOM/storage forbidden sentinel。截图证据：`docs/runs/artifacts/m3-19-closed-incident-archive-status-filter/status-filter-desktop.png` / `status-filter-mobile.png`。**真实验证**：新增 status filter E2E `1 passed in 19.95s`；M3-18 closure + M3-17 evidence pack E2E `2 passed in 10.63s`；incident report + preview + Dashboard responsive E2E `4 passed in 26.91s`；后端 incident 契约 `17 passed`；关键 E2E 串跑首轮 `10 passed / 4 setup failures` 后重启本地 dev server 复跑失败项 `4 passed in 36.88s`；后端全量 `344 passed, 15 skipped, 17 warnings`；Guardrails `139 passed, 17 warnings`；前端 `npm run typecheck` 与 `npm run build` 通过（`/dashboard` 55 kB / First Load JS 202 kB）。**未改**认证/授权、Guardrails、SSRF、DB schema、后端 incident/report API、npm 依赖、rate limit 或 `closed_at` 语义；未自动关闭案件；未调用 LLM；未使用 `dangerouslySetInnerHTML` / `innerHTML`；未提交 `.coverage` / 真实 env / 数据库 / 密钥。运行日志：`docs/runs/2026-06-21-m3-19-closed-incident-archive-status-filter-ux.md`。
29. **M3-20 Incident Workbench Bulk Selection / Export Queue UX 收口**已交付（2026-06-22）：新增 `IncidentBulkActionBar.tsx`、`IncidentExportQueuePanel.tsx` 与 `incidentBulkActions.ts`，在案件列表中提供当前筛选多选、全选当前列表、清空选择、批量复制安全摘要和前端内存级导出队列提示；`IncidentList.tsx` 为列表项补 sibling checkbox，点击 checkbox 不打开详情；`IncidentSection.tsx` 只用 React state 保存 `selectedIncidentIds` / `exportQueue`，筛选或列表刷新时清理 stale selection，队列去重并限制最多 25 项。安全摘要只包含 incident id、状态、严重度、告警数、更新时间、`closed_at` 是否存在与 title length，不包含 title 正文、summary、payload、note、报告 markdown、secret 或 stack trace。新增 `server/tests/test_incident_bulk_selection_export_queue_e2e.py`，真实浏览器覆盖 open / contained / resolved 样本、多选、全选、清空、复制摘要、导出队列、筛选切换清理、checkbox 不打开详情、详情打开回归、刷新后不从 storage 恢复、桌面/移动截图和 DOM/clipboard/storage forbidden sentinel。截图证据：`docs/runs/artifacts/m3-20-incident-workbench-bulk-selection-export-queue/bulk-selection-desktop.png` / `bulk-selection-mobile.png`。**真实验证**：新增 bulk selection E2E `1 passed in 19.56s`；相邻案件 UX + Dashboard responsive 回归 `7 passed in 74.98s`；关键 E2E 串跑最终 `15 passed in 145.85s`；后端 incident 契约 `17 passed in 3.12s`；后端全量 `344 passed, 16 skipped, 17 warnings`；Guardrails `139 passed, 17 warnings`；前端 `npm run typecheck` 与 `npm run build` 通过（`/dashboard` 57.1 kB / First Load JS 204 kB）。**未改**认证/授权、Guardrails、SSRF、DB schema、后端 incident/report API、npm 依赖、rate limit 或导出格式；未自动关闭/删除/批量修改案件；未调用 LLM；未使用 `localStorage` / `sessionStorage` / `dangerouslySetInnerHTML` / `innerHTML`；未提交 `.coverage` / 真实 env / 数据库 / 密钥。运行日志：`docs/runs/2026-06-22-m3-20-incident-workbench-bulk-selection-export-queue-ux.md`。

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
4. 已完成：统一数据库配置和 Alembic 迁移策略，替代启动时手写 ALTER TABLE。M2-01 已建立 Alembic baseline（`d9af4388f20a_baseline_schema.py`），`DATABASE_URL` 真正成为 engine 事实来源；旧 `ensure_user_config_columns()` 保留为 legacy 兼容层并被显式标注。PostgreSQL 端到端验收留给 M2-07。
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
5. **M3-02 告警研判与处置工作台**：在 Dashboard 中选中告警后可推进到“研判中 / 已遏制 / 误报 / 已解决”状态，记录处置备注，复制含研判状态的事件报告，并为每次状态变化留下可审计记录。
6. **M3-03 告警研判持久化与历史**：把 M3-02 的内存状态升级为数据库持久化 + 可查询历史 + 重启恢复；`GET /alerts` 在清空进程 backlog 后仍可从 `alert_records` 恢复；`GET /alerts/{alert_id}/triage/history` 返回 owner 隔离的 newest-first 变更事件。
7. **M3-10 Dashboard route composition**：Dashboard 父层只保留业务 hook/controller 与跨区块 handler；route section 组件只接收 props 渲染 UI；`SystemStatusBar` 与父层共享单一路由元数据；`incidents` 在桌面/移动顶部导航中是一等入口。

验收：

- 关键路径在桌面和移动端无布局错乱。
- UI 改动必须经过浏览器截图或手动验证说明。
- 不把营销落地页当作产品首页，第一屏必须可操作。
- M3-02 验收：`PATCH /alerts/{alert_id}/triage` 必须使用 `require_auth_user`；非 owner / 不存在统一返回 404；`analyst_note` 上限 800 字符；`Log(action="alert_triage_update")` 写入脱敏摘要；前端 `alert-triage-panel` / `triage-status-*` / `triage-save` / `triage-status-badge` / `triage-row-badge` 全部可用；简报“待研判 / 已闭环”计数必须从真实 alert triage 派生。
- M3-03 验收：必须在临时 SQLite + 新 SQLAlchemy engine（同一 DB 文件）下验证 `GET /alerts` 在清空 `app_state.alert.backlog` 后仍能恢复；`alert_records.triage_status` 与 `alert_triage_events` 由 `PATCH /alerts/{alert_id}/triage` 写入；`GET /alerts/{alert_id}/triage/history?limit=50` 仅 owner 可见，非 owner 404；`analyst_note` 仍 800 字符上限；`Log` 仍只写脱敏摘要；Alembic migration `d33d40488e0f` 必须能 `upgrade head` 与 `downgrade base`；前端 `AlertTriageHistory` 在保存成功后自动刷新（`historyRefreshKey` 自增）。
- M3-04 验收：所有 incident 端点必须 `require_auth_user`；非 owner / 不存在统一 404，不通过 403 暴露存在性；`POST /incidents` 携带 `alert_id` 时自动 link 该 alert 并写 `created` + `alert_linked` 事件；`resolved / false_positive` 自动设 `closed_at`、改回打开态清空；`POST /incidents/{id}/alerts` 重复 link 幂等(不重复写 active link / `IncidentEvent` / Log);`DELETE /incidents/{id}/alerts/{alert_id}` 软删除 link 不删 `alert_records`;`Log(action=incident_*)` 全部脱敏;`IncidentEvent.note` 可由 owner API 看到但 `Log.detail` 不含完整 note;Al embic migration `4f3c9a1d8b7e` 必须能 `upgrade head` / `downgrade base`;案件在清空 `app_state.alert.backlog` + 新建 engine 后仍能从 DB 恢复;前端 `IncidentSection` / `IncidentList` / `IncidentDetailPanel` / `IncidentTimeline` / `IncidentLinkedAlerts` + `RouteKey="incidents"` 全部可用;Copilot 案件摘要走前端拼接消息模板,只含 incident id / title / severity / status / 关联告警数 / 最多 5 条告警摘要 + 四段式输出要求,不含 secret / system prompt / stack trace。
- M3-07 验收：`GET /incidents/{id}/report?format=json|markdown` 可用;owner 可生成报告;非 owner / 不存在统一 404,不区分;invalid format 422;DB 失败 503;filename 只由 incident_id 派生,绝不包含 title(防注入 + 防 title 泄密);报告**不**含完整 raw payload / 完整 note / fake secret / system prompt / stack trace / Guardrails regex(只放 `payload_length` + 截断 preview,`note_length` + 截断 preview);截断限制:summary 1000 / alert summary 240 / payload preview 180 / event detail 240 / event note preview 160 / linked_alerts ≤ 20 / events ≤ 50 newest-first;大案件截断行为有测试 (`test_report_truncates_alerts_and_events`);audit `Log(action="incident_report_export")` 仅在成功生成时写,detail 只含 `incident_id / format / alert_count / included_alerts / event_count / included_events / redaction_count`,**不**含 title / summary / payload / note / markdown 全文;非 owner / 不存在 / invalid format / DB 失败**不**写 success Log;前端 `IncidentDetailPanel` `复制报告` / `下载报告` 按钮 + 状态文案 + `navigator.clipboard` 降级 + `Blob` 下载,前端不拼报告 / 不读 payload / note 全文;**不调用 LLM / 不引入 PDF/DOCX/外部渲染 / 不新增 schema / 不引入 env var / 不触碰 `server/security/**`**;后端 `pytest server/tests/test_incident_report_export.py` 14 passed;后端 `pytest server/tests` 全量 332 passed, 2 skipped;Guardrails 专项 139 passed 0 回归;前端 `npm run typecheck` 0 错误 + `npm run build` 通过。
- M3-10 验收：`server/tests/test_dashboard_route_sections_e2e.py --run-e2e` 必须覆盖六个 route tab 与核心 section wrapper；`SystemStatusBar` 桌面/移动导航必须包含 `incidents`；`dashboard-client.tsx` 不再承载大段 route JSX，父层继续持有业务 hook/controller，section 内不得重新创建 `useIncidents()` / `useAlerts()` 等业务 hook；Auth/Demo/Incident/Dashboard 四条连续 E2E、后端全量、Guardrails、前端 typecheck/build 必须通过。

M3-03 当前实现边界（重要）：

- 研判状态以 `alert_records` 为事实来源；内存 `app_state.alert.backlog` 仍作为 WebSocket 实时推送缓存与 worker 短期缓存。
- 跨进程实例与跨多副本部署已可共享（共用同一 DB 即可），跨重启完全恢复。
- alert payload / LLM analysis JSON 存 `Text` 列（`json.dumps(..., ensure_ascii=False)`），不依赖 PostgreSQL JSONB；SQLite 测试库与 Compose PostgreSQL 走同一份代码。
- `analyst_note` 在 DB 中保留全文（800 字上限），但通过认证 API 私有返回给 owner；`Log` 审计与时间线仍只记录脱敏摘要（`status=...` / `disposition=...` / `note_length=...` / `source_ip=...`），不写完整 note / payload / secret。
- 当前不做：完整工单系统、SLA、负责人分派、批量处置、通知升级、Jira/Slack 集成；M3-02 的简报分桶语义不变。

M3-04 当前实现边界（重要）：

- `incidents` / `incident_alert_links` / `incident_events` 是案件事实来源；`Log(action=incident_create / incident_update / incident_alert_link / incident_alert_unlink)` 仍只写脱敏摘要（`incident_id=...` / `changed=...` / `status=A->B` / `severity=A->B` / `note_length=...` / `alert_id=...`），不写完整 note / payload / secret / stack trace。
- `IncidentEvent.note` 在 DB 中以全文保存（1000 字上限），但只通过 owner API 私有返回给 owner；`Log` 审计与时间线仍不写完整 note。
- `closed_at` 行为：进入 `resolved / false_positive` 时自动设置；从这两态改回 `open / investigating / contained` 时清空；两个关闭态之间互转保持 `closed_at`（不重置）。
- 重复 link 幂等：同一 `(incident_record_id, alert_record_id)` 已有 active link 时不重复写 active link、不写新 `IncidentEvent(alert_linked)`、不写新 Log；这是任务文档 §4 推荐行为，由 `test_post_incident_alert_idempotent_for_duplicate_link` 锁定。
- 前端 `AlertDetailPanel` 提供"从此告警创建案件"按钮，按 `riskLevel` 映射到 incident severity；Copilot 案件摘要走前端拼接（`buildCopilotPrompt`），不走后端 incident-aware contract；后续 M3-05 再做后端 incident-aware Copilot 上下文。
- 当前不做：多租户分派、SLA 计时、Jira/Slack 集成、批量选择 / 拖拽 / 多选表格、通知升级、负责人协作权限（`assignee_user_id` 仅作 owner 自身默认值预留）。

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
| M3-03 alert JSON 存储策略 | 中 | 当前 raw alert / LLM analysis 走 `Text` + `json.dumps`，不依赖 PostgreSQL JSONB；后续若升级到 JSONB 索引搜索，必须先做 RFC 评估 |

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
