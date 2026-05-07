import type { AlertRisk, AlertItem, BackendAlertItem } from "@/types/alert";

export function parseRisk(riskLevel: string | undefined): AlertRisk {
  const value = String(riskLevel || "").trim().toLowerCase();
  if (value === "critical" || value === "high" || value === "medium" || value === "low") {
    return value;
  }
  return "medium";
}

export function mapBackendAlert(item: BackendAlertItem, index: number): AlertItem {
  const alertId = String(item.alert_id || "").trim();
  const source = String(item.raw_alert?.source_ip || "unknown");
  const target = String(item.raw_alert?.destination_ip || "unknown");
  const payload = String(item.raw_alert?.payload || "");
  const summary = String(item.llm_analysis?.summary || "暂无模型摘要，可在 Copilot 侧栏继续追问。");
  const risk = parseRisk(item.llm_analysis?.risk_level);

  return {
    id: alertId || `B-${String(index + 1).padStart(3, "0")}`,
    alertId,
    source,
    target,
    risk,
    payload,
    summary,
    timestamp: Number.isFinite(item.raw_alert?.timestamp) ? Number(item.raw_alert?.timestamp) : null,
    blocked: Boolean(item.raw_alert?.blocked),
  };
}

export function classifyAttack(payload: string): string {
  const text = String(payload || "").toLowerCase();
  if (text.includes("union select") || text.includes(" or 1=1") || text.includes("drop table")) {
    return "SQL 注入";
  }
  if (text.includes("<script") || text.includes("onerror=") || text.includes("javascript:")) {
    return "XSS";
  }
  if (text.includes("nmap") || text.includes("awvs") || text.includes("masscan") || text.includes("scan")) {
    return "自动化扫描";
  }
  if (text.includes("login") || text.includes("password") || text.includes("auth failed")) {
    return "暴力破解";
  }
  return "异常流量";
}

export function formatTimestamp(ts: number | null): string {
  if (!Number.isFinite(ts) || !ts || ts <= 0) {
    return "--";
  }
  return new Date(ts * 1000).toLocaleString();
}

export function formatLoadError(message: string): string {
  if (message.includes("401")) {
    return "会话失效，请重新登录";
  }
  if (message.includes("403") || message.includes("blocked")) {
    return "请求被拒绝，请稍后重试";
  }
  if (message.includes("429") || message.includes("rate")) {
    return "请求过于频繁，请稍后重试";
  }
  return "操作失败，请稍后重试";
}
