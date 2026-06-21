"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clipboard,
  Info,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import type { SiteTargetState } from "@/components/dashboard/SystemStatusSection";

type RunbookTone = "ok" | "warn" | "manual" | "blocked";

interface RunbookCheckItem {
  id: string;
  title: string;
  status: string;
  tone: RunbookTone;
  detail: string;
}

export interface OperationalRunbookPanelProps {
  siteState: SiteTargetState;
  userEmail: string;
}

const RUNBOOK_COMMANDS = [
  String.raw`.venv\Scripts\python.exe -m pytest server\tests -q --tb=short`,
  String.raw`.venv\Scripts\python.exe -m pytest server\tests\security\llm_guardrails -q --tb=short`,
  "cd web-next && npm run typecheck",
  "cd web-next && npm run build",
  String.raw`.venv\Scripts\python.exe scripts\check_env_security.py`,
] as const;

const TONE_META: Record<
  RunbookTone,
  { label: string; className: string; icon: typeof CheckCircle2 }
> = {
  ok: {
    label: "OK",
    className: "border-success/40 bg-success-soft text-success",
    icon: CheckCircle2,
  },
  warn: {
    label: "WARN",
    className: "border-warning/40 bg-warning-soft text-warning",
    icon: AlertTriangle,
  },
  manual: {
    label: "MANUAL",
    className: "border-line bg-bg-raised text-ink-secondary",
    icon: Info,
  },
  blocked: {
    label: "BLOCKED",
    className: "border-danger/40 bg-danger-soft text-danger",
    icon: XCircle,
  },
};

function maskEmail(email: string): string {
  const trimmed = email.trim();
  if (!trimmed) return "未确认登录身份";
  const atIndex = trimmed.indexOf("@");
  if (atIndex <= 0) return "已登录";
  const local = trimmed.slice(0, atIndex);
  const domain = trimmed.slice(atIndex + 1);
  if (!domain) return "已登录";
  return `${local.slice(0, 1)}***@${domain}`;
}

function safeSiteLabel(url?: string): string {
  const trimmed = (url ?? "").trim();
  if (!trimmed) return "未设置目标站点";
  try {
    return new URL(trimmed).origin.slice(0, 80);
  } catch {
    return "已配置目标站点";
  }
}

function backendTone(siteTone: SiteTargetState["tone"]): RunbookTone {
  if (siteTone === "online") return "ok";
  if (siteTone === "warning") return "warn";
  return "blocked";
}

function buildChecks(
  siteState: SiteTargetState,
  maskedEmail: string,
  hasSession: boolean
): RunbookCheckItem[] {
  return [
    {
      id: "backend-health",
      title: "Backend health",
      status: siteState.text,
      tone: backendTone(siteState.tone),
      detail: `${safeSiteLabel(siteState.url)} · 来自 Dashboard 现有站点健康状态`,
    },
    {
      id: "proxy-health",
      title: "Next API proxy",
      status: "E2E probe",
      tone: "manual",
      detail: "/api/backend/health 可由真实浏览器 E2E 自动探测，不在面板内主动执行",
    },
    {
      id: "auth-session",
      title: "Login session",
      status: hasSession ? maskedEmail : "未确认",
      tone: hasSession ? "ok" : "blocked",
      detail: "仅展示脱敏邮箱，不暴露 token、cookie 或会话原文",
    },
    {
      id: "demo-readiness",
      title: "Demo readiness",
      status: "Manual",
      tone: "manual",
      detail: "检查 trigger-demo-attack 入口、告警列表刷新与 Copilot fallback",
    },
    {
      id: "e2e-readiness",
      title: "E2E readiness",
      status: "Manual",
      tone: "manual",
      detail: "使用下方命令串跑，面板只提供复制材料，不自动执行",
    },
    {
      id: "env-security",
      title: "Env security check",
      status: "Manual",
      tone: "manual",
      detail: "本地运行 scripts/check_env_security.py；生产阻断项需先清零",
    },
  ];
}

function buildSummary(
  siteState: SiteTargetState,
  maskedEmail: string,
  checks: RunbookCheckItem[]
): string {
  const generatedAt = new Date().toISOString();
  const statuses = checks
    .map((check) => `- ${check.id}=${check.tone}:${check.status}`)
    .join("\n");
  const commands = RUNBOOK_COMMANDS.map((command) => `- ${command}`).join("\n");

  return [
    "[AI-CyberSentinel Runbook]",
    `generated_at=${generatedAt}`,
    `backend_health=${siteState.tone}:${siteState.text}`,
    "proxy_probe=/api/backend/health manual-e2e",
    `auth_session=${maskedEmail}`,
    "demo_readiness=manual trigger-demo-attack alerts copilot-fallback",
    "e2e_readiness=manual pytest typecheck build",
    "env_security=manual scripts/check_env_security.py production-blocks",
    "check_statuses:",
    statuses,
    "commands:",
    commands,
  ].join("\n");
}

