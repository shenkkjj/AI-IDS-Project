"use client";

import type { ReactNode } from "react";
import { AlertTriangle, Inbox, Loader2, Power, RefreshCcw, ShieldAlert, WifiOff } from "lucide-react";

/**
 * 状态壳：统一渲染 loading / empty / error / degraded / offline 五态。
 *
 * 设计原则：
 * - 不强制写一个空 div 占位；统一 icon + title + description + action。
 * - `tone="offline"` 与 `tone="error"` 的差别：offline 暗示网络/WS 断开，
 *   error 暗示后端 5xx/4xx 业务失败。两者均允许渲染不同 icon。
 * - 不引入新依赖；图标沿用 lucide-react。
 */

export type StatusTone = "loading" | "empty" | "error" | "degraded" | "offline" | "ready";

export interface StatusViewProps {
  tone: StatusTone;
  title: string;
  description?: string;
  action?: ReactNode;
  /** 高度控制：默认 min-h-[180px]，可被覆盖 */
  minHeight?: number;
  testId?: string;
}

const TONE_META: Record<
  Exclude<StatusTone, "ready">,
  { icon: typeof Loader2; iconClass: string; testId: string }
> = {
  loading: {
    icon: Loader2,
    iconClass: "text-ink-tertiary animate-spin",
    testId: "status-view-loading",
  },
  empty: {
    icon: Inbox,
    iconClass: "text-ink-tertiary",
    testId: "status-view-empty",
  },
  error: {
    icon: ShieldAlert,
    iconClass: "text-danger",
    testId: "status-view-error",
  },
  degraded: {
    icon: AlertTriangle,
    iconClass: "text-warning",
    testId: "status-view-degraded",
  },
  offline: {
    icon: WifiOff,
    iconClass: "text-warning",
    testId: "status-view-offline",
  },
};

export default function StatusView({
  tone,
  title,
  description,
  action,
  minHeight = 180,
  testId,
}: StatusViewProps) {
  // ready 不渲染任何壳，由调用方继续渲染
  if (tone === "ready") {
    return null;
  }

  const meta = TONE_META[tone];
  const Icon = meta.icon;

  return (
    <div
      data-testid={testId || meta.testId}
      data-status-tone={tone}
      className="flex flex-col items-center justify-center text-center gap-3 px-6 py-8"
      style={{ minHeight }}
    >
      <Icon className={`w-6 h-6 ${meta.iconClass}`} />
      <div className="space-y-1">
        <div className="text-sm text-ink">{title}</div>
        {description ? (
          <div className="text-xs text-ink-tertiary max-w-md mx-auto leading-relaxed">
            {description}
          </div>
        ) : null}
      </div>
      {action ? <div className="pt-1">{action}</div> : null}
    </div>
  );
}

/**
 * 给调用方方便拼出"刷新"按钮的 helper。
 * - `onRetry` 用于 error/empty/degraded。
 * - `onRetry` 不是必传；当未传时只渲染 description，不渲染按钮。
 */
export function buildRetryAction(
  onRetry?: () => void,
  label = "重试"
): ReactNode {
  if (!onRetry) return null;
  return (
    <button
      type="button"
      onClick={onRetry}
      className="inline-flex items-center gap-1.5 text-[11px] font-mono uppercase tracking-[0.15em] text-accent hover:text-accent-hover transition-colors"
    >
      <RefreshCcw className="w-3 h-3" />
      {label}
    </button>
  );
}

/** `Power` 重启按钮的 icon 复出口，方便以后做"重启 demo"动作 */
export { Power };
