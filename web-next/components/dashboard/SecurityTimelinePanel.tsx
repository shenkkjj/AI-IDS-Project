"use client";

import { RefreshCw } from "lucide-react";
import StatusView, { buildRetryAction } from "./StatusView";
import type {
  SecurityTimelineCategory,
  SecurityTimelineItem,
  SecurityTimelineSource,
} from "@/types/securityTimeline";

/**
 * 安全时间线面板：保留原 SecurityTimeline 的展示契约,
 * 但把 loading/empty/error/degraded 四态接到 StatusView 统一壳上。
 */
export interface SecurityTimelinePanelProps {
  items: SecurityTimelineItem[];
  loadState: "loading" | "ready" | "empty" | "error";
  degraded: boolean;
  limit: number;
  /** 当后端 5xx 或 SSE 错误时,设为 true;面板会显示 degraded 提示 */
  offline?: boolean;
  onRefresh: () => void;
}

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

export default function SecurityTimelinePanel({
  items,
  loadState,
  degraded,
  limit,
  offline = false,
  onRefresh,
}: SecurityTimelinePanelProps) {
  return (
    <div
      data-testid="security-timeline"
      data-degraded={degraded || undefined}
      data-offline={offline || undefined}
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
          {offline ? (
            <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-warning">
              离线模式
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

      <div className="flex-1 overflow-y-auto px-5 py-3 text-xs min-h-0">
        {loadState === "loading" ? (
          <StatusView tone="loading" title="时间线加载中..." minHeight={220} />
        ) : offline ? (
          <StatusView
            tone="offline"
            title="时间线暂时不可用"
            description="实时通道已断开。系统将继续以轮询模式拉取最近 50 条事件,无需操作。"
            action={buildRetryAction(onRefresh, "重新拉取")}
            minHeight={220}
          />
        ) : loadState === "error" ? (
          <StatusView
            tone="error"
            title="时间线加载失败"
            description="后端暂时无法返回事件。可点击重试或等待下一次轮询。"
            action={buildRetryAction(onRefresh)}
            minHeight={220}
          />
        ) : items.length === 0 ? (
          <StatusView
            tone="empty"
            title="暂无安全事件"
            description="系统在过去 24 小时内没有记录到 demo attack / Copilot / 护栏事件。"
            minHeight={220}
          />
        ) : (
          <ul className="space-y-2">
            {items.map((item) => (
              <li
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
                    item.status
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
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
