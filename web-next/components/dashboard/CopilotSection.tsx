"use client";

import { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import { Sparkles, WifiOff } from "lucide-react";
import type { CopilotMessage } from "@/types/copilot";

// Copilot 主体是 code-split 的；这边统一懒加载并在切换时显示一致占位
const CopilotPanel = dynamic(
  () => import("@/components/dashboard/CopilotPanel"),
  {
    ssr: false,
    loading: () => <div className="h-full bg-bg-raised/40 animate-pulse" />,
  }
);

/**
 * Copilot 区域壳。
 *
 * 接管了原 dashboard-client 中对 Copilot 的空/降级/上下文处理逻辑,
 * 把"面板态 + 上下文标签 + 可选降级说明"统一在一处渲染。
 *
 * 关键设计：`offline`（WebSocket 实时通道断开）不再等同于"AI 完全不可用"。
 * - 输入框、历史消息、发送按钮、analyze-alert 入口全部保留可见可用。
 * - 仅在头部显示 OFFLINE 标签 + 头部下方一条轻量提示条，
 *   说明实时 SSE 流式可能回退为分段响应，但 HTTP/SSE 请求仍可发。
 */
export interface CopilotSectionProps {
  messages: CopilotMessage[];
  draft: string;
  sending: boolean;
  contextLabel?: string;
  /** 显式标记"AI 助手当前不可用"，比如没有 key / 后端没就绪 */
  degraded?: boolean;
  degradedReason?: string;
  /** 是否离线：与 WebSocket 状态联动。离线仅影响头部与提示条，不影响面板可用性。 */
  offline?: boolean;
  onDraftChange: (value: string) => void;
  onSend: () => void;
  onAnalyzeAlert?: () => void;
}

export default function CopilotSection({
  messages,
  draft,
  sending,
  contextLabel,
  degraded = false,
  degradedReason,
  offline = false,
  onDraftChange,
  onSend,
  onAnalyzeAlert,
}: CopilotSectionProps) {
  // 内部维护一个轻量的"通知"状态(降级时显示的 hint)
  const [showDegraded, setShowDegraded] = useState(false);

  useEffect(() => {
    if (!degraded) {
      setShowDegraded(false);
      return;
    }
    setShowDegraded(true);
  }, [degraded]);

  return (
    <div className="h-full min-h-[480px] flex flex-col">
      <CopilotHeader
        degraded={degraded}
        degradedReason={degradedReason}
        showDegraded={showDegraded}
        offline={offline}
      />
      {offline ? <OfflineNotice /> : null}
      <CopilotPanel
        messages={messages}
        draft={draft}
        loading={sending}
        contextLabel={contextLabel}
        onDraftChange={onDraftChange}
        onSend={onSend}
        onAnalyzeAlert={degraded ? undefined : onAnalyzeAlert}
      />
    </div>
  );
}

function OfflineNotice() {
  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="copilot-offline-notice"
      className="mx-5 mt-3 mb-1 flex items-start gap-2 text-[11px] font-mono text-warning bg-warning-soft border-l-2 border-warning px-3 py-2 rounded-md"
    >
      <WifiOff className="w-3.5 h-3.5 mt-px shrink-0" />
      <div className="leading-relaxed">
        实时通道已断开。Copilot 仍可继续输入与发送，HTTP/SSE 请求会按最近一次成功路径提交；
        流式输出可能回退为分段响应，恢复连接后自动切回实时通道。
      </div>
    </div>
  );
}

function CopilotHeader({
  degraded = false,
  degradedReason,
  showDegraded = false,
  offline = false,
}: {
  degraded?: boolean;
  degradedReason?: string;
  showDegraded?: boolean;
  offline?: boolean;
}) {
  return (
    <div className="px-5 py-3 flex items-baseline justify-between border-b border-line">
      <span className="font-display text-base text-ink flex items-center gap-2">
        <Sparkles className={`w-3.5 h-3.5 ${offline ? "text-warning" : "text-accent"}`} />
        AI 助手
      </span>
      <span
        data-testid="copilot-status"
        data-offline={offline ? "true" : "false"}
        className={`text-[10px] font-mono uppercase tracking-[0.15em] ${
          offline
            ? "text-warning"
            : degraded && showDegraded
              ? "text-warning"
              : "text-accent"
        }`}
      >
        {offline ? "OFFLINE" : degraded && showDegraded ? "DEGRADED" : "ON"}
      </span>
      {degraded && showDegraded && degradedReason ? (
        <span className="hidden">{degradedReason}</span>
      ) : null}
    </div>
  );
}
