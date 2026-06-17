import type { AlertItem, AlertRisk, AlertTriageStatus } from "./alert";

/**
 * 单条告警的"详情扩展字段"。
 *
 * 设计原则：
 * - M3-01 阶段不修改后端；所有字段在前端从 `AlertItem` 派生。
 * - M3-02 阶段接入后端 ``PATCH /alerts/{alert_id}/triage``,
 *   ``triageStatus*`` / ``triageDisposition`` / ``triageNote`` 等字段
 *   直接来自后端契约 (``mapBackendAlert`` 已确保默认 ``new``)。
 * - 所有字段都是 readonly；调用方应使用 `deriveAlertDetail(alert)` 构造。
 * - 字段名稳定,方便后端后续接入时 1:1 替换。
 */
export interface AlertDetail {
  /** 告警风险等级（前端可读的细分标签） */
  riskLevel: AlertRisk;
  /** 风险等级的中文展示名 */
  riskLabel: string;
  /** 风险颜色 tone，落到现有 CSS class */
  riskTone: "danger" | "warning" | "info" | "default";
  /** 攻击类别（SQL 注入 / XSS / 扫描 / 暴力破解 / 异常流量） */
  attackClass: string;
  /** 证据：来自 payload / source / target 的可读拼接 */
  evidence: string;
  /** 影响范围：受影响的目标 / 端口 / 拦截状态 */
  impact: string;
  /** 建议动作：3 条以内的可执行建议 */
  recommendedActions: string[];
  /** 复制报告的 markdown 全文 */
  report: string;
  /** 是否被自动拦截 */
  blocked: boolean;
  /** 格式化时间戳；空时为 "—" */
  timestampLabel: string;
  /** 研判状态 */
  triageStatus: AlertTriageStatus;
  /** 研判状态中文标签 */
  triageStatusLabel: string;
  /** 研判状态颜色 tone */
  triageStatusTone: "default" | "info" | "warning" | "danger" | "success";
  /** 处置分类(可选) */
  triageDisposition: string | null;
  /** 处置备注(可选) */
  triageNote: string | null;
  /** 研判更新时间戳(秒) */
  triageUpdatedAt: number;
  /** 研判更新者 id(可选) */
  triageUpdatedBy: number | null;
}

/**
 * 简报：日/周维度的统计。
 *
 * - `windowHours` 表示窗口长度（24=日，168=周）。
 * - `buckets` 给出按小时的告警数时间桶（最长 24 个）。
 * - `topSources` 给出来源 IP top 8。
 * - `riskBreakdown` 按 risk 维度给出计数。
 * - `blockRate` 0~1，已拦截 / 总数。
 * - `triageBreakdown` 只含 count>0 的项;`triageOpen` / `triageClosed` 给
 *   简报卡使用。
 * - `note` 是给 UI 看的备注：数据是否过少。
 */
export interface AlertBriefing {
  windowHours: 24 | 168;
  windowLabel: string;
  total: number;
  highRisk: number;
  blocked: number;
  blockRate: number;
  riskBreakdown: Array<{ risk: AlertRisk; count: number; label: string }>;
  topSources: Array<{ source: string; count: number }>;
  topAttackClass: Array<{ class: string; count: number }>;
  buckets: Array<{ time: string; count: number }>;
  latestAlerts: AlertItem[];
  /** 研判状态分布（只保留 count>0 的项） */
  triageBreakdown: Array<{ status: AlertTriageStatus; label: string; count: number }>;
  /** 窗口内处于"待研判（new / investigating）"的告警数 */
  triageOpen: number;
  /** 窗口内处于"已闭环（contained / false_positive / resolved）"的告警数 */
  triageClosed: number;
  note: string | null;
}
