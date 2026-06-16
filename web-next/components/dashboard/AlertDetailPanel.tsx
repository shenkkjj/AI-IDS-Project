"use client";

import { useState, useCallback } from "react";
import { Clipboard, ClipboardCheck, ShieldAlert } from "lucide-react";
import type { AlertDetail } from "@/types/alertBriefing";
import StatusView from "./StatusView";

/**
 * 告警详情面板。
 *
 * - 数据来自 `deriveAlertDetail(alert)`,不在组件内做风险判定。
 * - 包含风险等级 / 攻击类别 / 证据 / 影响 / 建议动作 / 可复制报告。
 * - 空态：未选中告警时使用 StatusView.tone="empty"。
 * - 错误态：本组件不直接发请求,错误由 `AlertSection` 拦截后传入。
 */
export interface AlertDetailPanelProps {
  detail: AlertDetail | null;
  /** 当前选中的告警 id（用于追踪） */
  alertId?: string;
  /** 触发复制报告回调,默认是 navigator.clipboard */
  onCopyReport?: (report: string) => Promise<boolean> | boolean;
  /** 触发"分析当前告警"回调,触发后由 Copilot 接管 */
  onAnalyzeInCopilot?: () => void;
}

const TONE_CLASS: Record<AlertDetail["riskTone"], string> = {
  danger: "text-danger",
  warning: "text-warning",
  info: "text-info",
  default: "text-ink-tertiary",
};

const TONE_BG: Record<AlertDetail["riskTone"], string> = {
  danger: "bg-danger-soft border-danger",
  warning: "bg-warning-soft border-warning",
  info: "bg-info-soft border-info",
  default: "bg-bg-sunken border-line",
};

export default function AlertDetailPanel({
  detail,
  alertId,
  onCopyReport,
  onAnalyzeInCopilot,
}: AlertDetailPanelProps) {
  const [copied, setCopied] = useState<"none" | "report" | "summary">("none");

  const handleCopyReport = useCallback(async () => {
    if (!detail) return;
    try {
      let ok = false;
      if (onCopyReport) {
        ok = await onCopyReport(detail.report);
      } else if (typeof navigator !== "undefined" && navigator.clipboard) {
        await navigator.clipboard.writeText(detail.report);
        ok = true;
      }
      if (ok) {
        setCopied("report");
        window.setTimeout(() => setCopied("none"), 1800);
      }
    } catch {
      // ignore: 静默失败,用户可重试
    }
  }, [detail, onCopyReport]);

  if (!detail) {
    return (
      <StatusView
        tone="empty"
        title="未选择告警"
        description="从左侧列表中选中一条告警以查看风险、证据、影响和建议动作。"
        minHeight={260}
      />
    );
  }

  return (
    <div
      data-testid="alert-detail-panel"
      data-alert-id={alertId}
      className="border-l border-accent bg-bg-raised flex flex-col"
    >
      {/* 头部：风险等级 + 时间戳 */}
      <div
        className={`px-5 py-4 border-l-4 ${TONE_BG[detail.riskTone]}`}
      >
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <ShieldAlert className={`w-3.5 h-3.5 ${TONE_CLASS[detail.riskTone]}`} />
            <span className={`text-[10px] font-mono uppercase tracking-[0.2em] ${TONE_CLASS[detail.riskTone]}`}>
              {detail.riskLabel} · {detail.attackClass}
            </span>
          </div>
          <span className="text-[10px] font-mono text-ink-tertiary">
            {detail.timestampLabel}
          </span>
        </div>
        <div className="mt-2 text-sm text-ink leading-relaxed break-words">
          {detail.evidence}
        </div>
        <div className="mt-1 text-[11px] text-ink-secondary">
          {detail.impact}
        </div>
      </div>

      {/* 主体：建议动作 + 模型摘要 */}
      <div className="flex-1 px-5 py-4 space-y-4 overflow-y-auto min-h-0">
        <section>
          <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary mb-2">
            建议动作
          </div>
          {detail.recommendedActions.length > 0 ? (
            <ol className="space-y-1.5 text-xs text-ink leading-relaxed list-decimal pl-4">
              {detail.recommendedActions.map((action, index) => (
                <li key={`${action}-${index}`}>{action}</li>
              ))}
            </ol>
          ) : (
            <div className="text-xs text-ink-tertiary">暂无建议动作</div>
          )}
        </section>

        {onAnalyzeInCopilot ? (
          <button
            type="button"
            onClick={onAnalyzeInCopilot}
            data-testid="alert-detail-analyze"
            className="text-[10px] font-mono uppercase tracking-[0.15em] text-accent hover:text-accent-hover transition-colors"
          >
            在 AI 助手中继续分析 →
          </button>
        ) : null}
      </div>

      {/* 底部：可复制报告 */}
      <div className="px-5 py-3 border-t border-line flex items-center justify-between gap-2">
        <span className="text-[10px] font-mono text-ink-tertiary">
          报告 ID · {alertId || "—"}
        </span>
        <button
          type="button"
          onClick={() => void handleCopyReport()}
          data-testid="alert-detail-copy-report"
          className="inline-flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-[0.15em] text-accent hover:text-accent-hover transition-colors"
        >
          {copied === "report" ? (
            <>
              <ClipboardCheck className="w-3 h-3" />
              已复制报告
            </>
          ) : (
            <>
              <Clipboard className="w-3 h-3" />
              复制报告
            </>
          )}
        </button>
      </div>
    </div>
  );
}
