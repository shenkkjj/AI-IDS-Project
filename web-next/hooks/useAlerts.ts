"use client";

import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useDesktopNotify } from "@/hooks/useDesktopNotify";
import type {
  AlertItem,
  AlertTriage,
  AlertTriageEvent,
  AlertTriageStatus,
  AlertTriageHistoryResponse,
  BackendAlertItem,
  DemoAttackResponse,
} from "@/types/alert";
import { mapBackendAlert } from "@/utils/alertUtils";

// Polling cadence is now a single tunable. Keep this aligned with the
// backend's /alerts handler capacity; the WebSocket connection is the
// preferred real-time path, polling is the fallback.
const ALERTS_POLL_MS = Number(process.env.NEXT_PUBLIC_ALERTS_POLL_MS) || 8_000;
const PAGE_SIZE = 15;
// Maximum in-memory alerts kept after a poll refresh. Older entries are
// dropped on the next poll, but `id`-based dedup below keeps WebSocket
// pushes from re-introducing already-evicted entries.
const MAX_RETAINED_ALERTS = 300;

export function useAlerts() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [selected, setSelected] = useState<AlertItem | null>(null);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "empty" | "error">("loading");
  const [demoState, setDemoState] = useState<"idle" | "running" | "success" | "error">("idle");
  const [demoMessage, setDemoMessage] = useState("点击触发 Demo 攻击，生成一条可分析告警。");
  const [page, setPage] = useState(0);

  const { wsAlerts, wsConnected } = useWebSocket();
  const { notifyAlert } = useDesktopNotify();

  const prevAlertCount = useRef(0);
  const prevAlertIds = useRef<Set<string>>(new Set());
  const [newAlertIds, setNewAlertIds] = useState<Set<string>>(new Set());
  const pollTimer = useRef<number | null>(null);
  const newIdTimers = useRef<Map<string, number>>(new Map());
  // Stable id-keyed lookup so dedup is O(1) regardless of buffer size.
  // Both polling and WebSocket pushes are merged through this map.
  const alertById = useRef<Map<string, AlertItem>>(new Map());

  const syncAlertsFromMap = useCallback(() => {
    setAlerts(Array.from(alertById.current.values()).slice(-MAX_RETAINED_ALERTS));
  }, []);

  useEffect(() => {
    let changed = false;
    wsAlerts?.forEach((raw, index) => {
      const mapped = mapBackendAlert(raw, index);
      if (mapped.id && !alertById.current.has(mapped.id)) {
        alertById.current.set(mapped.id, mapped);
        changed = true;
      }
    });
    if (changed) {
      syncAlertsFromMap();
    }
  }, [syncAlertsFromMap, wsAlerts]);

  const mergedAlerts = alerts;

  const paginatedAlerts = useMemo(() => {
    const start = page * PAGE_SIZE;
    return mergedAlerts.slice(start, start + PAGE_SIZE);
  }, [mergedAlerts, page]);

  const totalPages = Math.max(1, Math.ceil(mergedAlerts.length / PAGE_SIZE));

  useEffect(() => {
    const currentCount = mergedAlerts.length;
    if (prevAlertCount.current > 0 && currentCount > prevAlertCount.current) {
      const newAlerts = mergedAlerts.slice(prevAlertCount.current);
      const trulyNew: string[] = [];
      for (const alert of newAlerts) {
        if (!prevAlertIds.current.has(alert.id)) {
          trulyNew.push(alert.id);
        }
        if (alert.risk === "critical" || alert.risk === "high") {
          notifyAlert({ alertId: alert.id, risk: alert.risk, summary: alert.summary, source: alert.source });
        }
      }

      if (trulyNew.length > 0) {
        setNewAlertIds((prev) => {
          const next = new Set(prev);
          for (const id of trulyNew) next.add(id);
          return next;
        });
        for (const id of trulyNew) {
          const existing = newIdTimers.current.get(id);
          if (existing) window.clearTimeout(existing);
          const timer = window.setTimeout(() => {
            setNewAlertIds((prev) => {
              if (!prev.has(id)) return prev;
              const next = new Set(prev);
              next.delete(id);
              return next;
            });
            newIdTimers.current.delete(id);
          }, 1500);
          newIdTimers.current.set(id, timer);
        }
      }
    }
    prevAlertCount.current = currentCount;
    prevAlertIds.current = new Set(mergedAlerts.map((a) => a.id));
  }, [mergedAlerts, notifyAlert]);

  useEffect(() => {
    return () => {
      for (const timer of newIdTimers.current.values()) {
        window.clearTimeout(timer);
      }
      newIdTimers.current.clear();
    };
  }, []);

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
      alertById.current = new Map();
      setAlerts([]);
      setSelected(null);
      setLoadState("empty");
      return;
    }

    const mapped = items.map(mapBackendAlert).reverse();
    // Replace the id-keyed map with the latest poll snapshot. WebSocket
    // pushes that arrive later are merged in via `mergedAlerts` memo above.
    alertById.current = new Map(mapped.map((a) => [a.id, a] as const));
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

  const triggerDemoAttack = useCallback(async (scenario: "sql_injection" | "xss" | "scanner" = "sql_injection") => {
    setDemoState("running");
    setDemoMessage("正在触发固定攻击样本...");
    const response = await fetch(`/api/backend/alerts/demo`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario }),
      cache: "no-store",
    });

    if (!response.ok) {
      const payload = (await response.json().catch(() => ({}))) as { detail?: string };
      setDemoState("error");
      setDemoMessage("Demo 攻击触发失败，请检查登录状态和后端服务。");
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }

    const payload = (await response.json().catch(() => ({}))) as Partial<DemoAttackResponse>;
    if (!payload.alert) {
      setDemoState("error");
      setDemoMessage("Demo 攻击触发失败：后端响应缺少告警。");
      throw new Error("Demo alert response missing alert");
    }

    const mapped = mapBackendAlert(payload.alert, alertById.current.size);
    alertById.current.set(mapped.id, mapped);
    syncAlertsFromMap();
    setSelected(mapped);
    setLoadState("ready");
    setDemoState("success");
    setDemoMessage(payload.copilot?.next_action || "Demo 告警已生成，可在 AI 助手中分析。");
    return { alert: mapped, copilot: payload.copilot };
  }, [syncAlertsFromMap]);

  /**
   * 加载指定告警的研判历史 (M3-03)。
   *
   * - 返回 ``{ ok: true, items }`` 或 ``{ ok: false, error }``;
   * - 404(非 owner / 不存在)按失败处理,展示低调错误态,不阻断保存。
   * - 默认 limit = 5(只展示最近的几条;完整历史可用更大 limit 二次查询)。
   */
  const loadTriageHistory = useCallback(
    async (
      alertId: string,
      options?: { limit?: number; signal?: AbortSignal }
    ): Promise<{ ok: boolean; items?: AlertTriageEvent[]; error?: string }> => {
      const limit = options?.limit ?? 5;
      try {
        const response = await fetch(
          `/api/backend/alerts/${encodeURIComponent(alertId)}/triage/history?limit=${limit}`,
          {
            credentials: "include",
            cache: "no-store",
            signal: options?.signal,
          }
        );
        if (response.status === 404) {
          return { ok: false, error: "未找到该告警的研判历史" };
        }
        if (!response.ok) {
          const payload = (await response.json().catch(() => ({}))) as { detail?: string };
          return { ok: false, error: payload.detail || `HTTP ${response.status}` };
        }
        const body = (await response.json().catch(() => ({}))) as Partial<AlertTriageHistoryResponse>;
        if (body.status !== "ok" || !Array.isArray(body.items)) {
          return { ok: false, error: "历史响应缺少 items 字段" };
        }
        return { ok: true, items: body.items };
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        return { ok: false, error: message };
      }
    },
    []
  );

  /**
   * 研判状态更新 (M3-02)。
   *
   * - 成功时,就地更新本地缓存 + 选中的告警 + 触发 React re-render;
   * - 失败时返回 ``{ ok: false, error }``,调用方负责错误提示。
   */
  const updateTriage = useCallback(
    async (input: {
      alertId: string;
      status: AlertTriageStatus;
      disposition: string | null;
      analyst_note: string | null;
    }): Promise<{ ok: boolean; triage?: AlertTriage; alert?: AlertItem; error?: string }> => {
      const target = alertById.current.get(input.alertId);
      if (!target) {
        return { ok: false, error: "未在当前告警列表中找到该告警" };
      }
      try {
        const response = await fetch(
          `/api/backend/alerts/${encodeURIComponent(input.alertId)}/triage`,
          {
            method: "PATCH",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              status: input.status,
              disposition: input.disposition,
              analyst_note: input.analyst_note,
            }),
            cache: "no-store",
          }
        );
        if (!response.ok) {
          const payload = (await response.json().catch(() => ({}))) as { detail?: string };
          return { ok: false, error: payload.detail || `HTTP ${response.status}` };
        }
        const body = (await response.json().catch(() => ({}))) as {
          status?: string;
          alert_id?: string;
          triage?: AlertTriage;
          alert?: BackendAlertItem;
        };
        if (body.status !== "ok" || !body.triage) {
          return { ok: false, error: "保存成功但响应缺少 triage" };
        }
        let updated: AlertItem;
        if (body.alert) {
          const refreshed = mapBackendAlert(body.alert, alertById.current.size);
          updated = { ...refreshed, triage: body.triage };
        } else {
          updated = { ...target, triage: body.triage };
        }
        alertById.current.set(updated.id, updated);
        syncAlertsFromMap();
        setSelected((prev) => (prev && prev.id === updated.id ? updated : prev));
        return { ok: true, triage: body.triage, alert: updated };
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        return { ok: false, error: message };
      }
    },
    [syncAlertsFromMap]
  );

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
    triggerDemoAttack,
    updateTriage,
    loadTriageHistory,
    demoState,
    demoMessage,
    paginatedAlerts,
    totalPages,
    wsConnected,
    handleSelectLog,
    newAlertIds,
  };
}
