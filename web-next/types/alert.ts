export type AlertRisk = "critical" | "high" | "medium" | "low";

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
}
