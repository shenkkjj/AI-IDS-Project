# M3-21 Incident Workspace Keyboard Navigation / Accessibility QA UX 收口任务

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` to implement this plan task by task. Also use `superpowers:test-driven-development`, `superpowers:verification-before-completion`, `frontend-patterns`, `frontend-design`, and `e2e-testing`.
>
> **Goal:** 把 M3-17 到 M3-20 叠加出来的案件工作台控件收口成可键盘操作、焦点清晰、ARIA 可审计、真实浏览器可回归的产品面。
>
> **Architecture:** 本任务只在前端 Dashboard 案件工作台内补可访问性语义、键盘导航、焦点恢复和 E2E 证据。状态仍保留在现有 React state 与既有 hooks 中，不新增后端契约。
>
> **Tech Stack:** Next.js / React / TypeScript / Tailwind / lucide-react / pytest + Playwright。

## 0. 任务一句话

在 M3-20 Incident Workbench Bulk Selection / Export Queue UX 之上，新增 **Keyboard Navigation / Accessibility QA** 收口：让 owner 可以只用键盘完成案件筛选、列表多选、打开详情、状态/严重度切换、报告预览关闭、Evidence Pack / Closure Review 操作、批量复制安全摘要和导出队列清空；同时为关键区域补稳定焦点、ARIA 标签、焦点恢复、桌面/移动截图和真实浏览器 E2E 证据。不要新增业务后端能力，不要引入新依赖，不要把快捷键说明做成可见教程。

## 1. 背景

已交付能力：

- M3-17 已交付 Evidence Pack Checklist。
- M3-18 已交付 Closure Review Checklist。
- M3-19 已交付案件列表状态筛选、关闭态归档视图和 `closed_at` 可见性。
- M3-20 已交付案件列表多选、全选当前筛选、批量复制安全摘要和前端内存级导出队列提示。

当前体验缺口：

- 案件工作台已经有大量按钮、checkbox、列表项、radio-like 状态控件、报告预览、检查清单和复制动作，但没有一条真实浏览器 E2E 证明它们能被键盘稳定使用。
- 列表项与 sibling checkbox 已能分离点击，但还缺少清晰的键盘焦点验收：`Space` 是否只切换 checkbox，`Enter` 是否只打开详情，焦点是否按可预期顺序流动。
- `IncidentDetailPanel` 里的 status / severity 使用 `role="radio"`，但需要验证并补齐方向键导航、`aria-checked`、焦点状态和保存回归。
- 报告预览已支持 `Escape` 关闭，但需要保证打开后焦点进入预览区域，关闭后焦点回到 `incident-preview-report`。
- Evidence Pack / Closure Review 的复制和刷新按钮有 aria-label，但没有端到端证明按钮可通过键盘触发，复制状态可被 `aria-live` 暴露，DOM/clipboard 不泄漏敏感内容。
- 移动 viewport 已有视觉截图，但还缺少“键盘可访问性增强后不破坏移动布局”的截图证据。

本任务目标不是做 WCAG 全量认证，也不是引入 axe-core 等新依赖；目标是为当前产品最关键的案件工作台补一条可长期回归的键盘和可访问性质量门。

## 2. 必读上下文

开始前必须完整阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/agent/M3_17_INCIDENT_ALERT_EVIDENCE_PACK_CHECKLIST_UX_TASK.md`
- `docs/agent/M3_18_INCIDENT_CLOSURE_POST_INCIDENT_REVIEW_CHECKLIST_UX_TASK.md`
- `docs/agent/M3_19_CLOSED_INCIDENT_ARCHIVE_STATUS_FILTER_UX_TASK.md`
- `docs/agent/M3_20_INCIDENT_WORKBENCH_BULK_SELECTION_EXPORT_QUEUE_UX_TASK.md`
- `docs/runs/2026-06-21-m3-17-incident-alert-evidence-pack-checklist-ux.md`
- `docs/runs/2026-06-21-m3-18-incident-closure-post-incident-review-checklist-ux.md`
- `docs/runs/2026-06-21-m3-19-closed-incident-archive-status-filter-ux.md`
- `docs/runs/2026-06-22-m3-20-incident-workbench-bulk-selection-export-queue-ux.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md` 中 M3-17 / M3-18 / M3-19 / M3-20 段落
- `web-next/components/dashboard/IncidentSection.tsx`
- `web-next/components/dashboard/IncidentList.tsx`
- `web-next/components/dashboard/IncidentStatusFilterBar.tsx`
- `web-next/components/dashboard/IncidentBulkActionBar.tsx`
- `web-next/components/dashboard/IncidentExportQueuePanel.tsx`
- `web-next/components/dashboard/IncidentDetailPanel.tsx`
- `web-next/components/dashboard/IncidentReportPreview.tsx`
- `web-next/components/dashboard/IncidentEvidencePackChecklist.tsx`
- `web-next/components/dashboard/IncidentClosureReviewChecklist.tsx`
- `web-next/types/incidentBulkActions.ts`
- `server/tests/e2e_helpers.py`
- `server/tests/test_incident_bulk_selection_export_queue_e2e.py`
- `server/tests/test_incident_status_filter_archive_e2e.py`
- `server/tests/test_incident_closure_review_checklist_e2e.py`
- `server/tests/test_incident_evidence_pack_checklist_e2e.py`
- `server/tests/test_incident_report_preview_e2e.py`
- `server/tests/test_dashboard_responsive_e2e.py`

