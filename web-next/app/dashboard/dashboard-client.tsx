"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { RefreshCw, LogOut, Sun, Moon } from "lucide-react";
import { signOut } from "next-auth/react";
import CyberSidebar from "@/components/dashboard/CyberSidebar";
import StatsCards from "@/components/dashboard/StatsCards";
import AttackLogTable from "@/components/dashboard/AttackLogTable";
import HackerTerminal from "@/components/dashboard/HackerTerminal";
import CopilotPanel from "@/components/dashboard/CopilotPanel";
import AttackTrendChart from "@/components/dashboard/AttackTrendChart";
import SourcePieChart from "@/components/dashboard/SourcePieChart";
import { Button } from "@/components/ui/button";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useTheme } from "@/contexts/ThemeContext";

type RouteKey = "overview" | "monitor" | "waf" | "ai" | "report";

type AlertRisk = "critical" | "high" | "medium" | "low";

type AlertItem = {
  id: string;
  alertId: string;
  source: string;
  target: string;
  risk: AlertRisk;
  payload: string;
  summary: string;
  timestamp: number | null;
  blocked: boolean;
};

type BackendAlertItem = {
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

type PersistedUserConfig = {
  ai_provider: string;
  model: string;
  base_url: string;
  timeout_seconds: number;
  alert_email_enabled: boolean;
  alert_voice_enabled: boolean;
  ui_theme: string;
  ui_density: string;
  has_api_key: boolean;
  api_key_masked: string;
};

type ConfigDraft = {
  ai_provider: string;
  model: string;
  base_url: string;
  api_key: string;
};

type SiteHealthPayload = {
  status?: string;
  detail?: string;
  checked_at?: string;
  url?: string;
  uptime_status?: string;
  uptime_http_status?: number | null;
  uptime_detail?: string;
  ssl_tone?: string;
  ssl_days_left?: number | null;
};

type SiteHealthUi = {
  tone: "online" | "warning" | "offline";
  text: string;
};

type ThreatConfirmResponse = {
  status?: string;
  saved_to?: string;
  alert_id?: string;
  label?: string;
  detail?: string;
};

type SiteTargetResponse = {
  status?: string;
  target?: string;
  detail?: string;
};

type CopilotMessage = {
  role: "user" | "assistant";
  content: string;
};

type DashboardClientProps = {
  userEmail: string;
};

const ALERTS_POLL_MS = 8000;
const COPILOT_HISTORY_LIMIT = 16;
const COPILOT_HISTORY_REQUEST_LIMIT = 10;
const TERMINAL_LOG_LIMIT = 120;
const REPORT_LATEST_ALERTS_LIMIT = 5;

const NAV_ITEMS: { key: RouteKey; label: string; icon: string }[] = [
  { key: "overview", label: "概览", icon: "01" },
  { key: "monitor", label: "监测", icon: "02" },
  { key: "waf", label: "WAF 管理", icon: "03" },
  { key: "ai", label: "AI 配置", icon: "04" },
  { key: "report", label: "安全日报", icon: "05" },
];

const PROVIDERS = ["custom"] as const;

type ProviderValue = (typeof PROVIDERS)[number];

function normalizeProviderForDraft(value: string | undefined): ProviderValue {
  return PROVIDERS.includes(value as ProviderValue) ? (value as ProviderValue) : "custom";
}

function hasSupportedProvider(value: string | undefined): value is ProviderValue {
  return PROVIDERS.includes(value as ProviderValue);
}

function formatLoadError(message: string): string {
  if (message.includes("401")) {
    return "会话失效，请重新登录";
  }
  if (message.includes("403") || message.includes("blocked")) {
    return "请求被拒绝，请稍后重试";
  }
  if (message.includes("429") || message.includes("rate")) {
    return "请求过于频繁，请稍后重试";
  }
  return "操作失败，请稍后重试";
}

function parseRisk(riskLevel: string | undefined): AlertRisk {
  const value = String(riskLevel || "").trim().toLowerCase();
  if (value === "critical" || value === "high" || value === "medium" || value === "low") {
    return value;
  }
  return "medium";
}

function mapBackendAlert(item: BackendAlertItem, index: number): AlertItem {
  const alertId = String(item.alert_id || "").trim();
  const source = String(item.raw_alert?.source_ip || "unknown");
  const target = String(item.raw_alert?.destination_ip || "unknown");
  const payload = String(item.raw_alert?.payload || "");
  const summary = String(item.llm_analysis?.summary || "暂无模型摘要，可在 Copilot 侧栏继续追问。");
  const risk = parseRisk(item.llm_analysis?.risk_level);

  return {
    id: alertId || `B-${String(index + 1).padStart(3, "0")}`,
    alertId,
    source,
    target,
    risk,
    payload,
    summary,
    timestamp: Number.isFinite(item.raw_alert?.timestamp) ? Number(item.raw_alert?.timestamp) : null,
    blocked: Boolean(item.raw_alert?.blocked),
  };
}

function parseSseBuffer(rawBuffer: string): { events: { event: string; dataText: string }[]; rest: string } {
  const events: { event: string; dataText: string }[] = [];
  let rest = rawBuffer.replaceAll("\r\n", "\n");

  while (true) {
    const boundary = rest.indexOf("\n\n");
    if (boundary < 0) {
      break;
    }

    const block = rest.slice(0, boundary);
    rest = rest.slice(boundary + 2);

    const lines = block
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line);

    if (lines.length === 0) {
      continue;
    }

    let event = "message";
    const dataLines: string[] = [];

    for (const line of lines) {
      if (line.startsWith("event:")) {
        event = line.slice(6).trim() || "message";
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim());
      }
    }

    events.push({ event, dataText: dataLines.join("\n") });
  }

  return { events, rest };
}

