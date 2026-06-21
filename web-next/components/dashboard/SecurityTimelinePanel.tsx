"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronDown, Copy, RefreshCw, ShieldCheck } from "lucide-react";
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

type TimelineFilterKey = "all" | "demo" | "copilot" | "guardrails" | "system";

const FILTER_OPTIONS: Array<{
  key: TimelineFilterKey;
  label: string;
  testId: string;
}> = [
  { key: "all", label: "全部", testId: "security-timeline-filter-all" },
  { key: "demo", label: "Demo", testId: "security-timeline-filter-demo" },
  { key: "copilot", label: "Copilot", testId: "security-timeline-filter-copilot" },
  {
    key: "guardrails",
    label: "护栏",
    testId: "security-timeline-filter-guardrails",
  },
  { key: "system", label: "系统", testId: "security-timeline-filter-system" },
];

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

function itemKey(item: SecurityTimelineItem): string {
  return `${item.source}-${item.id}-${item.ts ?? "no-ts"}-${item.category}`;
}

function filterForCategory(category: SecurityTimelineCategory): TimelineFilterKey {
  const value = String(category);
  if (value === "demo_attack") return "demo";
  if (value === "copilot_stream") return "copilot";
  if (value.startsWith("guardrail_")) return "guardrails";
  return "system";
}

function itemMatchesFilter(
  item: SecurityTimelineItem,
  filter: TimelineFilterKey
): boolean {
  if (filter === "all") return true;
  return filterForCategory(item.category) === filter;
}

function buildCopySummary(item: SecurityTimelineItem): string {
  return `[SOC] ${formatTs(item.ts)} ${sourceTag(item.source)}/${categoryLabel(
    item.category
  )} ${String(item.status)} - ${item.summary}`;
}

