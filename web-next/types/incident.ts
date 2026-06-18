/**
 * 安全事件 / 案件类型定义 (M3-04)。
 *
 * 与后端 ``server/services/incident_service.py`` / ``server/routers/incidents_router.py``
 * 返回的字段一一对应,前端不要随意重命名,后端契约稳定。
 */

export type IncidentStatus =
  | "open"
  | "investigating"
  | "contained"
  | "resolved"
  | "false_positive";

export type IncidentSeverity = "critical" | "high" | "medium" | "low";

export type IncidentEventType =
  | "created"
  | "status_changed"
  | "alert_linked"
  | "alert_unlinked"
  | "note_added"
  | "summary_updated"
  | "severity_changed"
  | "title_changed";

/** 列表 / 详情中的案件基础信息。 */
export interface IncidentSummary {
  incident_id: string;
  title: string;
  summary: string | null;
  severity: IncidentSeverity;
  status: IncidentStatus;
  user_id: number;
  assignee_user_id: number | null;
  created_from_alert_id: string | null;
  alert_count: number;
  created_at: number;
  updated_at: number;
  closed_at: number | null;
}

/** 事件时间线条目。 */
export interface IncidentEvent {
  id: number;
  event_type: IncidentEventType;
  from_status: IncidentStatus | null;
  to_status: IncidentStatus | null;
  detail: string;
  note: string | null;
  actor_user_id: number | null;
  created_at: number;
}

/** 案件详情中关联的告警项,结构与 ``BackendAlertItem`` 兼容。 */
export interface IncidentLinkedAlert {
  alert_id: string;
  raw_alert: {
    source_ip?: string;
    destination_ip?: string;
    payload?: string;
    timestamp?: number;
    blocked?: boolean;
    alert_user_id?: number;
  };
  llm_analysis: {
    risk_level?: string;
    summary?: string;
  } | null;
  analysis_error?: string | null;
  processed_at?: number;
  triage: {
    status: string;
    disposition: string | null;
    analyst_note: string | null;
    updated_at: number;
    updated_by: number | null;
  };
}

export interface IncidentListResponse {
  status: "ok";
  items: IncidentSummary[];
  count: number;
  limit: number;
}

export interface IncidentDetailResponse {
  status: "ok";
  incident: IncidentSummary;
  linked_alerts: IncidentLinkedAlert[];
  events: IncidentEvent[];
  event_limit: number;
}

export interface IncidentCreateResponse {
  status: "ok";
  incident: IncidentSummary;
  linked_alerts: IncidentLinkedAlert[];
  events: IncidentEvent[];
}

export interface IncidentUpdateResponse {
  status: "ok";
  incident: IncidentSummary;
  events: IncidentEvent[];
}

export interface IncidentLinkResponse {
  status: "ok";
  incident: IncidentSummary;
  alert_count: number;
  idempotent: boolean;
}

export interface IncidentUnlinkResponse {
  status: "ok";
  incident: IncidentSummary;
  alert_count: number;
}

// ---------------------------------------------------------------------------
// 案件证据报告导出 (M3-07)
// ---------------------------------------------------------------------------

/** 报告元信息(只含计数与生成时间,不含敏感正文)。 */
export interface IncidentReportMeta {
  generated_at: number;
  alert_count: number;
  included_alerts: number;
  event_count: number;
  included_events: number;
  redaction_count: number;
  truncated: boolean;
}

/** ``GET /incidents/{id}/report?format=json`` 响应 envelope。 */
export interface IncidentReportResponse {
  status: "ok";
  incident_id: string;
  filename: string;
  markdown: string;
  meta: IncidentReportMeta;
}

/** 前端展示用常量。 */
export const INCIDENT_STATUS_OPTIONS: ReadonlyArray<{
  value: IncidentStatus;
  label: string;
  shortLabel: string;
  tone: "default" | "info" | "warning" | "danger" | "success";
}> = [
  { value: "open", label: "已开启", shortLabel: "OPEN", tone: "default" },
  { value: "investigating", label: "调查中", shortLabel: "INV", tone: "warning" },
  { value: "contained", label: "已遏制", shortLabel: "CON", tone: "info" },
  { value: "resolved", label: "已解决", shortLabel: "DONE", tone: "success" },
  { value: "false_positive", label: "误报", shortLabel: "FP", tone: "default" },
];

export const INCIDENT_SEVERITY_OPTIONS: ReadonlyArray<{
  value: IncidentSeverity;
  label: string;
  tone: "default" | "info" | "warning" | "danger";
}> = [
  { value: "low", label: "低", tone: "default" },
  { value: "medium", label: "中", tone: "info" },
  { value: "high", label: "高", tone: "warning" },
  { value: "critical", label: "严重", tone: "danger" },
];

/** 状态文案映射。 */
export const INCIDENT_STATUS_LABEL: Record<IncidentStatus, string> =
  INCIDENT_STATUS_OPTIONS.reduce(
    (acc, opt) => {
      acc[opt.value] = opt.label;
      return acc;
    },
    {} as Record<IncidentStatus, string>
  );

export const INCIDENT_SEVERITY_LABEL: Record<IncidentSeverity, string> =
  INCIDENT_SEVERITY_OPTIONS.reduce(
    (acc, opt) => {
      acc[opt.value] = opt.label;
      return acc;
    },
    {} as Record<IncidentSeverity, string>
  );
