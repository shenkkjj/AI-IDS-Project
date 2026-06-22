"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clipboard,
  FileCheck2,
  FileSearch,
  Info,
  Loader2,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import type {
  IncidentEvent,
  IncidentLinkedAlert,
  IncidentReportMeta,
  IncidentSummary,
} from "@/types/incident";

type ClosureTone = "ready" | "review" | "manual" | "missing";
type ReportLoadStatus = "unchecked" | "loading" | "ready" | "error";
type RecommendationKey = "ready" | "review" | "not_ready";

interface ClosureCheckItem {
  testId: string;
  title: string;
  tone: ClosureTone;
  status: string;
  count: string;
  detail: string;
}

export interface IncidentClosureReviewChecklistProps {
  incident: IncidentSummary;
  linkedAlerts: IncidentLinkedAlert[];
  events: IncidentEvent[];
  onLoadReport: (incidentId: string) => Promise<{
    ok: boolean;
    incidentId?: string;
    filename?: string;
    markdown?: string;
    meta?: IncidentReportMeta;
    error?: string;
  }>;
}

const TONE_META: Record<
  ClosureTone,
  { label: string; className: string; icon: typeof CheckCircle2 }
> = {
  ready: {
    label: "READY",
    className: "border-success/40 bg-success-soft text-success",
    icon: CheckCircle2,
  },
  review: {
    label: "REVIEW",
    className: "border-warning/40 bg-warning-soft text-warning",
    icon: AlertTriangle,
  },
  manual: {
    label: "MANUAL",
    className: "border-line bg-bg-raised text-ink-secondary",
    icon: Info,
  },
  missing: {
    label: "MISSING",
    className: "border-danger/40 bg-danger-soft text-danger",
    icon: XCircle,
  },
};

const RECOMMENDATION_META: Record<
  RecommendationKey,
  { label: string; className: string }
> = {
  ready: {
    label: "可关闭",
    className: "border-success/40 bg-success-soft text-success",
  },
  review: {
    label: "人工复核",
    className: "border-warning/40 bg-warning-soft text-warning",
  },
  not_ready: {
    label: "暂不建议关闭",
    className: "border-danger/40 bg-danger-soft text-danger",
  },
};

function reviewedAlerts(linkedAlerts: IncidentLinkedAlert[]): number {
  return linkedAlerts.filter((alert) => {
    const status = alert.triage?.status?.trim();
    return Boolean(status && status !== "new");
  }).length;
}

function isClosureStatus(status: IncidentSummary["status"]): boolean {
  return status === "resolved" || status === "false_positive";
}

function isReviewableStatus(status: IncidentSummary["status"]): boolean {
  return status === "contained" || isClosureStatus(status);
}

function deriveFinalNoteStatus(args: {
  incident: IncidentSummary;
  events: IncidentEvent[];
}): { present: boolean; source: string } {
  const hasEventNote = args.events.some(
    (event) =>
      event.event_type === "note_added" ||
      Boolean(event.note && event.note.trim())
  );
  if (hasEventNote) return { present: true, source: "时间线备注" };
  if (args.incident.summary?.trim()) return { present: true, source: "案件摘要" };
  return { present: false, source: "未记录" };
}

function closedAtText(incident: IncidentSummary): string {
  if (!isClosureStatus(incident.status)) return "不适用";
  return incident.closed_at ? "已记录" : "缺失";
}

function deriveMissingItems(args: {
  incident: IncidentSummary;
  linkedAlerts: IncidentLinkedAlert[];
  events: IncidentEvent[];
  reviewed: number;
  reportStatus: ReportLoadStatus;
  finalNotePresent: boolean;
}): string[] {
  const missing: string[] = [];
  if (args.incident.status === "open") {
    missing.push("先推进到已遏制");
  } else if (args.incident.status === "investigating") {
    missing.push("完成调查并进入关闭前复核");
  }
  if (isClosureStatus(args.incident.status) && !args.incident.closed_at) {
    missing.push("核对关闭时间");
  }
  if (args.reportStatus === "unchecked") missing.push("检查报告元信息");
  if (args.reportStatus === "error") missing.push("重新检查报告元信息");
  if (args.linkedAlerts.length === 0) missing.push("补充关联告警");
  if (args.events.length === 0) missing.push("刷新案件时间线");
  if (args.linkedAlerts.length > 0 && args.reviewed < args.linkedAlerts.length) {
    missing.push("完成告警研判");
  }
  if (!args.finalNotePresent) missing.push("补充复盘备注或摘要");
  return missing;
}

