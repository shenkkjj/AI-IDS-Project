"use client";

import { FileText, ShieldCheck, X } from "lucide-react";
import type { IncidentReportMeta } from "@/types/incident";

export interface IncidentReportPreviewProps {
  filename: string;
  meta: IncidentReportMeta;
  previewMarkdown: string;
  loadedAt: number;
  onClose: () => void;
}

function formatLoadedAt(epochMs: number): string {
  if (!epochMs || epochMs <= 0) return "-";
  return new Date(epochMs).toLocaleString("zh-CN", { hour12: false });
}

function renderMarkdownLine(line: string, index: number) {
  const trimmed = line.trim();
  const key = `${index}-${trimmed.slice(0, 16)}`;
  if (!trimmed) {
    return <div key={key} className="h-2" aria-hidden="true" />;
  }
  if (trimmed.startsWith("## ")) {
    return (
      <h4
        key={key}
        className="mt-3 first:mt-0 text-[11px] font-mono uppercase tracking-[0.12em] text-accent break-words"
      >
        {trimmed.replace(/^##\s+/, "")}
      </h4>
    );
  }
  if (trimmed.startsWith("# ")) {
    return (
      <h3 key={key} className="text-sm font-display text-ink break-words">
        {trimmed.replace(/^#\s+/, "")}
      </h3>
    );
  }
  if (trimmed.startsWith("- ") || trimmed.startsWith("> ")) {
    return (
      <p key={key} className="text-[11px] leading-relaxed text-ink-secondary break-words">
        {trimmed}
      </p>
    );
  }
  if (trimmed.startsWith("|")) {
    return (
      <p
        key={key}
        className="text-[10px] leading-relaxed font-mono text-ink-tertiary break-all"
      >
        {trimmed}
      </p>
    );
  }
  return (
    <p key={key} className="text-[11px] leading-relaxed text-ink-secondary break-words">
      {trimmed}
    </p>
  );
}

export default function IncidentReportPreview({
  filename,
  meta,
  previewMarkdown,
  loadedAt,
  onClose,
}: IncidentReportPreviewProps) {
  const lines = previewMarkdown.split(/\r?\n/).slice(0, 90);

  return (
    <section
      data-testid="incident-report-preview"
      className="mb-3 border border-line bg-bg-panel px-3 py-3 sm:px-4 sm:py-4 overflow-hidden"
      aria-label="案件报告预览"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-[0.15em] text-accent">
            <FileText className="w-3 h-3 shrink-0" />
            报告预览
          </div>
          <div
            data-testid="incident-report-preview-filename"
            className="mt-1 text-sm font-mono text-ink break-all"
          >
            {filename}
          </div>
          <div className="mt-1 text-[10px] font-mono text-ink-tertiary">
            生成于 {formatLoadedAt(loadedAt)}
          </div>
        </div>
        <button
          type="button"
          data-testid="incident-report-preview-close"
          onClick={onClose}
          className="inline-flex h-7 w-7 shrink-0 items-center justify-center border border-line text-ink-tertiary hover:text-ink hover:border-ink-tertiary transition-colors"
          aria-label="关闭报告预览"
          title="关闭报告预览"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      <div
        data-testid="incident-report-preview-meta"
        className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4"
      >
        <div className="border border-line px-2 py-2">
          <div className="text-[9px] font-mono uppercase tracking-[0.12em] text-ink-tertiary">
            告警
          </div>
          <div className="mt-1 text-sm font-mono text-ink">
            {meta.included_alerts}/{meta.alert_count}
          </div>
        </div>
        <div className="border border-line px-2 py-2">
          <div className="text-[9px] font-mono uppercase tracking-[0.12em] text-ink-tertiary">
            事件
          </div>
          <div className="mt-1 text-sm font-mono text-ink">
            {meta.included_events}/{meta.event_count}
          </div>
        </div>
        <div className="border border-line px-2 py-2">
          <div className="text-[9px] font-mono uppercase tracking-[0.12em] text-ink-tertiary">
            脱敏
          </div>
          <div className="mt-1 text-sm font-mono text-ink">
            {meta.redaction_count}
          </div>
        </div>
        <div className="border border-line px-2 py-2">
          <div className="text-[9px] font-mono uppercase tracking-[0.12em] text-ink-tertiary">
            截断
          </div>
          <div className="mt-1 text-sm font-mono text-ink">
            {meta.truncated ? "是" : "否"}
          </div>
        </div>
      </div>

      <div className="mt-3 flex items-start gap-2 border border-line bg-bg-raised px-2.5 py-2 text-[11px] text-ink-secondary">
        <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" />
        <p className="leading-relaxed break-words">
          已脱敏；{meta.truncated ? "部分告警或事件已截断。" : "未触发条目截断。"}
          预览只显示后端报告片段，复制和下载会重新拉取完整脱敏报告。
        </p>
      </div>

      <div
        data-testid="incident-report-preview-body"
        className="mt-3 max-h-[360px] overflow-y-auto overflow-x-hidden border border-line bg-bg-raised px-3 py-3"
      >
        <div className="space-y-1.5">{lines.map(renderMarkdownLine)}</div>
      </div>
    </section>
  );
}
