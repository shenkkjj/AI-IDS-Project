"use client";

import { useEffect, useMemo, useState, useCallback } from "react";
import { Check, Loader2 } from "lucide-react";
import type { AlertTriageStatus, AlertTriage, AlertTriageEvent } from "@/types/alert";
import { TRIAGE_STATUS_OPTIONS } from "@/types/alert";
import AlertTriageHistory from "./AlertTriageHistory";

/**
 * 告警研判与处置面板。
 *
 * 设计要点（docs/agent/M3_02_ALERT_TRIAGE_RESPONSE_WORKBENCH_TASK.md §4）:
 * - 紧凑 segmented controls 切换 5 个状态；不弹模态、不做营销式大卡片。
 * - 备注输入本地 state 优先，保存失败时不清空（保留当前输入）。
 * - loading / success / error 三态在保存按钮附近显示。
 * - 仅在 ``alertId`` 存在时渲染。
 * - 移动端 flex-wrap,不重叠不溢出。
 * - M3-03: 末尾集成 ``AlertTriageHistory``,展示最近 5 条 triage 历史;
 *   保存成功后由 ``refreshKey`` 触发自动重新拉取。
 */
export interface AlertTriagePanelProps {
  alertId: string | null | undefined;
  triage: AlertTriage | null | undefined;
  onSubmit: (input: {
    status: AlertTriageStatus;
    disposition: string | null;
    analyst_note: string | null;
  }) => Promise<boolean>;
  /** 当前是否离线（WS 断开 + 轮询失败时为 true） */
  offline?: boolean;
  /** M3-03: 加载研判历史;不传则不展示历史。 */
  loadHistory?: (
    alertId: string,
    options?: { limit?: number; signal?: AbortSignal }
  ) => Promise<{ ok: boolean; items?: AlertTriageEvent[]; error?: string }>;
  /** M3-03: 变更即重新拉取历史(由 dashboard 端在保存成功后自增)。 */
  refreshKey?: number;
  /** M3-03: 历史展示条数,默认 5。 */
  historyLimit?: number;
}

const NOTE_MAX_LENGTH = 800;
const DISPOSITION_MAX_LENGTH = 64;

type SaveState =
  | { kind: "idle" }
  | { kind: "saving" }
  | { kind: "success"; at: number }
  | { kind: "error"; message: string };

function formatTriageTimestamp(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return "未研判";
  }
  return new Date(seconds * 1000).toLocaleString("zh-CN", { hour12: false });
}