必须使用或参考的 skill：

- `superpowers:executing-plans` 或 `superpowers:subagent-driven-development`
- `superpowers:test-driven-development`
- `superpowers:verification-before-completion`
- `frontend-patterns`
- `frontend-design`
- `e2e-testing`

## 3. 硬边界

允许修改：

- `web-next/components/dashboard/IncidentSection.tsx`
- `web-next/components/dashboard/IncidentList.tsx`
- `web-next/components/dashboard/IncidentStatusFilterBar.tsx`
- `web-next/components/dashboard/IncidentBulkActionBar.tsx`
- `web-next/components/dashboard/IncidentExportQueuePanel.tsx`
- `web-next/components/dashboard/IncidentDetailPanel.tsx`
- `web-next/components/dashboard/IncidentReportPreview.tsx`
- `web-next/components/dashboard/IncidentEvidencePackChecklist.tsx`
- `web-next/components/dashboard/IncidentClosureReviewChecklist.tsx`
- 可新增 `web-next/components/dashboard/IncidentA11yUtils.ts`，仅放前端焦点/ARIA 辅助常量或纯函数
- 可新增 `server/tests/test_incident_workspace_accessibility_e2e.py`
- `docs/runs/2026-06-22-m3-21-incident-workspace-keyboard-navigation-accessibility-qa-ux.md`
- `docs/runs/artifacts/m3-21-incident-workspace-accessibility/**`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

禁止修改：

- 认证 / 授权
- `server/security/**` / Guardrails
- SSRF
- DB schema / Alembic migration
- 后端 incident / report API contract
- `server/routers/incidents_router.py`
- `server/services/incident_service.py`
- `server/services/incident_report_service.py`
- `server/models_db.py`
- npm 依赖
- rate limit 常量
- `.env`、`.coverage`、数据库、真实密钥
- 案件状态语义、`closed_at` 语义、报告导出格式、Evidence Pack / Closure Review 的业务判定标准
- 自动关闭、删除或批量修改案件
- 调用 LLM 生成可访问性文案或摘要
- 把完整 title、summary、payload、note、报告 markdown、system prompt、stack trace、API key 写入新增 aria-label、复制文本、截图说明、运行日志或测试输出

前端实现约束：

- 不使用 `localStorage` / `sessionStorage` 持久化键盘状态、焦点状态、选中项或队列。
- 不使用 `dangerouslySetInnerHTML` / `innerHTML`。
- 不新增可见的“快捷键教程”或“如何使用键盘”的说明文本；允许新增 `sr-only` 辅助文本、`aria-label`、`aria-describedby`、`aria-live`。
- 不用全局键盘监听抢占输入框、textarea、select、checkbox 或按钮的原生行为。
- 只在明确需要的局部 radiogroup / preview 区域处理方向键和 `Escape`。
- 保持现有视觉风格，补 `focus-visible` 状态时使用已有 token 类，如 `outline-accent`、`border-accent`、`bg-accent-soft`，不要重做界面。

## 4. 运行预算与停止条件

建议预算：

- 总耗时：90-180 分钟。
- 文件改动：优先控制在 8 个前端文件 + 1 个 E2E 文件 + 3 个文档文件 + 2 张截图。
- commit：建议 3 个，分别是 E2E、前端 UX、文档与截图。

停止条件：

- 如果 Playwright / Chrome 无法启动，先诊断 `PLAYWRIGHT_CHROMIUM_EXECUTABLE`、前端 URL、后端 health 和代理 health；不能把未运行浏览器测试写成通过。
- 如果登录 / 注册 rate limit 阻塞，按 M3-20 run log 方式重启临时本地 backend 或预置独立本地测试账号；不能修改生产 rate limit。
- 如果 keyboard E2E 需要改认证、后端 API、DB schema、Guardrails 或 npm 依赖才能通过，停止并记录阻塞。
- 如果发现现有组件已经满足某项验收，仍要用 E2E 或 DOM audit 证明，不要无意义重写。
- 如果真实浏览器 E2E 不通过，不允许 push。

