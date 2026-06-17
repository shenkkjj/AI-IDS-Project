"use client";

import { CheckCircle2 } from "lucide-react";
import type { AlertRisk, AlertItem, AlertTriageStatus } from "@/types/alert";
import { TRIAGE_STATUS_OPTIONS } from "@/types/alert";

type AttackLogTableProps = {
  logs: AlertItem[];
  highlightId?: string;
  selectedId?: string;
  onSelect?: (id: string) => void;
  newIds?: Set<string>;
};

function riskLabel(risk: AlertRisk): string {
  if (risk === "critical") return "严重";
  if (risk === "high") return "高危";
  if (risk === "medium") return "中危";
  return "低危";
}

function riskTone(risk: AlertRisk): "danger" | "warning" | "info" | "default" {
  if (risk === "critical") return "danger";
  if (risk === "high") return "warning";
  if (risk === "medium") return "info";
  return "default";
}

function formatTimestamp(ts: number | null): string {
  if (!Number.isFinite(ts) || !ts || ts <= 0) {
    return "—";
  }
  return new Date(ts * 1000).toLocaleString("zh-CN", { hour12: false });
}

const toneColor: Record<"danger" | "warning" | "info" | "default", string> = {
  danger: "text-danger",
  warning: "text-warning",
  info: "text-info",
  default: "text-ink-tertiary",
};

function TriageCell({ status }: { status: AlertTriageStatus }) {
  const meta = TRIAGE_STATUS_OPTIONS.find((option) => option.value === status);
  const tone = meta?.tone || "default";
  const cellTone: Record<typeof tone, string> = {
    danger: "text-danger border-danger",
    warning: "text-warning border-warning",
    info: "text-info border-info",
    success: "text-success border-success",
    default: "text-ink-tertiary border-line",
  } as const;
  return (
    <span
      data-testid="triage-row-badge"
      data-status={status}
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-mono uppercase tracking-[0.1em] border ${cellTone[tone]}`}
    >
      <span aria-hidden>·</span>
      {meta?.shortLabel || status}
    </span>
  );
}

export default function AttackLogTable({ logs, highlightId, selectedId, onSelect, newIds }: AttackLogTableProps) {
  return (
    <div className="h-full flex flex-col">
      <div className="flex justify-between items-baseline mb-4">
        <h3 className="font-display text-lg text-ink">实时告警流</h3>
        <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-accent">
          {logs.length > 0 ? `${logs.length} 条 · 实时` : "等待中"}
        </span>
      </div>

      <div className="flex-1 overflow-auto border-t border-line">
        <table className="w-full text-left text-xs whitespace-nowrap">
          <thead className="text-ink-tertiary sticky top-0 bg-bg">
            <tr className="border-b border-line">
              <th className="py-2.5 pr-3 font-mono uppercase tracking-[0.1em] text-[10px] font-normal">时间</th>
              <th className="py-2.5 pr-3 font-mono uppercase tracking-[0.1em] text-[10px] font-normal">来源 IP</th>
              <th className="py-2.5 pr-3 font-mono uppercase tracking-[0.1em] text-[10px] font-normal">目标</th>
              <th className="py-2.5 pr-3 font-mono uppercase tracking-[0.1em] text-[10px] font-normal">载荷</th>
              <th className="py-2.5 pr-3 font-mono uppercase tracking-[0.1em] text-[10px] font-normal">等级</th>
              <th className="py-2.5 pr-3 font-mono uppercase tracking-[0.1em] text-[10px] font-normal">研判</th>
              <th className="py-2.5 font-mono uppercase tracking-[0.1em] text-[10px] font-normal">拦截</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => {
              const tone = riskTone(log.risk);
              const isSelected = selectedId === log.id;
              const isNew = newIds?.has(log.id) ?? false;
              return (
                <tr
                  key={log.id}
                  data-testid="attack-log-row"
                  data-risk={log.risk}
                  data-alert-id={log.alertId || log.id}
                  data-triage-status={log.triage?.status ?? "new"}
                  className={`border-b border-line-subtle transition-colors ${
                    isSelected ? "bg-accent-soft" : ""
                  } ${onSelect ? "cursor-pointer hover:bg-bg-sunken" : ""} ${
                    isNew ? "row-new" : ""
                  }`}
                  onClick={onSelect ? () => onSelect(log.id) : undefined}
                >
                  <td className="py-2.5 pr-3 font-mono text-ink-tertiary">
                    {formatTimestamp(log.timestamp)}
                  </td>
                  <td className="py-2.5 pr-3 font-mono text-ink">
                    {log.source}
                  </td>
                  <td className="py-2.5 pr-3 font-mono text-ink-secondary">
                    {log.target}
                  </td>
                  <td className="py-2.5 pr-3 max-w-[300px] overflow-hidden text-ellipsis text-ink-tertiary">
                    {log.payload || "—"}
                  </td>
                  <td className="py-2.5 pr-3">
                    <span className={`font-mono text-[10px] uppercase tracking-wider ${toneColor[tone]}`}>
                      · {riskLabel(log.risk)}
                    </span>
                  </td>
                  <td className="py-2.5 pr-3">
                    <TriageCell status={log.triage?.status ?? "new"} />
                  </td>
                  <td className="py-2.5">
                    <span
                      className={`font-mono text-[10px] uppercase tracking-wider ${
                        log.blocked ? "text-success" : "text-ink-tertiary"
                      }`}
                    >
                      {log.blocked ? "是" : "否"}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {logs.length === 0 ? (
          <div className="text-center text-ink-tertiary py-16 text-sm">
            <CheckCircle2 className="w-5 h-5 mx-auto mb-2 text-success" />
            未检测到异常
          </div>
        ) : null}
      </div>
    </div>
  );
}
