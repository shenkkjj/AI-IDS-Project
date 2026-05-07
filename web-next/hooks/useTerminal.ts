"use client";

import { useState, useCallback } from "react";
import type { AlertItem } from "@/types/alert";
import type { TerminalTone } from "@/types/terminal";
import {
  runTerminalCommand,
  buildTerminalBootstrapLines,
  formatTerminalLine,
} from "@/utils/terminalUtils";

const TERMINAL_LOG_LIMIT = 120;

export function useTerminal(alerts: AlertItem[]) {
  const [logs, setLogs] = useState<string[]>(buildTerminalBootstrapLines());

  const appendLogs = useCallback((lines: string[], tone: TerminalTone = "normal") => {
    if (lines.length === 0) return;
    const formatted = lines.map((line) => formatTerminalLine(line, tone));
    setLogs((prev) => [...prev, ...formatted].slice(-TERMINAL_LOG_LIMIT));
  }, []);

  const executeCommand = useCallback((command: string) => {
    const outputLines = runTerminalCommand(command, alerts);
    if (outputLines.length === 0) return;

    if (outputLines.includes("__CLEAR__")) {
      const kept = outputLines.filter((line) => line !== "__CLEAR__");
      setLogs(kept.length > 0 ? kept.map((line) => formatTerminalLine(line)) : []);
      return;
    }

    const hasUnknown = outputLines.some((line) => line.startsWith("未知命令"));
    appendLogs(outputLines, hasUnknown ? "warn" : "normal");
  }, [alerts, appendLogs]);

  return { logs, executeCommand, appendLogs };
}