function deriveRecommendation(args: {
  incident: IncidentSummary;
  missingItems: string[];
}): { key: RecommendationKey; detail: string } {
  if (args.missingItems.length === 0 && isReviewableStatus(args.incident.status)) {
    return { key: "ready", detail: "复盘材料齐备，可由人工确认关闭。" };
  }
  if (!isReviewableStatus(args.incident.status)) {
    return { key: "not_ready", detail: "仍需完成处置进展与复核材料。" };
  }
  return { key: "review", detail: "可进入人工复核，但仍有缺失项待补齐。" };
}

function buildChecks(args: {
  incident: IncidentSummary;
  linkedAlerts: IncidentLinkedAlert[];
  events: IncidentEvent[];
  reviewed: number;
  reportStatus: ReportLoadStatus;
  reportMeta: IncidentReportMeta | null;
  missingItems: string[];
  finalNotePresent: boolean;
  finalNoteSource: string;
}): ClosureCheckItem[] {
  const statusTone: ClosureTone = isReviewableStatus(args.incident.status)
    ? "ready"
    : args.incident.status === "investigating"
      ? "review"
      : "missing";
  const evidenceReady =
    args.linkedAlerts.length > 0 &&
    args.events.length > 0 &&
    args.reportStatus === "ready" &&
    args.reviewed === args.linkedAlerts.length;
  const evidenceTone: ClosureTone =
    args.linkedAlerts.length === 0 || args.events.length === 0
      ? "missing"
      : evidenceReady
        ? "ready"
        : "review";
  const reportTone: ClosureTone =
    args.reportStatus === "ready"
      ? "ready"
      : args.reportStatus === "error"
        ? "review"
        : "manual";
  const triageTone: ClosureTone =
    args.linkedAlerts.length === 0
      ? "missing"
      : args.reviewed === args.linkedAlerts.length
        ? "ready"
        : args.reviewed > 0
          ? "review"
          : "manual";

  return [
    {
      testId: "closure-check-status-ready",
      title: "状态可复核",
      tone: statusTone,
      status: isReviewableStatus(args.incident.status) ? "可复核" : "待处置",
      count: `关闭时间 ${closedAtText(args.incident)}`,
      detail: isClosureStatus(args.incident.status)
        ? "当前案件已进入关闭态，需确认关闭时间与复盘材料一致。"
        : args.incident.status === "contained"
          ? "当前案件已遏制，可继续做关闭前人工复核。"
          : "当前案件仍处于处置阶段，暂不进入关闭确认。",
    },
    {
      testId: "closure-check-evidence-pack",
      title: "证据包基础材料",
      tone: evidenceTone,
      status: evidenceReady ? "齐备" : "需复核",
      count: `${args.linkedAlerts.length} 告警 / ${args.events.length} 事件`,
      detail: "综合关联告警、时间线、研判覆盖和报告元信息的只读结果。",
    },
    {
      testId: "closure-check-report-meta",
      title: "报告元信息",
      tone: reportTone,
      status:
        args.reportStatus === "ready"
          ? "已检查"
          : args.reportStatus === "loading"
            ? "检查中"
            : args.reportStatus === "error"
              ? "检查失败"
              : "未检查",
      count: args.reportMeta
        ? `${args.reportMeta.included_alerts}/${args.reportMeta.alert_count} 告警`
        : "meta 待检查",
      detail: args.reportMeta
        ? `事件 ${args.reportMeta.included_events}/${args.reportMeta.event_count}，脱敏 ${args.reportMeta.redaction_count}，截断 ${args.reportMeta.truncated ? "是" : "否"}。`
        : "点击检查后只读取既有报告 JSON 元信息，不保存报告正文。",
    },
    {
      testId: "closure-check-linked-alerts",
      title: "关联告警",
      tone: args.linkedAlerts.length > 0 ? "ready" : "missing",
      status: args.linkedAlerts.length > 0 ? "已关联" : "缺失",
      count: `${args.linkedAlerts.length} 条`,
      detail: "基于当前案件详情中的 linked_alerts 计数。",
    },
    {
      testId: "closure-check-triage-coverage",
      title: "研判覆盖",
      tone: triageTone,
      status:
        args.linkedAlerts.length === 0
          ? "无告警"
          : `${args.reviewed}/${args.linkedAlerts.length}`,
      count: `${args.reviewed} 已研判`,
      detail: "统计 triage.status 不为空且不是 new 的关联告警。",
    },
    {
      testId: "closure-check-timeline-events",
      title: "时间线事件",
      tone: args.events.length > 0 ? "ready" : "missing",
      status: args.events.length > 0 ? "已记录" : "缺失",
      count: `${args.events.length} 条`,
      detail: "用于确认创建、关联、状态变化与复盘备注是否留痕。",
    },
    {
      testId: "closure-check-final-note",
      title: "复盘备注",
      tone: args.finalNotePresent ? "ready" : "manual",
      status: args.finalNotePresent ? "已记录" : "待补充",
      count: args.finalNoteSource,
      detail: "只显示备注是否存在，不展示备注正文或完整时间线说明。",
    },
    {
      testId: "closure-check-missing",
      title: "关闭缺失项",
      tone: args.missingItems.length > 0 ? "review" : "ready",
      status: args.missingItems.length > 0 ? "需要补齐" : "未发现缺失",
      count: `${args.missingItems.length} 项`,
      detail:
        args.missingItems.length > 0
          ? args.missingItems.join("、")
          : "当前关闭前复核材料完整。",
    },
  ];
}