## 5. 产品验收标准

### 5.1 案件工作台区域语义

`IncidentSection` 必须具备：

- `data-testid="incident-section"` 保持不变。
- 给整体区域加稳定可访问名称，例如 `aria-label="案件工作台"`。
- 左侧列表区域和右侧详情区域有可区分的 region / aria label。
- 不新增可见教学文本。
- 桌面和移动布局不产生横向滚动。

### 5.2 状态筛选键盘路径

`IncidentStatusFilterBar` 必须具备：

- `incident-status-filter-bar` 保持不变。
- 筛选按钮保持原有 test id：
  - `incident-filter-all`
  - `incident-filter-active`
  - `incident-filter-open`
  - `incident-filter-investigating`
  - `incident-filter-contained`
  - `incident-filter-resolved`
  - `incident-filter-false-positive`
  - `incident-filter-closed`
- 当前筛选必须通过 `aria-pressed="true"` 或等价语义暴露。
- `Tab` 可以进入筛选组，`Enter` / `Space` 可以切换筛选。
- 切换筛选后 `incident-filter-summary` 继续通过 `aria-live="polite"` 暴露结果。
- 焦点样式必须在键盘操作时可见。

### 5.3 列表多选与详情打开

`IncidentList` 必须具备：

- `incident-select-checkbox` 继续作为 `incident-list-item` 的 sibling，不嵌套在列表项按钮里。
- checkbox 的 accessible name 不得新增完整 title 正文；允许包含 `incident_id`、状态、严重度、告警数量。
- `Space` 在 checkbox 聚焦时只切换批量选择，不打开详情。
- `Tab` 从 checkbox 进入对应 `incident-list-item` 按钮。
- `Enter` 在 `incident-list-item` 聚焦时打开详情。
- 当前详情案件必须通过 `aria-current`、`aria-selected` 或等价属性暴露。
- 列表项和 checkbox 均有稳定 `focus-visible` 状态。

### 5.4 批量操作与导出队列

`IncidentBulkActionBar` / `IncidentExportQueuePanel` 必须具备：

- 保留 test id：
  - `incident-bulk-action-bar`
  - `incident-bulk-selected-count`
  - `incident-bulk-select-page`
  - `incident-bulk-clear-selection`
  - `incident-bulk-copy-summary`
  - `incident-bulk-copy-status`
  - `incident-add-export-queue`
  - `incident-export-queue-panel`
  - `incident-export-queue-count`
  - `incident-export-queue-item`
  - `incident-export-queue-clear`
- `incident-bulk-selected-count` 与 `incident-bulk-copy-status` 保持 `aria-live="polite"` 或等价状态语义。
- `incident-export-queue-count` 保持 `aria-live="polite"`。
- `Enter` / `Space` 可触发全选、清空、复制、加入队列、清空队列。
- 禁用按钮使用真实 `disabled`，不要只靠样式表达。
- 批量复制摘要仍只包含安全字段：incident id、状态、严重度、告警数、更新时间、`closed_at` 是否存在、title length。

### 5.5 详情面板 radiogroup

`IncidentDetailPanel` 必须具备：

- `incident-detail-panel` 保持不变。
- status radiogroup 保持 `role="radiogroup"` / `aria-label="事件状态"`。
- severity radiogroup 保持 `role="radiogroup"` / `aria-label="事件严重度"`。
- 每个 status / severity 项保留 `role="radio"` 和 `aria-checked`。
- 在 status radiogroup 内：
  - `ArrowRight` / `ArrowDown` 移动到下一个状态并激活。
  - `ArrowLeft` / `ArrowUp` 移动到上一个状态并激活。
  - `Home` 移动到第一个状态。
  - `End` 移动到最后一个状态。
- severity radiogroup 同上。
- 不要让方向键影响页面滚动。
- 不要在用户正在 title / summary / note / link input 中输入时拦截方向键。
- 保存按钮 `incident-save` 的键盘行为保持原生。

### 5.6 报告预览焦点恢复

`IncidentReportPreview` / `IncidentDetailPanel` 必须具备：

- `incident-preview-report` 保持不变。
- 打开报告预览后，焦点进入 `incident-report-preview` 或 `incident-report-preview-close`。
- `incident-report-preview` 可以设置 `tabIndex={-1}`，并有 `role="region"` 或等价可访问区域语义。
- 按 `Escape` 关闭预览。
- 关闭后焦点回到 `incident-preview-report`。
- `incident-report-preview-close` 保持明确 aria label。
- 不持久化 markdown，不使用 HTML 注入。

