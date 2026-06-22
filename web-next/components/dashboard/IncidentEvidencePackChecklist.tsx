"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clipboard,
  FileSearch,
  Info,
  Loader2,
  PackageCheck,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import type {
  IncidentEvent,
  IncidentLinkedAlert,
  IncidentReportMeta,
  IncidentSummary,
} from "@/types/incident";

type EvidenceTone = "ok" | "warn" | "manual" | "missing";
type ReportLoadStatus = "unchecked" | "loading" | "ready" | "error";

interface EvidenceCheckItem {
  id: string;
  title: string;
  tone: EvidenceTone;
  status: string;
  count: string;
  detail: string;
}

export interface IncidentEvidencePackChecklistProps {
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
  EvidenceTone,
  { label: string; className: string; icon: typeof CheckCircle2 }
> = {
  ok: {
    label: "OK",
    className: "border-success/40 bg-success-soft text-success",
    icon: CheckCircle2,
  },
  warn: {
    label: "WARN",
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

function reviewedAlerts(linkedAlerts: IncidentLinkedAlert[]): number {
  return linkedAlerts.filter((alert) => {
    const status = alert.triage?.status?.trim();
    return Boolean(status && status !== "new");
  }).length;
}

function deriveMissingItems(args: {
  linkedAlerts: IncidentLinkedAlert[];
  events: IncidentEvent[];
  reportStatus: ReportLoadStatus;
  reviewed: number;
}): string[] {
  const missing: string[] = [];
  if (args.reportStatus === "unchecked") missing.push("报告元信息未检查");
  if (args.reportStatus === "error") missing.push("报告元信息加载失败");
  if (args.linkedAlerts.length === 0) missing.push("缺少关联告警");
  if (args.events.length === 0) missing.push("缺少案件时间线");
  if (args.linkedAlerts.length > 0 && args.reviewed < args.linkedAlerts.length) {
    missing.push("存在未研判告警");
  }
  return missing;
}

function buildChecks(args: {
  linkedAlerts: IncidentLinkedAlert[];
  events: IncidentEvent[];
  reportStatus: ReportLoadStatus;
  reportMeta: IncidentReportMeta | null;
  reviewed: number;
  missingItems: string[];
}): EvidenceCheckItem[] {
  const reportTone: EvidenceTone =
    args.reportStatus === "ready"
      ? "ok"
      : args.reportStatus === "error"
        ? "warn"
        : "manual";
  const reportStatusText =
    args.reportStatus === "ready"
      ? "可生成"
      : args.reportStatus === "loading"
        ? "检查中"
        : args.reportStatus === "error"
          ? "检查失败"
          : "未检查";

  const linkedTone: EvidenceTone =
    args.linkedAlerts.length > 0 ? "ok" : "missing";
  const timelineTone: EvidenceTone = args.events.length > 0 ? "ok" : "missing";

  const triageTone: EvidenceTone =
    args.linkedAlerts.length === 0
      ? "missing"
      : args.reviewed === args.linkedAlerts.length
        ? "ok"
        : args.reviewed > 0
          ? "warn"
          : "manual";

  const redactionTone: EvidenceTone =
    !args.reportMeta
      ? "manual"
      : args.reportMeta.redaction_count > 0 || args.reportMeta.truncated
        ? "ok"
        : "warn";

  return [
    {
      id: "report",
      title: "报告可生成",
      tone: reportTone,
      status: reportStatusText,
      count: args.reportMeta ? "meta 已加载" : "meta 待检查",
      detail: "通过已有报告 JSON endpoint 读取元信息，不新增导出格式。",
    },
    {
      id: "linked-alerts",
      title: "关联告警",
      tone: linkedTone,
      status: args.linkedAlerts.length > 0 ? "已关联" : "缺失",
      count: `${args.linkedAlerts.length} 条`,
      detail: "基于当前案件详情中的 linked_alerts 计数。",
    },
    {
      id: "timeline",
      title: "案件时间线",
      tone: timelineTone,
      status: args.events.length > 0 ? "已记录" : "缺失",
      count: `${args.events.length} 条`,
      detail: "基于当前案件详情中的事件时间线计数。",
    },
    {
      id: "triage",
      title: "告警研判覆盖",
      tone: triageTone,
      status:
        args.linkedAlerts.length === 0
          ? "无告警"
          : `${args.reviewed}/${args.linkedAlerts.length}`,
      count: `${args.reviewed} 已研判`,
      detail: "统计 triage.status 不为空且不是 new 的关联告警。",
    },
    {
      id: "redaction",
      title: "脱敏状态",
      tone: redactionTone,
      status: args.reportMeta
        ? args.reportMeta.truncated
          ? "已截断"
          : args.reportMeta.redaction_count > 0
            ? "已脱敏"
            : "需复核"
        : "未检查",
      count: args.reportMeta
        ? `${args.reportMeta.redaction_count} 次脱敏`
        : "meta 待检查",
      detail: args.reportMeta
        ? args.reportMeta.redaction_count > 0 || args.reportMeta.truncated
          ? "后端报告服务已记录脱敏或截断计数。"
          : "未触发脱敏计数，仍由后端报告服务生成。"
        : "点击检查报告元信息后展示脱敏与截断计数。",
    },
    {
      id: "missing",
      title: "缺失项",
      tone: args.missingItems.length > 0 ? "warn" : "ok",
      status: args.missingItems.length > 0 ? "需要补齐" : "未发现缺失",
      count: `${args.missingItems.length} 项`,
      detail:
        args.missingItems.length > 0
          ? args.missingItems.join("、")
          : "当前 evidence pack 基础材料完整。",
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
}): string {
  const meta = args.reportMeta;
  return [
    "[AI-CyberSentinel Evidence Pack]",
    `incident_id=${args.incident.incident_id}`,
    `status=${args.incident.status}`,
    `severity=${args.incident.severity}`,
    `linked_alerts=${args.linkedAlerts.length}`,
    `timeline_events=${args.events.length}`,
    `triage_reviewed=${args.reviewed}/${args.linkedAlerts.length}`,
    `report_checked=${args.reportStatus === "ready" ? "yes" : "no"}`,
    `report_alerts=${meta ? `${meta.included_alerts}/${meta.alert_count}` : "unchecked"}`,
    `report_events=${meta ? `${meta.included_events}/${meta.event_count}` : "unchecked"}`,
    `redactions=${meta ? meta.redaction_count : "unchecked"}`,
    `truncated=${meta ? (meta.truncated ? "yes" : "no") : "unchecked"}`,
    `missing=${args.missingItems.length > 0 ? args.missingItems.join(", ") : "none"}`,
  ].join("\n");
}

export default function IncidentEvidencePackChecklist({
  incident,
  linkedAlerts,
  events,
  onLoadReport,
}: IncidentEvidencePackChecklistProps) {
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
  const missingItems = useMemo(
    () =>
      deriveMissingItems({
        linkedAlerts,
        events,
        reportStatus,
        reviewed,
      }),
    [events, linkedAlerts, reportStatus, reviewed]
  );
  const checks = useMemo(
    () =>
      buildChecks({
        linkedAlerts,
        events,
        reportStatus,
        reportMeta,
        reviewed,
        missingItems,
      }),
    [events, linkedAlerts, missingItems, reportMeta, reportStatus, reviewed]
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
      }),
    [events, incident, linkedAlerts, missingItems, reportMeta, reportStatus, reviewed]
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

  return (
    <section
      data-testid="incident-evidence-pack-checklist"
      className="border-b border-line bg-bg-sunken px-5 py-4"
      aria-labelledby="incident-evidence-pack-title"
    >
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="mb-1.5 flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-[0.15em] text-accent">
            <PackageCheck className="h-3.5 w-3.5" aria-hidden="true" />
            Evidence Pack
          </div>
          <h3
            id="incident-evidence-pack-title"
            className="font-display text-base text-ink"
          >
            Evidence Pack Checklist
          </h3>
          <p className="mt-1 max-w-2xl text-xs leading-relaxed text-ink-secondary">
            只读汇总当前案件可交付证据状态，复制摘要仅包含安全计数与缺失项。
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <button
            type="button"
            data-testid="evidence-pack-refresh-report"
            onClick={() => void handleRefreshReport()}
            disabled={reportStatus === "loading"}
            className="inline-flex items-center gap-1.5 border border-line px-2.5 py-1.5 text-[10px] font-mono uppercase tracking-[0.12em] text-accent transition-colors hover:border-accent hover:bg-accent-soft disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            aria-label="检查报告元信息"
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
            data-testid="evidence-pack-copy-summary"
            onClick={() => void handleCopySummary()}
            className="inline-flex items-center gap-1.5 border border-line px-2.5 py-1.5 text-[10px] font-mono uppercase tracking-[0.12em] text-accent transition-colors hover:border-accent hover:bg-accent-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            aria-label="复制证据包摘要"
          >
            <Clipboard className="h-3.5 w-3.5" aria-hidden="true" />
            复制证据包摘要
          </button>
          <span
            data-testid="evidence-pack-copy-status"
            className="min-w-[4rem] text-[11px] font-mono text-ink-tertiary"
            aria-live="polite"
          >
            {copyStatus}
          </span>
        </div>
      </div>

      {reportFilename || reportMeta ? (
        <div className="mb-4 grid gap-2 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
          {reportFilename ? (
            <div
              data-testid="evidence-pack-report-filename"
              className="min-w-0 border border-line bg-bg-panel px-3 py-2 text-[11px] font-mono text-ink break-all"
            >
              {reportFilename}
            </div>
          ) : null}
          {reportMeta ? (
            <div
              data-testid="evidence-pack-report-meta"
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
        aria-label="证据包检查项"
      >
        {checks.map((check) => {
          const tone = TONE_META[check.tone];
          const Icon = tone.icon;
          return (
            <article
              key={check.id}
              data-testid={`evidence-pack-check-${check.id}`}
              data-tone={check.tone}
              role="listitem"
              className="min-w-0 border border-line bg-bg-panel px-3 py-2.5"
            >
              <div className="mb-2 flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h4 className="text-xs font-semibold text-ink">{check.title}</h4>
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

      <div className="mt-3 flex items-start gap-2 border border-line bg-bg-panel px-3 py-2 text-[11px] leading-relaxed text-ink-secondary">
        <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" />
        <p className="min-w-0 break-words">
          面板不会修改案件状态、关联告警或备注；报告元信息来自既有后端报告服务。
        </p>
      </div>
    </section>
  );
}
