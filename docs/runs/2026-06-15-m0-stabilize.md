# Run: M0-STABILIZE

开始时间：2026-06-15
运行模式：L2，无人值守长任务
预算：最长 4 小时；同一失败最多修复 3 轮；diff 超过约 1000 行停止总结，主要为文档或锁文件时除外。

## 目标

- 让新 agent 或新手开发者可以运行默认验证命令，不再被 Playwright E2E、Next lint 交互式流程、过时 CI 配置卡住。

## 启动前必读

- 已读取：`PRODUCT.md`
- 已读取：`AGENTS.md`
- 已读取：`CLAUDE.md`
- 已读取：`docs/agent/UNATTENDED_LONG_TASKS.md`
- 已读取：`README.md`

## Skill 检查

- 使用 `terminal-ops`：证据优先执行、记录 git 状态、命令和验证结果。
- 使用 `verification-loop`：阶段收尾和最终验证。
- 使用 `python-testing`：处理 pytest 收集与 E2E marker/skip 策略。
- 使用 `frontend-patterns`：处理 Next.js 前端脚本、lint 和 CI 非交互验证。

## 范围

允许修改：
- `server/tests/**`
- `pytest.ini`、`setup.cfg` 或其他 pytest 配置文件
- `web-next/package.json`
- `web-next/package-lock.json`
- `web-next/eslint.config.*` 或 `.eslintrc.*`
- `.github/workflows/ci.yml`
- `README.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/runs/**`

禁止修改：
- 真实 `.env`
- `.claude/settings.local.json`
- git 历史
- 认证、授权、JWT、cookie、安全护栏核心策略
- 数据库 schema / migration
- 部署密钥、生产配置
- 业务功能代码，除非只是为了让测试配置正确识别

## 初始工作区状态

启动时 `git status --short` 已显示以下既有改动，本任务不会主动回滚：

- `M .claude/settings.local.json`（禁止范围，记录但不触碰）
- `M .coverage`（既有覆盖率产物，记录但不触碰）
- `M AGENTS.md`（不在本任务允许修改范围，记录但不触碰）
- `M README.md`
- `M docs/ALEMBIC_MIGRATION.md`（不在本任务允许修改范围，记录但不触碰）
- `M docs/RELEASE_NOTES.md`（不在本任务允许修改范围，记录但不触碰）
- `M server/STRUCTURE.md`（不在本任务允许修改范围，记录但不触碰）
- `?? PRODUCT.md`
- `?? docs/agent/`
- `?? docs/runs/`
- `?? server/.coverage`（既有覆盖率产物，记录但不触碰）

本任务新增/修改将从本文件创建开始记录。

## 计划

- [x] 阶段 1：基线复现
- [x] 阶段 2：修复后端默认测试
- [x] 阶段 3：修复前端 lint/CI 非交互问题
- [x] 阶段 4：更新文档
- [x] 阶段 5：最终验证

## 阶段记录

### 阶段 1：基线复现

改动：暂无。
验证：
- `$env:APP_SECRET=...; $env:AUTH_SECRET=...; .\.venv\Scripts\python.exe -m pytest server\tests -q --tb=short`
- `cd web-next; npm run typecheck`
- `cd web-next; npm run build`
- 检查 `.github/workflows/ci.yml`

结果：
- 后端默认 pytest 失败：收集 `server/tests/test_e2e.py` 时 `ModuleNotFoundError: No module named 'playwright'`。
- 前端 `npm run typecheck` 首次失败：`.next/types/**/*.ts` include 匹配了缺失的 Next 生成类型。
- 前端 `npm run build` 通过。
- CI 仍包含 `npx next lint`。

下一步：隔离 Playwright E2E，修复前端验证命令和 CI 非交互链路。

### 阶段 2：修复后端默认测试

改动：
- `server/tests/conftest.py`：新增 `--run-e2e` pytest option、`e2e` marker、默认 skip E2E；补 `AUTH_SECRET` 测试默认值。
- `server/tests/test_e2e.py`：标记 `pytest.mark.e2e`，延迟导入 Playwright；显式 E2E 缺依赖时 skip；浏览器 executable 改为可选 env `PLAYWRIGHT_CHROMIUM_EXECUTABLE`。

验证：
- `$env:APP_SECRET=...; $env:AUTH_SECRET=...; .\.venv\Scripts\python.exe -m pytest server\tests -q --tb=short`
- `$env:APP_SECRET=...; $env:AUTH_SECRET=...; .\.venv\Scripts\python.exe -m pytest server\tests\test_e2e.py -q --tb=short --run-e2e`

