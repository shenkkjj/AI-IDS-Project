"use client";

import { useEffect, useRef, useState } from "react";

type HackerTerminalProps = {
  lines: string[];
  onCommand: (command: string) => void;
};

export default function HackerTerminal({ lines, onCommand }: HackerTerminalProps) {
  const [command, setCommand] = useState("");
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  return (
    <div className="bg-[#1D1D1F] rounded-[18px] shadow-card p-5 h-full min-h-[300px] flex flex-col font-mono relative overflow-hidden">
      <div className="flex justify-between items-center mb-3 pb-3 border-b border-white/10">
        <h3 className="text-xs font-semibold text-white/60 uppercase tracking-wider">终端输出</h3>
        <span className="text-white/30 text-xs">tty1</span>
      </div>

      <div className="flex-1 overflow-y-auto pr-2 text-xs md:text-sm text-white/70 space-y-1">
        {lines.map((line, index) => {
          const lower = line.toLowerCase();
          let color = "text-white/70";
          if (lower.includes("error") || lower.includes("failed") || lower.includes("401")) {
            color = "text-[#FF453A]";
          } else if (lower.includes("warn") || lower.includes("blocked") || lower.includes("422")) {
            color = "text-[#FF9F0A]";
          }

          return (
            <div key={`${line}-${index}`} className={`${color} break-all`}>
              <span className="opacity-30 mr-2">&gt;</span>
              {line}
            </div>
          );
        })}
        <div ref={endRef} />
      </div>

      <form
        className="pt-3 border-t border-white/10 mt-2"
        onSubmit={(event) => {
          event.preventDefault();
          const text = command.trim();
          if (!text) {
            return;
          }
          onCommand(text);
          setCommand("");
        }}
      >
        <div className="flex items-center gap-2">
          <span className="text-white/40">$</span>
          <input
            value={command}
            onChange={(event) => setCommand(event.target.value)}
            placeholder="help | stats | tail"
            className="flex-1 bg-transparent outline-none text-white/60 placeholder:text-white/20"
          />
        </div>
      </form>
    </div>
  );
}
