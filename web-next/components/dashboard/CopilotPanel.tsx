"use client";

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
    <div className="h-full flex flex-col backdrop-blur-md border border-slate-700/50 bg-[#0F172A]/80 rounded-lg overflow-hidden">
      <div className="bg-cyber-cyan/5 p-3 border-b border-slate-700/30 flex items-center justify-between">
        <h3 className="text-cyber-cyan font-bold tracking-wider uppercase text-sm">Nexus AI Copilot</h3>
        <span className="w-2 h-2 bg-cyber-cyan rounded-full animate-pulse" />
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message, index) => (
          <div key={`${message.role}-${index}`} className={`flex flex-col ${message.role === "user" ? "items-end" : "items-start"}`}>
            <span className="text-[10px] text-slate-600 uppercase mb-1">{message.role === "assistant" ? "SYSTEM" : "OPERATOR"}</span>
            <div
              className={`p-2.5 text-sm max-w-[90%] rounded-md ${
                message.role === "assistant"
                  ? "bg-cyber-cyan/5 border-l-2 border-cyber-cyan/50 text-slate-200"
                  : "bg-violet-500/5 border-r-2 border-violet-500/30 text-slate-200"
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
        className="p-3 border-t border-slate-700/30 bg-[#0B0F1A]/50"
      >
        <div className="relative flex items-center gap-2">
          <span className="text-cyber-cyan/50 text-sm">&gt;</span>
          <input
            type="text"
            value={draft}
            onChange={(event) => onDraftChange(event.target.value)}
            className="w-full bg-[#0B0F1A] border border-slate-700/50 text-slate-200 text-sm py-2 px-2 rounded focus:outline-none focus:border-cyber-cyan/50 focus:shadow-[0_0_6px_rgba(34,211,238,0.15)] transition-all placeholder-slate-600"
            placeholder="Input command..."
          />
          <button
            type="submit"
            disabled={!draft.trim() || loading}
            className="px-3 py-2 border border-cyber-cyan/40 text-cyber-cyan hover:bg-cyber-cyan hover:text-[#0B0F1A] disabled:opacity-40 rounded transition-colors"
          >
            {loading ? "..." : "Send"}
          </button>
        </div>
      </form>
    </div>
  );
}