### 5.7 Evidence Pack / Closure Review 可访问性

`IncidentEvidencePackChecklist` 必须具备：

- `incident-evidence-pack-checklist` 保持不变。
- `evidence-pack-refresh-report` / `evidence-pack-copy-summary` 可通过键盘触发。
- `evidence-pack-copy-status` 保持 `aria-live="polite"`。
- 每个 evidence check 需要可审计的语义：可以使用 `role="list"` / `role="listitem"`，或为每项提供明确的文本状态。
- 图标继续 `aria-hidden="true"`。

`IncidentClosureReviewChecklist` 必须具备：

- `incident-closure-review-checklist` 保持不变。
- `closure-refresh-report` / `closure-copy-summary` 可通过键盘触发。
- `closure-copy-status` 保持 `aria-live="polite"`。
- `closure-recommendation` 对辅助技术有明确语义。
- 每个 closure check 需要可审计的语义：可以使用 `role="list"` / `role="listitem"`，或为每项提供明确的文本状态。
- 图标继续 `aria-hidden="true"`。

### 5.8 DOM audit

新增 E2E 中必须执行最小 DOM audit：

- `incident-section` 内所有可交互元素都必须有 accessible name。
- `incident-section` 内不能有重复 id。
- 当前激活元素在 Tab 导航时必须位于 viewport 内。
- 案件工作台在 390px 移动宽度下不能横向溢出。
- DOM 文本不命中 forbidden sentinel。
- clipboard 文本不命中 forbidden sentinel。
- `localStorage` / `sessionStorage` 不出现与 `incident-accessibility`、`incident-keyboard`、`incident-bulk`、`incident-export`、`incident-focus` 相关的 key。

## 6. 推荐设计

### 6.1 统一 focus-visible 样式

优先在组件内直接加 Tailwind class，不新增全局 CSS。

推荐样式：

```text
focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent
```

可以组合：

```text
focus-visible:border-accent focus-visible:bg-accent-soft
```

不要只用颜色变化表达焦点；需要 outline 或等价明确边界。

### 6.2 radiogroup helper

可以在 `IncidentDetailPanel.tsx` 内实现局部 helper：

```ts
function getNextOptionIndex(
  currentIndex: number,
  length: number,
  key: string
): number | null {
  if (length <= 0) return null;
  if (key === "ArrowRight" || key === "ArrowDown") return (currentIndex + 1) % length;
  if (key === "ArrowLeft" || key === "ArrowUp") return (currentIndex - 1 + length) % length;
  if (key === "Home") return 0;
  if (key === "End") return length - 1;
  return null;
}
```

实现要求：

- 只绑定在 status / severity radiogroup 容器上。
- `event.preventDefault()` 只在命中方向键 / Home / End 时执行。
- 激活选项后把焦点移动到对应 button。
- 不改变保存逻辑；用户仍需点击或键盘触发 `incident-save` 保存。

### 6.3 报告预览焦点恢复

推荐在 `IncidentDetailPanel` 中：

- 给 `incident-preview-report` 按钮加 `ref`。
- 预览打开后，在 `requestAnimationFrame` 或 effect 中 focus `incident-report-preview`。
- 关闭预览时调用统一 `closeReportPreview({ restoreFocus: true })`。
- `Escape` 关闭时也走同一函数。

不要把 focus 状态写入 storage。

### 6.4 accessible name 审计策略

E2E 中可以用以下 JS 思路做最小审计，不需要引入 axe：

```js
() => {
  const root = document.querySelector('[data-testid="incident-section"]');
  if (!root) return ['missing incident-section'];
  const nodes = Array.from(root.querySelectorAll(
    'button,input,textarea,select,[role="button"],[role="radio"],[tabindex]:not([tabindex="-1"])'
  ));
  return nodes
    .filter((node) => {
      const ariaLabel = node.getAttribute('aria-label') || '';
      const labelledBy = node.getAttribute('aria-labelledby') || '';
      const title = node.getAttribute('title') || '';
      const text = node.textContent || '';
      const placeholder = node.getAttribute('placeholder') || '';
      const value = node.getAttribute('value') || '';
      return !(ariaLabel || labelledBy || title || text.trim() || placeholder || value);
    })
    .map((node) => node.getAttribute('data-testid') || node.tagName);
}
```

如果现有输入框没有 label，但有 placeholder 和明确上下文，可以在本任务中补 `aria-label`。

## 7. TDD / E2E 计划

### Task 1：创建运行日志

新建：

```text
docs/runs/2026-06-22-m3-21-incident-workspace-keyboard-navigation-accessibility-qa-ux.md
```

