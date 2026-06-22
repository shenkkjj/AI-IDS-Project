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
  selectedIds?: ReadonlySet<string>;
  filterLabel?: string;
  mode?: "default" | "archive";
  onSelect: (incident: IncidentSummary) => void;
  onToggleSelect?: (incident: IncidentSummary) => void;
}

export default function IncidentList({
  items,
  loadState,
  selectedId,
  selectedIds,
  filterLabel = "全部",
  mode = "default",
  onSelect,
  onToggleSelect,
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
    const emptyDescription =
      filterLabel === "已关闭归档"
        ? "暂无已关闭案件。"
        : filterLabel === "活跃"
        ? "暂无活跃案件。"
        : filterLabel === "全部"
        ? "点击触发 Demo 攻击后,在告警详情创建第一个案件。"
        : `当前状态暂无案件。`;
    return (
      <div data-testid="incident-list-empty-filtered">
        <StatusView
          tone="empty"
          title={filterLabel === "全部" ? "暂无案件" : `${filterLabel}为空`}
          description={emptyDescription}
          minHeight={200}
        />
      </div>
    );
  }
  return (
    <ol data-testid="incident-list" className="space-y-2">
      {items.map((incident) => {
        const isSelected = incident.incident_id === selectedId;
        const isBulkSelected = selectedIds?.has(incident.incident_id) ?? false;
        return (
          <li key={incident.incident_id}>
            <div
              className={`w-full text-left px-3 py-2.5 border transition-colors ${
                isSelected
                  ? "border-accent bg-accent-soft"
                  : "border-line hover:border-ink-tertiary"
              }`}
            >
              <div className="flex items-start gap-2">
                {onToggleSelect ? (
                  <input
                    type="checkbox"
                    data-testid="incident-select-checkbox"
                    checked={isBulkSelected}
                    onChange={() => onToggleSelect(incident)}
                    onClick={(event) => event.stopPropagation()}
                    aria-label={`选择案件 ${incident.title || incident.incident_id}`}
                    className="mt-0.5 h-4 w-4 shrink-0 accent-accent"
                  />
                ) : null}
                <button
                  type="button"
                  data-testid="incident-list-item"
                  data-incident-id={incident.incident_id}
                  onClick={() => onSelect(incident)}
                  className="min-w-0 flex-1 text-left"
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
                    {mode === "archive" ? (
                      <>
                        <span data-testid="incident-closed-at">
                          关闭时间: {incident.closed_at ? formatTime(incident.closed_at) : "未记录"}
                        </span>
                        <span> · 更新 {formatTime(incident.updated_at)}</span>
                      </>
                    ) : (
                      <span data-testid="incident-list-updated-at">
                        更新 {formatTime(incident.updated_at)}
                      </span>
                    )}
                  </div>
                </button>
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
