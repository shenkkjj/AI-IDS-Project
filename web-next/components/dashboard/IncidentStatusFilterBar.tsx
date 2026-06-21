"use client";

import { Archive, CheckCircle2, Filter } from "lucide-react";
import type { IncidentStatus } from "@/types/incident";

export type IncidentListFilter =
  | "all"
  | "active"
  | "open"
  | "investigating"
  | "contained"
  | "resolved"
  | "false_positive"
  | "closed";

export type IncidentFilterLoadState = "idle" | "loading" | "ready" | "empty" | "error";

type FilterOption = {
  value: IncidentListFilter;
  label: string;
  testId: string;
  icon: "filter" | "check" | "archive";
};

export const ACTIVE_INCIDENT_STATUSES: IncidentStatus[] = [
  "open",
  "investigating",
  "contained",
];

export const CLOSED_INCIDENT_STATUSES: IncidentStatus[] = [
  "resolved",
  "false_positive",
];

export const INCIDENT_FILTER_OPTIONS: FilterOption[] = [
  { value: "all", label: "全部", testId: "incident-filter-all", icon: "filter" },
  { value: "active", label: "活跃", testId: "incident-filter-active", icon: "check" },
  { value: "open", label: "已开启", testId: "incident-filter-open", icon: "filter" },
  {
    value: "investigating",
    label: "调查中",
    testId: "incident-filter-investigating",
    icon: "filter",
  },
  {
    value: "contained",
    label: "已遏制",
    testId: "incident-filter-contained",
    icon: "filter",
  },
  {
    value: "resolved",
    label: "已解决",
    testId: "incident-filter-resolved",
    icon: "archive",
  },
  {
    value: "false_positive",
    label: "误报",
    testId: "incident-filter-false-positive",
    icon: "archive",
  },
  {
    value: "closed",
    label: "已关闭归档",
    testId: "incident-filter-closed",
    icon: "archive",
  },
];

export function getIncidentFilterLabel(value: IncidentListFilter): string {
  return (
    INCIDENT_FILTER_OPTIONS.find((option) => option.value === value)?.label ?? "全部"
  );
}

function OptionIcon({ icon }: { icon: FilterOption["icon"] }) {
  if (icon === "archive") return <Archive className="w-3 h-3" aria-hidden />;
  if (icon === "check") return <CheckCircle2 className="w-3 h-3" aria-hidden />;
  return <Filter className="w-3 h-3" aria-hidden />;
}

export interface IncidentStatusFilterBarProps {
  value: IncidentListFilter;
  loadState: IncidentFilterLoadState;
  count: number;
  onChange: (value: IncidentListFilter) => void;
}

export default function IncidentStatusFilterBar({
  value,
  loadState,
  count,
  onChange,
}: IncidentStatusFilterBarProps) {
  const label = getIncidentFilterLabel(value);
  const summary =
    loadState === "loading"
      ? `加载中 · ${label}`
      : loadState === "error"
      ? `${label} 加载失败`
      : `${label} · ${count} 个案件`;

  return (
    <div
      data-testid="incident-status-filter-bar"
      className="space-y-2 border-y border-line-subtle py-3"
    >
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary inline-flex items-center gap-1.5">
          <Filter className="w-3 h-3" aria-hidden />
          状态筛选
        </div>
        <div
          data-testid="incident-filter-summary"
          className="text-[10px] font-mono text-ink-tertiary"
          aria-live="polite"
        >
          {summary}
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5" role="group" aria-label="案件状态筛选">
        {INCIDENT_FILTER_OPTIONS.map((option) => {
          const active = option.value === value;
          return (
            <button
              key={option.value}
              type="button"
              data-testid={option.testId}
              aria-pressed={active}
              onClick={() => onChange(option.value)}
              className={`inline-flex items-center gap-1.5 px-2 py-1 text-[10px] font-mono uppercase tracking-[0.1em] border transition-colors ${
                active
                  ? "border-accent bg-accent-soft text-accent"
                  : "border-line text-ink-tertiary hover:text-ink hover:border-ink-tertiary"
              }`}
            >
              <OptionIcon icon={option.icon} />
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
