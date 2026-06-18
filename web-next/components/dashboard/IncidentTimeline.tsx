"use client";

import {
  INCIDENT_STATUS_LABEL,
  type IncidentEvent,
  type IncidentEventType,
} from "@/types/incident";

const EVENT_LABEL: Record<IncidentEventType, string> = {
  created: "案件创建",
  status_changed: "状态变化",
  alert_linked: "告警加入",
  alert_unlinked: "告警移出",
  note_added: "新增备注",
  summary_updated: "摘要更新",
  severity_changed: "严重度变化",
  title_changed: "标题变化",
};

function formatTime(epoch: number): string {
  if (!epoch || epoch <= 0) return "—";
  return new Date(epoch * 1000).toLocaleString("zh-CN", { hour12: false });
}

export interface IncidentTimelineProps {
  events: IncidentEvent[];
}

export default function IncidentTimeline({ events }: IncidentTimelineProps) {
  if (events.length === 0) {
    return (
      <div className="text-[10px] font-mono text-ink-tertiary">暂无事件</div>
    );
  }
  return (
    <ol data-testid="incident-timeline" className="space-y-2">
      {events.map((event) => {
        const label = EVENT_LABEL[event.event_type] || event.event_type;
        const statusText =
          event.event_type === "status_changed"
            ? `${INCIDENT_STATUS_LABEL[event.from_status as keyof typeof INCIDENT_STATUS_LABEL] || "—"} → ${INCIDENT_STATUS_LABEL[event.to_status as keyof typeof INCIDENT_STATUS_LABEL] || "—"}`
            : null;
        return (
          <li
            key={event.id}
            data-testid="incident-timeline-item"
            data-event-type={event.event_type}
            className="text-[11px] text-ink leading-relaxed border-l border-line pl-3"
          >
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <span className="font-mono text-ink">
                {label}
                {statusText ? ` · ${statusText}` : ""}
              </span>
              <span className="text-[10px] font-mono text-ink-tertiary">
                {formatTime(event.created_at)}
                {event.actor_user_id !== null ? ` · #${event.actor_user_id}` : ""}
              </span>
            </div>
            {event.note ? (
              <div className="mt-0.5 text-[11px] text-ink-secondary break-words whitespace-pre-wrap">
                {event.note}
              </div>
            ) : null}
            {event.detail ? (
              <div className="mt-0.5 text-[10px] font-mono text-ink-tertiary break-all">
                {event.detail}
              </div>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
