# M3 Agent Ops and Push Readiness Task

> Task level: L5 unattended closing task.
> Scenario: M3 Demo-Ready SOC workbench has already been implemented, verified, and split into commits locally. The remaining work is to preserve the long-task operating docs, re-audit the commit stack, run the final quality gate, and push only if the repository is clean enough.
> Language: reply in Chinese.

---

## 0. Required Reading

Before touching files, read these documents completely:

- `AGENTS.md`
- `CLAUDE.md`
- `PRODUCT.md`
- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/agent/M3_DEMO_READY_SOC_WORKBENCH_CLOSING_TASK.md`
- `docs/runs/2026-06-16-m3-demo-ready-soc-workbench.md`
- this file

If any instruction conflicts, follow the more specific safety rule. Do not skip the project rule that all user-facing replies and commit messages must be Chinese.

---

## 1. Goal

Turn the current local M3 state into a durable, pushed baseline:

1. Confirm the four existing M3 commits are present and do not include local noise files.
2. Add the long-task operating docs to the repository with a separate documentation commit.
3. Re-run the final verification matrix after the documentation commit.
4. Confirm only acceptable local noise remains.
5. Push `main` to `origin/main` only after all checks pass.

This is not a quick push task. Treat it as a full release-readiness audit.

---

## 2. Budget

- Mode: L5 unattended closing task.
- Max runtime: 2 hours.
- Max repair attempts for the same failure: 3.
- Stop if the fix would require changing authentication, authorization, guardrails, database schema, deployment secrets, or git history.
- Stop if validation cannot be run locally for reasons you cannot fix without external login or production secrets.

---

## 3. Allowed Changes

You may edit or stage only these files:

- `docs/agent/UNATTENDED_LONG_TASKS.md`
- `docs/agent/M3_DEMO_READY_SOC_WORKBENCH_CLOSING_TASK.md`
- `docs/agent/M3_AGENT_OPS_AND_PUSH_READINESS_TASK.md`
- a new run log under `docs/runs/`

You may create exactly one new run log:

- `docs/runs/2026-06-16-m3-agent-ops-and-push-readiness.md`

---

## 4. Forbidden Changes

Do not modify, stage, commit, or push these files:

- `.coverage`
- `.claude/settings.local.json`
- any real `.env`
- database files
- generated caches
- build output

Forbidden operations:

- Do not use `git add .`.
- Do not run `git reset --hard`, `git clean`, or history rewriting commands.
- Do not weaken, skip, or delete tests to make the build pass.
- Do not push if any forbidden file is staged.
- Do not push if validation fails.

---

## 5. Expected Starting Point

The expected local state is:

- Branch: `main`
- Local branch: ahead of `origin/main` by 4 M3 commits.
- Existing M3 commits should include these messages:
  - `test(e2e): 修复 Demo Flow 浏览器验收链路`
  - `chore(dashboard): 增加简报派生类型与状态壳`
  - `feat(dashboard): 拆分 SOC 工作台组件并增强告警体验`
  - `docs: 记录 M3 Demo-Ready SOC 工作台收口`
- Expected uncommitted files:
  - `.coverage`
  - `.claude/settings.local.json`
  - `docs/agent/UNATTENDED_LONG_TASKS.md`
  - `docs/agent/M3_DEMO_READY_SOC_WORKBENCH_CLOSING_TASK.md`
  - `docs/agent/M3_AGENT_OPS_AND_PUSH_READINESS_TASK.md`

If the actual state differs, inspect before acting and document the difference in the run log.

---

## 6. Phase Plan

### Phase 1: Create the Run Log

Create or update:

```text
docs/runs/2026-06-16-m3-agent-ops-and-push-readiness.md
```

Record:

- start time
- current branch
- initial `git status --short --branch`
- task budget
- planned phases

Update this log after every phase.

### Phase 2: Git Stack Audit

Run:

```powershell
git status --short --branch
git diff --cached --name-only
git log --oneline origin/main..HEAD
git log --name-only --format="commit %h %s" origin/main..HEAD -- .coverage .claude/settings.local.json
```

Acceptance:

- staged area is empty
- existing M3 commits do not include `.coverage` or `.claude/settings.local.json`
- no unexpected business-code changes are uncommitted

### Phase 3: Documentation Coherence Audit

Read the docs being added and confirm:

- `UNATTENDED_LONG_TASKS.md` states that future agent tasks should default to L4/L5 long tasks.
- `M3_DEMO_READY_SOC_WORKBENCH_CLOSING_TASK.md` accurately describes the M3 closing task and explicitly forbids push.
- this file describes the next push-readiness task and explicitly allows push only after validation passes.

If `UNATTENDED_LONG_TASKS.md` does not reference this file, add a short bullet for it under the reusable long-task documents section.

### Phase 4: Stage and Commit Only Agent-Ops Docs

Stage with exact paths only:

```powershell
git add -- docs/agent/UNATTENDED_LONG_TASKS.md docs/agent/M3_DEMO_READY_SOC_WORKBENCH_CLOSING_TASK.md docs/agent/M3_AGENT_OPS_AND_PUSH_READINESS_TASK.md docs/runs/2026-06-16-m3-agent-ops-and-push-readiness.md
git diff --cached --name-only
```

Before committing, confirm the staged file list contains only those four paths. If any forbidden file appears, unstage it and stop.

Commit message:

```text
docs(agent): 固化超长任务默认工作流
```

### Phase 5: Final Verification Matrix

Run these checks in order. Do not run `npm run typecheck` and `npm run build` in parallel because `.next/types` can race.

```powershell
node docs\runs\2026-06-16-m3-verify-briefing-buckets.mjs
cd web-next
npm run typecheck
npm run build
cd ..
$env:APP_SECRET='test-local-secret-key-for-baseline-32chars'
$env:AUTH_SECRET='test-local-auth-secret-for-baseline-32chars'
.venv\Scripts\python.exe -m pytest server\tests -q --tb=short
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
.venv\Scripts\python.exe -m pytest server\tests\test_demo_flow_e2e.py --run-e2e -q -rs --tb=short
git diff --check
```

If the explicit browser E2E cannot run because Chrome is absent, record that as a local-environment limitation. Do not claim it passed. If Chrome exists and the E2E fails, repair only within the already authorized M3 files, or stop if the repair would exceed scope.

### Phase 6: Push Gate

Run:

```powershell
git status --short --branch
git log --oneline origin/main..HEAD
git diff --cached --name-only
git log --name-only --format="commit %h %s" origin/main..HEAD -- .coverage .claude/settings.local.json
```

Push only if all are true:

- validation matrix passed or any skipped browser E2E is explicitly justified by missing local browser only
- staged area is empty
- `.coverage` and `.claude/settings.local.json` are not in any local commit
- uncommitted files are only acceptable local noise
- `origin/main..HEAD` contains the four M3 commits plus the docs-agent commit

If all gates pass:

```powershell
git push origin main
```

After push:

```powershell
git status --short --branch
git rev-parse HEAD
git ls-remote origin refs/heads/main
```

Confirm local `HEAD` matches remote `origin/main`.

---

## 7. Stop Conditions

Stop and report instead of pushing if:

- any validation command fails after 3 focused repair attempts
- forbidden files are staged or committed
- branch is not `main`
- remote branch has advanced and requires reconciliation
- local changes include business code not covered by this task
- pushing would require credentials, login, or external confirmation not already available

---

## 8. Final Report

When done, report in Chinese:

- status: completed / partially completed / blocked
- commits pushed, with hashes and messages
- verification commands and results
- final `git status --short --branch`
- final local HEAD and remote HEAD
- run log path
- any remaining local noise files

