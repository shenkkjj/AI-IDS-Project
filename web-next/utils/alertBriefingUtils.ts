import type { AlertDetail, AlertBriefing } from "@/types/alertBriefing";
import type { AlertItem, AlertRisk, AlertTriageStatus } from "@/types/alert";
import {
  TRIAGE_CLOSED_STATUSES,
  TRIAGE_OPEN_STATUSES,
  TRIAGE_STATUS_OPTIONS,
} from "@/types/alert";
import { classifyAttack, formatTimestamp } from "./alertUtils";

/* ---------- 风险标签 / tone ---------- */

const RISK_LABEL: Record<AlertRisk, string> = {
  critical: "严重",
  high: "高危",
  medium: "中危",
  low: "低危",
};

export function triageStatusLabel(status: AlertTriageStatus): string {
  const found = TRIAGE_STATUS_OPTIONS.find((option) => option.value === status);
  return found?.label || status;
}

export function triageStatusTone(
  status: AlertTriageStatus
): "default" | "info" | "warning" | "danger" | "success" {
  const found = TRIAGE_STATUS_OPTIONS.find((option) => option.value === status);
  return found?.tone || "default";
}

export function triageShortLabel(status: AlertTriageStatus): string {
  const found = TRIAGE_STATUS_OPTIONS.find((option) => option.value === status);
  return found?.shortLabel || status.toUpperCase().slice(0, 4);
}

const RISK_TONE: Record<AlertRisk, "danger" | "warning" | "info" | "default"> = {
  critical: "danger",
  high: "warning",
  medium: "info",
  low: "default",
};

const RISK_RANK: Record<AlertRisk, number> = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
};

export function riskLabel(risk: AlertRisk): string {
  return RISK_LABEL[risk] || risk;
}

export function riskTone(risk: AlertRisk): "danger" | "warning" | "info" | "default" {
  return RISK_TONE[risk] || "default";
}

export function compareRisk(a: AlertRisk, b: AlertRisk): number {
  return RISK_RANK[b] - RISK_RANK[a];
}

/* ---------- 告警详情派生 ---------- */

const ACTION_BY_RISK: Record<AlertRisk, string[]> = {
  critical: [
    "立即隔离源 IP，确认后写入新威胁库",
    "拉取目标资产日志，评估横向扩散面",
    "通知值班 SOC 升级响应，30 分钟内复核",
  ],
  high: [
    "确认 WAF 拦截是否生效，必要时手动封禁",
    "复盘 payload 是否触发其他告警",
    "在终端使用 `block <ip>` 写入临时规则",
  ],
  medium: [
    "持续观察同源是否出现新攻击",
    "在 Copilot 侧栏继续追问缓解建议",
    "补全威胁确认标签以便归档",
  ],
  low: [
    "继续观察，归档为背景流量",
    "如重复出现再升级关注",
  ],
};

const ACTION_BY_CLASS: Record<string, string[]> = {
  "SQL 注入": [
    "确认目标接口未直接拼接 SQL",
    "检查 WAF 是否已匹配 `UNION SELECT` 规则",
  ],
  "XSS": [
    "确认输出位置是否已做 HTML 实体转义",
    "如为富文本字段,检查 sanitizer 配置",
  ],
  "自动化扫描": [
    "在 WAF 提高对此 IP 的限速",
    "记录扫描指纹供后续关联分析",
  ],
  "暴力破解": [
    "对源 IP 启用登录限速 / 验证码",
    "如为内部账号,触发告警通知账号负责人",
  ],
};

function buildImpact(alert: AlertItem): string {
  const target = alert.target || "未知目标";
  const blockedLabel = alert.blocked ? "已拦截" : "未拦截";
  return `目标 ${target} · ${blockedLabel}`;
}

function buildEvidence(alert: AlertItem): string {
  const payload = String(alert.payload || "").trim();
  const source = alert.source || "未知来源";
  if (payload) {
    const truncated = payload.length > 120 ? `${payload.slice(0, 120)}…` : payload;
    return `${source} → ${alert.target} · 载荷: ${truncated}`;
  }
  return `${source} → ${alert.target} · 载荷为空`;
}

