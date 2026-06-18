"use client";

import { Unlink } from "lucide-react";
import type { IncidentLinkedAlert } from "@/types/incident";

function truncate(value: string | undefined, max: number): string {
  if (!value) return "—";
  if (value.length <= max) return value;
  return value.slice(0, max) + "…";
}

export interface IncidentLinkedAlertsProps {
  alerts: IncidentLinkedAlert[];
  onUnlink: (alertId: string) => void;
}

export default function IncidentLinkedAlerts({
  alerts,
  onUnlink,
}: IncidentLinkedAlertsProps) {
  if (alerts.length === 0) {
    return (
      <div
        data-testid="incident-linked-alerts-empty"
        className="text-[10px] font-mono text-ink-tertiary"
      >
        暂未关联告警
      </div>
    );
  }
  return (
    <ul data-testid="incident-linked-alerts" className="space-y-1.5">
      {alerts.map((a) => {
        const raw = a.raw_alert || {};
        const analysis = a.llm_analysis || null;
        const risk = (analysis?.risk_level ?? "unknown").toString();
        const summary = analysis?.summary ?? "";
        return (
          <li
            key={a.alert_id}
            data-testid="incident-linked-alert"
            data-alert-id={a.alert_id}
            className="flex items-start justify-between gap-2 border-l border-line pl-3"
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 text-[10px] font-mono text-ink-tertiary">
                <span className="break-all">{a.alert_id}</span>
                <span>·</span>
                <span>risk={risk}</span>
              </div>
              <div className="text-[11px] text-ink leading-relaxed break-words">
                {truncate(raw.source_ip, 80)} → {truncate(raw.destination_ip, 80)}
              </div>
              {summary ? (
                <div className="text-[10px] text-ink-secondary break-words mt-0.5">
                  {truncate(summary, 120)}
                </div>
              ) : null}
              {a.triage?.status ? (
                <div className="text-[10px] font-mono text-ink-tertiary mt-0.5">
                  triage={a.triage.status}
                  {a.triage.disposition ? ` · ${a.triage.disposition}` : ""}
                </div>
              ) : null}
            </div>
            <button
              type="button"
              data-testid="incident-unlink"
              data-alert-id={a.alert_id}
              onClick={() => onUnlink(a.alert_id)}
              className="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary hover:text-danger inline-flex items-center gap-1 shrink-0"
              aria-label={`移出 ${a.alert_id}`}
            >
              <Unlink className="w-3 h-3" />
              移出
            </button>
          </li>
        );
      })}
    </ul>
  );
}
