# Run: M0-01 修复 README 与关键文档乱码，重写小白启动说明

开始时间：2026-06-15
运行模式：L1，无人值守
预算：最长 2 小时；同一个失败最多修复 3 轮；diff 超过约 800 行时停止总结，纯文档改动除外

## 目标

- 让一个新手能读懂 AI-CyberSentinel 是什么、如何启动、如何验证当前项目状态。

## 范围

允许修改：
- `README.md`
- `server/STRUCTURE.md`
- `docs/ALEMBIC_MIGRATION.md`
- `docs/RELEASE_NOTES.md`
- `docs/runs/**`

禁止修改：
- 真实 `.env`
- git 历史
- 认证、授权、安全护栏、数据库 schema
- 部署配置、push、merge、生产配置
- 业务代码，除非只是修文档引用路径

## 计划

- [x] 阶段 1：盘点当前文档、入口文件、启动脚本和验证命令。
- [x] 阶段 2：重写 `README.md`，补齐新手启动、验证和已知限制。
- [x] 阶段 3：修订 `server/STRUCTURE.md`、`docs/ALEMBIC_MIGRATION.md`、`docs/RELEASE_NOTES.md` 的可读性和事实口径。
- [x] 阶段 4：检查文档可读性、命令一致性、链接和 diff 范围。

## 阶段记录

### 阶段 1：盘点当前文档与事实

改动：
- 创建本运行日志。

验证：
- 已读取 `PRODUCT.md`、`AGENTS.md`、`CLAUDE.md`、`docs/agent/UNATTENDED_LONG_TASKS.md`。
- 已读取 `README.md`、`server/STRUCTURE.md`、`docs/ALEMBIC_MIGRATION.md`、`docs/RELEASE_NOTES.md`。
- 已读取 `.env.example`、`requirements.txt`、`web-next/package.json`、`server/main.py`、`server/core/config.py`。

结果：
- PowerShell 默认编码读取会显示乱码；使用 `-Encoding UTF8` 后，README 和关键 docs 当前内容可读。
- README 的项目结构、技术栈和启动说明存在过时或过宽泛的描述，需要改成当前仓库可验证口径。
- 当前前端命令位于 `web-next/`，脚本包括 `npm run typecheck`、`npm run build`、`npm run dev`。
- 当前后端入口为 `server.main:app`，启动前必须配置非默认 `APP_SECRET` 和 `AUTH_SECRET`。

下一步：
- 重写 README 的入口说明，保留已验证事实，不确定内容标为“待确认”。

### 阶段 2：重写 README 新手启动

改动：
- 重写 `README.md`。
- 将项目说明聚焦为 IDS / WAF / SOC Copilot 闭环。
- 增加本地开发启动步骤：后端虚拟环境、根 `.env`、前端 `.env.local`、启动命令、健康检查。
- 增加当前验证基线：前端 typecheck/build、后端非 E2E pytest、Guardrails pytest。
- 将 Docker Compose 路径标注为“待确认”，避免新手把未验证接线当作首选路径。

验证：
- 核对 `web-next/package.json`：存在 `dev`、`build`、`typecheck`，没有 `lint`。
- 核对 `server/main.py`：启动时要求 `APP_SECRET` 和 `AUTH_SECRET` 均非弱默认值。
- 核对 `server/core/config.py`：本地生产模式下 localhost CORS 会导致启动拒绝。
- 核对 `server/core/database.py`：当前数据库 URL 硬编码为 `data/app.db` SQLite。
- 核对 `docker-compose.yml`：backend 未显式传入 `AUTH_SECRET`。

结果：
- README 已转为 UTF-8 中文可读的新手入口。
- 本地启动步骤与当前入口文件、脚本和验证命令一致。
- 未验证或存在接线疑点的内容已写成“待确认”。

下一步：
- 修订后端结构、Alembic 计划和 Release Notes，使关键文档口径与 README 一致。

### 阶段 3：修订关键文档口径

改动：
- 重写 `server/STRUCTURE.md` 为中文后端结构速查。
- 重写 `docs/ALEMBIC_MIGRATION.md`，明确当前只是迁移计划，尚未实施。
- 重写 `docs/RELEASE_NOTES.md`，保留 Guardrails 发布说明，同时标注历史验证数字与当前验证基线的区别。

验证：
- 核对 `server/routers/**` 路由前缀和 `server/main.py` 的 `/health`、`/ready`、`/mcp`。
- 核对 `server/security/llm_guardrails/**` 现有模块和测试文件。
- 核对 `server/migrations/sql/sc22_audit_indexes.sql` 存在。
- 核对 `server/tests/test_e2e.py` 依赖 Playwright 和本机浏览器路径。

结果：
- 关键文档不再把 PostgreSQL / Docker Compose / 历史测试数字写成当前已重新验证事实。
- 三份文档都明确了当前默认验证命令。

下一步：
- 检查中文可读性、潜在乱码、链接存在性、diff 范围和命令一致性。

### 阶段 4：最终检查

改动：
- 清理 `docs/RELEASE_NOTES.md` 中的行尾空格。

验证：
- `Get-Content -Raw -Encoding UTF8` 读取 README 和关键文档，中文可读。
- `rg "�|鈥|鐨|鍙|绋|涔|乧|乣|搂|馃|銆|€" ...` 未命中常见乱码片段。
- Markdown 本地链接检查通过：`OK: markdown links exist`。
- `git diff --check -- README.md server\STRUCTURE.md docs\ALEMBIC_MIGRATION.md docs\RELEASE_NOTES.md docs\runs\2026-06-15-m0-01-docs-cleanup.md` 通过，仅有 Git 的 LF/CRLF 提示。
- `git diff --stat` 显示已跟踪文档变更为纯文档：568 insertions、392 deletions；新增运行日志未纳入该 stat，因为它是新文件。

结果：
- README 中文可读。
- 启动命令和验证命令已按当前 `server.main:app`、`web-next/package.json`、`server/tests/test_e2e.py` 现状修正。
- 未运行全量测试，按任务要求只说明当前验证基线。

## 验证证据

- README / 关键 docs UTF-8 中文读取通过。
- 常见乱码片段扫描无命中。
- Markdown 本地链接存在性检查通过。
- `git diff --check` 通过。
- 已核对验证基线：
  - 前端：`npm run typecheck`、`npm run build`
  - 后端非 E2E：`pytest server/tests --ignore=server/tests/test_e2e.py`
  - Guardrails：`pytest server/tests/security/llm_guardrails`

## 未解决问题

- Docker Compose 路径待确认：backend 未显式传入 `AUTH_SECRET`，同时后端当前数据库 engine 硬编码 SQLite。
- 本次未运行前端 build/typecheck 或后端 pytest；只做文档和命令一致性检查。
- 仓库在任务开始前已有其他未提交/未跟踪文件，本任务未处理它们。

## 最终状态

完成
