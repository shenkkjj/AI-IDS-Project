"use client";

import StatusView from "./StatusView";
import {
  INCIDENT_SEVERITY_LABEL,
  INCIDENT_STATUS_LABEL,
  type IncidentSeverity,
  type IncidentStatus,
  type IncidentSummary,
} from "@/types/incident";

const STATUS_TONE: Record<
  IncidentStatus,
  "default" | "info" | "warning" | "danger" | "success"
> = {
  open: "default",
  investigating: "warning",
  contained: "info",
  resolved: "success",
  false_positive: "default",
};

const SEVERITY_TONE: Record<
  IncidentSeverity,
  "default" | "info" | "warning" | "danger"
> = {
  low: "default",
  medium: "info",
  high: "warning",
  critical: "danger",
};

const TONE_CLASS: Record<
  "default" | "info" | "warning" | "danger" | "success",
  string
> = {
  default: "border-line text-ink-tertiary",
  info: "border-info text-info",
  warning: "border-warning text-warning",
  danger: "border-danger text-danger",
  success: "border-success text-success",
};

function StatusBadge({ status }: { status: IncidentStatus }) {
  const tone = STATUS_TONE[status] || "default";
  return (
    <span
      data-testid="incident-status-badge"
      data-status={status}
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-mono uppercase tracking-[0.15em] border ${
        TONE_CLASS[tone]
      }`}
    >
      <span aria-hidden>·</span>
      {INCIDENT_STATUS_LABEL[status] || status}
    </span>
  );
}

function SeverityBadge({ severity }: { severity: IncidentSeverity }) {
  const tone = SEVERITY_TONE[severity] || "default";
  return (
    <span
      data-testid="incident-severity-badge"
      data-severity={severity}
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-mono uppercase tracking-[0.15em] border ${
        TONE_CLASS[tone]
      }`}
    >
      {INCIDENT_SEVERITY_LABEL[severity] || severity}
    </span>
  );
}

function formatTime(epoch: number): string {
  if (!epoch || epoch <= 0) return "—";
  return new Date(epoch * 1000).toLocaleString("zh-CN", { hour12: false });
}

export interface IncidentListProps {
  items: IncidentSummary[];
  loadState: "idle" | "loading" | "ready" | "empty" | "error";
  selectedId: string | null;
  onSelect: (incident: IncidentSummary) => void;
}

export default function IncidentList({
  items,
  loadState,
  selectedId,
  onSelect,
}: IncidentListProps) {
  if (loadState === "loading" && items.length === 0) {
    return (
      <StatusView
        tone="empty"
        title="加载中"
        description="正在读取案件列表…"
        minHeight={200}
      />
    );
  }
  if (loadState === "error") {
    return (
      <StatusView
        tone="error"
        title="加载失败"
        description="无法读取案件列表,请稍后重试。"
        minHeight={200}
      />
    );
  }
  if (items.length === 0) {
    return (
      <StatusView
        tone="empty"
        title="暂无案件"
        description="点击触发 Demo 攻击后,在告警详情创建第一个案件。"
        minHeight={200}
      />
    );
  }
  return (
    <ol data-testid="incident-list" className="space-y-2">
      {items.map((incident) => {
        const isSelected = incident.incident_id === selectedId;
        return (
          <li key={incident.incident_id}>
            <button
              type="button"
              data-testid="incident-list-item"
              data-incident-id={incident.incident_id}
              onClick={() => onSelect(incident)}
              className={`w-full text-left px-3 py-2.5 border transition-colors ${
                isSelected
                  ? "border-accent bg-accent-soft"
                  : "border-line hover:border-ink-tertiary"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm text-ink font-mono break-all">
                  {incident.title}
                </span>
                <StatusBadge status={incident.status} />
              </div>
              <div className="mt-1.5 flex items-center justify-between gap-2 text-[10px] text-ink-tertiary font-mono">
                <span>
                  {incident.incident_id} · {incident.alert_count} 关联告警
                </span>
                <SeverityBadge severity={incident.severity} />
              </div>
              <div className="mt-1 text-[10px] font-mono text-ink-tertiary">
                更新 {formatTime(incident.updated_at)}
                {incident.closed_at ? ` · 已关闭` : ""}
              </div>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
