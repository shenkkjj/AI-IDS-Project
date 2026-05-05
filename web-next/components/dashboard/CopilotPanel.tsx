"use client";

import { Send } from "lucide-react";

type CopilotMessage = {
  role: "user" | "assistant";
  content: string;
};

type CopilotPanelProps = {
  messages: CopilotMessage[];
  draft: string;
  loading: boolean;
  onDraftChange: (value: string) => void;
  onSend: () => void;
};

export default function CopilotPanel({ messages, draft, loading, onDraftChange, onSend }: CopilotPanelProps) {
  return (
    <div className="h-full flex flex-col bg-surface rounded-apple-lg shadow-card overflow-hidden">
      <div className="bg-background p-4 border-b border-border-subtle flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text">AI 助手</h3>
        <span className="w-2 h-2 bg-primary rounded-full" />
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message, index) => (
          <div key={`${message.role}-${index}`} className={`flex flex-col ${message.role === "user" ? "items-end" : "items-start"}`}>
            <span className="text-[11px] text-text-tertiary font-medium mb-1">{message.role === "assistant" ? "系统" : "用户"}</span>
            <div
              className={`p-3 text-sm max-w-[90%] rounded-apple ${
                message.role === "assistant"
                  ? "bg-background text-text"
                  : "bg-primary text-white"
              }`}
            >
              {message.content}
            </div>
          </div>
        ))}
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (!draft.trim() || loading) {
            return;
          }
          onSend();
        }}
        className="p-4 border-t border-border-subtle bg-surface"
      >
        <div className="flex items-center gap-2">
          <input
            value={draft}
            onChange={(event) => onDraftChange(event.target.value)}
            placeholder="输入问题..."
            className="flex-1 bg-background border border-border-subtle rounded-apple text-text text-sm py-2.5 px-3 focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all"
          />
          <button
            type="submit"
            disabled={loading || !draft.trim()}
            className="w-10 h-10 bg-primary text-white rounded-apple flex items-center justify-center hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </form>
    </div>
  );
}
