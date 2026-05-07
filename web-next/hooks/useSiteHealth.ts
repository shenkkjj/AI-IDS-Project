"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import type { SiteHealthPayload, SiteHealthUi } from "@/types/site";
import type { SiteTargetResponse } from "@/types/site";
import { mapSiteHealthToUptime, inferProxyPath } from "@/utils/siteUtils";

export function useSiteHealth(setConfigStatus: (msg: string) => void) {
  const [targetInput, setTargetInput] = useState("");
  const [targetSaving, setTargetSaving] = useState(false);
  const [health, setHealth] = useState<SiteHealthPayload | null>(null);
  const [healthUi, setHealthUi] = useState<SiteHealthUi>({ tone: "offline", text: "未检测" });
  const [proxyPathInput, setProxyPathInput] = useState("/");
  const [proxyTesting, setProxyTesting] = useState(false);

  const healthTimer = useRef<number | null>(null);

  const pingHealth = useCallback(async (signal?: AbortSignal) => {
    const response = await fetch(`/api/backend/site/health`, {
      signal,
      credentials: "include",
      cache: "no-store",
    });

    const raw = (await response.json().catch(() => ({}))) as SiteHealthPayload & { detail?: string };
    if (!response.ok) {
      throw new Error(raw.detail || `HTTP ${response.status}`);
    }

    setHealth(raw);
    const mapped = mapSiteHealthToUptime(raw);
    setHealthUi(mapped);
  }, []);

  const startPolling = useCallback(() => {
    if (healthTimer.current) {
      window.clearInterval(healthTimer.current);
      healthTimer.current = null;
    }

    healthTimer.current = window.setInterval(() => {
      pingHealth().catch(() => {
        setHealthUi({ tone: "offline", text: "离线" });
      });
    }, 20000);
  }, [pingHealth]);

  const saveTarget = useCallback(async () => {
    const rawUrl = String(targetInput || "").trim();
    if (!rawUrl) {
      setConfigStatus("请输入受保护站点 URL");
      return;
    }

    let normalizedUrl = "";
    try {
      const parsed = new URL(rawUrl);
      if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
        throw new Error("protocol");
      }
      normalizedUrl = parsed.toString();
    } catch {
      setConfigStatus("站点 URL 无效，请输入 http(s) 地址");
      return;
    }

    setTargetSaving(true);
    setConfigStatus("正在保存站点...");
    try {
      const response = await fetch(`/api/backend/site/target`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ url: normalizedUrl }),
      });

      const raw = (await response.json().catch(() => ({}))) as SiteTargetResponse;
      if (!response.ok) {
        throw new Error(raw.detail || `HTTP ${response.status}`);
      }

      setTargetInput(String(raw.target || normalizedUrl));
      setConfigStatus("站点保存成功，正在刷新健康状态");
      await pingHealth();
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      setConfigStatus(`站点保存失败：${message}`);
    } finally {
      setTargetSaving(false);
    }
  }, [targetInput, pingHealth, setConfigStatus]);

  const testProxy = useCallback(async () => {
    setProxyTesting(true);
    setConfigStatus("正在测试代理链路...");

    try {
      const path = inferProxyPath(proxyPathInput);
      const response = await fetch(`/api/backend/site/proxy${path}`, {
        method: "GET",
        credentials: "include",
      });

      const bodyText = await response.text().catch(() => "");
      const brief = bodyText.slice(0, 80).replace(/\s+/g, " ").trim();

      if (response.status === 403) {
        setConfigStatus("代理测试命中 WAF 拦截（403）");
        return;
      }

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      setConfigStatus(`代理测试成功：HTTP ${response.status}${brief ? ` · ${brief}` : ""}`);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      setConfigStatus(`代理测试失败：${message}`);
    } finally {
      setProxyTesting(false);
    }
  }, [proxyPathInput, setConfigStatus]);

  useEffect(() => {
    let cancelled = false;
    pingHealth().catch(() => {
      if (cancelled) return;
      setHealthUi({ tone: "offline", text: "离线" });
    });
    startPolling();

    return () => {
      cancelled = true;
      if (healthTimer.current) {
        window.clearInterval(healthTimer.current);
        healthTimer.current = null;
      }
    };
  }, [pingHealth, startPolling]);

  return {
    targetInput,
    setTargetInput,
    targetSaving,
    health,
    healthUi,
    proxyPathInput,
    setProxyPathInput,
    proxyTesting,
    saveTarget,
    testProxy,
  };
}
