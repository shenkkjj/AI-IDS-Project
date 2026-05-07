"use client";

import { useState, useRef, useCallback, useEffect, useMemo } from "react";
import type { AlertItem } from "@/types/alert";
import { buildReportMarkdown } from "@/utils/reportUtils";

export function useReport(alerts: AlertItem[]) {
  const [markdown, setMarkdown] = useState<string>(() => buildReportMarkdown(alerts));
  const [typing, setTyping] = useState(false);
  const typingToken = useRef(0);

  const typewriteReport = useCallback(async (text: string) => {
    typingToken.current += 1;
    const token = typingToken.current;
    const lines = text.split("\n");
    const current: string[] = [];
    setTyping(true);

    try {
      for (const line of lines) {
        if (token !== typingToken.current) {
          setTyping(false);
          return;
        }
        current.push(line);
        setMarkdown(current.join("\n"));
        await new Promise((resolve) => {
          window.setTimeout(resolve, line.startsWith("#") ? 80 : 26);
        });
      }
    } finally {
      if (token === typingToken.current) {
        setTyping(false);
      }
    }
  }, []);

  const refreshWithTypewriter = useCallback(async () => {
    const next = buildReportMarkdown(alerts);
    await typewriteReport(next);
  }, [alerts, typewriteReport]);

  useEffect(() => {
    setMarkdown(buildReportMarkdown(alerts));
  }, [alerts]);

  return { markdown, typing, refreshWithTypewriter };
}
