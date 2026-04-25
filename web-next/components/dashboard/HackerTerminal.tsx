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
    <div className="bg-[#020202] border border-cyber-cyan/30 p-4 h-full min-h-[300px] flex flex-col font-mono relative overflow-hidden shadow-[inset_0_0_20px_rgba(0,0,0,1)]">
      <div className="absolute inset-0 pointer-events-none bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(255,0,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))] bg-[length:100%_4px,3px_100%] z-10 opacity-40" />

      <div className="flex justify-between items-center mb-2 pb-2 border-b border-green-900/50 z-20">
        <h3 className="text-green-500 uppercase tracking-widest text-sm font-bold">Terminal Output</h3>
        <span className="text-green-500/50 text-xs">tty1</span>
      </div>

      <div className="flex-1 overflow-y-auto pr-2 text-xs md:text-sm text-green-400 space-y-1 z-20">
        {lines.map((line, index) => {
          const lower = line.toLowerCase();
          let color = "text-green-400";
          if (lower.includes("error") || lower.includes("failed") || lower.includes("401")) {
            color = "text-red-400";
          } else if (lower.includes("warn") || lower.includes("blocked") || lower.includes("422")) {
            color = "text-yellow-300";
          }

          return (
            <div key={`${line}-${index}`} className={`${color} break-all`}>
              <span className="opacity-50 mr-2">&gt;</span>
              {line}
            </div>
          );
        })}
        <div ref={endRef} />
      </div>

      <form
        className="z-20 pt-3 border-t border-green-900/50 mt-2"
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
          <span className="text-green-400">$</span>
          <input
            value={command}
            onChange={(event) => setCommand(event.target.value)}
            placeholder="help | stats | tail"
            className="flex-1 bg-transparent outline-none text-green-300 placeholder:text-green-700/70"
          />
        </div>
      </form>
    </div>
  );
}
