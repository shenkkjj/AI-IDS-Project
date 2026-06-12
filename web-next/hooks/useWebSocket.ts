"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type WsAlertItem = {
  alert_id?: string;
  raw_alert?: {
    source_ip?: string;
    destination_ip?: string;
    payload?: string;
    timestamp?: number;
    blocked?: boolean;
  };
  llm_analysis?: {
    risk_level?: string;
    summary?: string;
  };
};

// Reconnect delay after a socket close. Exponentially-backed-off retries are
// out of scope; a constant 5s is fine for a fallback transport.
const WS_RECONNECT_MS = 5_000;
// Maximum alerts kept in the in-memory buffer for the dashboard view. Once
// the buffer fills, the oldest entry is dropped on each new push.
const WS_ALERT_BUFFER = 200;

/**
 * Establish a WebSocket connection to the alerts feed.
 *
 * Authentication is handled via the `access_token` HttpOnly cookie, which the
 * browser automatically attaches to the WebSocket upgrade request. The
 * previous implementation appended the JWT to the URL as a query parameter,
 * which leaks the token into server access logs, proxy logs, browser history
 * and the `Referer` header — see H1 in the refactor insight report.
 */
export function useWebSocket() {
  const [wsAlerts, setWsAlerts] = useState<WsAlertItem[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    // No `?token=...` — rely on the HttpOnly access_token cookie.
    const wsUrl = `${protocol}//${window.location.host}/api/backend/alerts/ws/alerts`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setWsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as WsAlertItem;
          setWsAlerts((prev) => {
            const next = [...prev, data];
            return next.slice(-WS_ALERT_BUFFER);
          });
        } catch {
          // ignore malformed payloads
        }
      };

      ws.onclose = () => {
        setWsConnected(false);
        wsRef.current = null;
        if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
        reconnectTimer.current = setTimeout(connect, WS_RECONNECT_MS);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      reconnectTimer.current = setTimeout(connect, WS_RECONNECT_MS);
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { wsAlerts, wsConnected };
}
