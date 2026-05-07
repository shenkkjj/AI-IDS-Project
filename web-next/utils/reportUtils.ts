import type { AlertItem } from "@/types/alert";
import { classifyAttack, formatTimestamp } from "./alertUtils";

export const REPORT_LATEST_ALERTS_LIMIT = 5;

export function listToMarkdownLines(list: string[]): string {
  if (list.length === 0) {
    return "- 无";
  }
  return list.map((item) => `- ${item}`).join("\n");
}

export function buildReportMarkdown(alerts: AlertItem[]): string {
  const total = alerts.length;
  const highRisk = alerts.filter((item) => item.risk === "high" || item.risk === "critical").length;
  const blocked = alerts.filter((item) => item.blocked).length;

  const riskCounter = new Map<string, number>();
  const sourceCounter = new Map<string, number>();

  for (const item of alerts) {
    riskCounter.set(item.risk, (riskCounter.get(item.risk) || 0) + 1);
    sourceCounter.set(item.source, (sourceCounter.get(item.source) || 0) + 1);
  }

  const topRiskEntry = Array.from(riskCounter.entries()).sort((a, b) => b[1] - a[1])[0] || ["unknown", 0];
  const topSources = Array.from(sourceCounter.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([ip, count]) => `${ip} (${count})`);

  const latestAlerts = alerts.slice(0, REPORT_LATEST_ALERTS_LIMIT).map((item) => {
    return `- ${formatTimestamp(item.timestamp)} · ${item.source} → ${item.target} · ${classifyAttack(item.payload)} · ${item.risk}`;
  });

  return [
    "# 安全态势总结报告",
    `- 生成时间: ${new Date().toLocaleString()}`,
    `- 当前窗口告警总数: ${total}`,
    `- 高危告警: ${highRisk}`,
    `- 自动拦截: ${blocked}`,
    "",
    "## 风险焦点",
    `- 最高频风险级别: ${topRiskEntry[0]} (${topRiskEntry[1]})`,
    "",
    "## 高频来源",
    listToMarkdownLines(topSources),
    "",
    `## 最近 ${REPORT_LATEST_ALERTS_LIMIT} 条告警`,
    latestAlerts.length > 0 ? latestAlerts.join("\n") : "- 无",
  ].join("\n");
}