结果：
- 默认后端测试通过：219 passed, 1 skipped, 17 warnings。
- 显式 E2E 在缺少 Playwright 时为 1 skipped，没有收集失败。

下一步：替换 CI 中的交互式 `npx next lint`，稳定前端 typecheck。

### 阶段 3：修复前端 lint/CI 非交互问题

改动：
- `web-next/package.json`：`typecheck` 改为 `next typegen && tsc --noEmit`，让干净环境先生成 Next 类型。
- `.github/workflows/ci.yml`：移除 `npx next lint`；前端 CI 使用 `npm run typecheck` 和 `npm run build`。

验证：
- `cd web-next; npm run typecheck`
- `cd web-next; npm run build`

结果：
- 首次把 `npm run typecheck` 和 `npm run build` 并行执行时出现 `.next` 写入竞态，顺序执行后 `npm run typecheck` 通过。
- `npm run build` 通过。
- 未新增 lint 脚本或 ESLint 依赖，避免低价值锁文件 churn；CI 已无交互式 lint 命令。

下一步：同步 README、PRODUCT、长任务手册。

### 阶段 4：更新文档

改动：
- `README.md`：默认后端测试改为直接 `pytest server\tests`；新增可选 Playwright E2E 入口和安装说明；说明不要使用 `npx next lint`。
- `PRODUCT.md`：更新 M0 当前状态、风险登记和下一批推荐工单。
- `docs/agent/UNATTENDED_LONG_TASKS.md`：更新默认验证基线、E2E 独立入口和推荐队列。
- `docs/runs/2026-06-15-m0-stabilize.md`：记录阶段证据。

验证：
- 文档命令将进入阶段 5 最终验证。

结果：
- 默认验证链路与 CI 说明已同步。

下一步：最终验证并检查 diff/禁止范围。

### 阶段 5：最终验证

验证：
- `$env:APP_SECRET=...; $env:AUTH_SECRET=...; .\.venv\Scripts\python.exe -m pytest server\tests -q --tb=short`
- `$env:APP_SECRET=...; $env:AUTH_SECRET=...; .\.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short`
- `cd web-next; npm run typecheck`
- `cd web-next; npm run build`
- `rg -n "npx next lint|next lint" .github\workflows\ci.yml web-next\package.json README.md PRODUCT.md docs\agent\UNATTENDED_LONG_TASKS.md`
- 附加 CI 风险检查：`$env:APP_SECRET=...; $env:AUTH_SECRET=...; .\.venv\Scripts\python.exe -m pytest server\tests -q --tb=short --cov=server --cov-report=term --cov-fail-under=80`

结果：
- 后端默认测试通过：219 passed, 1 skipped, 17 warnings。
- Guardrails 专项通过：139 passed, 17 warnings。
- 前端 `npm run typecheck` 通过。
- 前端 `npm run build` 通过。
- CI/workflow 中没有执行 `npx next lint`；该字符串只出现在文档说明里。
- 附加 CI 覆盖率检查失败：测试本身 219 passed, 1 skipped，但总覆盖率 52.31%，低于 `--cov-fail-under=80`。

## 验证证据

- 阶段 1 基线：后端 pytest 因 Playwright 收集失败；前端 build 通过；CI 含 `npx next lint`。
- 阶段 2 修复后：默认后端测试通过，E2E 缺依赖时独立 skip。
- 阶段 3 修复后：前端 `npm run typecheck`、`npm run build` 顺序执行通过。
- 阶段 5 最终验证：后端默认测试、Guardrails、前端 typecheck/build 全部通过。

## 未解决问题

- 真实 Playwright E2E 未跑通；当前只验证了显式入口和缺依赖 skip 行为。需要安装 Playwright 浏览器并启动前后端后单独跑。
- 后端 CI 覆盖率门槛仍会失败：当前 `--cov-fail-under=80` 对全 `server` 包要求 80%，实测总覆盖率 52.31%。本任务未降低覆盖率门槛，建议另开 `M0-CI-COVERAGE-01`。
- 仓库启动前已有多个文档/覆盖率/本地设置改动，本任务只在允许范围内追加修改，没有回滚既有改动。

## 最终状态

完成。M0-STABILIZE 的默认验证链路已稳定；剩余 CI 覆盖率门槛风险已记录为下一步工单。