export default function OperationalRunbookPanel({
  siteState,
  userEmail,
}: OperationalRunbookPanelProps) {
  const [copyStatus, setCopyStatus] = useState("");
  const maskedEmail = useMemo(() => maskEmail(userEmail), [userEmail]);
  const hasSession = Boolean(userEmail.trim());
  const checks = useMemo(
    () => buildChecks(siteState, maskedEmail, hasSession),
    [hasSession, maskedEmail, siteState]
  );
  const summary = useMemo(
    () => buildSummary(siteState, maskedEmail, checks),
    [checks, maskedEmail, siteState]
  );

  const handleCopy = async () => {
    try {
      if (!navigator.clipboard?.writeText) {
        setCopyStatus("复制失败");
        return;
      }
      await navigator.clipboard.writeText(summary);
      setCopyStatus("已复制");
    } catch {
      setCopyStatus("复制失败");
    }
  };

  return (
    <section
      data-testid="operational-runbook-panel"
      className="border border-line bg-bg-sunken"
      aria-labelledby="operational-runbook-title"
    >
      <div className="flex flex-col gap-4 border-b border-line px-5 py-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="mb-2 flex flex-wrap items-center gap-2 text-[10px] font-mono text-accent">
            <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
            Operational Runbook
          </div>
          <h3
            id="operational-runbook-title"
            className="font-display text-xl text-ink"
          >
            Health Checklist
          </h3>
          <p className="mt-1 max-w-3xl text-xs leading-relaxed text-ink-secondary">
            汇总站点健康、代理探测、登录会话、Demo 链路、E2E 命令和环境安全检查。所有命令均需人工在终端执行。
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-3">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleCopy}
            data-testid="runbook-copy-summary"
            className="gap-1.5"
          >
            <Clipboard className="h-3.5 w-3.5" aria-hidden="true" />
            复制摘要
          </Button>
          <span
            data-testid="runbook-copy-status"
            className="min-w-[4rem] text-[11px] font-mono text-ink-tertiary"
            aria-live="polite"
          >
            {copyStatus}
          </span>
        </div>
      </div>

      <div className="grid gap-4 px-5 py-5 lg:grid-cols-2">
        {checks.map((check) => {
          const tone = TONE_META[check.tone];
          const Icon = tone.icon;
          return (
            <article
              key={check.id}
              data-testid={`runbook-check-${check.id}`}
              data-tone={check.tone}
              className="min-w-0 border border-line bg-bg-panel px-4 py-3"
            >
              <div className="mb-2 flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h4 className="text-sm font-semibold text-ink">{check.title}</h4>
                  <p className="mt-1 break-words text-xs text-ink-secondary">
                    {check.status}
                  </p>
                </div>
                <span
                  className={`inline-flex shrink-0 items-center gap-1 rounded-md border px-2 py-1 text-[10px] font-mono uppercase ${tone.className}`}
                >
                  <Icon className="h-3 w-3" aria-hidden="true" />
                  {tone.label}
                </span>
              </div>
              <p className="break-words text-[11px] leading-relaxed text-ink-tertiary">
                {check.detail}
              </p>
            </article>
          );
        })}
      </div>

      <div className="grid gap-5 border-t border-line px-5 py-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.8fr)]">
        <div className="min-w-0">
          <div className="mb-3 text-[10px] font-mono uppercase text-ink-tertiary">
            Key commands
          </div>
          <div className="space-y-2">
            {RUNBOOK_COMMANDS.map((command, index) => (
              <code
                key={command}
                data-testid={`runbook-command-${index}`}
                className="block overflow-x-auto whitespace-pre rounded-sm border border-line bg-bg px-3 py-2 text-[11px] leading-relaxed text-ink-secondary"
              >
                {command}
              </code>
            ))}
          </div>
        </div>

        <div className="min-w-0">
          <div className="mb-3 text-[10px] font-mono uppercase text-ink-tertiary">
            Safe diagnostic summary
          </div>
          <pre
            data-testid="runbook-summary-preview"
            className="max-h-64 overflow-auto whitespace-pre-wrap break-words border border-line bg-bg px-3 py-2 text-[11px] leading-relaxed text-ink-secondary"
          >
            {summary}
          </pre>
        </div>
      </div>
    </section>
  );
}
