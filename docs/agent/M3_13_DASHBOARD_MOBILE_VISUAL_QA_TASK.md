# M3-13 Dashboard Mobile Visual QA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 M3-11 移动端截图证据，把 Dashboard 移动 viewport 的可读性、统计卡片密度、section 间距和导航体验收口成可重复验证的视觉 QA。

**Architecture:** 先新增一个移动视觉 E2E，只在 390x844 / 430x932 viewport 下检查 Dashboard `overview` 与 `incidents`：统计卡片不能产生大面积空白块，section 顶部间距不能过大，移动导航当前 tab 必须可见，整页仍无横向溢出和 forbidden sentinel。再做轻量 Tailwind class 修复，优先集中在 `StatsCards.tsx`、`SystemStatusBar.tsx` 和 Dashboard section wrapper，禁止重做视觉设计、迁移状态管理或修改业务/安全后端。最后保存新截图证据并同步产品/无人值守文档。

**Tech Stack:** Next.js App Router, React Client Components, Tailwind CSS utility classes, pytest, Playwright async Python API, existing `server/tests/e2e_helpers.py`.

---

## 0. 背景

M3-11 已完成响应式 QA，但移动截图仍暴露可读性和空间利用问题：

- `docs/runs/artifacts/m3-11-dashboard-responsive/mobile-overview.png`：顶部移动 nav 横向滚动可用，但 item 字号/间距偏弱；下方统计卡片与简报区之间纵向节奏偏松。
- `docs/runs/artifacts/m3-11-dashboard-responsive/mobile-incidents.png`：`incidents` route 的统计区出现一大块空白色块，像桌面 2x2 stats grid 在移动端没有被压紧。
- 两张截图左下有一个圆形 `N` 浮层，疑似浏览器/开发工具注入；本任务要记录它是否来自应用 DOM。若是外部 overlay，不要修应用代码，只在 run log 中解释。

本任务不是重做视觉设计；目标是移动端“像产品”，但改动必须克制、可测、有截图证据。

---

## 1. 必读上下文

