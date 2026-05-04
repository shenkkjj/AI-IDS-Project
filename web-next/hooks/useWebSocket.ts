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

export function useWebSocket(token: string | null) {
  const [wsAlerts, setWsAlerts] = useState<WsAlertItem[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    if (!token) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
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
            return next.slice(-200);
          });
        } catch {
          // 忽略解析失败
        }
      };

      ws.onclose = () => {
        setWsConnected(false);
        wsRef.current = null;
        if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
        reconnectTimer.current = setTimeout(connect, 5000);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      reconnectTimer.current = setTimeout(connect, 5000);
    }
  }, [token]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { wsAlerts, wsConnected };
}
