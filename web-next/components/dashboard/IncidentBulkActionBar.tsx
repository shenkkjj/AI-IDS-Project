"use client";

import { CheckSquare, Clipboard, Eraser, ListPlus, SquareCheckBig } from "lucide-react";
import type { BulkCopyStatus } from "@/types/incidentBulkActions";

export interface IncidentBulkActionBarProps {
  selectedCount: number;
  visibleCount: number;
  filterLabel: string;
  copyStatus: BulkCopyStatus;
  onSelectPage: () => void;
  onClearSelection: () => void;
  onCopySummary: () => void;
  onAddToQueue: () => void;
}

export default function IncidentBulkActionBar({
  selectedCount,
  visibleCount,
  filterLabel,
  copyStatus,
  onSelectPage,
  onClearSelection,
  onCopySummary,
  onAddToQueue,
}: IncidentBulkActionBarProps) {
  const hasSelection = selectedCount > 0;
  const hasVisibleItems = visibleCount > 0;
  const copyLabel =
    copyStatus === "copied"
      ? "已复制"
      : copyStatus === "failed"
      ? "复制失败"
      : hasSelection
      ? "准备复制"
      : "等待选择";

  return (
    <div
      data-testid="incident-bulk-action-bar"
      className="border border-line bg-bg-raised px-3 py-2.5 space-y-2"
    >
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="min-w-0">
          <div className="text-[10px] font-mono uppercase text-ink-tertiary">
            批量操作
          </div>
          <div
            data-testid="incident-bulk-selected-count"
            className="text-xs font-mono text-ink"
            aria-live="polite"
          >
            已选择 {selectedCount} / 当前 {filterLabel} {visibleCount} 个案件
          </div>
        </div>
        <div
          data-testid="incident-bulk-copy-status"
          className="text-[10px] font-mono text-ink-tertiary"
          role="status"
          aria-live="polite"
        >
          {copyLabel}
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5">
        <button
          type="button"
          data-testid="incident-bulk-select-page"
          onClick={onSelectPage}
          disabled={!hasVisibleItems}
          className="inline-flex items-center gap-1.5 px-2 py-1 text-[10px] font-mono uppercase border border-line text-ink-tertiary hover:text-ink hover:border-ink-tertiary transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          <SquareCheckBig className="w-3 h-3" aria-hidden />
          全选当前列表
        </button>
        <button
          type="button"
          data-testid="incident-bulk-clear-selection"
          onClick={onClearSelection}
          disabled={!hasSelection}
          className="inline-flex items-center gap-1.5 px-2 py-1 text-[10px] font-mono uppercase border border-line text-ink-tertiary hover:text-ink hover:border-ink-tertiary transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          <Eraser className="w-3 h-3" aria-hidden />
          清空选择
        </button>
        <button
          type="button"
          data-testid="incident-bulk-copy-summary"
          onClick={onCopySummary}
          disabled={!hasSelection}
          className="inline-flex items-center gap-1.5 px-2 py-1 text-[10px] font-mono uppercase border border-accent text-accent hover:bg-accent-soft transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          {copyStatus === "copied" ? (
            <CheckSquare className="w-3 h-3" aria-hidden />
          ) : (
            <Clipboard className="w-3 h-3" aria-hidden />
          )}
          复制安全摘要
        </button>
        <button
          type="button"
          data-testid="incident-add-export-queue"
          onClick={onAddToQueue}
          disabled={!hasSelection}
          className="inline-flex items-center gap-1.5 px-2 py-1 text-[10px] font-mono uppercase border border-accent text-accent hover:bg-accent-soft transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          <ListPlus className="w-3 h-3" aria-hidden />
          加入导出队列
        </button>
      </div>
    </div>
  );
}
