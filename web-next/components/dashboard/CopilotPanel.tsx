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
    <div className="h-full flex flex-col bg-white rounded-[18px] shadow-card overflow-hidden">
      <div className="bg-[#F5F5F7] p-4 border-b border-[#E8E8ED] flex items-center justify-between">
        <h3 className="text-sm font-semibold text-[#1D1D1F]">AI 助手</h3>
        <span className="w-2 h-2 bg-[#0071E3] rounded-full" />
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message, index) => (
          <div key={`${message.role}-${index}`} className={`flex flex-col ${message.role === "user" ? "items-end" : "items-start"}`}>
            <span className="text-[10px] text-[#A1A1A6] font-medium uppercase mb-1">{message.role === "assistant" ? "系统" : "用户"}</span>
            <div
              className={`p-3 text-sm max-w-[90%] rounded-[12px] ${
                message.role === "assistant"
                  ? "bg-[#F5F5F7] text-[#1D1D1F]"
                  : "bg-[#0071E3] text-white"
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
        className="p-4 border-t border-[#E8E8ED] bg-white"
      >
        <div className="relative flex items-center gap-2">
          <input
            type="text"
            value={draft}
            onChange={(event) => onDraftChange(event.target.value)}
            className="w-full bg-[#F5F5F7] border border-[#E8E8ED] text-[#1D1D1F] text-sm py-2.5 px-4 rounded-[12px] focus:outline-none focus:border-[#0071E3] focus:ring-2 focus:ring-[#0071E3]/20 transition-all placeholder:text-[#A1A1A6]"
            placeholder="输入命令..."
          />
          <button
            type="submit"
            disabled={!draft.trim() || loading}
            className="px-4 py-2.5 bg-[#0071E3] hover:bg-[#0077ED] text-white text-sm font-medium rounded-[12px] disabled:opacity-40 transition-colors"
          >
            {loading ? "..." : "发送"}
          </button>
        </div>
      </form>
    </div>
  );
}
