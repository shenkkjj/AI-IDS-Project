"use client";

import { useCallback, useEffect, useState } from "react";
import type {
  SecurityTimelineItem,
  SecurityTimelinePayload,
} from "@/types/securityTimeline";

const DEFAULT_LIMIT = 50;
const POLL_MS = Number(process.env.NEXT_PUBLIC_TIMELINE_POLL_MS) || 30_000;

export function useSecurityTimeline() {
  const [items, setItems] = useState<SecurityTimelineItem[]>([]);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "empty" | "error">(
    "loading",
  );
  const [degraded, setDegraded] = useState(false);
  const [limit, setLimit] = useState(DEFAULT_LIMIT);

  const loadTimeline = useCallback(async () => {
    try {
      const response = await fetch(
        `/api/backend/logs/security-timeline?limit=${DEFAULT_LIMIT}`,
        {
          credentials: "include",
          cache: "no-store",
        },
      );
      if (!response.ok) {
        setLoadState("error");
        return;
      }
      const payload = (await response.json().catch(() => ({}))) as Partial<SecurityTimelinePayload>;
      const list = Array.isArray(payload.items) ? payload.items : [];
      setDegraded(Boolean(payload.degraded));
      if (typeof payload.limit === "number") {
        setLimit(payload.limit);
      }
      setItems(list);
      setLoadState(list.length === 0 ? "empty" : "ready");
    } catch {
      setLoadState("error");
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    loadTimeline().catch(() => {
      if (cancelled) return;
      setLoadState("error");
    });
    const timer = window.setInterval(() => {
      if (!cancelled) {
        loadTimeline().catch(() => {});
      }
    }, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [loadTimeline]);

  return { items, loadState, degraded, limit, refresh: loadTimeline };
}
