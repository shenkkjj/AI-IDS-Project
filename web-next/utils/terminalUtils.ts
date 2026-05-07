import type { AlertItem } from "@/types/alert";
import type { TerminalTone } from "@/types/terminal";
import { formatTimestamp } from "./alertUtils";

export function runTerminalCommand(command: string, alerts: AlertItem[]): string[] {
  const text = String(command || "").trim();
  if (!text) {
    return [];
  }

  const lines: string[] = [`$ ${text}`];

  if (text === "help") {
    lines.push("help | stats | tail | block <ip> | clear");
    return lines;
  }

  if (text === "stats") {
    const total = alerts.length;
    const blocked = alerts.filter((item) => item.blocked).length;
    const high = alerts.filter((item) => item.risk === "high" || item.risk === "critical").length;
    lines.push(`alerts=${total} high=${high} blocked=${blocked}`);
    return lines;
  }

  if (text === "tail") {
    const latest = alerts.slice(0, 3);
    if (latest.length === 0) {
      lines.push("暂无告警");
      return lines;
    }
    for (const item of latest) {
      lines.push(`${formatTimestamp(item.timestamp)} ${item.source} -> ${item.target} ${item.risk}`);
    }
    return lines;
  }

  if (text.startsWith("block ")) {
    const ip = text.slice(6).trim();
    if (!ip) {
      lines.push("用法: block <ip>");
      return lines;
    }
    lines.push(`已提交模拟封禁规则: ${ip}`);
    return lines;
  }

  if (text === "clear") {
    lines.push("__CLEAR__");
    return lines;
  }

  lines.push(`未知命令: ${text}`);
  return lines;
}

export function buildTerminalBootstrapLines(): string[] {
  return ["[INFO] CyberSentinel terminal online", "[INFO] 可用命令: help, stats, tail, block <ip>, clear"];
}

export function formatTerminalLine(text: string, tone: TerminalTone = "normal"): string {
  const now = new Date().toLocaleTimeString();
  const prefix = tone === "warn" ? "[WARN]" : tone === "error" ? "[ERR ]" : "[INFO]";
  return `${now} ${prefix} ${text}`;
}
