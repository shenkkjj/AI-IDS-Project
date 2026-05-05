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
    <div className="bg-[#080C14] border border-slate-700/50 rounded-lg p-4 h-full min-h-[300px] flex flex-col font-mono relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.2)_50%),linear-gradient(90deg,rgba(255,0,0,0.03),rgba(0,255,0,0.01),rgba(0,0,255,0.03))] bg-[length:100%_4px,3px_100%] z-10 opacity-30" />

      <div className="flex justify-between items-center mb-2 pb-2 border-b border-slate-700/30 z-20">
        <h3 className="text-emerald-400 uppercase tracking-widest text-sm font-bold">Terminal Output</h3>
        <span className="text-emerald-400/40 text-xs">tty1</span>
      </div>

      <div className="flex-1 overflow-y-auto pr-2 text-xs md:text-sm text-emerald-400/80 space-y-1 z-20">
        {lines.map((line, index) => {
          const lower = line.toLowerCase();
          let color = "text-emerald-400/80";
          if (lower.includes("error") || lower.includes("failed") || lower.includes("401")) {
            color = "text-rose-400/80";
          } else if (lower.includes("warn") || lower.includes("blocked") || lower.includes("422")) {
            color = "text-amber-300/80";
          }

          return (
            <div key={`${line}-${index}`} className={`${color} break-all`}>
              <span className="opacity-40 mr-2">&gt;</span>
              {line}
            </div>
          );
        })}
        <div ref={endRef} />
      </div>

      <form
        className="z-20 pt-3 border-t border-slate-700/30 mt-2"
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
          <span className="text-emerald-400/60">$</span>
          <input
            value={command}
            onChange={(event) => setCommand(event.target.value)}
            placeholder="help | stats | tail"
            className="flex-1 bg-transparent outline-none text-emerald-300/70 placeholder:text-emerald-700/50"
          />
        </div>
      </form>
    </div>
  );
}