执行前完整阅读：

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/runs/2026-06-19-m3-11-dashboard-section-responsive-qa.md`
- `docs/runs/2026-06-19-m3-12-demo-flow-e2e-stability.md`
- `docs/agent/M3_13_DASHBOARD_MOBILE_VISUAL_QA_TASK.md`
- `server/tests/e2e_helpers.py`
- `server/tests/test_dashboard_responsive_e2e.py`
- `web-next/components/dashboard/StatsCards.tsx`
- `web-next/components/dashboard/SystemStatusBar.tsx`
- `web-next/components/dashboard/SectionHeading.tsx`
- `web-next/components/dashboard/BriefingSection.tsx`
- `web-next/components/dashboard/IncidentSection.tsx`
- `web-next/components/dashboard/IncidentList.tsx`
- `web-next/components/dashboard/IncidentDetailPanel.tsx`
- `web-next/components/dashboard/sections/DashboardBriefingSection.tsx`
- `web-next/components/dashboard/sections/DashboardIncidentWorkspaceSection.tsx`
- `web-next/components/dashboard/sections/DashboardAlertWorkspaceSection.tsx`
- `web-next/components/dashboard/sections/*.tsx`

启动时创建运行日志：

```text
docs/runs/2026-06-19-m3-13-dashboard-mobile-visual-qa.md
```

运行日志必须记录：

- 当前 git status / 最近 commit
- M3-11 两张移动截图观察
- 真实 dev server 状态
- 每轮 E2E / typecheck / build 结果
- 新截图路径和文件大小
- 是否发现 `N` 浮层来自应用 DOM
- 精确 staged set / push 结果

---

## 2. 边界

允许修改：

- `server/tests/test_dashboard_mobile_visual_e2e.py`（新增）
- `web-next/components/dashboard/StatsCards.tsx`
- `web-next/components/dashboard/SystemStatusBar.tsx`
- `web-next/components/dashboard/SectionHeading.tsx`
- `web-next/components/dashboard/sections/*.tsx`
- `web-next/components/dashboard/BriefingSection.tsx`
- `web-next/components/dashboard/IncidentSection.tsx`
- `web-next/components/dashboard/IncidentList.tsx`
- `web-next/components/dashboard/IncidentDetailPanel.tsx`
- `docs/runs/2026-06-19-m3-13-dashboard-mobile-visual-qa.md`
- `docs/runs/artifacts/m3-13-dashboard-mobile-visual/**`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

禁止修改：

- `server/services/auth_service.py`
- `server/core/auth*`
- `server/routers/auth*`
- `server/security/**`
- `server/analyzer.py`
- `server/core/utils.py`
- `server/core/config.py`
- Alembic migration / DB schema
- 后端 API contract
- npm 依赖
- rate limit 常量
- `.env` / `.coverage` / 数据库 / 密钥

禁止行为：

- 不要把移动端改成全新视觉风格。
- 不要删除 M3-11 / M3-12 的 E2E 断言。
- 不要为了截图漂亮伪造数据。
- 不要隐藏真实 DOM 泄漏或横向溢出。
- 不要使用 `git add .`。

---

## 3. 成功标准

必须全部满足：

1. 新增 `server/tests/test_dashboard_mobile_visual_e2e.py`，默认 `pytest server/tests` skip，只有 `--run-e2e` 执行。
2. 在 `390x844` 与 `430x932` 两个移动 viewport 下，`overview` 与 `incidents` route 都保存截图。
3. `dashboard-section-stats` 可见，且 stats grid 的移动高度受控：高度不得超过 viewport 高度的 42%，不得出现单个 stats 区块高度超过 160px 的大空白。
4. `dashboard-section-briefing` 与上一 section 的垂直间距受控：移动端 section gap 不得超过 64px。
5. 当前 active 移动 nav button 必须在水平滚动容器可见区域内，切换到 `incidents` 后也要可见。
6. 页面 `scrollWidth <= clientWidth + 4`。
7. 可见文字不能出现 forbidden sentinel。
8. 如果发现圆形 `N` 浮层来自应用 DOM，必须修掉；如果来自浏览器/插件/外部 overlay，运行日志记录检测证据，不改应用代码。
9. M3-11 responsive E2E、M3-12 Demo Flow stability E2E、后端全量、Guardrails、前端 typecheck/build 通过。
10. 文档同步，精确 commit/push，工作区只允许保留本地生成物（如 `.coverage`，但不能提交）。

---

## 4. Task 1 RED：新增移动视觉 E2E

**Files:**

- Create: `server/tests/test_dashboard_mobile_visual_e2e.py`
- Modify: `docs/runs/2026-06-19-m3-13-dashboard-mobile-visual-qa.md`

- [ ] **Step 1: 创建测试文件**

创建 `server/tests/test_dashboard_mobile_visual_e2e.py`：

```python
"""M3-13 Dashboard mobile visual QA E2E（可选，需 --run-e2e）。

目标：
- 基于 M3-11 截图暴露的移动端统计卡片空白、section 间距和 nav 可读性问题，
  给出浏览器级尺寸断言和截图证据。
- 只验证真实 DOM 和真实布局，不伪造数据。
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

BASE = os.getenv("E2E_BASE_URL", "http://localhost:3000")
ARTIFACT_DIR = Path("docs/runs/artifacts/m3-13-dashboard-mobile-visual")

VIEWPORTS: tuple[tuple[str, dict[str, int]], ...] = (
    ("mobile-390", {"width": 390, "height": 844}),
    ("mobile-430", {"width": 430, "height": 932}),
)

ROUTES: tuple[str, ...] = ("overview", "incidents")

_FORBIDDEN_DOM_PATTERNS: tuple[re.Pattern[str], ...] = (
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


async def _click_mobile_route(page, route: str) -> None:
    button = page.locator(f'[data-testid="dashboard-route-mobile-{route}"]').first
    await button.wait_for(state="visible", timeout=15000)
    await button.scroll_into_view_if_needed(timeout=5000)
    await button.click()
    await page.wait_for_timeout(250)
    active = await button.get_attribute("aria-current")
    assert active == "page", f"{route} mobile nav should be active, got {active!r}"


async def _expect_no_page_horizontal_overflow(page) -> None:
    metrics = await page.evaluate(
        """
        () => ({
            scrollWidth: document.documentElement.scrollWidth,
            clientWidth: document.documentElement.clientWidth,
        })
        """
    )
    assert metrics["scrollWidth"] <= metrics["clientWidth"] + 4, (
        f"page horizontal overflow: {metrics}"
    )


async def _expect_active_mobile_tab_visible(page, route: str) -> None:
    result = await page.evaluate(
        """
        (route) => {
            const button = document.querySelector(`[data-testid="dashboard-route-mobile-${route}"]`);
            const scroller = button?.closest('.overflow-x-auto');
            if (!button || !scroller) return { ok: false, reason: 'missing' };
            const b = button.getBoundingClientRect();
            const s = scroller.getBoundingClientRect();
            const visible = b.left >= s.left - 2 && b.right <= s.right + 2;
            return {
                ok: visible,
                buttonLeft: b.left,
                buttonRight: b.right,
                scrollerLeft: s.left,
                scrollerRight: s.right,
                text: button.textContent,
            };
        }
        """,
        route,
    )
    assert result["ok"], f"active mobile tab is not fully visible: {result}"


async def _expect_mobile_stats_density(page, viewport_height: int) -> None:
    result = await page.evaluate(
        """
        () => {
            const statsSection = document.querySelector('[data-testid="dashboard-section-stats"]');
            if (!statsSection) return { ok: false, reason: 'missing stats section' };
            const grid = statsSection.querySelector('.grid');
            const cards = Array.from(statsSection.querySelectorAll('.grid > div'));
            const sectionRect = statsSection.getBoundingClientRect();
            const gridRect = grid ? grid.getBoundingClientRect() : sectionRect;
            const cardRects = cards.map((card) => {
                const rect = card.getBoundingClientRect();
                const text = (card.textContent || '').trim();
                return { height: rect.height, width: rect.width, text };
            });
            return {
                ok: true,
                sectionHeight: sectionRect.height,
                gridHeight: gridRect.height,
                cardRects,
            };
        }
        """
    )
    assert result["ok"], result
    max_card_height = max((item["height"] for item in result["cardRects"]), default=0)
    assert result["gridHeight"] <= viewport_height * 0.42, (
        f"mobile stats grid too tall: {result}"
    )
    assert max_card_height <= 160, f"mobile stat card too tall: {result}"


async def _expect_mobile_section_gap(page) -> None:
    result = await page.evaluate(
        """
        () => {
            const stats = document.querySelector('[data-testid="dashboard-section-stats"]');
            const briefing = document.querySelector('[data-testid="dashboard-section-briefing"]');
            if (!stats || !briefing) return { ok: false, reason: 'missing section' };
            const a = stats.getBoundingClientRect();
            const b = briefing.getBoundingClientRect();
            return { ok: true, gap: b.top - a.bottom, statsBottom: a.bottom, briefingTop: b.top };
        }
        """
    )
    assert result["ok"], result
    assert result["gap"] <= 64, f"mobile section gap too large: {result}"


async def _detect_n_overlay(page) -> dict:
    return await page.evaluate(
        """
        () => {
            const candidates = Array.from(document.querySelectorAll('body *'))
                .map((node) => {
                    const rect = node.getBoundingClientRect();
                    const text = (node.textContent || '').trim();
                    const style = window.getComputedStyle(node);
                    return {
                        tag: node.tagName,
                        text,
                        left: rect.left,
                        top: rect.top,
                        width: rect.width,
                        height: rect.height,
                        position: style.position,
                        zIndex: style.zIndex,
                        className: String(node.className || ''),
                    };
                })
                .filter((item) => {
                    return item.text === 'N'
                        && item.width >= 24
                        && item.width <= 60
                        && item.height >= 24
                        && item.height <= 60
                        && item.left <= 80;
                });
            return { count: candidates.length, candidates };
        }
        """
    )


async def _screenshot(page, name: str) -> str:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / f"{name}.png"
    await page.screenshot(path=str(path), full_page=True)
    return str(path)


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.parametrize(("viewport_name", "viewport"), VIEWPORTS)
async def test_dashboard_mobile_visual_density(viewport_name: str, viewport: dict[str, int]) -> None:
    skip_without_playwright()
    from playwright.async_api import async_playwright

    diag: dict[str, object] = {
        "viewport": viewport_name,
        "routes": [],
        "screenshots": [],
        "n_overlay": None,
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

        try:
            context = await browser.new_context(viewport=viewport)
            page = await context.new_page()
            await assert_dev_server_reachable(page)
            await register_or_login_for_e2e(page, f"e2e-mobile-visual-{viewport_name}")

            for route in ROUTES:
                await _click_mobile_route(page, route)
                await page.locator('[data-testid="dashboard-section-stats"]').first.wait_for(
                    state="visible",
                    timeout=15000,
                )
                await _expect_active_mobile_tab_visible(page, route)
                await _expect_no_page_horizontal_overflow(page)
                await _expect_mobile_stats_density(page, int(viewport["height"]))
                await _expect_mobile_section_gap(page)
                diag["routes"].append(route)
                diag["screenshots"].append(
                    await _screenshot(page, f"{viewport_name}-{route}")
                )

            overlay = await _detect_n_overlay(page)
            diag["n_overlay"] = overlay
            assert overlay["count"] == 0, (
                "Found app DOM that looks like the circular N overlay. "
                f"If this is browser/plugin injected, document evidence and update the test. {overlay}"
            )

            visible_text = await _collect_visible_text(page)
            forbidden = _contains_forbidden(visible_text)
            diag["forbidden"] = forbidden
            assert forbidden is None, (
                f"Dashboard mobile visual QA 出现禁止外泄内容(命中模式: {forbidden})。"
                f"前 200 字: {visible_text[:200]!r}"
            )

            print(f"\n[E2E 诊断] {diag}")
        finally:
            await context.close()
            await browser.close()
```

- [ ] **Step 2: 跑 RED**

运行：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_dashboard_mobile_visual_e2e.py -q --tb=short --run-e2e -s
```

预期：至少一个断言失败，通常是 `mobile stats grid too tall`、`mobile stat card too tall` 或 `mobile section gap too large`。如果全部通过，也保留测试并进入 IMPROVE，只做截图和文档同步；不要为了制造失败乱改阈值。

---

## 5. Task 2 GREEN：移动端 stats 与 section 密度修复

**Files:**

- Modify: `web-next/components/dashboard/StatsCards.tsx`
- Modify if needed: `web-next/components/dashboard/sections/DashboardBriefingSection.tsx`
- Modify if needed: `web-next/components/dashboard/sections/DashboardIncidentWorkspaceSection.tsx`
- Modify if needed: `web-next/components/dashboard/sections/*.tsx`

- [ ] **Step 1: 压紧 stats card 移动 padding 和字号**

优先在 `StatsCards.tsx` 做最小 class 调整：

```tsx
<div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-line border border-line" data-testid="stats-card-grid">
```

每个 card 改为：

```tsx
className="bg-bg-raised p-4 sm:p-6 md:p-8 min-h-[118px] sm:min-h-[132px] md:min-h-0"
```

header 间距改为：

```tsx
<div className="flex items-baseline justify-between mb-4 sm:mb-6 gap-3">
```

label 加宽度保护：

```tsx
<span className="text-[10px] font-mono uppercase tracking-[0.12em] sm:tracking-[0.15em] text-ink-tertiary text-right break-words">
```

value 字号改为：

```tsx
className={`font-display text-2xl sm:text-3xl md:text-5xl tracking-tight tabular-nums leading-none break-words ...`}
```

注意：不要改 `useCountUp` 或 stats 数据来源。

- [ ] **Step 2: 压紧移动 section 顶部间距**

如果 RED 是 section gap，允许把 route section wrapper 的移动 `mt-14` 改为 `mt-8 sm:mt-14`。优先改实际失败的文件，不要全量机械改。

示例：

```tsx
<div className="mt-8 sm:mt-14" data-testid="dashboard-section-briefing">
```

和：

```tsx
<div className="mt-8 sm:mt-14" data-testid="dashboard-section-incidents">
```

- [ ] **Step 3: 跑 GREEN**

运行：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_dashboard_mobile_visual_e2e.py -q --tb=short --run-e2e -s
```

期望：`2 passed`（两个 viewport）。

---

## 6. Task 3 GREEN：移动 nav 可读性与 overlay 判断

**Files:**

- Modify if needed: `web-next/components/dashboard/SystemStatusBar.tsx`
- Modify: `docs/runs/2026-06-19-m3-13-dashboard-mobile-visual-qa.md`

- [ ] **Step 1: 如果 active mobile nav 不完全可见**

如果测试报 active tab 不在可见区域，修改 `SystemStatusBar.tsx` 的移动 nav click 行为不要在组件里手动 scroll；测试已执行 `scroll_into_view_if_needed`。只有当 DOM 结构导致按钮不可滚动时，改 class：

```tsx
<div className="md:hidden border-t border-line-subtle overflow-x-auto overscroll-x-contain">
  <div className="flex gap-3 px-4 py-2 min-w-max">
```

按钮 class 可从：

```tsx
className="... tracking-[0.15em] ... gap-1.5 whitespace-nowrap"
```

调整为：

```tsx
className="... tracking-[0.08em] ... gap-1 whitespace-nowrap"
```

不要隐藏任何 route，不要删 `data-testid` / `aria-current`。

- [ ] **Step 2: 判断 `N` overlay**

如果 `_detect_n_overlay` 失败：

1. 先看诊断里 `className` / `tag` / `position`。
2. 如果候选元素属于应用代码（例如在 `web-next/**` 可搜索到相关 class/text），修应用代码。
3. 如果候选来自 Playwright/浏览器/插件注入，而不是应用 DOM，则把测试改为记录 overlay 但不 fail，并在 run log 说明证据。

允许的测试调整：

```python
diag["n_overlay"] = overlay
# External browser overlays are not part of app DOM in CI; if candidates are
# empty in DOM, the screenshot artifact alone is not a product failure.
assert overlay["count"] == 0, ...
```

不要为了通过而移除真实应用浮层断言。

- [ ] **Step 3: 重跑移动视觉 E2E**

运行：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_dashboard_mobile_visual_e2e.py -q --tb=short --run-e2e -s
```

---

## 7. Task 4：回归矩阵

按顺序运行：

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_dashboard_mobile_visual_e2e.py -q --tb=short --run-e2e -s
```

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_dashboard_responsive_e2e.py -q --tb=short --run-e2e -s
```

```powershell
.venv\Scripts\python.exe -m pytest server\tests\test_auth_session_e2e.py server\tests\test_demo_flow_e2e.py server\tests\test_incident_report_e2e.py server\tests\test_dashboard_route_sections_e2e.py server\tests\test_dashboard_responsive_e2e.py server\tests\test_demo_flow_stability_e2e.py server\tests\test_dashboard_mobile_visual_e2e.py -q --tb=short --run-e2e -s
```

期望：

- Mobile visual：`2 passed`
- Responsive：`2 passed`
- 七组关键 E2E：`9 passed`（Auth 1 + Demo 1 + Incident 1 + Route 1 + Responsive 2 + Demo stability 1 + Mobile visual 2）

如果因为 M3-12 记录的 Guardrails moderation pool 退化导致 Copilot E2E 失败，按 M3-12 run log 处理：重启 dev backend 后重跑，并在本 run log 记录；不要改 Guardrails。

---

## 8. Task 5：全量质量门

按顺序运行：

```powershell
.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
```

```powershell
.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short
```

```powershell
cd web-next
npm run typecheck
```

```powershell
cd web-next
npm run build
```

要求：

- `pytest server/tests` 默认 skip E2E，不 collection fail。
- Guardrails 不回归。
- `npm run typecheck` 和 `npm run build` 顺序运行，不并行。
- build 后如 dev server 进入 production `.next` 状态，重启 dev server 并记录，不要提交 `.next`。

---

## 9. Task 6：视觉证据与安全检查

检查截图：

```powershell
Get-ChildItem -Path docs\runs\artifacts\m3-13-dashboard-mobile-visual -File | Select-Object Name,Length
```

期望：

- `mobile-390-overview.png`
- `mobile-390-incidents.png`
- `mobile-430-overview.png`
- `mobile-430-incidents.png`
- 总量小于 5 MB。

扫描：

```powershell
rg -n "console\.log|localStorage|sessionStorage|innerHTML|dangerouslySetInnerHTML|useIncidents\(|useAlerts\(|REGISTER_RATE_LIMIT|COPILOT_RATE_LIMIT|pytest\.skip|xfail" server\tests\test_dashboard_mobile_visual_e2e.py web-next\components\dashboard web-next\app\dashboard web-next\constants server\core server\security
```

要求：

- 不新增生产 `console.log`。
- 不新增 storage / dangerous HTML。
- 不新增业务 hook 重复实例。
- 不改 rate limit。
- 不触碰 `server/security/**`。
- `pytest.skip` 只允许缺浏览器前置 skip。

---

## 10. Task 7：文档同步

更新：

- `docs/runs/2026-06-19-m3-13-dashboard-mobile-visual-qa.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `PRODUCT.md`
- `docs/plans/M2_PRODUCT_ROADMAP.md`

必须写清：

- M3-13 是移动视觉 QA 与轻量布局修复，不是业务功能。
- 修复前问题来自 M3-11 `mobile-overview.png` / `mobile-incidents.png`。
- 新截图证据路径和大小。
- E2E / 后端 / Guardrails / 前端验证数字。
- 未改认证/授权、Guardrails、SSRF、DB schema、后端 API、npm 依赖、rate limit。
- 下一条建议工单更新为 M3-14 候选，不再指向 M3-13。

---

## 11. 精确 commit 策略

严禁 `git add .`。

建议拆 3 个 commit：

1. `test(e2e): 覆盖 dashboard 移动视觉密度`
   - `server/tests/test_dashboard_mobile_visual_e2e.py`

2. `fix(dashboard): 收口移动端统计与间距`
   - `web-next/components/dashboard/StatsCards.tsx`
   - 失败驱动需要修改的 section / nav 文件

3. `docs(dashboard): 记录移动视觉 QA 收口`
   - run log
   - screenshots
   - task doc
   - `UNATTENDED_LONG_TASKS.md`
   - `PRODUCT.md`
   - `docs/plans/M2_PRODUCT_ROADMAP.md`

提交前必须运行：

```powershell
git status --short
git diff --check
git diff --cached --check
git diff --cached --name-only
```

确认 staged set 不含：

- `.coverage`
- `.env` / `.env.local` / `web-next/.env*`
- `*.db` / `*.sqlite`
- `*.key` / `*.pem` / `*.p12`
- 真实 token / secret

通过后 push：

```powershell
git push origin main
```

---

## 12. 停止条件

遇到以下情况必须停止：

- 移动视觉问题需要重做整体设计系统，而不是轻量 class 修复。
- 需要修改认证/授权、Guardrails、SSRF、DB schema、后端 API 或 rate limit。
- E2E 必须靠删断言、skip、xfail 才能通过。
- 截图或 artifact 出现真实 secret/token。
- 同一失败连续 3 轮仍无法定位。

---

## 13. 最终报告模板

```text
M3-13 Dashboard 移动视觉 QA 收口完成。

变更：
- 测试：
- UI：
- 文档：
- 截图：

验证：
- Mobile visual E2E：
- Responsive E2E：
- 七组关键 E2E：
- 后端全量：
- Guardrails：
- 前端 typecheck/build：

安全边界：
- 未改 auth / Guardrails / SSRF / DB schema / API / rate limit：
- 未提交 .coverage / env / DB / 密钥：

提交：
- commit 列表：
- push 状态：

下一条建议工单：
- ...
```

