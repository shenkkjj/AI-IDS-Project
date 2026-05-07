import type { SiteHealthPayload, SiteHealthUi } from "@/types/site";

export function mapSiteHealthToUptime(health: SiteHealthPayload): SiteHealthUi {
  const status = String(health?.status || "").trim();
  const sslTone = String(health?.ssl_tone || "").trim();
  const daysLeft = Number(health?.ssl_days_left);

  if (status === "idle") {
    return { tone: "warning", text: "未配置" };
  }
  if (status === "error" || status === "invalid") {
    return { tone: "offline", text: "检测失败" };
  }
  if (status === "no_ssl") {
    return { tone: "offline", text: "无 HTTPS" };
  }

  if (status === "ok") {
    if (sslTone === "critical") {
      if (Number.isFinite(daysLeft)) {
        return { tone: "offline", text: `证书${daysLeft}天到期` };
      }
      return { tone: "offline", text: "证书高危" };
    }

    if (sslTone === "warning") {
      if (Number.isFinite(daysLeft)) {
        return { tone: "warning", text: `证书${daysLeft}天到期` };
      }
      return { tone: "warning", text: "证书预警" };
    }

    return { tone: "online", text: "正常" };
  }

  return { tone: "offline", text: "异常" };
}

export function inferProxyPath(urlText: string): string {
  const text = String(urlText || "").trim();
  if (!text) {
    return "/";
  }

  try {
    const parsed = new URL(text);
    const pathname = parsed.pathname || "/";
    return `${pathname}${parsed.search || ""}`;
  } catch {
    return text.startsWith("/") ? text : `/${text}`;
  }
}
