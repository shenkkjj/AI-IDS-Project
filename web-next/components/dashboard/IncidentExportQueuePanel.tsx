"use client";

import { Clock3, Trash2 } from "lucide-react";
import type { IncidentExportQueueItem } from "@/types/incidentBulkActions";

export interface IncidentExportQueuePanelProps {
  queue: IncidentExportQueueItem[];
  onClear: () => void;
}

function formatQueuedAt(epochMs: number): string {
  if (!epochMs || epochMs <= 0) return "刚刚";
  return new Date(epochMs).toLocaleTimeString("zh-CN", { hour12: false });
}

export default function IncidentExportQueuePanel({
  queue,
  onClear,
}: IncidentExportQueuePanelProps) {
  const latest = queue.at(-1);

  return (
    <div
      data-testid="incident-export-queue-panel"
      className="border border-line-subtle bg-bg px-3 py-2.5 space-y-2"
    >
      <div className="flex items-start justify-between gap-2 flex-wrap">
        <div className="min-w-0">
          <div className="text-[10px] font-mono uppercase text-ink-tertiary inline-flex items-center gap-1.5">
            <Clock3 className="w-3 h-3" aria-hidden />
            前端导出准备队列
          </div>
          <div className="mt-1 text-xs text-ink-secondary leading-relaxed">
            当前只是待逐案导出的前端准备队列，不是后台导出任务。
          </div>
          <div
            data-testid="incident-export-queue-count"
            className="mt-1 text-[11px] font-mono text-ink"
            aria-live="polite"
          >
            队列 {queue.length} 个案件
            {latest ? (
              <span className="break-all"> · 最近 {latest.incident_id}</span>
            ) : null}
          </div>
        </div>
        <button
          type="button"
          data-testid="incident-export-queue-clear"
          onClick={onClear}
          disabled={queue.length === 0}
          className="inline-flex items-center gap-1.5 px-2 py-1 text-[10px] font-mono uppercase border border-line text-ink-tertiary hover:text-ink hover:border-ink-tertiary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Trash2 className="w-3 h-3" aria-hidden />
          清空队列
        </button>
      </div>

      {queue.length > 0 ? (
        <ol className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
          {queue.map((item) => (
            <li
              key={item.incident_id}
              data-testid="incident-export-queue-item"
              data-incident-id={item.incident_id}
              className="border border-line-subtle px-2 py-1.5"
            >
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <span className="text-[11px] font-mono text-ink break-all">
                  {item.incident_id}
                </span>
                <span className="text-[10px] font-mono text-ink-tertiary">
                  {formatQueuedAt(item.queued_at)}
                </span>
              </div>
              <div className="mt-1 text-[10px] font-mono text-ink-tertiary break-words">
                status={item.status} · severity={item.severity} · alerts=
                {item.alert_count} · title_length={item.title_length} ·
                closed_at={item.closed_at_present ? "present" : "absent"}
              </div>
              <div className="mt-1 text-[10px] text-ink-secondary">
                仅保留安全字段，后续逐案打开详情导出报告。
              </div>
            </li>
          ))}
        </ol>
      ) : (
        <div className="text-[11px] text-ink-tertiary">
          选择案件后可加入准备队列，刷新页面会清空。
        </div>
      )}
    </div>
  );
}