function buildSummary(args: {
  incident: IncidentSummary;
  linkedAlerts: IncidentLinkedAlert[];
  events: IncidentEvent[];
  reviewed: number;
  reportMeta: IncidentReportMeta | null;
  reportStatus: ReportLoadStatus;
  missingItems: string[];
  finalNotePresent: boolean;
  recommendation: RecommendationKey;
}): string {
  const meta = args.reportMeta;
  const closedAt =
    isClosureStatus(args.incident.status)
      ? args.incident.closed_at
        ? "present"
        : "absent"
      : "not_applicable";
  return [
    "[AI-CyberSentinel Closure Review]",
    `incident_id=${args.incident.incident_id}`,
    `status=${args.incident.status}`,
    `severity=${args.incident.severity}`,
    `closed_at=${closedAt}`,
    `linked_alerts=${args.linkedAlerts.length}`,
    `timeline_events=${args.events.length}`,
    `triage_reviewed=${args.reviewed}/${args.linkedAlerts.length}`,
    `report_checked=${args.reportStatus === "ready" ? "yes" : "no"}`,
    `report_alerts=${meta ? `${meta.included_alerts}/${meta.alert_count}` : "unchecked"}`,
    `report_events=${meta ? `${meta.included_events}/${meta.event_count}` : "unchecked"}`,
    `report_redactions=${meta ? meta.redaction_count : "unchecked"}`,
    `report_truncated=${meta ? (meta.truncated ? "yes" : "no") : "unchecked"}`,
    `final_note_seen=${args.finalNotePresent ? "yes" : "no"}`,
    `recommendation=${args.recommendation}`,
    `missing=${args.missingItems.length > 0 ? args.missingItems.join(", ") : "none"}`,
  ].join("\n");
}

