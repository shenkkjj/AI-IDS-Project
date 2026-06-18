"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { History, Loader2 } from "lucide-react";
import type { AlertTriageEvent, AlertTriageStatus } from "@/types/alert";
import { TRIAGE_STATUS_OPTIONS } from "@/types/alert";

/**
 * 告警研判历史列表 (M3-03)。
 *
 * 设计要点:
 * - 紧凑列表,不弹模态;最近 5 条,newest-first。
 * - 历史加载失败显示低调错误态,不阻断保存操作。
 * - 切换告警或保存成功后自动重新拉取。
 * - 不展示后端 stack trace / 完整 traceback;error 文案走中文 + HTTP code 简述。
 */

export interface AlertTriageHistoryProps {
  alertId: string | null | undefined;
  loadHistory: (
    alertId: string,
    options?: { limit?: number; signal?: AbortSignal }
  ) => Promise<{ ok: boolean; items?: AlertTriageEvent[]; error?: string }>;
  /** 最近一次保存成功的 epoch,触发自动刷新。 */
  refreshKey?: number;
  /** 历史拉取条数,默认 5。 */
  limit?: number;
}

type LoadState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ready"; items: AlertTriageEvent[] }
  | { kind: "error"; message: string };

const STATUS_LABEL: Record<AlertTriageStatus, string> = TRIAGE_STATUS_OPTIONS.reduce(
  (acc, opt) => {
    acc[opt.value] = opt.label;
    return acc;
  },
  {} as Record<AlertTriageStatus, string>
);

function formatEventTime(epoch: number): string {
  if (!Number.isFinite(epoch) || epoch <= 0) {
    return "—";
  }
  return new Date(epoch * 1000).toLocaleString("zh-CN", { hour12: false });
}

function statusText(status: AlertTriageStatus | null | undefined): string {
  if (!status) return "—";
  return STATUS_LABEL[status] || status;
}

function describeEvent(event: AlertTriageEvent): string {
  const from = statusText(event.from_status);
  const to = statusText(event.to_status);
  return `${from} → ${to}`;
}

export default function AlertTriageHistory({
  alertId,
  loadHistory,
  refreshKey,
  limit = 5,
}: AlertTriageHistoryProps) {
  const [state, setState] = useState<LoadState>({ kind: "idle" });
  const abortRef = useRef<AbortController | null>(null);

  const fetchHistory = useCallback(async () => {
    if (!alertId) {
      setState({ kind: "idle" });
      return;
    }
    if (abortRef.current) {
      abortRef.current.abort();
    }
    const controller = new AbortController();
    abortRef.current = controller;
    setState({ kind: "loading" });
    const result = await loadHistory(alertId, { limit, signal: controller.signal });
    if (controller.signal.aborted) {
      return;
    }
    if (result.ok && result.items) {
      setState({ kind: "ready", items: result.items });
    } else {
      setState({ kind: "error", message: result.error || "历史加载失败" });
    }
  }, [alertId, loadHistory, limit]);

  useEffect(() => {
    void fetchHistory();
    return () => {
      if (abortRef.current) abortRef.current.abort();
    };
  }, [fetchHistory, refreshKey]);

  if (!alertId) {
    return null;
  }

  return (
    <section
      data-testid="alert-triage-history"
      data-alert-id={alertId}
      className="border-t border-line bg-bg-raised/40 px-5 py-3 space-y-2"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary">
          <History className="w-3 h-3" />
          研判历史
        </div>
        {state.kind === "loading" ? (
          <span className="inline-flex items-center gap-1 text-[10px] font-mono text-ink-tertiary">
            <Loader2 className="w-3 h-3 animate-spin" />
            加载中
          </span>
        ) : state.kind === "ready" ? (
          <span className="text-[10px] font-mono text-ink-tertiary">
            最近 {state.items.length} 条
          </span>
        ) : null}
      </div>

      {state.kind === "error" ? (
        <div
          data-testid="triage-history-error"
          className="text-[10px] font-mono text-ink-tertiary"
        >
          历史加载失败 · {state.message}
        </div>
      ) : null}

      {state.kind === "ready" && state.items.length === 0 ? (
        <div className="text-[10px] font-mono text-ink-tertiary">
          暂无研判历史
        </div>
      ) : null}

      {state.kind === "ready" && state.items.length > 0 ? (
        <ol className="space-y-1.5" data-testid="triage-history-list">
          {state.items.map((event) => (
            <li
              key={event.id}
              data-testid="triage-history-item"
              className="text-[11px] text-ink leading-relaxed border-l border-line pl-3"
            >
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <span className="font-mono text-ink">
                  {describeEvent(event)}
                </span>
                <span className="text-[10px] font-mono text-ink-tertiary">
                  {formatEventTime(event.created_at)}
                  {event.updated_by !== null ? ` · #${event.updated_by}` : ""}
                </span>
              </div>
              {event.disposition ? (
                <div className="text-[10px] font-mono text-ink-tertiary break-all">
                  处置: {event.disposition}
                </div>
              ) : null}
              {event.analyst_note ? (
                <div className="text-[11px] text-ink-secondary break-words whitespace-pre-wrap mt-0.5">
                  {event.analyst_note}
                </div>
              ) : null}
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}
