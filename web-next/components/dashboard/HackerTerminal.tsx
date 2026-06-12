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
    <div className="h-full min-h-[320px] flex flex-col border-l border-accent bg-bg-sunken">
      <div className="px-5 py-3 flex items-baseline justify-between border-b border-line">
        <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-accent">
          TTY · 终端
        </span>
        <span className="text-[10px] font-mono text-ink-tertiary">
          {lines.length} 行
        </span>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-3 text-xs font-mono space-y-0.5">
        {lines.map((line, index) => {
          const lower = line.toLowerCase();
          let color = "text-ink-secondary";
          if (lower.includes("error") || lower.includes("failed") || lower.includes("401")) {
            color = "text-danger";
          } else if (lower.includes("warn") || lower.includes("blocked") || lower.includes("422")) {
            color = "text-warning";
          } else if (lower.includes("ok") || lower.includes("ready") || lower.includes("200")) {
            color = "text-success";
          }
          return (
            <div key={`${line}-${index}`} className={`${color} leading-relaxed break-all`}>
              <span className="text-ink-tertiary mr-2">›</span>
              {line}
            </div>
          );
        })}
        <div ref={endRef} />
      </div>

      <form
        className="px-5 py-3 border-t border-line"
        onSubmit={(event) => {
          event.preventDefault();
          const text = command.trim();
          if (!text) return;
          onCommand(text);
          setCommand("");
        }}
      >
        <div className="flex items-center gap-2">
          <span className="text-accent text-xs font-mono">$</span>
          <input
            value={command}
            onChange={(event) => setCommand(event.target.value)}
            placeholder="help | stats | tail"
            className="flex-1 bg-transparent outline-none text-ink text-xs font-mono placeholder:text-ink-tertiary"
          />
        </div>
      </form>
    </div>
  );
}
