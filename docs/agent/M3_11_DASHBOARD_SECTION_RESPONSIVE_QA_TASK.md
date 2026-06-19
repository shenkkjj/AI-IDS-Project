# M3-11 Dashboard Section Responsive QA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 M3-10 已拆分 Dashboard route section 后，用真实浏览器 E2E 和必要的轻量 UI 修复，收口桌面/移动响应式、导航可达性、焦点/ARIA、文字溢出和 DOM 安全 sentinel。

**Architecture:** 先新增一个可选 Playwright E2E，覆盖桌面与移动视口下六个 Dashboard route 的导航、section wrapper、页面横向溢出、按钮文字溢出、active route `aria-current`、键盘可达性和 forbidden sentinel。若 RED 暴露问题，只允许在现有 `web-next/components/dashboard/**` 与 `web-next/app/dashboard/dashboard-client.tsx` 内做轻量布局/可访问性修复，不改业务 hook、后端 API、认证、Guardrails、SSRF 或 DB schema。最后更新运行日志、无人值守手册、产品文档与路线图，并按精确 staged set commit/push。

**Tech Stack:** Next.js App Router, React Client Components, Tailwind CSS classes, pytest, Playwright async Python API, existing `server/tests/e2e_helpers.py`.

---

## 0. 必读上下文