写入：

```markdown
# Run: M3-21 Incident Workspace Keyboard Navigation / Accessibility QA UX 收口

## 范围

- 只改前端案件工作台键盘导航、焦点状态、ARIA、E2E、截图和文档。
- 不改认证/授权、Guardrails、SSRF、DB schema、后端 incident/report API、npm 依赖或 rate limit。
- 不调用 LLM，不使用 localStorage/sessionStorage 或 dangerouslySetInnerHTML。

## 阶段记录

- [ ] 阶段 0 基线与上下文读取
- [ ] 阶段 1 RED：新增 keyboard/a11y E2E 并确认失败
- [ ] 阶段 2 GREEN：补最小键盘导航、ARIA 和焦点恢复
- [ ] 阶段 3 IMPROVE：de-sloppify、DOM audit、截图
- [ ] 阶段 4 验证矩阵
- [ ] 阶段 5 文档同步
- [ ] 阶段 6 精确 commit / push
```

立即记录：

- `git status --short --branch`
- 最新 `git log --oneline --decorate -5`
- M3-20 已交付验证摘要
- 当前 dev server / backend health 前置条件

### Task 2：RED - 新增真实浏览器 E2E

新建：

```text
server/tests/test_incident_workspace_accessibility_e2e.py
```

测试文件必须包含：

- `pytestmark = [pytest.mark.e2e]`
- 默认 `pytest server/tests` 跳过，只有 `--run-e2e` 执行。
- 复用 `server.tests.e2e_helpers`：
  - `assert_dev_server_reachable`
  - `register_or_login_for_e2e`
  - `skip_without_playwright`
- 使用 `E2E_BASE_URL`，默认 `http://localhost:3000`。
- 使用 artifact 目录：

```python
ARTIFACT_DIR = Path("docs/runs/artifacts/m3-21-incident-workspace-accessibility")
```

最小测试名：

```python
async def test_incident_workspace_keyboard_navigation_accessibility_browser_e2e() -> None:
```

RED 测试必须覆盖：

1. 登录 Dashboard。
2. 用现有 UI 创建至少 1 个 `contained` 案件样本。
3. 进入 `incidents` route。
4. 断言 `incident-section` 可见。
5. 用 keyboard 操作 `incident-filter-contained`，断言 `aria-pressed="true"` 和 summary 更新。
6. 聚焦第一条 `incident-select-checkbox`，按 `Space`，断言 `incident-bulk-selected-count` 变为 `已选择 1`。
7. 按 `Tab` 到对应 `incident-list-item`，按 `Enter`，断言 `incident-detail-panel` 打开且 `data-incident-id` 匹配。
8. 在 status radiogroup 中聚焦 `incident-status-contained`，按 `ArrowRight`，断言下一个 status 的 `aria-checked="true"`。
9. 在 severity radiogroup 中聚焦当前 severity，按 `ArrowRight`，断言下一个 severity 的 `aria-checked="true"`。
10. 触发 `incident-save`，断言保存状态出现。
11. 用键盘触发 `incident-preview-report`，断言 `incident-report-preview` 出现且焦点进入 preview 或 close button。
12. 按 `Escape`，断言 preview 关闭且焦点回到 `incident-preview-report`。
13. 用键盘触发 `evidence-pack-refresh-report` 和 `evidence-pack-copy-summary`，断言 `evidence-pack-copy-status` 为 `已复制` 或 `复制失败`。
14. 用键盘触发 `closure-refresh-report` 和 `closure-copy-summary`，断言 `closure-copy-status` 为 `已复制` 或 `复制失败`。
15. 用键盘触发 `incident-bulk-copy-summary` 和 `incident-add-export-queue`，断言 copy status / queue count 更新。
16. 用键盘触发 `incident-export-queue-clear`，断言队列清空。
17. 执行 accessible name audit。
18. 执行 duplicate id audit。
19. 执行 storage key audit。
20. 执行 DOM / clipboard forbidden sentinel。
21. 保存桌面截图：

```text
docs/runs/artifacts/m3-21-incident-workspace-accessibility/accessibility-desktop.png
```

22. 切到 390 x 844 viewport，重新进入 incidents route，保存移动截图：

```text
docs/runs/artifacts/m3-21-incident-workspace-accessibility/accessibility-mobile.png
```

RED 期望：

- 当前代码大概率在以下任一处失败：
  - report preview 打开后焦点没有进入 preview。
  - `Escape` 关闭 preview 后焦点没有回到 `incident-preview-report`。
  - status / severity radiogroup 方向键不改变选项。
  - 某些交互控件 accessible name 审计失败。
