import type { IncidentSeverity, IncidentStatus, IncidentSummary } from "./incident";

export type BulkCopyStatus = "idle" | "copied" | "failed";

export interface IncidentExportQueueItem {
  incident_id: string;
  title_length: number;
  status: IncidentStatus;
  severity: IncidentSeverity;
  alert_count: number;
  updated_at: number;
  closed_at_present: boolean;
  queued_at: number;
}

export function buildIncidentExportQueueItem(
  incident: IncidentSummary,
  queuedAt = Date.now()
): IncidentExportQueueItem {
  return {
    incident_id: incident.incident_id,
    title_length: incident.title.length,
    status: incident.status,
    severity: incident.severity,
    alert_count: incident.alert_count,
    updated_at: incident.updated_at,
    closed_at_present:
      typeof incident.closed_at === "number" && incident.closed_at > 0,
    queued_at: queuedAt,
  };
}

export function buildIncidentBulkSummary(
  incidents: IncidentSummary[],
  filterLabel: string
): string {
  const lines = [
    "[AI-CyberSentinel Incident Bulk Summary]",
    `count=${incidents.length}`,
    `filter=${filterLabel}`,
    "",
  ];

  for (const incident of incidents) {
    const safe = buildIncidentExportQueueItem(incident, 0);
    lines.push(
      `- incident_id=${safe.incident_id}`,
      `  title_length=${safe.title_length}`,
      `  status=${safe.status}`,
      `  severity=${safe.severity}`,
      `  alert_count=${safe.alert_count}`,
      `  updated_at=${safe.updated_at}`,
      `  closed_at=${safe.closed_at_present ? "present" : "absent"}`
    );
  }

  return lines.join("\n");
}