export default function IncidentClosureReviewChecklist({
  incident,
  linkedAlerts,
  events,
  onLoadReport,
}: IncidentClosureReviewChecklistProps) {
  const [reportStatus, setReportStatus] =
    useState<ReportLoadStatus>("unchecked");
  const [reportFilename, setReportFilename] = useState<string | null>(null);
  const [reportMeta, setReportMeta] = useState<IncidentReportMeta | null>(null);
  const [copyStatus, setCopyStatus] = useState("");

  useEffect(() => {
    setReportStatus("unchecked");
    setReportFilename(null);
    setReportMeta(null);
    setCopyStatus("");
  }, [incident.incident_id]);

  const reviewed = useMemo(() => reviewedAlerts(linkedAlerts), [linkedAlerts]);
  const finalNote = useMemo(
    () => deriveFinalNoteStatus({ incident, events }),
    [incident, events]
  );
  const missingItems = useMemo(
    () =>
      deriveMissingItems({
        incident,
        linkedAlerts,
        events,
        reviewed,
        reportStatus,
        finalNotePresent: finalNote.present,
      }),
    [events, finalNote.present, incident, linkedAlerts, reportStatus, reviewed]
  );
  const recommendation = useMemo(
    () => deriveRecommendation({ incident, missingItems }),
    [incident, missingItems]
  );
  const checks = useMemo(
    () =>
      buildChecks({
        incident,
        linkedAlerts,
        events,
        reviewed,
        reportStatus,
        reportMeta,
        missingItems,
        finalNotePresent: finalNote.present,
        finalNoteSource: finalNote.source,
      }),
    [
      events,
      finalNote.present,
      finalNote.source,
      incident,
      linkedAlerts,
      missingItems,
      reportMeta,
      reportStatus,
      reviewed,
    ]
  );
  const summary = useMemo(
    () =>
      buildSummary({
        incident,
        linkedAlerts,
        events,
        reviewed,
        reportMeta,
        reportStatus,
        missingItems,
        finalNotePresent: finalNote.present,
        recommendation: recommendation.key,
      }),
    [
      events,
      finalNote.present,
      incident,
      linkedAlerts,
      missingItems,
      recommendation.key,
      reportMeta,
      reportStatus,
      reviewed,
    ]
  );

  const handleRefreshReport = useCallback(async () => {
    if (reportStatus === "loading") return;
    setReportStatus("loading");
    const result = await onLoadReport(incident.incident_id);
    if (!result.ok || !result.filename || !result.meta) {
      setReportFilename(null);
      setReportMeta(null);
      setReportStatus("error");
      return;
    }
    setReportFilename(result.filename);
    setReportMeta(result.meta);
    setReportStatus("ready");
  }, [incident.incident_id, onLoadReport, reportStatus]);

  const handleCopySummary = useCallback(async () => {
    try {
      if (!navigator.clipboard?.writeText) {
        setCopyStatus("复制失败");
        return;
      }
      await navigator.clipboard.writeText(summary);
      setCopyStatus("已复制");
    } catch {
      setCopyStatus("复制失败");
    }
  }, [summary]);

  const recommendationMeta = RECOMMENDATION_META[recommendation.key];

  return (
    <section
      data-testid="incident-closure-review-checklist"
      className="border-b border-line bg-bg-sunken px-5 py-4"
      aria-labelledby="incident-closure-review-title"
    >
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="mb-1.5 flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-[0.15em] text-accent">
            <FileCheck2 className="h-3.5 w-3.5" aria-hidden="true" />
            Closure Review
          </div>
          <h3
            id="incident-closure-review-title"
            className="font-display text-base text-ink"
          >
            Post-Incident Review Checklist
          </h3>
          <p className="mt-1 max-w-2xl text-xs leading-relaxed text-ink-secondary">
            只读汇总关闭前复核条件；不会自动关闭案件，也不会复制备注正文。
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <button
            type="button"
            data-testid="closure-refresh-report"
            onClick={() => void handleRefreshReport()}
            disabled={reportStatus === "loading"}
            className="inline-flex items-center gap-1.5 border border-line px-2.5 py-1.5 text-[10px] font-mono uppercase tracking-[0.12em] text-accent transition-colors hover:border-accent hover:bg-accent-soft disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            aria-label="检查关闭复核报告元信息"
          >
            {reportStatus === "loading" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            ) : (
              <FileSearch className="h-3.5 w-3.5" aria-hidden="true" />
            )}
            检查报告元信息
          </button>
          <button
            type="button"
            data-testid="closure-copy-summary"
            onClick={() => void handleCopySummary()}
            className="inline-flex items-center gap-1.5 border border-line px-2.5 py-1.5 text-[10px] font-mono uppercase tracking-[0.12em] text-accent transition-colors hover:border-accent hover:bg-accent-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            aria-label="复制关闭前复盘摘要"
          >
            <Clipboard className="h-3.5 w-3.5" aria-hidden="true" />
            复制复盘摘要
          </button>
          <span
            data-testid="closure-copy-status"
            className="min-w-[4rem] text-[11px] font-mono text-ink-tertiary"
            aria-live="polite"
          >
            {copyStatus}
          </span>
        </div>
      </div>

      <div
        data-testid="closure-recommendation"
        data-readiness={recommendation.key}
        role="status"
        aria-live="polite"
        className={`mb-4 flex flex-col gap-2 border px-3 py-2 text-[11px] sm:flex-row sm:items-center sm:justify-between ${recommendationMeta.className}`}
      >
        <span className="inline-flex items-center gap-1.5 font-mono uppercase tracking-[0.12em]">
          <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
          {recommendationMeta.label}
        </span>
        <span className="min-w-0 break-words text-ink-secondary">
          {recommendation.detail}
        </span>
      </div>

      {reportFilename || reportMeta ? (
        <div className="mb-4 grid gap-2 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
          {reportFilename ? (
            <div
              data-testid="closure-report-filename"
              className="min-w-0 border border-line bg-bg-panel px-3 py-2 text-[11px] font-mono text-ink break-all"
            >
              {reportFilename}
            </div>
          ) : null}
          {reportMeta ? (
            <div
              data-testid="closure-report-meta"
              className="grid min-w-0 grid-cols-2 gap-2 border border-line bg-bg-panel px-3 py-2 text-[11px] sm:grid-cols-4"
            >
              <span className="font-mono text-ink-secondary">
                告警 {reportMeta.included_alerts}/{reportMeta.alert_count}
              </span>
              <span className="font-mono text-ink-secondary">
                事件 {reportMeta.included_events}/{reportMeta.event_count}
              </span>
              <span className="font-mono text-ink-secondary">
                脱敏 {reportMeta.redaction_count}
              </span>
              <span className="font-mono text-ink-secondary">
                截断 {reportMeta.truncated ? "是" : "否"}
              </span>
            </div>
          ) : null}
        </div>
      ) : null}

      <div
        className="grid gap-2 md:grid-cols-2"
        role="list"
        aria-label="关闭前复盘检查项"
      >
        {checks.map((check) => {
          const tone = TONE_META[check.tone];
          const Icon = tone.icon;
          return (
            <article
              key={check.testId}
              data-testid={check.testId}
              data-tone={check.tone}
              role="listitem"
              className="min-w-0 border border-line bg-bg-panel px-3 py-2.5"
            >
              <div className="mb-2 flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h4 className="text-xs font-semibold text-ink">
                    {check.title}
                  </h4>
                  <p className="mt-1 break-words text-[11px] font-mono text-ink-secondary">
                    {check.status} · {check.count}
                  </p>
                </div>
                <span
                  className={`inline-flex shrink-0 items-center gap-1 rounded-md border px-2 py-1 text-[9px] font-mono uppercase ${tone.className}`}
                >
                  <Icon className="h-3 w-3" aria-hidden="true" />
                  {tone.label}
                </span>
              </div>
              <p className="break-words text-[11px] leading-relaxed text-ink-tertiary">
                {check.detail}
              </p>
            </article>
          );
        })}
      </div>
    </section>
  );
}