- 失败必须是测试红，不允许 skip / xfail / 删除断言。

RED 命令：

```powershell
$env:E2E_BASE_URL='http://localhost:3140'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_incident_workspace_accessibility_e2e.py -q --tb=short --run-e2e -s -rs
```

如果本机端口不是 3140，先按当前 dev server 调整 `E2E_BASE_URL`，并把实际值写入 run log。

### Task 3：GREEN - 实现最小可访问性 UX

按 RED 失败点最小实现：

1. `IncidentSection.tsx`
   - 为整体区域和左右两列补 aria label / region。
   - 不改变布局结构。

2. `IncidentStatusFilterBar.tsx`
   - 为筛选组保留 `role="group"` 或升级为更明确的标签结构。
   - 给按钮补 `focus-visible` 样式。
   - 保持 `aria-pressed` 和 test id。

3. `IncidentList.tsx`
   - checkbox 的 `aria-label` 改为安全字段，不新增完整 title 正文。
   - list item button 加 `aria-current` 或 `aria-selected`。
   - checkbox 与 list item button 加 `focus-visible` 样式。
   - 保持 checkbox 点击不打开详情。

4. `IncidentBulkActionBar.tsx`
   - 保留 `aria-live`。
   - 给按钮补 `focus-visible` 样式。
   - 确认禁用按钮使用真实 `disabled`。

5. `IncidentExportQueuePanel.tsx`
   - 保留 queue count `aria-live`。
   - 给清空按钮补 `focus-visible`。
   - 给队列列表补 list 语义。

6. `IncidentDetailPanel.tsx`
   - 为 status / severity radiogroup 实现局部方向键导航。
   - 给 report preview button 增加 ref。
   - 打开 report preview 后 focus preview region 或 close button。
   - `Escape` 关闭 preview 后 restore focus。
   - 给主要按钮和输入补缺失 aria label / focus-visible。

7. `IncidentReportPreview.tsx`
   - 给 root section 加 `role="region"`、`tabIndex={-1}`、可访问名称。
   - close button 保持明确 aria label 和 focus-visible。

8. `IncidentEvidencePackChecklist.tsx`
   - 给 checklist 项补 list/listitem 或等价语义。
   - 给 refresh/copy 按钮补 focus-visible。
   - 保持 copy status `aria-live`。

9. `IncidentClosureReviewChecklist.tsx`
   - 给 checklist 项补 list/listitem 或等价语义。
   - 给 refresh/copy 按钮补 focus-visible。
   - 保持 copy status `aria-live`。

GREEN 命令：

```powershell
$env:E2E_BASE_URL='http://localhost:3140'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_incident_workspace_accessibility_e2e.py -q --tb=short --run-e2e -s -rs
```

期望：

```text
1 passed
```

### Task 4：IMPROVE - de-sloppify

检查并修正：

- 没有新增重复 `data-testid` 破坏旧 E2E。
- 没有新增可见快捷键教程。
- 没有在 `aria-label` 中新增完整 title / summary / payload / note / markdown。
- 没有把 focus 状态写入 storage。
- 没有全局键盘监听抢占输入框。
- 移动 390px 下无横向滚动。
- 截图中文本无重叠。
- 所有新增按钮仍有 lucide icon `aria-hidden`。
- `report preview` close button 可键盘关闭，`Escape` 关闭和按钮关闭都 restore focus。

静态扫描命令：

```powershell
rg -n "console\.log|localStorage|sessionStorage|dangerouslySetInnerHTML|innerHTML|sk-|AKIA|ghp_|PRIVATE KEY|Traceback|system\s*:|developer\s*:" web-next\components\dashboard server\tests\test_incident_workspace_accessibility_e2e.py
```

允许命中：

- 新 E2E 中的 forbidden sentinel 正则。
- 既有测试里的 storage audit 文本。

不允许命中：

- 产品代码中的 `localStorage` / `sessionStorage`
- 产品代码中的 `dangerouslySetInnerHTML` / `innerHTML`
- 产品代码中的真实 secret-like 字符串
- 产品代码中的 debug `console.log`

### Task 5：验证矩阵

必须按顺序执行并把结果写入 run log。

新增 E2E：

```powershell
$env:E2E_BASE_URL='http://localhost:3140'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_incident_workspace_accessibility_e2e.py -q --tb=short --run-e2e -s -rs
```

相邻案件 UX 回归：

```powershell
$env:E2E_BASE_URL='http://localhost:3140'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_incident_bulk_selection_export_queue_e2e.py server\tests\test_incident_status_filter_archive_e2e.py server\tests\test_incident_closure_review_checklist_e2e.py server\tests\test_incident_evidence_pack_checklist_e2e.py server\tests\test_incident_report_preview_e2e.py server\tests\test_dashboard_responsive_e2e.py -q --tb=short --run-e2e -s -rs
```

