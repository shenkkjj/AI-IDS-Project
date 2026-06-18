"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import type { AlertItem } from "@/types/alert";
import type { CopilotMessage } from "@/types/copilot";
import { parseSseBuffer, parseSseJson } from "@/utils/sseUtils";

const COPILOT_HISTORY_LIMIT = 16;
const COPILOT_HISTORY_REQUEST_LIMIT = 10;

export interface SendMessageOptions {
  /** 显式声明 incident context;后端负责 owner 隔离与受控 context_block 注入。 */
  incidentId?: string | null;
  /** 显式覆盖 alert context(默认仍走 selected?.alertId)。 */
  alertId?: string | null;
}

export function useCopilot(selected: AlertItem | null) {
  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [hint, setHint] = useState("通用咨询模式");
  // M3-05: 当一次 send 显式带 incidentId,锁定 hint 为"案件上下文"。
  // 显式传 alertId 或不传则恢复为告警上下文 / 通用模式。
  const [activeIncidentId, setActiveIncidentId] = useState<string | null>(null);
  const activeRequestId = useRef(0);

  useEffect(() => {
    if (activeIncidentId) {
      setHint(`案件上下文: ${activeIncidentId}`);
      return;
    }
    if (!selected) {
      setHint("通用咨询模式");
      return;
    }
    const contextId = selected.alertId || selected.id;
    setHint(`告警上下文: ${contextId} / ${selected.source} → ${selected.target}`);
  }, [selected, activeIncidentId]);

  function updateLastAssistantMessage(nextContent: string) {
    setMessages((prev) => {
      if (prev.length === 0) {
        return [{ role: "assistant", content: nextContent }];
      }
      const copied = [...prev];
      const last = copied[copied.length - 1];
      if (last.role === "assistant") {
        copied[copied.length - 1] = { role: "assistant", content: nextContent };
        return copied;
      }
      return [...copied, { role: "assistant", content: nextContent }];
    });
  }

  const sendMessage = useCallback(async (
    messageText: string,
    options?: SendMessageOptions,
  ) => {
    const message = String(messageText || "").trim();
    if (!message || sending) {
      return;
    }

    const requestId = ++activeRequestId.current;
    const historyForRequest: CopilotMessage[] = messages
      .slice(-COPILOT_HISTORY_REQUEST_LIMIT)
      .map((item) => ({ role: item.role, content: item.content }));

    // 解析最终请求体里的 alert_id / incident_id:
    // - alertId: 显式 options 优先;否则回退到 selected?.alertId。
    // - incidentId: 显式 options 优先;否则 null(无 incident 上下文)。
    // 当 incidentId 非空,后端会走 incident-aware contract,alert_id 仅作
    // selected_alert_id 行写入 context_block。
    const bodyAlertId = options?.alertId !== undefined
      ? options.alertId
      : selected?.alertId || null;
    const bodyIncidentId = options?.incidentId !== undefined
      ? options.incidentId
      : null;

    if (bodyIncidentId) {
      setActiveIncidentId(bodyIncidentId);
    } else {
      setActiveIncidentId(null);
    }

    setMessages((prev) => {
      const next: CopilotMessage[] = [
        ...prev,
        { role: "user", content: message },
        { role: "assistant", content: "" },
      ];
      return next.slice(-COPILOT_HISTORY_LIMIT);
    });

    setInput("");
    setSending(true);

    try {
      const response = await fetch(`/api/backend/copilot/stream`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          alert_id: bodyAlertId,
          incident_id: bodyIncidentId,
          history: historyForRequest,
        }),
      });

      if (!response.ok || !response.body) {
        const payload = (await response.json().catch(() => ({}))) as { detail?: string };
        throw new Error(payload.detail || `HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let assistantContent = "";

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (requestId !== activeRequestId.current) return;
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const parsed = parseSseBuffer(buffer);
          buffer = parsed.rest;

          for (const eventItem of parsed.events) {
            if (eventItem.event === "done") continue;

            if (eventItem.event === "error") {
              const errorData = parseSseJson(eventItem.dataText);
              throw new Error(String(errorData.message || "流式响应错误"));
            }

            const data = parseSseJson(eventItem.dataText);
            const token = String(data.token || "");
            if (!token) continue;

            assistantContent += token;
            updateLastAssistantMessage(assistantContent);
          }
        }

        if (!assistantContent.trim()) {
          updateLastAssistantMessage("模型未返回内容，请稍后重试。");
        }
      } finally {
        reader.cancel().catch(() => {});
      }
    } catch (error: unknown) {
      const messageText = error instanceof Error ? error.message : String(error);
      updateLastAssistantMessage(`请求失败: ${messageText}`);
    } finally {
      if (requestId === activeRequestId.current) {
        setSending(false);
      }
    }
  }, [sending, messages, selected?.alertId, activeRequestId]);

  return {
    messages,
    input,
    setInput,
    sending,
    hint,
    sendMessage,
  };
}