function TriageBadge({ status }: { status: AlertTriageStatus }) {
  const meta = TRIAGE_STATUS_OPTIONS.find((option) => option.value === status);
  const tone = meta?.tone || "default";
  const toneClass: Record<typeof tone, string> = {
    danger: "text-danger border-danger",
    warning: "text-warning border-warning",
    info: "text-info border-info",
    success: "text-success border-success",
    default: "text-ink-tertiary border-line",
  } as const;
  return (
    <span
      data-testid="triage-status-badge"
      data-status={status}
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-mono uppercase tracking-[0.15em] border ${toneClass[tone]}`}
    >
      <span aria-hidden>·</span>
      {meta?.shortLabel || status}
    </span>
  );
}

export default function AlertTriagePanel({
  alertId,
  triage,
  onSubmit,
  offline = false,
  loadHistory,
  refreshKey,
  historyLimit = 5,
}: AlertTriagePanelProps) {
  const initialStatus: AlertTriageStatus = triage?.status ?? "new";
  const [status, setStatus] = useState<AlertTriageStatus>(initialStatus);
  const [disposition, setDisposition] = useState<string>(triage?.disposition ?? "");
  const [note, setNote] = useState<string>(triage?.analyst_note ?? "");
  const [state, setState] = useState<SaveState>({ kind: "idle" });

  // 选中的告警变化时,本地 state 同步
  useEffect(() => {
    setStatus(initialStatus);
    setDisposition(triage?.disposition ?? "");
    setNote(triage?.analyst_note ?? "");
    setState({ kind: "idle" });
  }, [alertId, initialStatus, triage?.disposition, triage?.analyst_note]);

  const noteCount = note.length;
  const noteOverflow = noteCount > NOTE_MAX_LENGTH;
  const dispositionOverflow = disposition.length > DISPOSITION_MAX_LENGTH;

  const dirty = useMemo(() => {
    if (status !== initialStatus) return true;
    if ((triage?.disposition ?? "") !== disposition) return true;
    if ((triage?.analyst_note ?? "") !== note) return true;
    return false;
  }, [status, initialStatus, disposition, note, triage?.disposition, triage?.analyst_note]);

  const handleSave = useCallback(async () => {
    if (!alertId || noteOverflow || dispositionOverflow) {
      setState({
        kind: "error",
        message: noteOverflow
          ? `处置备注超过 ${NOTE_MAX_LENGTH} 字符上限`
          : "处置分类长度超限",
      });
      return;
    }
    setState({ kind: "saving" });
    try {
      const ok = await onSubmit({
        status,
        disposition: disposition.trim() || null,
        analyst_note: note.trim() || null,
      });
      if (ok) {
        setState({ kind: "success", at: Date.now() });
        window.setTimeout(() => {
          setState((current) =>
            current.kind === "success" ? { kind: "idle" } : current
          );
        }, 2200);
      } else {
        setState({ kind: "error", message: "保存失败,请稍后重试" });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "保存失败";
      setState({ kind: "error", message });
    }
  }, [alertId, noteOverflow, dispositionOverflow, onSubmit, status, disposition, note]);

  if (!alertId) {
    return null;
  }

  return (
    <section
      data-testid="alert-triage-panel"
      data-alert-id={alertId}
      className="border-t border-line bg-bg-raised px-5 py-4 space-y-3"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary">
          研判状态
        </div>
        <TriageBadge status={triage?.status ?? "new"} />
      </div>

      {/* 状态 segmented controls */}
      <div
        role="radiogroup"
        aria-label="研判状态"
        className="flex flex-wrap gap-1"
      >
        {TRIAGE_STATUS_OPTIONS.map((option) => {
          const isActive = status === option.value;
          const activeTone: Record<typeof option.tone, string> = {
            danger: "bg-danger-soft text-danger border-danger",
            warning: "bg-warning-soft text-warning border-warning",
            info: "bg-info-soft text-info border-info",
            success: "bg-success-soft text-success border-success",
            default: "bg-accent-soft text-accent border-accent",
          } as const;
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={isActive}
              data-testid={`triage-status-${option.value}`}
              onClick={() => setStatus(option.value)}
              className={`px-2 py-1 text-[11px] font-mono uppercase tracking-[0.1em] border transition-colors ${
                isActive
                  ? activeTone[option.tone]
                  : "border-line text-ink-tertiary hover:text-ink hover:border-ink-tertiary"
              }`}
            >
              {option.label}
            </button>
          );
        })}
      </div>

      {/* 处置分类 + 备注 */}
      <div className="grid grid-cols-1 md:grid-cols-[160px_1fr] gap-3">
        <div>
          <label className="block text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary mb-1.5">
            处置分类（可选）
          </label>
          <input
            type="text"
            value={disposition}
            onChange={(event) => setDisposition(event.target.value)}
            maxLength={DISPOSITION_MAX_LENGTH}
            placeholder="blocked_at_waf"
            className={`w-full bg-transparent text-ink text-xs py-1.5 px-0 border-0 border-b ${
              dispositionOverflow ? "border-danger" : "border-line"
            } focus:outline-none focus:border-accent transition-colors placeholder:text-ink-tertiary font-mono`}
          />
        </div>
        <div>
          <label className="block text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary mb-1.5">
            处置备注（{noteCount}/{NOTE_MAX_LENGTH}）
          </label>
          <textarea
            data-testid="triage-note-input"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            maxLength={NOTE_MAX_LENGTH + 32 /* 允许短暂超出以便显示提示 */}
            placeholder="例如:已确认 WAF 拦截生效,继续观察同源 IP"
            rows={3}
            className={`w-full bg-transparent text-ink text-xs leading-relaxed py-1.5 px-0 border-0 border-b ${
              noteOverflow ? "border-danger" : "border-line"
            } focus:outline-none focus:border-accent transition-colors placeholder:text-ink-tertiary resize-y min-h-[64px]`}
          />
        </div>
      </div>

      {/* 底部:更新时间 + 保存按钮 */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="text-[10px] font-mono text-ink-tertiary">
          {triage?.updated_at
            ? `上次更新: ${formatTriageTimestamp(triage.updated_at)}${
                triage.updated_by !== null ? ` · #${triage.updated_by}` : ""
              }`
            : "尚未研判"}
        </div>
        <div className="flex items-center gap-2">
          {state.kind === "error" ? (
            <span className="text-[10px] font-mono text-danger">{state.message}</span>
          ) : state.kind === "success" ? (
            <span className="text-[10px] font-mono text-success inline-flex items-center gap-1">
              <Check className="w-3 h-3" />
              已保存
            </span>
          ) : null}
          <button
            type="button"
            data-testid="triage-save"
            onClick={() => void handleSave()}
            disabled={
              state.kind === "saving" || offline || !dirty || noteOverflow || dispositionOverflow
            }
            className={`px-3 py-1.5 text-[10px] font-mono uppercase tracking-[0.15em] border transition-colors ${
              dirty
                ? "border-accent text-accent hover:bg-accent-soft"
                : "border-line text-ink-tertiary"
            } disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center gap-1.5`}
          >
            {state.kind === "saving" ? (
              <>
                <Loader2 className="w-3 h-3 animate-spin" />
                保存中
              </>
            ) : (
              "保存研判"
            )}
          </button>
        </div>
      </div>

      {/* M3-03: 研判历史(可选,父组件传 loadHistory 才展示) */}
      {loadHistory ? (
        <AlertTriageHistory
          alertId={alertId}
          loadHistory={loadHistory}
          refreshKey={refreshKey}
          limit={historyLimit}
        />
      ) : null}
    </section>
  );
}
