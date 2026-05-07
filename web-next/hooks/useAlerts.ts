"use client";

import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useDesktopNotify } from "@/hooks/useDesktopNotify";
import type { AlertItem, BackendAlertItem } from "@/types/alert";
import { mapBackendAlert } from "@/utils/alertUtils";

const ALERTS_POLL_MS = 8000;
const PAGE_SIZE = 15;

export function useAlerts() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [selected, setSelected] = useState<AlertItem | null>(null);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "empty" | "error">("loading");
  const [page, setPage] = useState(0);

  const { wsAlerts, wsConnected } = useWebSocket(null);
  const { notifyAlert } = useDesktopNotify();

  const prevAlertCount = useRef(0);
  const pollTimer = useRef<number | null>(null);

  const mergedAlerts = useMemo(() => {
    const wsMapped = (wsAlerts || []).map(mapBackendAlert);
    const existingIds = new Set(alerts.map((a) => a.id));
    const newWsAlerts = wsMapped.filter((a) => !existingIds.has(a.id));
    const combined = [...alerts, ...newWsAlerts];
    return combined.slice(-300);
  }, [alerts, wsAlerts]);

  const paginatedAlerts = useMemo(() => {
    const start = page * PAGE_SIZE;
    return mergedAlerts.slice(start, start + PAGE_SIZE);
  }, [mergedAlerts, page]);

  const totalPages = Math.max(1, Math.ceil(mergedAlerts.length / PAGE_SIZE));

  useEffect(() => {
    const currentCount = mergedAlerts.length;
    if (prevAlertCount.current > 0 && currentCount > prevAlertCount.current) {
      const newAlerts = mergedAlerts.slice(prevAlertCount.current);
      for (const alert of newAlerts) {
        if (alert.risk === "critical" || alert.risk === "high") {
          notifyAlert({ alertId: alert.id, risk: alert.risk, summary: alert.summary, source: alert.source });
        }
      }
    }
    prevAlertCount.current = currentCount;
  }, [mergedAlerts.length, mergedAlerts, notifyAlert]);

  const loadAlerts = useCallback(async (options?: { signal?: AbortSignal; showLoading?: boolean }) => {
    const showLoading = Boolean(options?.showLoading);
    const controller = new AbortController();
    const signal = options?.signal || controller.signal;

    if (showLoading) {
      setLoadState("loading");
    }

    const response = await fetch(`/api/backend/alerts?limit=100`, {
      signal,
      credentials: "include",
      cache: "no-store",
    });

    if (!response.ok) {
      const payload = (await response.json().catch(() => ({}))) as { detail?: string };
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }

    const payload = (await response.json().catch(() => ({}))) as { items?: BackendAlertItem[] };
    const items = Array.isArray(payload.items) ? payload.items : [];
    if (items.length === 0) {
      setAlerts([]);
      setSelected(null);
      setLoadState("empty");
      return;
    }

    const mapped = items.map(mapBackendAlert).reverse();
    setAlerts(mapped);
    setLoadState("ready");

    setSelected((prev) => {
      if (prev) {
        const keep = mapped.find((item) => item.id === prev.id);
        if (keep) return keep;
      }
      return mapped[0] || null;
    });
  }, []);

  useEffect(() => {
    let cancelled = false;

    loadAlerts({ showLoading: true }).catch(() => {
      if (cancelled) return;
      setAlerts([]);
      setSelected(null);
      setLoadState("error");
    });

    pollTimer.current = window.setInterval(() => {
      if (!cancelled) {
        loadAlerts({ showLoading: false }).catch(() => {});
      }
    }, ALERTS_POLL_MS);

    return () => {
      cancelled = true;
      if (pollTimer.current) {
        window.clearInterval(pollTimer.current);
        pollTimer.current = null;
      }
    };
  }, [loadAlerts]);

  function handleSelectLog(id: string) {
    const found = mergedAlerts.find((item) => item.id === id) || null;
    setSelected(found);
  }

  return {
    alerts: mergedAlerts,
    selected,
    loadState,
    page,
    setPage,
    setSelected,
    loadAlerts,
    paginatedAlerts,
    totalPages,
    wsConnected,
    handleSelectLog,
  };
}