function parseSseJson(dataText: string): Record<string, unknown> {
  const text = String(dataText || "").trim();
  if (!text) {
    return {};
  }
  try {
    const parsed = JSON.parse(text) as Record<string, unknown>;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function classifyAttack(payload: string): string {
  const text = String(payload || "").toLowerCase();
  if (text.includes("union select") || text.includes(" or 1=1") || text.includes("drop table")) {
    return "SQL 注入";
  }
  if (text.includes("<script") || text.includes("onerror=") || text.includes("javascript:")) {
    return "XSS";
  }
  if (text.includes("nmap") || text.includes("awvs") || text.includes("masscan") || text.includes("scan")) {
    return "自动化扫描";
  }
  if (text.includes("login") || text.includes("password") || text.includes("auth failed")) {
    return "暴力破解";
  }
  return "异常流量";
}

function formatTimestamp(ts: number | null): string {
  if (!Number.isFinite(ts) || !ts || ts <= 0) {
    return "--";
  }
  return new Date(ts * 1000).toLocaleString();
}

function listToMarkdownLines(list: string[]): string {
  if (list.length === 0) {
    return "- 无";
  }
  return list.map((item) => `- ${item}`).join("\n");
}

function buildReportMarkdown(alerts: AlertItem[]): string {
  const total = alerts.length;
  const highRisk = alerts.filter((item) => item.risk === "high" || item.risk === "critical").length;
  const blocked = alerts.filter((item) => item.blocked).length;

  const riskCounter = new Map<string, number>();
  const sourceCounter = new Map<string, number>();

  for (const item of alerts) {
    riskCounter.set(item.risk, (riskCounter.get(item.risk) || 0) + 1);
    sourceCounter.set(item.source, (sourceCounter.get(item.source) || 0) + 1);
  }

  const topRiskEntry = Array.from(riskCounter.entries()).sort((a, b) => b[1] - a[1])[0] || ["unknown", 0];
  const topSources = Array.from(sourceCounter.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([ip, count]) => `${ip} (${count})`);

  const latestAlerts = alerts.slice(0, REPORT_LATEST_ALERTS_LIMIT).map((item) => {
    return `- ${formatTimestamp(item.timestamp)} · ${item.source} → ${item.target} · ${classifyAttack(item.payload)} · ${item.risk}`;
  });

  return [
    "# 安全态势总结报告",
    `- 生成时间: ${new Date().toLocaleString()}`,
    `- 当前窗口告警总数: ${total}`,
    `- 高危告警: ${highRisk}`,
    `- 自动拦截: ${blocked}`,
    "",
    "## 风险焦点",
    `- 最高频风险级别: ${topRiskEntry[0]} (${topRiskEntry[1]})`,
    "",
    "## 高频来源",
    listToMarkdownLines(topSources),
    "",
    `## 最近 ${REPORT_LATEST_ALERTS_LIMIT} 条告警`,
    latestAlerts.length > 0 ? latestAlerts.join("\n") : "- 无",
  ].join("\n");
}

function runTerminalCommand(command: string, alerts: AlertItem[]): string[] {
  const text = String(command || "").trim();
  if (!text) {
    return [];
  }

  const lines: string[] = [`$ ${text}`];

  if (text === "help") {
    lines.push("help | stats | tail | block <ip> | clear");
    return lines;
  }

  if (text === "stats") {
    const total = alerts.length;
    const blocked = alerts.filter((item) => item.blocked).length;
    const high = alerts.filter((item) => item.risk === "high" || item.risk === "critical").length;
    lines.push(`alerts=${total} high=${high} blocked=${blocked}`);
    return lines;
  }

  if (text === "tail") {
    const latest = alerts.slice(0, 3);
    if (latest.length === 0) {
      lines.push("暂无告警");
      return lines;
    }
    for (const item of latest) {
      lines.push(`${formatTimestamp(item.timestamp)} ${item.source} -> ${item.target} ${item.risk}`);
    }
    return lines;
  }

  if (text.startsWith("block ")) {
    const ip = text.slice(6).trim();
    if (!ip) {
      lines.push("用法: block <ip>");
      return lines;
    }
    lines.push(`已提交模拟封禁规则: ${ip}`);
    return lines;
  }

  if (text === "clear") {
    lines.push("__CLEAR__");
    return lines;
  }

  lines.push(`未知命令: ${text}`);
  return lines;
}

function buildTerminalBootstrapLines(): string[] {
  return ["[INFO] CyberSentinel terminal online", "[INFO] 可用命令: help, stats, tail, block <ip>, clear"];
}

function formatTerminalLine(text: string, tone: "normal" | "warn" | "error" = "normal"): string {
  const now = new Date().toLocaleTimeString();
  const prefix = tone === "warn" ? "[WARN]" : tone === "error" ? "[ERR ]" : "[INFO]";
  return `${now} ${prefix} ${text}`;
}

function mapSiteHealthToUptime(health: SiteHealthPayload): SiteHealthUi {
  const status = String(health?.status || "").trim();
  const sslTone = String(health?.ssl_tone || "").trim();
  const daysLeft = Number(health?.ssl_days_left);

  if (status === "idle") {
    return { tone: "warning", text: "未配置" };
  }
  if (status === "error" || status === "invalid") {
    return { tone: "offline", text: "检测失败" };
  }
  if (status === "no_ssl") {
    return { tone: "offline", text: "无 HTTPS" };
  }

  if (status === "ok") {
    if (sslTone === "critical") {
      if (Number.isFinite(daysLeft)) {
        return { tone: "offline", text: `证书${daysLeft}天到期` };
      }
      return { tone: "offline", text: "证书高危" };
    }

    if (sslTone === "warning") {
      if (Number.isFinite(daysLeft)) {
        return { tone: "warning", text: `证书${daysLeft}天到期` };
      }
      return { tone: "warning", text: "证书预警" };
    }

    return { tone: "online", text: "正常" };
  }

  return { tone: "offline", text: "异常" };
}

function inferProxyPath(urlText: string): string {
  const text = String(urlText || "").trim();
  if (!text) {
    return "/";
  }

  try {
    const parsed = new URL(text);
    const pathname = parsed.pathname || "/";
    return `${pathname}${parsed.search || ""}`;
  } catch {
    return text.startsWith("/") ? text : `/${text}`;
  }
}

function routeDescription(route: RouteKey): string {
  if (route === "overview") return "总览态势、告警与联动操作";
  if (route === "monitor") return "实时监测与日志链路";
  if (route === "waf") return "WAF 与代理防护策略";
  if (route === "ai") return "AI 模型路由与参数配置";
  return "安全日报生成与归档";
}

export default function DashboardClient({ userEmail }: DashboardClientProps) {
  const [route, setRoute] = useState<RouteKey>("overview");
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [selected, setSelected] = useState<AlertItem | null>(null);
  const [alertsLoadState, setAlertsLoadState] = useState<"loading" | "ready" | "empty" | "error">("loading");
  const [alertsPage, setAlertsPage] = useState(0);
  const PAGE_SIZE = 15;

  const { theme, toggleTheme } = useTheme();
  const { wsAlerts, wsConnected } = useWebSocket(null);

  const mergedAlerts = useMemo(() => {
    const wsMapped = (wsAlerts || []).map(mapBackendAlert);
    const existingIds = new Set(alerts.map((a) => a.id));
    const newWsAlerts = wsMapped.filter((a) => !existingIds.has(a.id));
    const combined = [...alerts, ...newWsAlerts];
    return combined.slice(-300);
  }, [alerts, wsAlerts]);

  const paginatedAlerts = useMemo(() => {
    const start = alertsPage * PAGE_SIZE;
    return mergedAlerts.slice(start, start + PAGE_SIZE);
  }, [mergedAlerts, alertsPage]);

  const totalPages = Math.max(1, Math.ceil(mergedAlerts.length / PAGE_SIZE));

  const [config, setConfig] = useState<PersistedUserConfig | null>(null);
  const [configDraft, setConfigDraft] = useState<ConfigDraft>({
    ai_provider: normalizeProviderForDraft(undefined),
    model: "",
    base_url: "",
    api_key: "",
  });
  const [configStatus, setConfigStatus] = useState("正在同步配置...");
  const [savingConfig, setSavingConfig] = useState(false);
  const [testingConfig, setTestingConfig] = useState(false);
  const [refreshingConfig, setRefreshingConfig] = useState(false);

  const [copilotMessages, setCopilotMessages] = useState<CopilotMessage[]>([]);
  const [copilotInput, setCopilotInput] = useState("");
  const [copilotSending, setCopilotSending] = useState(false);
  const [copilotHint, setCopilotHint] = useState("通用咨询模式");
  const activeCopilotRequestId = useRef(0);

  const [terminalLogs, setTerminalLogs] = useState<string[]>(buildTerminalBootstrapLines());
  const [reportMarkdown, setReportMarkdown] = useState<string>(() => buildReportMarkdown(mergedAlerts));
  const [reportTyping, setReportTyping] = useState(false);
  const reportTypingToken = useRef(0);

  const [siteTargetInput, setSiteTargetInput] = useState("");
  const [siteTargetSaving, setSiteTargetSaving] = useState(false);
  const [siteHealth, setSiteHealth] = useState<SiteHealthPayload | null>(null);
  const [siteHealthUi, setSiteHealthUi] = useState<SiteHealthUi>({ tone: "offline", text: "未检测" });
  const [proxyPathInput, setProxyPathInput] = useState("/");
  const [proxyTesting, setProxyTesting] = useState(false);
  const [threatStatus, setThreatStatus] = useState("请选择一条告警后可确认入库");
  const [threatStatusTone, setThreatStatusTone] = useState<"default" | "ok" | "error">("default");
  const [confirmingThreat, setConfirmingThreat] = useState(false);

  const siteHealthTimer = useRef<number | null>(null);

  const counters = useMemo(() => {
    const alertsTotal = mergedAlerts.length;
    const highRiskTotal = mergedAlerts.filter((a) => a.risk === "high" || a.risk === "critical").length;
    const blockedTotal = mergedAlerts.filter((a) => a.blocked).length;
    const siteHealthText = siteHealthUi.text;
    return { alertsTotal, highRiskTotal, blockedTotal, siteHealthText };
  }, [mergedAlerts, siteHealthUi.text]);



  function appendTerminalLogs(lines: string[], tone: "normal" | "warn" | "error" = "normal") {
    if (lines.length === 0) {
      return;
    }
    const formatted = lines.map((line) => formatTerminalLine(line, tone));
    setTerminalLogs((prev) => [...prev, ...formatted].slice(-TERMINAL_LOG_LIMIT));
  }

  async function typewriteReport(markdown: string) {
    reportTypingToken.current += 1;
    const token = reportTypingToken.current;
    const lines = markdown.split("\n");
    const current: string[] = [];
    setReportTyping(true);

    try {
      for (const line of lines) {
        if (token !== reportTypingToken.current) {
          setReportTyping(false);
          return;
        }
        current.push(line);
        setReportMarkdown(current.join("\n"));
        await new Promise((resolve) => {
          window.setTimeout(resolve, line.startsWith("#") ? 80 : 26);
        });
      }
    } finally {
      if (token === reportTypingToken.current) {
        setReportTyping(false);
      }
    }
  }

  async function refreshReportWithTypewriter() {
    const next = buildReportMarkdown(mergedAlerts);
    await typewriteReport(next);
  }

  function handleTerminalCommand(command: string) {
    const outputLines = runTerminalCommand(command, mergedAlerts);
    if (outputLines.length === 0) {
      return;
    }

    if (outputLines.includes("__CLEAR__")) {
      const kept = outputLines.filter((line) => line !== "__CLEAR__");
      setTerminalLogs(kept.length > 0 ? kept.map((line) => formatTerminalLine(line)) : []);
      return;
    }

    const hasUnknown = outputLines.some((line) => line.startsWith("未知命令"));
    appendTerminalLogs(outputLines, hasUnknown ? "warn" : "normal");
  }

  async function fetchWithRetry(url: string, options?: RequestInit & { retries?: number }): Promise<Response> {
    const headers: Record<string, string> = {
      ...(options?.headers as Record<string, string> || {}),
    };
    const response = await fetch(url, {
      ...options,
      headers,
      credentials: "include",
      cache: "no-store",
    });
    return response;
  }

  async function loadUserConfig(signal?: AbortSignal) {
    const response = await fetchWithRetry(`/api/backend/user/config`, { signal });

    const data = (await response.json().catch(() => ({}))) as PersistedUserConfig & { detail?: string };
    if (!response.ok) {
      throw new Error(data.detail || `HTTP ${response.status}`);
    }

    setConfig(data);
    setConfigDraft((prev) => ({
      ...prev,
      ai_provider: normalizeProviderForDraft(data.ai_provider),
      model: data.model || "",
      base_url: data.base_url || "",
    }));
    setConfigStatus("配置已同步");
  }

  async function loadAlerts(options?: { signal?: AbortSignal; showLoading?: boolean }) {
    const showLoading = Boolean(options?.showLoading);
    if (showLoading) {
      setAlertsLoadState("loading");
    }
    const response = await fetchWithRetry(`/api/backend/alerts?limit=100`, { signal: options?.signal });

    if (!response.ok) {
      const payload = (await response.json().catch(() => ({}))) as { detail?: string };
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }

    const payload = (await response.json().catch(() => ({}))) as { items?: BackendAlertItem[] };
    const items = Array.isArray(payload.items) ? payload.items : [];
    if (items.length === 0) {
      setAlerts([]);
      setSelected(null);
      setAlertsLoadState("empty");
      return;
    }

    const mapped = items.map(mapBackendAlert).reverse();
    setAlerts(mapped);
    setAlertsLoadState("ready");

    setSelected((prev) => {
      if (prev) {
        const keep = mapped.find((item) => item.id === prev.id);
        if (keep) {
          return keep;
        }
      }
      return mapped[0] || null;
    });
  }

  useEffect(() => {
    let cancelled = false;
    setConfigStatus("正在同步配置...");
    console.log("[dashboard] useEffect running, loading data...");

    loadUserConfig().then(() => {
      console.log("[dashboard] loadUserConfig success");
    }).catch((error: unknown) => {
      if (cancelled) return;
      console.log("[dashboard] loadUserConfig error:", error);
      const message = error instanceof Error ? error.message : String(error);
      setConfigStatus(formatLoadError(message));
    });

    loadAlerts({ showLoading: true }).then(() => {
      console.log("[dashboard] loadAlerts success");
    }).catch((error: unknown) => {
      if (cancelled) return;
      console.log("[dashboard] loadAlerts error:", error);
      setAlerts([]);
      setSelected(null);
      setAlertsLoadState("error");
    });

    const timer = window.setInterval(() => {
      loadAlerts({ showLoading: false }).catch(() => {
        if (!cancelled) {
          setConfigStatus("告警自动刷新失败，当前显示上次成功数据");
        }
      });
    }, ALERTS_POLL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!selected) {
      setCopilotHint("通用咨询模式");
      return;
    }
    const contextId = selected.alertId || selected.id;
    setCopilotHint(`告警上下文: ${contextId} / ${selected.source} → ${selected.target}`);
  }, [selected]);

  useEffect(() => {
    if (!selected) {
      setThreatStatus("请选择一条告警后可确认入库");
      setThreatStatusTone("default");
      return;
    }

    const currentId = selected.alertId || selected.id;
    setThreatStatus(`当前选中: ${currentId} / ${selected.source} → ${selected.target}`);
    setThreatStatusTone("default");
  }, [selected]);

  async function pingSiteHealth(signal?: AbortSignal) {
    const response = await fetchWithRetry(`/api/backend/site/health`, { signal });

    const payload = (await response.json().catch(() => ({}))) as SiteHealthPayload & { detail?: string };
    if (!response.ok) {
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }

    setSiteHealth(payload);
    const mapped = mapSiteHealthToUptime(payload);
    setSiteHealthUi(mapped);
  }

  function startSiteHealthPolling() {
    if (siteHealthTimer.current) {
      window.clearInterval(siteHealthTimer.current);
      siteHealthTimer.current = null;
    }

    siteHealthTimer.current = window.setInterval(() => {
      pingSiteHealth().catch(() => {
        setSiteHealthUi({ tone: "offline", text: "离线" });
      });
    }, 20000);
  }

  async function handleSaveSiteTarget() {
    const rawUrl = String(siteTargetInput || "").trim();
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

    setSiteTargetSaving(true);
    setConfigStatus("正在保存站点...");
    try {
      const response = await fetch(`/api/backend/site/target`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          },
        credentials: "include",
        body: JSON.stringify({ url: normalizedUrl }),
      });

      const payload = (await response.json().catch(() => ({}))) as SiteTargetResponse;
      if (!response.ok) {
        throw new Error(payload.detail || `HTTP ${response.status}`);
      }

      setSiteTargetInput(String(payload.target || normalizedUrl));
      setConfigStatus("站点保存成功，正在刷新健康状态");
      await pingSiteHealth();
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      setConfigStatus(`站点保存失败：${message}`);
    } finally {
      setSiteTargetSaving(false);
    }
  }

  async function handleTestSiteProxy() {
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
  }

  async function handleConfirmThreat() {
    const current = selected;
    const alertId = String(current?.alertId || "").trim();
    if (!alertId) {
      setThreatStatus("当前告警没有 alert_id，无法确认");
      setThreatStatusTone("error");
      return;
    }

    setConfirmingThreat(true);
    setThreatStatus("正在确认并写入新威胁库...");
    setThreatStatusTone("default");

    try {
      const response = await fetch(`/api/backend/threats/confirm`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          },
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

      setThreatStatus(`确认成功，已写入: ${String(payload.saved_to || "new_threats.csv")}`);
      setThreatStatusTone("ok");
      appendTerminalLogs([`threat ${alertId} confirmed`], "normal");
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      setThreatStatus(`确认失败: ${message}`);
      setThreatStatusTone("error");
    } finally {
      setConfirmingThreat(false);
    }
  }

  async function handleToggleVoiceAlert() {
    const next = !Boolean(config?.alert_voice_enabled);
    setConfigStatus("正在更新语音预警配置...");

    try {
      const response = await fetch(`/api/backend/user/config`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          },
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
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      setConfigStatus(`语音预警更新失败：${message}`);
    }
  }

  useEffect(() => {
    let cancelled = false;
    pingSiteHealth().catch(() => {
      if (cancelled) return;
      setSiteHealthUi({ tone: "offline", text: "离线" });
    });
    startSiteHealthPolling();

    return () => {
      cancelled = true;
      if (siteHealthTimer.current) {
        window.clearInterval(siteHealthTimer.current);
        siteHealthTimer.current = null;
      }
    };
  }, []);

  useEffect(() => {
    setReportMarkdown(buildReportMarkdown(mergedAlerts));
  }, [mergedAlerts]);

  function updateLastAssistantMessage(nextContent: string) {
    setCopilotMessages((prev) => {
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

  async function sendCopilotMessage(messageText: string) {
    const message = String(messageText || "").trim();
    if (!message || copilotSending) {
      return;
    }

    const requestId = ++activeCopilotRequestId.current;
    const historyForRequest: CopilotMessage[] = copilotMessages
      .slice(-COPILOT_HISTORY_REQUEST_LIMIT)
      .map((item) => ({ role: item.role, content: item.content }));

    setCopilotMessages((prev) => {
      const next: CopilotMessage[] = [...prev, { role: "user", content: message }, { role: "assistant", content: "" }];
      return next.slice(-COPILOT_HISTORY_LIMIT);
    });

    setCopilotInput("");
    setCopilotSending(true);

    try {
      const response = await fetch(`/api/backend/copilot/stream`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message,
          alert_id: selected?.alertId || null,
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
          if (requestId !== activeCopilotRequestId.current) {
            return;
          }
          if (done) {
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          const parsed = parseSseBuffer(buffer);
          buffer = parsed.rest;

          for (const eventItem of parsed.events) {
            if (eventItem.event === "done") {
              continue;
            }

            if (eventItem.event === "error") {
              const errorData = parseSseJson(eventItem.dataText);
              throw new Error(String(errorData.message || "流式响应错误"));
            }

            const data = parseSseJson(eventItem.dataText);
            const token = String(data.token || "");
            if (!token) {
              continue;
            }

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
      if (requestId === activeCopilotRequestId.current) {
        setCopilotSending(false);
      }
    }
  }

  async function handleRefreshConfig() {
    setConfigStatus("正在重新同步...");
    setRefreshingConfig(true);
    try {
      await loadUserConfig();
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      setConfigStatus(formatLoadError(message));
    } finally {
      setRefreshingConfig(false);
    }
  }

  async function handleSaveConfig() {
    setConfigStatus("正在保存配置...");
    setSavingConfig(true);
    const body: Record<string, unknown> = {
      ai_provider: configDraft.ai_provider,
      model: configDraft.model,
      base_url: configDraft.base_url,
    };
    if (configDraft.api_key.trim()) {
      body.api_key = configDraft.api_key.trim();
    }

    try {
      const response = await fetch(`/api/backend/user/config`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          },
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

      setConfigStatus("配置已保存，路由引擎已更新");
      setConfig((prev) => ({ ...(prev || ({} as PersistedUserConfig)), ...(payload.config || {}) }));
      setConfigDraft((prev) => ({ ...prev, api_key: "" }));
      await loadUserConfig();
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      setConfigStatus(`保存失败：${message}`);
    } finally {
      setSavingConfig(false);
    }
  }

  async function handleTestConfig() {
    setConfigStatus("正在测试多模型连通性...");
    setTestingConfig(true);
    const body: Record<string, unknown> = {
      ai_provider: configDraft.ai_provider,
      model: configDraft.model,
      base_url: configDraft.base_url,
      timeout_seconds: config?.timeout_seconds || 30,
    };
    if (configDraft.api_key.trim()) {
      body.api_key = configDraft.api_key.trim();
    }

    try {
      const response = await fetch(`/api/backend/llm/test`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          },
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
      const model = String(payload.result?.model || configDraft.model);
      const provider = String(payload.provider || configDraft.ai_provider);
      setConfigStatus(`测试成功：${provider} / ${model} / ${latency}ms`);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      setConfigStatus(`测试失败：${message}`);
    } finally {
      setTestingConfig(false);
    }
  }

  const selectedLogId = selected?.id;
  const isOverviewRoute = route === "overview";
  const isMonitorRoute = route === "monitor";
  const isWafRoute = route === "waf";
  const isAiRoute = route === "ai";
  const isReportRoute = route === "report";

  function handleSelectLog(id: string) {
    const found = mergedAlerts.find((item) => item.id === id) || null;
    setSelected(found);
  }

  return (
    <div className="min-h-screen bg-cyber-bg text-cyber-text">
      <div className="pointer-events-none fixed inset-0 opacity-20 [background-image:radial-gradient(circle_at_1px_1px,rgba(0,245,255,.25)_1px,transparent_0)] [background-size:16px_16px]" />
      <main className="relative mx-auto flex min-h-screen max-w-[1600px] flex-col md:flex-row gap-4 p-4">
        <CyberSidebar items={NAV_ITEMS} active={route} onSelect={setRoute} />

        <section className="flex-1 flex flex-col gap-4 min-h-[calc(100vh-2rem)]">
          <div className="flex items-center justify-end gap-2">
            <div className={`flex items-center gap-1 px-2 py-1 text-[10px] rounded ${wsConnected ? "bg-green-500/10 text-green-300" : "bg-red-500/10 text-red-400"}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${wsConnected ? "bg-green-400 animate-pulse" : "bg-red-400"}`} />
              {wsConnected ? "WS在线" : "WS离线"}
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={toggleTheme}
              className="border-cyber-cyan/30 text-cyber-text/70 hover:text-cyber-cyan hover:bg-cyber-cyan/10 hover:border-cyber-cyan/60"
            >
              {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => signOut({ callbackUrl: "/" })}
              className="border-cyber-cyan/30 text-cyber-text/70 hover:text-cyber-cyan hover:bg-cyber-cyan/10 hover:border-cyber-cyan/60"
            >
              <LogOut className="w-4 h-4 mr-2" />
              退出登录
            </Button>
          </div>
          <StatsCards stats={counters} />

          {(isOverviewRoute || isMonitorRoute) ? (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              <div className="bg-black/40 border border-cyber-cyan/30 backdrop-blur p-3 h-[280px]">
                <h3 className="text-[10px] uppercase tracking-widest text-cyber-text/60 mb-2">攻击趋势 (近24时段)</h3>
                <AttackTrendChart alerts={mergedAlerts} />
              </div>
              <div className="bg-black/40 border border-cyber-cyan/30 backdrop-blur p-3 h-[280px]">
                <h3 className="text-[10px] uppercase tracking-widest text-cyber-text/60 mb-2">攻击分布</h3>
                <SourcePieChart alerts={mergedAlerts} />
              </div>
            </div>
          ) : null}

          <div className="bg-black/40 border border-cyber-cyan/30 p-3 text-sm text-cyber-text/70">{configStatus}</div>

          {!isOverviewRoute ? (
            <div className="bg-black/40 border border-cyber-cyan/30 p-4 text-sm text-cyber-text/80">
              当前标签页：{NAV_ITEMS.find((item) => item.key === route)?.label || route} · {routeDescription(route)}
            </div>
          ) : null}

          {(isOverviewRoute || isMonitorRoute) ? (
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 min-h-0 flex-1">
              <div className="xl:col-span-2 min-h-0 flex flex-col gap-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm uppercase tracking-widest text-cyber-text/70">实时告警流</h2>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      const link = document.createElement("a");
                      link.href = "/api/backend/export/alerts?limit=1000";
                      link.download = "alerts.csv";
                      link.click();
                    }}
                    className="border-cyber-cyan/40 text-cyber-cyan"
                  >
                    导出CSV
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      loadAlerts({ showLoading: true }).catch(() => {
                        setAlertsLoadState("error");
                      });
                    }}
                    className="border-cyber-cyan/40 text-cyber-cyan"
                  >
                    刷新
                  </Button>
                </div>
                </div>
                <div className="min-h-0 flex-1">
                  {alertsLoadState === "loading" ? (
                    <div className="h-full min-h-[220px] bg-black/40 border border-cyber-cyan/30 flex items-center justify-center text-cyber-text/60 text-sm">
                      正在加载告警...
                    </div>
                  ) : alertsLoadState === "error" ? (
                    <div className="h-full min-h-[220px] bg-black/40 border border-red-400/30 flex flex-col items-center justify-center gap-2 text-sm text-red-300">
                      告警加载失败，请稍后重试
                      <Button variant="outline" size="sm" onClick={() => void loadAlerts()} className="border-red-300/40 text-red-200">
                        重试
                      </Button>
                    </div>
                  ) : alertsLoadState === "empty" ? (
                    <div className="h-full min-h-[220px] bg-black/40 border border-cyber-cyan/30 flex items-center justify-center text-cyber-text/60 text-sm">
                      暂无告警
                    </div>
                  ) : (
                    <div className="flex flex-col h-full min-h-0">
                      <div className="flex-1 min-h-0">
                        <AttackLogTable
                          logs={paginatedAlerts}
                          highlightId={selectedLogId}
                          selectedId={selectedLogId}
                          onSelect={handleSelectLog}
                        />
                      </div>
                      {totalPages > 1 && (
                        <div className="flex items-center justify-center gap-2 py-2 border-t border-cyber-cyan/20">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setAlertsPage(Math.max(0, alertsPage - 1))}
                            disabled={alertsPage === 0}
                            className="border-cyber-cyan/30 text-cyber-text/60 text-xs px-2 h-7"
                          >
                            上一页
                          </Button>
                          <span className="text-xs text-cyber-text/50">
                            {alertsPage + 1} / {totalPages}
                          </span>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setAlertsPage(Math.min(totalPages - 1, alertsPage + 1))}
                            disabled={alertsPage >= totalPages - 1}
                            className="border-cyber-cyan/30 text-cyber-text/60 text-xs px-2 h-7"
                          >
                            下一页
                          </Button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              <div className="min-h-0 flex flex-col gap-4">
                <CopilotPanel
                  messages={copilotMessages}
                  draft={copilotInput}
                  loading={copilotSending}
                  onDraftChange={setCopilotInput}
                  onSend={() => void sendCopilotMessage(copilotInput)}
                />
              </div>
            </div>
          ) : null}

          {(isOverviewRoute || isMonitorRoute) ? (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              <div className="h-[320px]">
                <HackerTerminal lines={terminalLogs} onCommand={handleTerminalCommand} />
              </div>

              <div className="bg-black/40 border border-cyber-cyan/30 backdrop-blur p-4 h-[320px] overflow-y-auto">
                <div className="mb-3 flex items-center justify-between text-sm text-cyber-text/80">
                  <span>安全日报</span>
                  <Button variant="outline" size="sm" onClick={() => void refreshReportWithTypewriter()} className="border-cyber-cyan/40 text-cyber-cyan">
                    <RefreshCw className={`mr-1 h-3.5 w-3.5 ${reportTyping ? "animate-spin" : ""}`} />
                    刷新
                  </Button>
                </div>
                <pre className="whitespace-pre-wrap text-xs leading-5 text-cyber-text/85">{reportMarkdown}</pre>
              </div>
            </div>
          ) : null}

          {(isOverviewRoute || isWafRoute) ? (
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
              <div className="bg-black/40 border border-cyber-cyan/30 p-4 space-y-3">
                <h3 className="text-sm uppercase tracking-widest text-cyber-text/70">站点监测</h3>
                <div className="text-xs text-cyber-text/80">状态: {siteHealthUi.text}</div>
                <input
                  value={siteTargetInput}
                  onChange={(event) => setSiteTargetInput(event.target.value)}
                  placeholder="https://example.com"
                  className="w-full bg-black/50 border border-cyber-cyan/30 text-cyber-text text-sm py-2 px-2 focus:outline-none"
                />
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full border-cyber-cyan/40 text-cyber-cyan"
                  onClick={() => void handleSaveSiteTarget()}
                  disabled={siteTargetSaving || !siteTargetInput.trim()}
                >
                  保存目标
                </Button>
                <div className="text-[11px] text-cyber-text/60">{siteHealth?.url ? `当前目标: ${siteHealth.url}` : "当前目标: 未设置"}</div>
              </div>

              <div className="bg-black/40 border border-cyber-cyan/30 p-4 space-y-3">
                <h3 className="text-sm uppercase tracking-widest text-cyber-text/70">代理与 WAF</h3>
                <input
                  value={proxyPathInput}
                  onChange={(event) => setProxyPathInput(event.target.value)}
                  placeholder="/"
                  className="w-full bg-black/50 border border-cyber-cyan/30 text-cyber-text text-sm py-2 px-2 focus:outline-none"
                />
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full border-cyber-cyan/40 text-cyber-cyan"
                  onClick={() => void handleTestSiteProxy()}
                  disabled={proxyTesting}
                >
                  {proxyTesting ? "测试中..." : "测试代理链路"}
                </Button>
                <div className="text-[11px] text-cyber-text/60">路径支持 URL 或相对路径，命中策略会返回 403。</div>
              </div>

              <div className="bg-black/40 border border-cyber-cyan/30 p-4 space-y-3">
                <h3 className="text-sm uppercase tracking-widest text-cyber-text/70">告警确认与语音</h3>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full border-cyber-cyan/40 text-cyber-cyan"
                  onClick={() => void handleConfirmThreat()}
                  disabled={confirmingThreat || !selected?.alertId}
                >
                  {confirmingThreat ? "确认中..." : "确认威胁入库"}
                </Button>
                <div
                  className={`text-[11px] px-2 py-1 rounded ${
                    threatStatusTone === "ok"
                      ? "bg-green-500/10 text-green-300"
                      : threatStatusTone === "error"
                        ? "bg-red-500/10 text-red-300"
                        : "bg-black/40 text-cyber-text/70"
                  }`}
                >
                  {threatStatus}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full border-cyber-cyan/40 text-cyber-cyan"
                  onClick={() => void handleToggleVoiceAlert()}
                >
                  {config?.alert_voice_enabled ? "关闭语音预警" : "开启语音预警"}
                </Button>
              </div>
            </div>
          ) : null}

          {(isOverviewRoute || isAiRoute) ? (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              <div className="bg-black/40 border border-cyber-cyan/30 p-4 space-y-2">
                <h3 className="text-sm uppercase tracking-widest text-cyber-text/70">AI 路由配置</h3>
                <select
                  value={configDraft.ai_provider}
                  onChange={(event) => setConfigDraft((prev) => ({ ...prev, ai_provider: event.target.value }))}
                  className="w-full bg-black/50 border border-cyber-cyan/30 text-cyber-text text-sm py-2 px-2"
                >
                  {PROVIDERS.map((provider) => (
                    <option key={provider} value={provider}>
                      {provider}
                    </option>
                  ))}
                </select>
                <input
                  autoComplete="off"
                  value={configDraft.model}
                  onChange={(event) => setConfigDraft((prev) => ({ ...prev, model: event.target.value }))}
                  placeholder="Model"
                  className="w-full bg-black/50 border border-cyber-cyan/30 text-cyber-text text-sm py-2 px-2"
                />
                <input
                  autoComplete="off"
                  value={configDraft.base_url}
                  onChange={(event) => setConfigDraft((prev) => ({ ...prev, base_url: event.target.value }))}
                  placeholder="Base URL"
                  className="w-full bg-black/50 border border-cyber-cyan/30 text-cyber-text text-sm py-2 px-2"
                />
                <input
                  type="password"
                  autoComplete="new-password"
                  value={configDraft.api_key}
                  onChange={(event) => setConfigDraft((prev) => ({ ...prev, api_key: event.target.value }))}
                  placeholder={config?.has_api_key ? "已配置，留空表示不修改" : "输入新的 API Key"}
                  className="w-full bg-black/50 border border-cyber-cyan/30 text-cyber-text text-sm py-2 px-2"
                />
                <div className="text-xs text-cyber-text/60">当前密钥状态：{config?.has_api_key ? config.api_key_masked : "未配置"}</div>
                <div className="flex gap-2 flex-wrap">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void handleSaveConfig()}
                    disabled={savingConfig || testingConfig || refreshingConfig}
                    className="border-cyber-cyan/40 text-cyber-cyan"
                  >
                    {savingConfig ? "保存中..." : "保存配置"}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void handleTestConfig()}
                    disabled={savingConfig || testingConfig || refreshingConfig}
                    className="border-cyber-cyan/40 text-cyber-cyan"
                  >
                    {testingConfig ? "测试中..." : "测试路由"}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void handleRefreshConfig()}
                    disabled={savingConfig || testingConfig || refreshingConfig}
                    className="border-cyber-cyan/40 text-cyber-cyan"
                  >
                    {refreshingConfig ? "同步中..." : "重新同步"}
                  </Button>
                </div>
              </div>

              <div className="bg-black/40 border border-cyber-cyan/30 p-4 space-y-2">
                <h3 className="text-sm uppercase tracking-widest text-cyber-text/70">当前会话</h3>
                <div className="text-sm text-cyber-text/80">用户: {userEmail || "unknown"}</div>
                <div className="text-xs text-cyber-text/60">上下文: {copilotHint}</div>
              </div>
            </div>
          ) : null}

          {(isOverviewRoute || isReportRoute) ? (
            <div className="bg-black/40 border border-cyber-cyan/30 p-4">
              <h3 className="text-sm uppercase tracking-widest text-cyber-text/70 mb-2">日报摘要</h3>
              <pre className="whitespace-pre-wrap text-xs leading-5 text-cyber-text/85">{reportMarkdown}</pre>
            </div>
          ) : null}
        </section>
      </main>
    </div>
  );
}
