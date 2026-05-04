"use client";

import { useCallback, useEffect, useRef } from "react";

type AlertRisk = "critical" | "high" | "medium" | "low";

type AlertItem = {
  alertId?: string;
  risk?: AlertRisk;
  summary?: string;
  source?: string;
};

export function useDesktopNotify() {
  const permission = useRef<NotificationPermission>("default");

  useEffect(() => {
    if (typeof window === "undefined" || !("Notification" in window)) return;
    permission.current = Notification.permission;
  }, []);

  const requestPermission = useCallback(async (): Promise<boolean> => {
    if (typeof window === "undefined" || !("Notification" in window)) return false;
    const result = await Notification.requestPermission();
    permission.current = result;
    return result === "granted";
  }, []);

  const notifyAlert = useCallback(
    (alert: AlertItem) => {
      if (typeof window === "undefined" || !("Notification" in window)) return;
      if (permission.current !== "granted") return;

      const risk = alert.risk || "medium";
      if (risk !== "critical" && risk !== "high") return;

      const icon = risk === "critical" ? "🔴" : "🟠";
      const title = `${icon} ${risk === "critical" ? "严重" : "高危"}告警`;
      const body = alert.summary || `来自 ${alert.source || "未知"} 的攻击`;

      try {
        new Notification(title, {
          body,
          tag: alert.alertId || "cyber-alert",
          requireInteraction: risk === "critical",
        });
      } catch {
        // 忽略通知失败
      }
    },
    []
  );

  return { notifyAlert, requestPermission, permission: permission.current };
}