执行前必须完整阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/runs/2026-06-19-m3-10-dashboard-route-composition.md`
- `docs/agent/M3_10_DASHBOARD_ROUTE_COMPOSITION_TASK.md`
- `server/tests/e2e_helpers.py`
- `server/tests/test_dashboard_route_sections_e2e.py`
- `web-next/constants/dashboardRoutes.ts`
- `web-next/app/dashboard/dashboard-client.tsx`
- `web-next/components/dashboard/SystemStatusBar.tsx`
- `web-next/components/dashboard/SectionHeading.tsx`
- `web-next/components/dashboard/DashboardFields.tsx`
- `web-next/components/dashboard/DashboardRows.tsx`
- `web-next/components/dashboard/sections/*.tsx`
- `web-next/components/dashboard/DemoFlowControls.tsx`
- `web-next/components/dashboard/AlertSection.tsx`
- `web-next/components/dashboard/AttackLogTable.tsx`
- `web-next/components/dashboard/CopilotSection.tsx`
- `web-next/components/dashboard/IncidentSection.tsx`
- `web-next/components/dashboard/IncidentDetailPanel.tsx`
- `web-next/components/dashboard/SystemStatusSection.tsx`

启动时创建运行日志：

```powershell
docs/runs/2026-06-19-m3-11-dashboard-section-responsive-qa.md
```

运行日志必须记录：

- 启动时 `git status --short --branch`
- 启动时 `git log --oneline --decorate -12`
- M3-10 最新 commit 栈确认
- 当前 `dashboard-client.tsx` 行数
- RED / GREEN / IMPROVE 每阶段命令和结果
- 截图/证据路径
- 最终验证矩阵
- 精确 commit / push 结果
- 未解决问题与下一条建议工单

---

## 1. 当前问题与任务边界

### 1.1 当前状态

M3-10 已完成：

- `dashboard-client.tsx` 从 840 行降到 406 行。
- `web-next/constants/dashboardRoutes.ts` 成为 route metadata 单一来源。
- `SystemStatusBar.tsx` 恢复 `incidents` 桌面/移动导航入口。
- route JSX 拆到 `web-next/components/dashboard/sections/*.tsx`。
- `server/tests/test_dashboard_route_sections_e2e.py` 锁住六个桌面 route tab 与核心 section wrapper。

M3-10 没有覆盖：

- 移动视口下六个 route 的可达性。
- 顶部移动横向导航中 `incidents` 是否可滚动可点击。
- section 在移动宽度下是否造成整页横向滚动。
- 按钮/标签/route 文案是否溢出自身容器。
- active route 的 `aria-current` 是否在桌面/移动都正确切换。
- 主要 icon-only 按钮是否有 `title` 或 `aria-label`。
- 键盘 Tab/Enter 是否能切换 route。
- 失败时是否能留下截图证据。

### 1.2 允许修复的内容

只允许轻量 UI / 可访问性修复：

- 增加 `type="button"`。
- 增加 `aria-label` / `title`。
- 增加 `min-w-0`、`break-words`、`truncate`、`overflow-x-auto`、`max-w-*`、`flex-wrap`、`whitespace-nowrap` 等布局类。
- 增加稳定 `data-testid`。
- 调整 section wrapper 的响应式 grid / min-height / gap。
- 调整按钮内部 `span` 包裹，让文字不撑破。
- 调整移动 nav 的滚动/可点击性。

### 1.3 禁止内容

禁止修改：

- `server/services/auth_service.py`
- `server/core/auth*`
- `server/routers/auth*`
- `server/security/**`
- `server/core/state.py`
- `server/core/config.py`
- `server/analyzer.py`
- `server/core/utils.py`
- Alembic migration / DB schema
- `REGISTER_RATE_LIMIT_MAX` / `REGISTER_RATE_LIMIT_WINDOW`
- 后端 API contract
- npm 依赖
- `.env` / 真实 env / 数据库文件 / 密钥 / 证书
- `.coverage`

禁止行为：

- 不重做视觉设计。
- 不迁移状态管理。
- 不新增业务功能。
- 不删除或弱化现有 E2E。
- 不把 token 写进 `localStorage` / `sessionStorage` / DOM。
- 不使用 `git add .`。

---

## 2. 验收标准

完成后必须满足：

1. 新增 `server/tests/test_dashboard_responsive_e2e.py`。
2. 该 E2E 默认被 `pytest server/tests` 跳过，仅 `--run-e2e` 显式运行。
3. 桌面视口 `1366x900` 能点击六个 desktop route button：
   - `dashboard-route-desktop-overview`
   - `dashboard-route-desktop-monitor`
   - `dashboard-route-desktop-incidents`
   - `dashboard-route-desktop-waf`
   - `dashboard-route-desktop-ai`
   - `dashboard-route-desktop-report`
4. 移动视口 `390x844` 能点击六个 mobile route button：
   - `dashboard-route-mobile-overview`
   - `dashboard-route-mobile-monitor`
   - `dashboard-route-mobile-incidents`
   - `dashboard-route-mobile-waf`
   - `dashboard-route-mobile-ai`
   - `dashboard-route-mobile-report`
5. 每次切换 route 后，active button 的 `aria-current` 为 `page`。
6. 所有 route 的核心 section wrapper 可见。
7. 页面没有整页横向溢出：`document.documentElement.scrollWidth <= clientWidth + 4`。
8. 可见按钮没有文本撑破：按钮 `scrollWidth <= clientWidth + 4`，或按钮自身/子元素显式使用可接受的滚动/截断处理。
9. icon-only 按钮有 `title` 或 `aria-label`。
10. Tab 到任一路由按钮后按 Enter 可以切换 route。
11. DOM 不出现 forbidden sentinel：
    - `sk-...`
    - `sk-proj-...`
    - `AKIA...`
    - `ghp_...`
    - `PRIVATE KEY`
    - `Traceback`
    - `ignore previous instructions`
    - `disregard system prompt`
    - `forget instructions`
    - `system:`
    - `developer:`
12. 失败时保留 screenshot 证据；成功时至少保留桌面与移动各一个总览截图。
13. Auth / Demo / Incident / Dashboard route / Dashboard responsive 五条关键 E2E 连续通过。
14. 后端全量、Guardrails、前端 typecheck/build 通过。

---

## 3. 文件结构目标

建议新增：

```text
server/tests/test_dashboard_responsive_e2e.py
docs/runs/2026-06-19-m3-11-dashboard-section-responsive-qa.md
docs/runs/artifacts/m3-11-dashboard-responsive/
```

可能修改：

```text
web-next/components/dashboard/SystemStatusBar.tsx
web-next/components/dashboard/SectionHeading.tsx
web-next/components/dashboard/DemoFlowControls.tsx
web-next/components/dashboard/AlertSection.tsx
web-next/components/dashboard/AttackLogTable.tsx
web-next/components/dashboard/CopilotSection.tsx
web-next/components/dashboard/SystemStatusSection.tsx
web-next/components/dashboard/IncidentSection.tsx
web-next/components/dashboard/IncidentDetailPanel.tsx
web-next/components/dashboard/sections/*.tsx
web-next/app/dashboard/dashboard-client.tsx
PRODUCT.md
docs/plans/M2_PRODUCT_ROADMAP.md
docs/agent/UNATTENDED_LONG_TASKS.md
```

截图策略：

- 创建 `docs/runs/artifacts/m3-11-dashboard-responsive/`。
- 失败截图必须保留。
- 成功截图至少保留：
  - `desktop-overview.png`
  - `mobile-overview.png`
  - `mobile-incidents.png`
- 如果截图总大小超过 5 MB，不要 commit 截图；在 run log 记录本地路径和大小。
- 如果总大小不超过 5 MB，可以把截图作为运行证据随文档 commit。

---

## 4. TDD 计划

### Task 1: RED - 新增响应式 Dashboard E2E

**Files:**

- Create: `server/tests/test_dashboard_responsive_e2e.py`
- Modify: `docs/runs/2026-06-19-m3-11-dashboard-section-responsive-qa.md`

- [ ] **Step 1: 写失败测试**

新增文件：

```python
"""M3-11 Dashboard 响应式与可访问性 E2E（可选，需 --run-e2e）。

覆盖：
- 桌面 / 移动视口下六个 Dashboard route 都可点击。
- active route button 暴露 aria-current="page"。
- 核心 section wrapper 可见。
- 页面没有整页横向溢出。
- 可见按钮文字不撑破按钮盒子。
- icon-only 按钮有 title 或 aria-label。
- route button 可通过键盘 Enter 切换。
- DOM 不出现 secret / stack trace / system prompt sentinel。

运行前置：
1. 启动后端 dev server（默认 :8000）和前端 dev server（默认 :3000）。
2. 安装 Playwright：``pip install playwright && playwright install chromium``。
3. 运行：``pytest server/tests/test_dashboard_responsive_e2e.py --run-e2e -q --tb=short -s``。
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from server.tests.e2e_helpers import (
    assert_dev_server_reachable,
    register_or_login_for_e2e,
    skip_without_playwright,
)

pytestmark = [pytest.mark.e2e]

ARTIFACT_DIR = Path("docs/runs/artifacts/m3-11-dashboard-responsive")

_FORBIDDEN_DOM_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"sk-proj-[A-Za-z0-9_-]+"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"\\bTraceback\\s+\\(most recent call last\\)", re.IGNORECASE),
    re.compile(r"ignore\\s+previous\\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\\s+.*system\\s+prompt", re.IGNORECASE),
    re.compile(r"forget\\s+.*instructions", re.IGNORECASE),
    re.compile(r"\\bsystem\\s*:\\s*", re.IGNORECASE),
    re.compile(r"\\bdeveloper\\s*:\\s*", re.IGNORECASE),
    re.compile(r"PRIVATE\\s+KEY", re.IGNORECASE),
)

ROUTE_SECTIONS: dict[str, tuple[str, ...]] = {
    "overview": (
        "dashboard-section-stats",
        "dashboard-section-briefing",
        "dashboard-section-trends",
        "dashboard-section-alerts",
        "dashboard-section-terminal-report",
        "dashboard-section-security-timeline",
        "dashboard-section-copilot",
        "dashboard-section-ai-config",
        "dashboard-section-webhook",
        "dashboard-section-report",
    ),
    "monitor": (
        "dashboard-section-stats",
        "dashboard-section-briefing",
        "dashboard-section-trends",
        "dashboard-section-alerts",
        "dashboard-section-terminal-report",
        "dashboard-section-security-timeline",
    ),
    "incidents": (
        "dashboard-section-stats",
        "dashboard-section-briefing",
        "dashboard-section-incidents",
        "incident-section",
    ),
    "waf": (
        "dashboard-section-stats",
        "dashboard-section-briefing",
        "dashboard-section-system-status",
    ),
    "ai": (
        "dashboard-section-stats",
        "dashboard-section-briefing",
        "dashboard-section-copilot",
        "dashboard-section-ai-config",
        "dashboard-section-webhook",
    ),
    "report": (
        "dashboard-section-stats",
        "dashboard-section-briefing",
        "dashboard-section-report",
    ),
}

VIEWPORTS: tuple[tuple[str, dict[str, int], str], ...] = (
    ("desktop", {"width": 1366, "height": 900}, "dashboard-route-desktop"),
    ("mobile", {"width": 390, "height": 844}, "dashboard-route-mobile"),
)


async def _collect_visible_text(page) -> str:
    return await page.evaluate(
        """
        () => {
            const body = document.body;
            if (!body) return '';
            const clone = body.cloneNode(true);
            clone.querySelectorAll('script, style, noscript').forEach((n) => n.remove());
            return (clone.innerText || clone.textContent || '').trim();
        }
        """
    )


def _contains_forbidden(text: str) -> str | None:
    for pattern in _FORBIDDEN_DOM_PATTERNS:
        if pattern.search(text):
            return pattern.pattern
    return None


async def _expect_section(page, test_id: str) -> None:
    await page.locator(f'[data-testid="{test_id}"]').first.wait_for(
        state="visible",
        timeout=15000,
    )


async def _click_route(page, route_key: str, route_prefix: str) -> None:
    button = page.locator(f'[data-testid="{route_prefix}-{route_key}"]').first
    await button.wait_for(state="attached", timeout=15000)
    await button.scroll_into_view_if_needed(timeout=5000)
    await button.click()
    await button.wait_for(state="visible", timeout=5000)
    current = await button.get_attribute("aria-current")
    assert current == "page", (
        f"{route_prefix}-{route_key} 点击后 aria-current 应为 page, 实际 {current!r}"
    )


async def _assert_no_page_horizontal_overflow(page, label: str) -> None:
    metrics = await page.evaluate(
        """
        () => ({
            scrollWidth: Math.ceil(document.documentElement.scrollWidth),
            clientWidth: Math.ceil(document.documentElement.clientWidth),
            bodyScrollWidth: Math.ceil(document.body ? document.body.scrollWidth : 0),
            bodyClientWidth: Math.ceil(document.body ? document.body.clientWidth : 0),
        })
        """
    )
    overflow = max(
        metrics["scrollWidth"] - metrics["clientWidth"],
        metrics["bodyScrollWidth"] - metrics["bodyClientWidth"],
    )
    assert overflow <= 4, f"{label} 存在整页横向溢出: {metrics}"


async def _assert_visible_buttons_fit(page, label: str) -> None:
    offenders = await page.evaluate(
        """
        () => {
            const visible = (el) => {
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== 'none'
                    && style.visibility !== 'hidden'
                    && rect.width > 0
                    && rect.height > 0;
            };
            const okOverflow = (el) => {
                const style = window.getComputedStyle(el);
                return style.overflowX === 'auto'
                    || style.overflowX === 'scroll'
                    || style.textOverflow === 'ellipsis';
            };
            return Array.from(document.querySelectorAll('button'))
                .filter(visible)
                .filter((button) => button.scrollWidth > button.clientWidth + 4)
                .filter((button) => !okOverflow(button))
                .map((button) => ({
                    testId: button.getAttribute('data-testid') || '',
                    text: (button.innerText || button.textContent || '').trim().slice(0, 120),
                    scrollWidth: button.scrollWidth,
                    clientWidth: button.clientWidth,
                    className: button.className,
                }));
        }
        """
    )
    assert offenders == [], f"{label} 存在按钮文字溢出: {offenders}"


async def _assert_icon_buttons_named(page, label: str) -> None:
    offenders = await page.evaluate(
        """
        () => {
            const visible = (el) => {
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== 'none'
                    && style.visibility !== 'hidden'
                    && rect.width > 0
                    && rect.height > 0;
            };
            const textOf = (el) => (el.innerText || el.textContent || '').trim();
            return Array.from(document.querySelectorAll('button'))
                .filter(visible)
                .filter((button) => textOf(button).length === 0)
                .filter((button) => !button.getAttribute('aria-label') && !button.getAttribute('title'))
                .map((button) => ({
                    testId: button.getAttribute('data-testid') || '',
                    className: button.className,
                    html: button.outerHTML.slice(0, 200),
                }));
        }
        """
    )
    assert offenders == [], f"{label} 存在未命名 icon-only 按钮: {offenders}"


async def _assert_keyboard_route_activation(page, route_key: str, route_prefix: str) -> None:
    button = page.locator(f'[data-testid="{route_prefix}-{route_key}"]').first
    await button.scroll_into_view_if_needed(timeout=5000)
    await button.focus()
    await page.keyboard.press("Enter")
    current = await button.get_attribute("aria-current")
    assert current == "page", (
        f"键盘 Enter 激活 {route_prefix}-{route_key} 后 aria-current 应为 page, 实际 {current!r}"
    )


async def _screenshot(page, name: str) -> str:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / f"{name}.png"
    await page.screenshot(path=str(path), full_page=False)
    return str(path)


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.parametrize("viewport_name,viewport,route_prefix", VIEWPORTS)
async def test_dashboard_routes_are_responsive_and_accessible(
    viewport_name: str,
    viewport: dict[str, int],
    route_prefix: str,
) -> None:
    skip_without_playwright()
    from playwright.async_api import async_playwright

    diag: dict[str, object] = {
        "viewport": viewport_name,
        "registered": False,
        "routes": [],
        "screenshots": [],
        "forbidden": None,
    }

    async with async_playwright() as p:
        launch_options: dict[str, object] = {"headless": True}
        executable_path = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
        if executable_path:
            launch_options["executable_path"] = executable_path

        try:
            browser = await p.chromium.launch(**launch_options)
        except Exception as exc:  # noqa: BLE001
            pytest.skip(
                "无法启动 chromium 浏览器。请运行 `playwright install chromium`。"
                f"原始错误: {exc}"
            )

        context = None
        try:
            context = await browser.new_context(viewport=viewport)
            page = await context.new_page()
            await assert_dev_server_reachable(page)

            _email, _password, register_status = await register_or_login_for_e2e(
                page, "e2e-auth"
            )
            diag["registered"] = register_status in {"created", "exists"}

            await _assert_no_page_horizontal_overflow(page, f"{viewport_name}:initial")
            await _assert_icon_buttons_named(page, f"{viewport_name}:initial")

            for route_key, section_ids in ROUTE_SECTIONS.items():
                await _click_route(page, route_key, route_prefix)
                for section_id in section_ids:
                    await _expect_section(page, section_id)
                await _assert_no_page_horizontal_overflow(page, f"{viewport_name}:{route_key}")
                await _assert_visible_buttons_fit(page, f"{viewport_name}:{route_key}")
                await _assert_icon_buttons_named(page, f"{viewport_name}:{route_key}")
                if route_key in {"overview", "incidents"}:
                    screenshot = await _screenshot(page, f"{viewport_name}-{route_key}")
                    diag["screenshots"].append(screenshot)
                diag["routes"].append(route_key)

            await _assert_keyboard_route_activation(page, "overview", route_prefix)

            visible_text = await _collect_visible_text(page)
            forbidden = _contains_forbidden(visible_text)
            diag["forbidden"] = forbidden
            assert forbidden is None, (
                f"{viewport_name} Dashboard 出现禁止外泄内容(命中模式: {forbidden})。"
                f"前 200 字: {visible_text[:200]!r}"
            )

            print(f"\\n[Responsive E2E 诊断] {diag}")
        except Exception:
            if context is not None:
                page = context.pages[-1] if context.pages else None
                if page is not None:
                    await _screenshot(page, f"{viewport_name}-failure")
            raise
        finally:
            if context is not None:
                await context.close()
            await browser.close()
```

- [ ] **Step 2: 运行 RED**

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_dashboard_responsive_e2e.py -q --tb=short --run-e2e -s
```

预期 RED 示例：

- 移动 route button 可见性/滚动问题。
- 按钮文字溢出。
- icon-only 按钮缺 `title` / `aria-label`。
- 整页横向 overflow。

如果失败在 dev server、浏览器缺失或注册限流而不是 UI/响应式断言，先按 M3-09 helper 路径排除环境问题，不要把环境失败当 RED。

- [ ] **Step 3: 提交 RED**

只在 RED 原因正确时提交：

```powershell
git --literal-pathspecs add -- server/tests/test_dashboard_responsive_e2e.py docs/runs/2026-06-19-m3-11-dashboard-section-responsive-qa.md
git diff --cached --check
git commit -m "test(e2e): 覆盖 dashboard 响应式可达性"
```

---

### Task 2: GREEN - 轻量修复响应式和可访问性缺口

**Files:**

- Modify only as needed:
  - `web-next/components/dashboard/SystemStatusBar.tsx`
  - `web-next/components/dashboard/SectionHeading.tsx`
  - `web-next/components/dashboard/DemoFlowControls.tsx`
  - `web-next/components/dashboard/AlertSection.tsx`
  - `web-next/components/dashboard/AttackLogTable.tsx`
  - `web-next/components/dashboard/CopilotSection.tsx`
  - `web-next/components/dashboard/SystemStatusSection.tsx`
  - `web-next/components/dashboard/IncidentSection.tsx`
  - `web-next/components/dashboard/IncidentDetailPanel.tsx`
  - `web-next/components/dashboard/sections/*.tsx`
  - `web-next/app/dashboard/dashboard-client.tsx`

- [ ] **Step 1: 修复 icon-only 按钮命名**

检查并修复：

- `SystemStatusBar.tsx` 的通知、主题切换、退出登录按钮都必须有 `title` 和 `aria-label`。
- 任何只显示 icon 的刷新、复制、下载、关闭按钮必须有 `title` 或 `aria-label`。

示例：

```tsx
<button
  onClick={toggleTheme}
  className="p-1.5 text-ink-secondary hover:text-ink transition-colors"
  title={theme === "light" ? "切换为深色主题" : "切换为浅色主题"}
  aria-label={theme === "light" ? "切换为深色主题" : "切换为浅色主题"}
  type="button"
>
  {theme === "light" ? <Moon className="w-3.5 h-3.5" /> : <Sun className="w-3.5 h-3.5" />}
</button>
```

- [ ] **Step 2: 修复移动导航和 route button**

要求：

- desktop / mobile route button 都有 `type="button"`。
- mobile nav 容器保留横向滚动，但不能造成页面横向溢出。
- route button 文案使用 `whitespace-nowrap`，不能压坏 header。

示例：

```tsx
<div className="md:hidden border-t border-line-subtle overflow-x-auto max-w-full">
  <div className="flex gap-4 px-4 py-2 min-w-max">
    ...
  </div>
</div>
```

- [ ] **Step 3: 修复 section wrapper 横向溢出**

常见位置：

- `DashboardAiConfigSection.tsx` 中 Base URL / API Key / session row。
- `DashboardWebhookSection.tsx` 中 Webhook URL。
- `IncidentDetailPanel.tsx` 中 incident id、title、summary、linked alert。
- `AttackLogTable.tsx` 中表格。
- `DemoFlowControls.tsx` 中按钮和状态消息。

允许使用：

- `min-w-0`
- `max-w-full`
- `overflow-x-auto`
- `break-words`
- `break-all`（只用于 id/url/token-like preview，不用于普通标题）
- `truncate`
- `flex-wrap`
- `grid-cols-1 md:grid-cols-*`

禁止：

- 用超小字体掩盖溢出。
- 删除文案。
- 删除按钮。
- 用隐藏整个 section 的方式通过测试。

- [ ] **Step 4: 修复按钮文字溢出**

如果 E2E 指出某个按钮 `scrollWidth > clientWidth + 4`：

- 对图标 + 文案按钮，给文本 `span` 加 `truncate` 和父按钮 `min-w-0`。
- 对需要完整可读的按钮，允许 `flex-wrap` 或扩大按钮容器。
- 对移动端工具条，优先让工具条 `flex-wrap`。

示例：

```tsx
<button className="inline-flex min-w-0 items-center gap-1.5 ...">
  <Icon className="w-3 h-3 shrink-0" />
  <span className="truncate">刷新告警</span>
</button>
```

- [ ] **Step 5: 修复键盘可达性**

如果 route button `focus()` + Enter 不切换：

- 确认 button 是原生 `<button type="button">`。
- 不要用 div 模拟 button。
- 不要阻止默认键盘事件。

- [ ] **Step 6: 最小前端验证**

```powershell
cd web-next
npm run typecheck
```

预期：0 TypeScript 错误。

---

### Task 3: GREEN - 跑通响应式 E2E 与关键 E2E

**Files:**

- Modify: `docs/runs/2026-06-19-m3-11-dashboard-section-responsive-qa.md`

- [ ] **Step 1: 响应式 E2E GREEN**

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_dashboard_responsive_e2e.py -q --tb=short --run-e2e -s
```

预期：

- 2 passed（desktop + mobile）。
- 诊断输出包含 `routes=['overview','monitor','incidents','waf','ai','report']`。
- `forbidden=None`。
- `docs/runs/artifacts/m3-11-dashboard-responsive/` 有成功截图。

- [ ] **Step 2: M3-10 route E2E 回归**

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_dashboard_route_sections_e2e.py -q --tb=short --run-e2e -s
```

预期：

- 1 passed。

- [ ] **Step 3: 五条关键 E2E 连续运行**

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\test_auth_session_e2e.py server\tests\test_demo_flow_e2e.py server\tests\test_incident_report_e2e.py server\tests\test_dashboard_route_sections_e2e.py server\tests\test_dashboard_responsive_e2e.py -q --tb=short --run-e2e -s
```

预期：

- 6 passed（Auth 1 + Demo 1 + Incident 1 + Route 1 + Responsive 2）。
- 不需要重启 dev server。
- Incident Report 仍直接等待 `incident-detail-panel`。

---

### Task 4: 全量质量门

**Files:**

- Modify: `docs/runs/2026-06-19-m3-11-dashboard-section-responsive-qa.md`

- [ ] **Step 1: 默认后端全量**

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

预期：

- E2E 默认 skip。
- 不出现新增失败。

- [ ] **Step 2: Guardrails 专项**

```powershell
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

预期：

- 与 M3-10 baseline 一致，无回归。

- [ ] **Step 3: 前端 typecheck/build，必须顺序执行**

```powershell
cd web-next
npm run typecheck
npm run build
```

注意：不得并行运行 `npm run typecheck` 与 `npm run build`。

---

### Task 5: IMPROVE - De-sloppify 与安全审查

**Files:**

- All touched files

- [ ] **Step 1: 搜索新增风险**

```powershell
rg -n "console\\.log|localStorage|sessionStorage|innerHTML|dangerouslySetInnerHTML|useIncidents\\(|useAlerts\\(" web-next\app\dashboard web-next\components\dashboard web-next\constants server\tests\test_dashboard_responsive_e2e.py
```

要求：

- 不得新增 `console.log`。
- 不得新增 storage token。
- 不得使用 `innerHTML` / `dangerouslySetInnerHTML`。
- `useIncidents(` 和 `useAlerts(` 只能出现在父层或 hook 文件，不能出现在 section 内。

- [ ] **Step 2: 检查 screenshot 大小**

```powershell
Get-ChildItem -LiteralPath docs\runs\artifacts\m3-11-dashboard-responsive -File | Select-Object Name,Length
```

如果总大小超过 5 MB：

- 不要 stage 截图。
- 在 run log 写明本地路径和总大小。

如果总大小不超过 5 MB：

- 可以 stage 截图作为证据。

- [ ] **Step 3: 检查 diff 范围**

```powershell
git diff --stat
git diff -- web-next\components\dashboard web-next\app\dashboard server\tests\test_dashboard_responsive_e2e.py
```

确认：

- 没有认证/后端/security/schema 代码改动。
- 没有 `.coverage`。
- 没有真实 env。
- 没有 token/password/cookie 输出。

- [ ] **Step 4: 前端安全自审写入 run log**

必须写明：

- 未改后端 auth。
- 未改 Guardrails。
- 未改 SSRF。
- 未改 DB schema。
- 未新增 API / npm 依赖。
- E2E helper 仍走 httpOnly cookie path。
- UI 修复仅限布局/可访问性。
- 未写 storage / dangerous HTML。

---

### Task 6: 文档同步

**Files:**

- Modify: `docs/runs/2026-06-19-m3-11-dashboard-section-responsive-qa.md`
- Modify: `docs/agent/UNATTENDED_LONG_TASKS.md`
- Modify: `PRODUCT.md`
- Modify: `docs/plans/M2_PRODUCT_ROADMAP.md`

- [ ] **Step 1: 更新 run log 最终状态**

必须包含：

- 改动摘要。
- RED 原因。
- GREEN 修复点。
- 桌面/移动 E2E 结果。
- 截图/证据路径与大小。
- 五条关键 E2E 连续结果。
- 后端全量 / Guardrails / 前端 typecheck/build 结果。
- 安全边界说明。
- 下一条建议工单。

- [ ] **Step 2: 更新 `UNATTENDED_LONG_TASKS.md`**

必须：

- 把 `M3_11_DASHBOARD_SECTION_RESPONSIVE_QA_TASK.md` 加入可用超长任务列表。
- 把 M3-11 条目标记为已交付。
- 把推荐启动口令更新为下一条建议工单。

- [ ] **Step 3: 更新 `PRODUCT.md` 与路线图**

必须记录：

- M3-11 已完成桌面/移动 Dashboard section 响应式 QA。
- 新增 E2E 覆盖 route、section、横向溢出、按钮溢出、ARIA、键盘可达性、DOM forbidden sentinel。
- 截图证据路径。
- 未改 auth/Guardrails/SSRF/DB schema。

---

## 5. 提交策略

禁止使用 `git add .`。

提交前必须运行：

```powershell
git status --short
git diff --cached --check
git diff --cached --name-only
```

不得 stage：

- `.coverage`
- `.claude/settings.local.json`
- `.env`
- 数据库文件
- 密钥 / 证书 / token

建议 commit 拆分：

1. `test(e2e): 覆盖 dashboard 响应式可达性`
   - `server/tests/test_dashboard_responsive_e2e.py`
   - run log RED 阶段

2. `fix(dashboard): 收口 section 响应式与可访问性`
   - 仅包含必要 UI 修复文件

3. `docs(dashboard): 记录 section 响应式 QA 收口`
   - run log
   - `docs/agent/UNATTENDED_LONG_TASKS.md`
   - `PRODUCT.md`
   - `docs/plans/M2_PRODUCT_ROADMAP.md`
   - 截图证据（仅当总大小不超过 5 MB）

通过全部质量门后可 push：

```powershell
git push origin main
```

---

## 6. 停止条件

满足任一条件必须停止并写清楚阻塞：

1. 新增响应式 E2E 同一断言失败 3 轮仍无法收口。
2. 为通过响应式 QA 需要重做视觉设计或大改布局信息架构。
3. 为通过测试需要修改认证/授权/Guardrails/SSRF/DB schema。
4. 需要新增 npm 依赖。
5. 需要删除现有 E2E 断言或扩大 skip/xfail。
6. Playwright / dev server 环境不可用且无法本地恢复。
7. 截图证据显示移动端布局明显重叠，但修复会超过轻量 UI 范围。
8. diff 超过约 700 行且主要不是测试/文档/轻量 class 修复。
9. 发现真实 secret / token / env 被改动或出现在 diff 中。

停止时必须交付：

- 已完成内容。
- 未完成内容。
- 阻塞证据。
- 建议下一条最小工单。

---

## 7. 最终报告模板

完成后按这个格式输出：

```markdown
完成状态：完成 / 部分完成 / 阻塞

改动摘要：
- ...

关键文件：
- ...

验证：
- `pytest server/tests/test_dashboard_responsive_e2e.py --run-e2e` -> ...
- `pytest server/tests/test_dashboard_route_sections_e2e.py --run-e2e` -> ...
- `pytest server/tests/test_auth_session_e2e.py server/tests/test_demo_flow_e2e.py server/tests/test_incident_report_e2e.py server/tests/test_dashboard_route_sections_e2e.py server/tests/test_dashboard_responsive_e2e.py --run-e2e` -> ...
- `pytest server/tests` -> ...
- `pytest server/tests/security/llm_guardrails` -> ...
- `npm run typecheck` -> ...
- `npm run build` -> ...

截图证据：
- ...

安全边界：
- 未改认证/授权/Guardrails/SSRF/DB schema。
- 未写 localStorage/sessionStorage/DOM token。
- 未提交 `.coverage` / env / 数据库 / 密钥。

运行日志：
- `docs/runs/2026-06-19-m3-11-dashboard-section-responsive-qa.md`

Commit / Push：
- ...

下一条建议工单：
- ...
```
