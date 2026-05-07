export interface SiteHealthPayload {
  status?: string;
  detail?: string;
  checked_at?: string;
  url?: string;
  uptime_status?: string;
  uptime_http_status?: number | null;
  uptime_detail?: string;
  ssl_tone?: string;
  ssl_days_left?: number | null;
}

export interface SiteHealthUi {
  tone: "online" | "warning" | "offline";
  text: string;
}

export interface SiteTargetResponse {
  status?: string;
  target?: string;
  detail?: string;
}