关键 E2E 串跑：

```powershell
$env:E2E_BASE_URL='http://localhost:3140'
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe -m pytest server\tests\test_auth_session_e2e.py server\tests\test_demo_flow_e2e.py server\tests\test_incident_report_e2e.py server\tests\test_dashboard_route_sections_e2e.py server\tests\test_dashboard_responsive_e2e.py server\tests\test_demo_flow_stability_e2e.py server\tests\test_dashboard_mobile_visual_e2e.py server\tests\test_incident_report_preview_e2e.py server\tests\test_security_timeline_drilldown_e2e.py server\tests\test_dashboard_operational_runbook_e2e.py server\tests\test_incident_evidence_pack_checklist_e2e.py server\tests\test_incident_closure_review_checklist_e2e.py server\tests\test_incident_status_filter_archive_e2e.py server\tests\test_incident_bulk_selection_export_queue_e2e.py server\tests\test_incident_workspace_accessibility_e2e.py -q --tb=short --run-e2e -s -rs
```

后端 incident 契约：

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\test_incident_api.py server\tests\test_incident_report_api.py -q --tb=short
```

后端全量：

```powershell
New-Item -ItemType Directory -Force -Path '.tmp\pytest-m3-21-full' | Out-Null
$env:TMP=(Resolve-Path '.tmp\pytest-m3-21-full').Path
$env:TEMP=$env:TMP
$env:APP_SECRET='test-local-secret-key-for-m3-21-full-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-m3-21-full-32chars'
.\.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

Guardrails 专项：

