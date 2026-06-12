"use client";

import { useState, useCallback } from "react";
import type { PersistedUserConfig, ConfigDraft, WebhookType } from "@/types/config";
import { WEBHOOK_TYPES } from "@/types/config";
import { formatLoadError } from "@/utils/alertUtils";

const PROVIDERS: readonly string[] = ["custom"];

export function normalizeProviderForDraft(value: string | undefined): string {
  return PROVIDERS.includes(value as string) ? (value as string) : "custom";
}

function normalizeWebhookType(value: string | undefined): WebhookType {
  return (WEBHOOK_TYPES as readonly string[]).includes(value as string)
    ? (value as WebhookType)
    : "generic";
}

export function useConfig() {
  const [config, setConfig] = useState<PersistedUserConfig | null>(null);
  const [draft, setDraft] = useState<ConfigDraft>({
    ai_provider: "custom",
    model: "",
    base_url: "",
    api_key: "",
    webhook_url: "",
    webhook_type: "generic",
  });
  const [status, setStatus] = useState("正在同步配置...");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [webhookTesting, setWebhookTesting] = useState(false);

  const loadConfig = useCallback(async (signal?: AbortSignal) => {
    const response = await fetch(`/api/backend/user/config`, {
      signal,
      credentials: "include",
      cache: "no-store",
    });

    const data = (await response.json().catch(() => ({}))) as PersistedUserConfig & { detail?: string };
    if (!response.ok) {
      throw new Error(data.detail || `HTTP ${response.status}`);
    }

    setConfig(data);
    setDraft((prev) => ({
      ...prev,
      ai_provider: normalizeProviderForDraft(data.ai_provider),
      model: data.model || "",
      base_url: data.base_url || "",
      webhook_url: data.webhook_url || "",
      webhook_type: normalizeWebhookType(data.webhook_type),
    }));
    setStatus("配置已同步");
  }, []);

  const saveConfig = useCallback(async () => {
    setStatus("正在保存配置...");
    setSaving(true);
    const body: Record<string, unknown> = {
      ai_provider: draft.ai_provider,
      model: draft.model,
      base_url: draft.base_url,
      webhook_url: draft.webhook_url,
      webhook_type: draft.webhook_type,
    };
    if (draft.api_key.trim()) {
      body.api_key = draft.api_key.trim();
    }

    try {
      const response = await fetch(`/api/backend/user/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(body),
      });

      const payload = (await response.json().catch(() => ({}))) as {
        detail?: string;
        config?: PersistedUserConfig;
      };

      if (!response.ok) {
        throw new Error(payload.detail || `HTTP ${response.status}`);
      }

      setStatus("配置已保存，路由引擎已更新");
      setConfig((prev) => ({ ...(prev || ({} as PersistedUserConfig)), ...(payload.config || {}) }));
      setDraft((prev) => ({ ...prev, api_key: "" }));
      await loadConfig();
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      setStatus(`保存失败：${message}`);
    } finally {
      setSaving(false);
    }
  }, [draft, loadConfig]);

  const testConfig = useCallback(async () => {
    setStatus("正在测试多模型连通性...");
    setTesting(true);
    const body: Record<string, unknown> = {
      ai_provider: draft.ai_provider,
      model: draft.model,
      base_url: draft.base_url,
      timeout_seconds: config?.timeout_seconds || 30,
    };
    if (draft.api_key.trim()) {
      body.api_key = draft.api_key.trim();
    }

    try {
      const response = await fetch(`/api/backend/llm/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(body),
      });

      const payload = (await response.json().catch(() => ({}))) as {
        detail?: string;
        provider?: string;
        result?: { latency_ms?: number; model?: string };
      };

      if (!response.ok) {
        throw new Error(payload.detail || `HTTP ${response.status}`);
      }

      const latency = Number(payload.result?.latency_ms || 0);
      const model = String(payload.result?.model || draft.model);
      const provider = String(payload.provider || draft.ai_provider);
      setStatus(`测试成功：${provider} / ${model} / ${latency}ms`);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      setStatus(`测试失败：${message}`);
    } finally {
      setTesting(false);
    }
  }, [draft, config?.timeout_seconds]);

  const refreshConfig = useCallback(async () => {
    setStatus("正在重新同步...");
    setRefreshing(true);
    try {
      await loadConfig();
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      setStatus(formatLoadError(message));
    } finally {
      setRefreshing(false);
    }
  }, [loadConfig]);

  const testWebhook = useCallback(async () => {
    const url = draft.webhook_url.trim();
    if (!url) {
      setStatus("请先填写 Webhook URL");
      return;
    }
    setWebhookTesting(true);
    setStatus("正在发送 Webhook 测试请求...");
    try {
      const params = new URLSearchParams({
        webhook_url: url,
        webhook_type: draft.webhook_type,
      });
      const response = await fetch(`/api/backend/notify/webhook/test?${params.toString()}`, {
        method: "POST",
        credentials: "include",
      });
      const data = (await response.json().catch(() => ({}))) as { status?: string; detail?: string };
      if (!response.ok) {
        throw new Error(data.detail || `HTTP ${response.status}`);
      }
      if (data.status === "sent") {
        setStatus(`Webhook 测试成功：${url.slice(0, 60)}`);
      } else if (data.status === "failed") {
        setStatus("Webhook 发送失败，请检查 URL 与目标服务");
      } else {
        setStatus(data.status ? `Webhook 状态：${data.status}` : "Webhook 已跳过");
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      setStatus(`Webhook 测试失败：${message}`);
    } finally {
      setWebhookTesting(false);
    }
  }, [draft.webhook_url, draft.webhook_type]);

  return {
    config,
    setConfig,
    draft,
    setDraft,
    status,
    setStatus,
    saving,
    testing,
    refreshing,
    webhookTesting,
    loadConfig,
    saveConfig,
    testConfig,
    refreshConfig,
    testWebhook,
  };
}
