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
    <div className="h-full flex flex-col backdrop-blur-md border border-cyber-cyan/50 shadow-neon-cyan bg-black/60 rounded-sm overflow-hidden">
      <div className="bg-cyber-cyan/10 p-3 border-b border-cyber-cyan/30 flex items-center justify-between">
        <h3 className="text-cyber-cyan font-bold tracking-wider uppercase text-sm">Nexus AI Copilot</h3>
        <span className="w-2 h-2 bg-cyber-cyan rounded-full animate-pulse shadow-[0_0_5px_#00F5FF]" />
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message, index) => (
          <div key={`${message.role}-${index}`} className={`flex flex-col ${message.role === "user" ? "items-end" : "items-start"}`}>
            <span className="text-[10px] text-cyber-text/40 uppercase mb-1">{message.role === "assistant" ? "SYSTEM" : "OPERATOR"}</span>
            <div
              className={`p-2 text-sm max-w-[90%] rounded-sm ${
                message.role === "assistant"
                  ? "bg-cyber-cyan/10 border-l-2 border-cyber-cyan text-cyber-text"
                  : "bg-cyber-purple/20 border-r-2 border-cyber-purple text-cyber-text"
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
        className="p-3 border-t border-cyber-cyan/30 bg-black/40"
      >
        <div className="relative flex items-center gap-2">
          <span className="text-cyber-cyan/70 text-sm">&gt;</span>
          <input
            type="text"
            value={draft}
            onChange={(event) => onDraftChange(event.target.value)}
            className="w-full bg-black/50 border border-cyber-cyan/30 text-cyber-text text-sm py-2 px-2 focus:outline-none focus:border-cyber-cyan focus:shadow-[0_0_8px_rgba(0,245,255,0.3)] transition-all placeholder-cyber-text/30"
            placeholder="Input command..."
          />
          <button
            type="submit"
            disabled={!draft.trim() || loading}
            className="px-3 py-2 border border-cyber-cyan/50 text-cyber-cyan hover:bg-cyber-cyan hover:text-cyber-bg disabled:opacity-40"
          >
            {loading ? "..." : "Send"}
          </button>
        </div>
      </form>
    </div>
  );
}