export default function SecurityTimelinePanel({
  items,
  loadState,
  degraded,
  limit,
  offline = false,
  onRefresh,
}: SecurityTimelinePanelProps) {
  const [activeFilter, setActiveFilter] = useState<TimelineFilterKey>("all");
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [copyStatus, setCopyStatus] = useState<{ key: string; text: string } | null>(
    null
  );

  const filterCounts = useMemo(() => {
    const counts = Object.fromEntries(
      FILTER_OPTIONS.map((option) => [option.key, 0])
    ) as Record<TimelineFilterKey, number>;
    counts.all = items.length;
    for (const item of items) {
      counts[filterForCategory(item.category)] += 1;
    }
    return counts;
  }, [items]);

  const filteredItems = useMemo(
    () => items.filter((item) => itemMatchesFilter(item, activeFilter)),
    [activeFilter, items]
  );

  useEffect(() => {
    if (expandedKey && !filteredItems.some((item) => itemKey(item) === expandedKey)) {
      setExpandedKey(null);
      setCopyStatus(null);
    }
  }, [expandedKey, filteredItems]);

  useEffect(() => {
    if (!expandedKey) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setExpandedKey(null);
        setCopyStatus(null);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [expandedKey]);

  const activeFilterLabel =
    FILTER_OPTIONS.find((option) => option.key === activeFilter)?.label ?? "全部";

  const handleToggleItem = (key: string) => {
    setExpandedKey((current) => (current === key ? null : key));
    setCopyStatus(null);
  };

  const handleCopySummary = async (item: SecurityTimelineItem) => {
    const key = itemKey(item);
    const text = buildCopySummary(item);
    try {
      if (!navigator.clipboard?.writeText) {
        setCopyStatus({ key, text: "复制失败" });
        return;
      }
      await navigator.clipboard.writeText(text);
      setCopyStatus({ key, text: "已复制" });
    } catch {
      setCopyStatus({ key, text: "复制失败" });
    }
  };

  return (
    <div
      data-testid="security-timeline"
      data-degraded={degraded || undefined}
      data-offline={offline || undefined}
      className="h-full min-h-[280px] flex flex-col border-l border-accent bg-bg-sunken"
    >
      <div className="px-5 py-3 flex flex-col gap-3 border-b border-line">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <div className="flex flex-wrap items-baseline gap-2">
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
            <span
              data-testid="security-timeline-filter-count"
              className="text-[10px] font-mono text-ink-tertiary whitespace-nowrap"
            >
              {activeFilterLabel} {filteredItems.length}/{items.length} · limit {limit}
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

        <div className="-mx-1 overflow-x-auto overscroll-x-contain">
          <div className="flex min-w-max items-center gap-1 px-1">
            {FILTER_OPTIONS.map((option) => {
              const pressed = activeFilter === option.key;
              return (
                <button
                  key={option.key}
                  type="button"
                  data-testid={option.testId}
                  aria-pressed={pressed}
                  onClick={() => {
                    setActiveFilter(option.key);
                    setCopyStatus(null);
                  }}
                  className={`inline-flex h-7 items-center gap-1.5 border px-2.5 text-[10px] font-mono uppercase tracking-[0.12em] transition-colors ${
                    pressed
                      ? "border-accent bg-accent-soft text-accent"
                      : "border-line text-ink-tertiary hover:border-ink-tertiary hover:text-ink"
                  }`}
                >
                  <span>{option.label}</span>
                  <span className="text-[9px] text-ink-tertiary">
                    {filterCounts[option.key]}
                  </span>
                </button>
              );
            })}
          </div>
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
        ) : filteredItems.length === 0 ? (
          <div
            data-testid="security-timeline-filter-empty"
            className="min-h-[180px] flex flex-col items-center justify-center gap-2 text-center"
          >
            <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary">
              {activeFilterLabel} · 0/{items.length}
            </span>
            <span className="text-xs text-ink-secondary">
              当前筛选下暂无 SOC 时间线事件。
            </span>
          </div>
        ) : (
          <ul className="space-y-2">
            {filteredItems.map((item) => {
              const key = itemKey(item);
              const expanded = expandedKey === key;
              return (
                <li key={key} className="border-b border-line-subtle pb-2 last:border-b-0">
                  <button
                    type="button"
                    data-testid="security-timeline-item"
                    data-category={item.category}
                    data-expanded={expanded ? "true" : undefined}
                    aria-expanded={expanded}
                    onClick={() => handleToggleItem(key)}
                    className={`group w-full text-left transition-colors ${
                      expanded ? "bg-bg-raised" : "hover:bg-bg-raised/60"
                    }`}
                  >
                    <span className="grid grid-cols-1 gap-1 px-2 py-2 sm:grid-cols-[8rem_2.5rem_6rem_4.5rem_minmax(0,1fr)_1rem] sm:items-baseline sm:gap-3">
                      <span className="font-mono text-[10px] text-ink-tertiary">
                        {formatTs(item.ts)}
                      </span>
                      <span className="font-mono text-[10px] uppercase tracking-wider text-ink-tertiary">
                        {sourceTag(item.source)}
                      </span>
                      <span className="font-mono text-[10px] uppercase tracking-wider text-accent truncate">
                        {categoryLabel(item.category)}
                      </span>
                      <span
                        className={`font-mono text-[10px] uppercase tracking-wider ${statusTone(
                          item.status
                        )}`}
                      >
                        · {item.status}
                      </span>
                      <span
                        data-testid="security-timeline-summary"
                        className="text-ink-secondary text-xs leading-relaxed min-w-0 truncate"
                      >
                        {item.summary}
                      </span>
                      <ChevronDown
                        className={`hidden h-3 w-3 text-ink-tertiary transition-transform sm:block ${
                          expanded ? "rotate-180" : ""
                        }`}
                        aria-hidden="true"
                      />
                    </span>
                  </button>

                  {expanded ? (
                    <div
                      data-testid="security-timeline-detail"
                      className="mt-2 border border-line bg-bg-raised px-3 py-3 text-[11px]"
                    >
                      <div className="grid gap-2 sm:grid-cols-2">
                        <div>
                          <span className="font-mono uppercase tracking-[0.12em] text-ink-tertiary">
                            时间
                          </span>
                          <p className="mt-1 text-ink-secondary">{formatTs(item.ts)}</p>
                        </div>
                        <div>
                          <span className="font-mono uppercase tracking-[0.12em] text-ink-tertiary">
                            来源
                          </span>
                          <p className="mt-1 font-mono text-ink-secondary">
                            {sourceTag(item.source)}
                          </p>
                        </div>
                        <div>
                          <span className="font-mono uppercase tracking-[0.12em] text-ink-tertiary">
                            类别
                          </span>
                          <p className="mt-1 text-ink-secondary">
                            {categoryLabel(item.category)}
                          </p>
                        </div>
                        <div>
                          <span className="font-mono uppercase tracking-[0.12em] text-ink-tertiary">
                            状态
                          </span>
                          <p className={`mt-1 font-mono ${statusTone(item.status)}`}>
                            {String(item.status)}
                          </p>
                        </div>
                      </div>

                      <div className="mt-3 border-l border-line pl-3">
                        <span className="font-mono uppercase tracking-[0.12em] text-ink-tertiary">
                          脱敏摘要
                        </span>
                        <p className="mt-1 text-xs leading-relaxed text-ink-secondary">
                          {item.summary}
                        </p>
                      </div>

                      <div className="mt-3 flex flex-col gap-2 border-t border-line-subtle pt-3 sm:flex-row sm:items-center sm:justify-between">
                        <div className="flex items-start gap-2 text-ink-tertiary">
                          <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" />
                          <span className="leading-relaxed">
                            安全说明：已隐藏敏感字段，仅显示脱敏摘要。
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          {copyStatus?.key === key ? (
                            <span
                              data-testid="security-timeline-copy-status"
                              className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-tertiary"
                            >
                              {copyStatus.text}
                            </span>
                          ) : null}
                          <button
                            type="button"
                            data-testid="security-timeline-copy-summary"
                            onClick={(event) => {
                              event.stopPropagation();
                              void handleCopySummary(item);
                            }}
                            className="inline-flex h-7 items-center gap-1.5 border border-line px-2.5 font-mono text-[10px] uppercase tracking-[0.12em] text-accent transition-colors hover:border-accent hover:bg-accent-soft"
                          >
                            <Copy className="h-3 w-3" />
                            复制摘要
                          </button>
                        </div>
                      </div>
                    </div>
                  ) : null}
              </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
