"use client";

import { useState, useCallback } from "react";
import type { AlertItem } from "@/types/alert";
import type { PersistedUserConfig } from "@/types/config";
import type { ThreatConfirmResponse } from "@/types/threat";

export function useThreatConfirm(
  selected: AlertItem | null,
  config: PersistedUserConfig | null,
  setConfig: React.Dispatch<React.SetStateAction<PersistedUserConfig | null>>,
  setConfigStatus: (msg: string) => void,
  appendTerminalLog: (lines: string[]) => void,
  refreshConfig?: () => Promise<void>
) {
  const [status, setStatus] = useState("请选择一条告警后可确认入库");
  const [statusTone, setStatusTone] = useState<"default" | "ok" | "error">("default");
  const [confirming, setConfirming] = useState(false);

  const confirmThreat = useCallback(async () => {
    const current = selected;
    const alertId = String(current?.alertId || "").trim();
    if (!alertId) {
      setStatus("当前告警没有 alert_id，无法确认");
      setStatusTone("error");
      return;
    }

    setConfirming(true);
    setStatus("正在确认并写入新威胁库...");
    setStatusTone("default");

    try {
      const response = await fetch(`/api/backend/threats/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          alert_id: alertId,
          label: "user_confirmed_threat",
        }),
      });

      const payload = (await response.json().catch(() => ({}))) as ThreatConfirmResponse;
      if (!response.ok) {
        throw new Error(payload.detail || `HTTP ${response.status}`);
      }

      setStatus(`确认成功，已写入: ${String(payload.saved_to || "new_threats.csv")}`);
      setStatusTone("ok");
      appendTerminalLog([`threat ${alertId} confirmed`]);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      setStatus(`确认失败: ${message}`);
      setStatusTone("error");
    } finally {
      setConfirming(false);
    }
  }, [selected, appendTerminalLog]);

  const toggleVoiceAlert = useCallback(async () => {
    const next = !Boolean(config?.alert_voice_enabled);
    setConfigStatus("正在更新语音预警配置...");

    try {
      const response = await fetch(`/api/backend/user/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ alert_voice_enabled: next }),
      });

      const payload = (await response.json().catch(() => ({}))) as {
        detail?: string;
        config?: PersistedUserConfig;
      };

      if (!response.ok) {
        throw new Error(payload.detail || `HTTP ${response.status}`);
      }

      setConfig((prev) => ({ ...(prev || ({} as PersistedUserConfig)), ...(payload.config || {}), alert_voice_enabled: next }));
      setConfigStatus(`语音预警已${next ? "开启" : "关闭"}`);
      if (refreshConfig) {
        refreshConfig().catch(() => {});
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      setConfigStatus(`语音预警更新失败：${message}`);
    }
  }, [config?.alert_voice_enabled, setConfigStatus, setConfig]);

  return {
    status,
    statusTone,
    confirming,
    confirmThreat,
    toggleVoiceAlert,
  };
}