```powershell
New-Item -ItemType Directory -Force -Path '.tmp\pytest-m3-21-guardrails' | Out-Null
$env:TMP=(Resolve-Path '.tmp\pytest-m3-21-guardrails').Path
$env:TEMP=$env:TMP
$env:APP_SECRET='test-local-secret-key-for-m3-21-guardrails-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-m3-21-guardrails-32chars'
.\.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

前端 typecheck：

```powershell
npm run typecheck
```

前端 build：

```powershell
npm run build
```

文档 / diff 检查：

```powershell
$patterns = @('T'+'BD','T'+'ODO','implement'+' later','fill in'+' details','待'+'补','暂无'+'已固化','请先'+'固化')
foreach ($pattern in $patterns) { rg -n --fixed-strings $pattern docs\agent\M3_21_INCIDENT_WORKSPACE_KEYBOARD_NAVIGATION_ACCESSIBILITY_QA_UX_TASK.md docs\runs\2026-06-22-m3-21-incident-workspace-keyboard-navigation-accessibility-qa-ux.md docs\agent\UNATTENDED_LONG_TASKS.md PRODUCT.md docs\plans\M2_PRODUCT_ROADMAP.md }
Select-String -LiteralPath 'docs\agent\M3_21_INCIDENT_WORKSPACE_KEYBOARD_NAVIGATION_ACCESSIBILITY_QA_UX_TASK.md','docs\runs\2026-06-22-m3-21-incident-workspace-keyboard-navigation-accessibility-qa-ux.md','docs\agent\UNATTENDED_LONG_TASKS.md','PRODUCT.md','docs\plans\M2_PRODUCT_ROADMAP.md' -Pattern '[\t ]+$'
git diff --check
```

不能把 skipped 当 passed。最终报告必须明确列出 passed / skipped / warnings。

### Task 6：文档同步

更新：

- `PRODUCT.md`：在 M3 实施状态中新增 M3-21 已交付说明，包含真实验证结果、截图路径和安全边界。
- `docs/plans/M2_PRODUCT_ROADMAP.md`：新增 M3-21 章节，记录目标、已交付、验证、边界、改动文件、未解决问题。
- `docs/agent/UNATTENDED_LONG_TASKS.md`：把 M3-21 从“已固化，等待执行”更新为“已交付”；推荐下一条默认工单改为 **M3-22 Incident Workspace Guided Review Session / Operator Handoff UX**。
- `docs/runs/2026-06-22-m3-21-incident-workspace-keyboard-navigation-accessibility-qa-ux.md`：补齐最终验证证据和最终状态。

M3-22 候选方向：

```text
Incident Workspace Guided Review Session / Operator Handoff UX：在不新增后端 API 和不调用 LLM 的前提下，把当前筛选、已选案件、Evidence Pack、Closure Review、报告可用性和队列状态组织成前端只读 review session 面板，并提供安全 handoff 摘要复制与 E2E 证据。
```

## 8. 安全与隐私检查

必须确认：

- 新增 aria-label / aria-describedby 不包含完整 title、summary、payload、note、报告 markdown、secret、stack trace。
- clipboard 中不包含 payload、note、报告 markdown、secret、token、system prompt、developer prompt。
- DOM visible text 不命中 forbidden sentinel。
- 截图只展示安全字段和既有 UI，不新增原始 payload / note。
- 不修改认证 / 授权 / Guardrails / SSRF / DB schema / 后端 API。
- 不新增 npm 依赖。
- 不使用 storage 持久化 focus / keyboard / selected / queue。
- 不使用 HTML 注入。
- 不提交 `.coverage`、真实 `.env`、数据库或密钥。

Forbidden sentinel 建议沿用 M3-20：

```python
_FORBIDDEN_DOM_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"sk-proj-[A-Za-z0-9_-]+"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"\bTraceback\s+\(most recent call last\)", re.IGNORECASE),
    re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+.*system\s+prompt", re.IGNORECASE),
    re.compile(r"forget\s+.*instructions", re.IGNORECASE),
    re.compile(r"\bsystem\s*:\s*", re.IGNORECASE),
    re.compile(r"\bdeveloper\s*:\s*", re.IGNORECASE),
    re.compile(r"PRIVATE\s+KEY", re.IGNORECASE),
)
```

## 9. 提交计划

提交前必须执行：

```powershell
git status --short --branch
git diff --check
git diff --cached --check
```

建议拆分：

1. E2E：

```text
test(e2e): 覆盖案件工作台键盘可访问性
```

包含：

- `server/tests/test_incident_workspace_accessibility_e2e.py`

2. 前端 UX：

```text
feat(a11y): 完善案件工作台键盘导航
```

包含实际修改过的前端文件，例如：

- `web-next/components/dashboard/IncidentSection.tsx`
- `web-next/components/dashboard/IncidentList.tsx`
- `web-next/components/dashboard/IncidentStatusFilterBar.tsx`
- `web-next/components/dashboard/IncidentBulkActionBar.tsx`
- `web-next/components/dashboard/IncidentExportQueuePanel.tsx`
- `web-next/components/dashboard/IncidentDetailPanel.tsx`
- `web-next/components/dashboard/IncidentReportPreview.tsx`
- `web-next/components/dashboard/IncidentEvidencePackChecklist.tsx`
- `web-next/components/dashboard/IncidentClosureReviewChecklist.tsx`
- 可选 `web-next/components/dashboard/IncidentA11yUtils.ts`

3. 文档与截图：

```text
docs(a11y): 记录案件工作台可访问性收口
```

包含：

- `docs/agent/M3_21_INCIDENT_WORKSPACE_KEYBOARD_NAVIGATION_ACCESSIBILITY_QA_UX_TASK.md`
- `docs/runs/2026-06-22-m3-21-incident-workspace-keyboard-navigation-accessibility-qa-ux.md`
- `docs/runs/artifacts/m3-21-incident-workspace-accessibility/*.png`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`

禁止：

- `git add .`
- 提交 `.coverage`
- 提交 `.tmp`
- 提交真实 `.env`
- 提交数据库文件
- 提交旧任务截图刷新，除非本任务确实重新生成并在 run log 解释
- 提交 dev server `.log`，除非文档明确需要且已脱敏

push：

```powershell
git push origin main
```

只有在完整验证矩阵通过后才能 push。

## 10. 最终报告格式

最终报告必须包含：

```markdown
## M3-21 最终报告

### 已交付

- 键盘导航 / focus-visible / ARIA / report preview focus restore / checklist 可访问性收口摘要。

### 验证

- 新增 keyboard/a11y E2E：X passed。
- 相邻案件 UX 回归：X passed。
- 关键 E2E 串跑：X passed。
- 后端 incident 契约：X passed。
- 后端全量：X passed, X skipped, X warnings。
- Guardrails：X passed, X warnings。
- 前端 typecheck：passed。
- 前端 build：passed。

### 截图

- docs/runs/artifacts/m3-21-incident-workspace-accessibility/accessibility-desktop.png
- docs/runs/artifacts/m3-21-incident-workspace-accessibility/accessibility-mobile.png

### 边界

- 未改认证/授权、Guardrails、SSRF、DB schema、后端 incident/report API、npm 依赖或 rate limit。
- 未调用 LLM。
- 未使用 localStorage/sessionStorage 或 dangerouslySetInnerHTML。
- 未提交 .coverage、真实 env、数据库或密钥。

### Git

- commit 列表
- push 结果

### 下一条建议工单

- M3-22 Incident Workspace Guided Review Session / Operator Handoff UX
```