function buildRecommendedActions(alert: AlertItem): string[] {
  const byRisk = ACTION_BY_RISK[alert.risk] || ACTION_BY_RISK.medium;
  const byClass = ACTION_BY_CLASS[classifyAttack(alert.payload)] || [];
  // 去重；上限 4 条；先放风险维度，再放攻击类别维度
  const merged: string[] = [];
  for (const action of [...byRisk, ...byClass]) {
    if (!merged.includes(action)) {
      merged.push(action);
    }
    if (merged.length >= 4) break;
  }
  return merged;
}

function buildReport(alert: AlertItem, detail: Omit<AlertDetail, "report">): string {
  const lines: string[] = [];
  lines.push(`# 告警报告 · ${alert.alertId || alert.id}`);
  lines.push("");
  lines.push(`- 风险等级: ${detail.riskLabel}`);
  lines.push(`- 攻击类别: ${detail.attackClass}`);
  lines.push(`- 时间: ${detail.timestampLabel}`);
  lines.push(`- 来源: ${alert.source || "未知"}`);
  lines.push(`- 目标: ${alert.target || "未知"}`);
  lines.push(`- 拦截: ${alert.blocked ? "是" : "否"}`);
  lines.push(`- 研判状态: ${detail.triageStatusLabel}${detail.triageDisposition ? `（${detail.triageDisposition}）` : ""}`);
  if (detail.triageUpdatedAt > 0) {
    lines.push(`- 研判更新: ${formatTimestamp(detail.triageUpdatedAt)}${
      detail.triageUpdatedBy !== null ? ` · 操作员 #${detail.triageUpdatedBy}` : ""
    }`);
  }
  if (alert.payload) {
    lines.push(`- 载荷: \`${alert.payload}\``);
  }
  if (alert.summary) {
    lines.push("");
    lines.push("## 模型摘要");
    lines.push(alert.summary);
  }
  if (detail.triageNote) {
    lines.push("");
    lines.push("## 处置备注");
    lines.push(detail.triageNote);
  }
  lines.push("");
  lines.push("## 影响");
  lines.push(detail.impact);
  lines.push("");
  lines.push("## 证据");
  lines.push(detail.evidence);
  lines.push("");
  lines.push("## 建议动作");
  for (const action of detail.recommendedActions) {
    lines.push(`- ${action}`);
  }
  return lines.join("\n");
}

/**
 * 从基础 AlertItem 派生出详情。
 *
 * 不会修改传入对象；返回新对象。
 */
export function deriveAlertDetail(alert: AlertItem | null): AlertDetail | null {
  if (!alert) return null;
  const risk = alert.risk;
  const attackClass = classifyAttack(alert.payload);
  const triage = alert.triage;
  const partial: Omit<AlertDetail, "report"> = {
    riskLevel: risk,
    riskLabel: RISK_LABEL[risk] || risk,
    riskTone: RISK_TONE[risk] || "default",
    attackClass,
    evidence: buildEvidence(alert),
    impact: buildImpact(alert),
    recommendedActions: buildRecommendedActions(alert),
    blocked: Boolean(alert.blocked),
    timestampLabel: formatTimestamp(alert.timestamp),
    triageStatus: triage.status,
    triageStatusLabel: triageStatusLabel(triage.status),
    triageStatusTone: triageStatusTone(triage.status),
    triageDisposition: triage.disposition,
    triageNote: triage.analyst_note,
    triageUpdatedAt: triage.updated_at,
    triageUpdatedBy: triage.updated_by,
  };
  return {
    ...partial,
    report: buildReport(alert, partial),
  };
}

/* ---------- 简报派生 ---------- */

function bucketLabel(timestamp: number, windowHours: 24 | 168): string {
  // 24h 按小时分桶；168h 按天分桶
  const date = new Date(timestamp * 1000);
  if (windowHours === 24) {
    return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false });
  }
  return date.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" });
}

