"use client";

import { RefreshCw } from "lucide-react";
import type { SecurityTimelineCategory, SecurityTimelineItem, SecurityTimelineSource } from "@/types/securityTimeline";

type SecurityTimelineProps = {
  items: SecurityTimelineItem[];
  loadState: "loading" | "ready" | "empty" | "error";
  degraded: boolean;
  limit: number;
  onRefresh: () => void;
};

const CATEGORY_LABELS: Record<string, string> = {
  demo_attack: "Demo 攻击",
  copilot_stream: "Copilot",
  guardrail_passed: "护栏通过",
  guardrail_blocked: "护栏拦截",
  guardrail_warning: "护栏告警",
  auth_event: "账号事件",
  config_event: "配置变更",
  threat_event: "威胁事件",
  other_log: "系统事件",
  other_audit: "审计事件",
};

function categoryLabel(category: SecurityTimelineCategory): string {
  return CATEGORY_LABELS[String(category)] ?? String(category);
}

function statusTone(status: string): string {
  if (status === "blocked" || status === "error") return "text-danger";
  if (status === "warning") return "text-warning";
  if (status === "passed" || status === "success") return "text-success";
  return "text-ink-tertiary";
}

function formatTs(ts: string | null): string {
  if (!ts) return "—";
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return ts;
  return date.toLocaleString("zh-CN", { hour12: false });
}

function sourceTag(source: SecurityTimelineSource): string {
  return source === "audit" ? "AUD" : "LOG";
}

export default function SecurityTimeline({
  items,
  loadState,
  degraded,
  limit,
  onRefresh,
}: SecurityTimelineProps) {
  return (
    <div
      data-testid="security-timeline"
      className="h-full min-h-[280px] flex flex-col border-l border-accent bg-bg-sunken"
    >
      <div className="px-5 py-3 flex items-baseline justify-between border-b border-line">
        <div className="flex items-baseline gap-2">
          <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-accent">
            SOC · 安全时间线
          </span>
          {degraded ? (
            <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-warning">
              降级模式
            </span>
          ) : null}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[10px] font-mono text-ink-tertiary">
            {items.length}/{limit}
          </span>
          <button
            type="button"
            onClick={onRefresh}
            data-testid="security-timeline-refresh"
            className="text-[10px] font-mono uppercase tracking-[0.15em] text-accent hover:text-accent-hover transition-colors flex items-center gap-1"
          >
            <RefreshCw className="w-3 h-3" />
            刷新
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-3 text-xs space-y-2 min-h-0">
        {loadState === "loading" ? (
          <div className="h-full flex items-center justify-center text-ink-tertiary font-mono">
            加载中...
          </div>
        ) : loadState === "error" ? (
          <div className="h-full flex items-center justify-center text-danger font-mono">
            时间线加载失败
          </div>
        ) : items.length === 0 ? (
          <div className="h-full flex items-center justify-center text-ink-tertiary font-mono">
            暂无安全事件
          </div>
        ) : (
          items.map((item) => (
            <div
              key={`${item.source}-${item.id}`}
              data-testid="security-timeline-item"
              data-category={item.category}
              className="flex items-baseline gap-3 border-b border-line-subtle pb-1.5 last:border-b-0"
            >
              <span className="font-mono text-[10px] text-ink-tertiary w-32 shrink-0">
                {formatTs(item.ts)}
              </span>
              <span className="font-mono text-[10px] uppercase tracking-wider text-ink-tertiary w-10 shrink-0">
                {sourceTag(item.source)}
              </span>
              <span className="font-mono text-[10px] uppercase tracking-wider text-accent w-24 shrink-0 truncate">
                {categoryLabel(item.category)}
              </span>
              <span
                className={`font-mono text-[10px] uppercase tracking-wider w-16 shrink-0 ${statusTone(
                  item.status,
                )}`}
              >
                · {item.status}
              </span>
              <span
                data-testid="security-timeline-summary"
                className="text-ink-secondary text-xs leading-relaxed flex-1 truncate"
              >
                {item.summary}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
