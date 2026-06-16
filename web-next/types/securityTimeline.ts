export type SecurityTimelineSource = "log" | "audit";

export type SecurityTimelineStatus =
  | "info"
  | "success"
  | "warning"
  | "blocked"
  | "passed"
  | string;

export type SecurityTimelineCategory =
  | "demo_attack"
  | "copilot_stream"
  | "guardrail_passed"
  | "guardrail_blocked"
  | "guardrail_warning"
  | "auth_event"
  | "config_event"
  | "threat_event"
  | "other_log"
  | "other_audit"
  | string;

export interface SecurityTimelineItem {
  id: number;
  ts: string | null;
  source: SecurityTimelineSource;
  category: SecurityTimelineCategory;
  summary: string;
  status: SecurityTimelineStatus;
}

export interface SecurityTimelinePayload {
  items: SecurityTimelineItem[];
  limit: number;
  degraded?: boolean;
}
