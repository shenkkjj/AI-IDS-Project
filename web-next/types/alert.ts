export type AlertRisk = "critical" | "high" | "medium" | "low";

/**
 * 研判状态(M3-02)。
 *
 * - 字段名与后端 Pydantic ``AlertTriageStatus`` 一一对应;
 *   前端不要随意重命名,后端契约稳定。
 * - ``disposition`` 是可选的处置分类(自定义短码,例如 ``blocked_at_waf``)。
 */
export type AlertTriageStatus =
  | "new"
  | "investigating"
  | "contained"
  | "false_positive"
  | "resolved";

export interface AlertTriage {
  status: AlertTriageStatus;
  disposition: string | null;
  analyst_note: string | null;
  updated_at: number;
  updated_by: number | null;
}

export interface AlertItem {
  id: string;
  alertId: string;
  source: string;
  target: string;
  risk: AlertRisk;
  payload: string;
  summary: string;
  timestamp: number | null;
  blocked: boolean;
  triage: AlertTriage;
}

export interface BackendAlertItem {
  alert_id?: string;
  raw_alert?: {
    source_ip?: string;
    destination_ip?: string;
    payload?: string;
    timestamp?: number;
    blocked?: boolean;
  };
  llm_analysis?: {
    risk_level?: string;
    summary?: string;
  };
  triage?: Partial<AlertTriage> | null;
}

export interface DemoCopilotState {
  ready: boolean;
  provider: string;
  model: string;
  fallback_reason?: string | null;
  next_action: string;
}

export interface DemoAttackResponse {
  status: "ok";
  scenario: "sql_injection" | "xss" | "scanner";
  alert: BackendAlertItem;
  copilot: DemoCopilotState;
}

/**
 * 研判历史事件（M3-03）。
 *
 * 与后端 ``server/services/alert_service.get_alert_triage_history`` 返回的
 * ``items`` 元素一一对应；前端不要随意重命名,后端契约稳定。
 */
export interface AlertTriageEvent {
  id: number;
  from_status: AlertTriageStatus | null;
  to_status: AlertTriageStatus;
  disposition: string | null;
  analyst_note: string | null;
  updated_by: number | null;
  created_at: number;
}

/**
 * 研判历史端点响应。
 *
 * ``limit`` 是请求时使用的有效 limit（默认 50,范围 1-100）。
 */
export interface AlertTriageHistoryResponse {
  status: "ok";
  alert_id: string;
  items: AlertTriageEvent[];
  count: number;
  limit: number;
}

/**
 * 研判面板的展示派生。
 *
 * 内部使用,与 backend AlertTriageStatus 一一对应。
 */
export const TRIAGE_STATUS_OPTIONS: ReadonlyArray<{
  value: AlertTriageStatus;
  label: string;
  shortLabel: string;
  tone: "default" | "info" | "warning" | "danger" | "success";
}> = [
  { value: "new", label: "新告警", shortLabel: "NEW", tone: "default" },
  { value: "investigating", label: "研判中", shortLabel: "INV", tone: "warning" },
  { value: "contained", label: "已遏制", shortLabel: "CON", tone: "info" },
  { value: "false_positive", label: "误报", shortLabel: "FP", tone: "default" },
  { value: "resolved", label: "已解决", shortLabel: "DONE", tone: "success" },
];

/**
 * 用于简报分桶:new / investigating 算"待研判",其余算"已闭环"。
 * 这是前端语义,不写到后端。
 */
export const TRIAGE_OPEN_STATUSES: ReadonlySet<AlertTriageStatus> = new Set([
  "new",
  "investigating",
]);

export const TRIAGE_CLOSED_STATUSES: ReadonlySet<AlertTriageStatus> = new Set([
  "contained",
  "false_positive",
  "resolved",
]);
