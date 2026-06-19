"use client";

import { Send, Sparkles } from "lucide-react";
import type { CopilotMessage } from "@/types/copilot";

type CopilotPanelProps = {
  messages: CopilotMessage[];
  draft: string;
  loading: boolean;
  contextLabel?: string;
  onDraftChange: (value: string) => void;
  onSend: () => void;
  onAnalyzeAlert?: () => void;
};

export default function CopilotPanel({
  messages,
  draft,
  loading,
  contextLabel,
  onDraftChange,
  onSend,
  onAnalyzeAlert,
}: CopilotPanelProps) {
  return (
    <div className="h-full flex flex-col border-l border-accent">
      <div className="px-5 py-3 flex items-baseline justify-between border-b border-line">
        <span className="font-display text-base text-ink flex items-center gap-2">
          <Sparkles className="w-3.5 h-3.5 text-accent" />
          AI 助手
        </span>
        <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-accent">
          ON
        </span>
      </div>
      <div className="px-5 py-3 border-b border-line-subtle">
        <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary truncate">
          {contextLabel || "通用咨询模式"}
        </div>
        {onAnalyzeAlert ? (
          <button
            type="button"
            onClick={onAnalyzeAlert}
            disabled={loading}
            data-testid="analyze-current-alert"
            className="mt-2 text-[10px] font-mono uppercase tracking-[0.15em] text-accent hover:text-accent-hover disabled:opacity-30 transition-colors"
          >
            分析当前告警
          </button>
        ) : null}
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4 min-h-0">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center text-ink-tertiary text-xs gap-2 py-8">
            <Sparkles className="w-5 h-5 text-ink-tertiary" />
            <div>开始与 AI 助手对话</div>
            <div className="text-[10px] font-mono">上下文 · 流式响应 · 告警关联</div>
          </div>
        ) : (
          messages.map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              data-testid="copilot-message"
              data-role={message.role}
              className={`flex flex-col ${message.role === "user" ? "items-end" : "items-start"}`}
            >
              <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary mb-1.5">
                {message.role === "assistant" ? "AI" : "YOU"}
              </span>
              <div
                className={`px-3 py-2 text-xs max-w-[90%] leading-relaxed rounded-md ${
                  message.role === "assistant"
                    ? "bg-bg-sunken text-ink"
                    : "bg-accent text-white"
                }`}
              >
                {message.content || (loading && message.role === "assistant" ? (
                  <span className="inline-flex gap-1 font-mono">
                    <span className="animate-pulse">·</span>
                    <span className="animate-pulse" style={{ animationDelay: "150ms" }}>·</span>
                    <span className="animate-pulse" style={{ animationDelay: "300ms" }}>·</span>
                  </span>
                ) : null)}
              </div>
            </div>
          ))
        )}
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (!draft.trim() || loading) return;
          onSend();
        }}
        className="px-3 py-3 border-t border-line"
      >
        <div className="flex items-center gap-2">
          <input
            value={draft}
            onChange={(event) => onDraftChange(event.target.value)}
            placeholder="输入问题..."
            className="flex-1 bg-transparent text-ink text-xs py-1.5 px-0 border-0 border-b border-line focus:outline-none focus:border-accent transition-colors placeholder:text-ink-tertiary"
          />
          <button
            type="submit"
            disabled={loading || !draft.trim()}
            className="text-accent hover:text-accent-hover disabled:opacity-30 transition-colors p-1"
            title="发送给 Copilot"
            aria-label="发送给 Copilot"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </div>
      </form>
    </div>
  );
}