export function deriveBriefing(
  alerts: AlertItem[],
  windowHours: 24 | 168 = 24
): AlertBriefing {
  const now = Date.now() / 1000;
  const windowStart = now - windowHours * 3600;
  const inWindow = alerts.filter((item) => {
    if (!Number.isFinite(item.timestamp) || !item.timestamp) return false;
    return item.timestamp >= windowStart && item.timestamp <= now;
  });

  const total = inWindow.length;
  const highRisk = inWindow.filter((item) => item.risk === "high" || item.risk === "critical").length;
  const blocked = inWindow.filter((item) => item.blocked).length;
  const blockRate = total > 0 ? blocked / total : 0;

  // 研判状态分布
  const triageCounter = new Map<AlertTriageStatus, number>();
  for (const item of inWindow) {
    const status = item.triage?.status ?? "new";
    triageCounter.set(status, (triageCounter.get(status) || 0) + 1);
  }
  const triageBreakdown = TRIAGE_STATUS_OPTIONS
    .map((option) => ({
      status: option.value,
      label: option.label,
      count: triageCounter.get(option.value) || 0,
    }))
    .filter((item) => item.count > 0);
  const triageOpen = inWindow.filter(
    (item) => item.triage && TRIAGE_OPEN_STATUSES.has(item.triage.status)
  ).length;
  const triageClosed = inWindow.filter(
    (item) => item.triage && TRIAGE_CLOSED_STATUSES.has(item.triage.status)
  ).length;

  // 风险分布
  const riskCounter = new Map<AlertRisk, number>();
  for (const item of inWindow) {
    riskCounter.set(item.risk, (riskCounter.get(item.risk) || 0) + 1);
  }
  const riskBreakdown = Array.from(riskCounter.entries())
    .map(([risk, count]) => ({ risk, count, label: RISK_LABEL[risk] || risk }))
    .sort((a, b) => RISK_RANK[b.risk] - RISK_RANK[a.risk]);

  // top 来源
  const sourceCounter = new Map<string, number>();
  for (const item of inWindow) {
    const key = item.source || "unknown";
    sourceCounter.set(key, (sourceCounter.get(key) || 0) + 1);
  }
  const topSources = Array.from(sourceCounter.entries())
    .map(([source, count]) => ({ source, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 8);

  // 攻击类别
  const classCounter = new Map<string, number>();
  for (const item of inWindow) {
    const key = classifyAttack(item.payload);
    classCounter.set(key, (classCounter.get(key) || 0) + 1);
  }
  const topAttackClass = Array.from(classCounter.entries())
    .map(([cls, count]) => ({ class: cls, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 5);

  // 时间桶：
  // - 24h 简报：24 个小时桶（bucketSize = 3600s）
  // - 168h 简报：7 个天桶（bucketSize = 86400s），不允许出现 168 个桶
  // 桶大小与桶数由 windowHours 显式决定，避免再写 "bucketCount = windowHours" 这类容易复发的误用。
  const bucketSize: number = windowHours === 24 ? 3600 : 86400;
  const bucketCount: number = windowHours === 24 ? 24 : 7;
  const buckets: Array<{ time: string; count: number }> = [];
  for (let i = bucketCount - 1; i >= 0; i--) {
    const start = now - (i + 1) * bucketSize;
    const end = now - i * bucketSize;
    const inBucket = inWindow.filter(
      (item) => item.timestamp && item.timestamp >= start && item.timestamp < end
    ).length;
    const sample = inWindow.find(
      (item) => typeof item.timestamp === "number" && item.timestamp >= start && item.timestamp < end
    );
    const time =
      sample && typeof sample.timestamp === "number"
        ? bucketLabel(sample.timestamp, windowHours)
        : bucketLabel(end, windowHours);
    buckets.push({ time, count: inBucket });
  }

  // 最新告警
  const latestAlerts = [...inWindow]
    .sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0))
    .slice(0, 5);

  // 备注：数据稀疏时提示
  let note: string | null = null;
  if (total === 0) {
    note = "当前窗口内暂无告警数据，所有指标均为 0";
  } else if (total < 5) {
    note = `当前窗口仅有 ${total} 条告警,简报为薄数据视图`;
  }

  return {
    windowHours,
    windowLabel: windowHours === 24 ? "今日（近 24 小时）" : "本周（近 7 天）",
    total,
    highRisk,
    blocked,
    blockRate,
    riskBreakdown,
    topSources,
    topAttackClass,
    buckets,
    latestAlerts,
    triageBreakdown,
    triageOpen,
    triageClosed,
    note,
  };
}
