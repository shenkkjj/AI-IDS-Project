"use client";

import { useEffect, useMemo, useRef, useState, type ComponentType, type FormEvent } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  BarChart3,
  Bot,
  Globe,
  Radar,
  RefreshCw,
  SendHorizonal,
  Shield,
  ShieldCheck,
  Siren,
  SlidersHorizontal,
  TerminalSquare,
  Volume2,
  VolumeX,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

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
  backendAccessToken: string;
  backendBaseUrl: string;
  userEmail: string;
};

const ALERTS_POLL_MS = 8000;
const COPILOT_HISTORY_LIMIT = 16;
const COPILOT_HISTORY_REQUEST_LIMIT = 10;
const TERMINAL_LOG_LIMIT = 120;
const REPORT_LATEST_ALERTS_LIMIT = 5;

const NAV_ITEMS: { key: RouteKey; label: string; icon: ComponentType<{ className?: string }> }[] = [
  { key: "overview", label: "概览", icon: BarChart3 },
  { key: "monitor", label: "监测", icon: Activity },
  { key: "waf", label: "WAF 管理", icon: Shield },
  { key: "ai", label: "AI 配置", icon: SlidersHorizontal },
  { key: "report", label: "安全日报", icon: Radar },
];

const PROVIDERS = ["openai", "claude", "gemini", "grok", "custom"] as const;

const DEMO_ALERTS: AlertItem[] = [
  {
    id: "A-2026-001",
    alertId: "",
    source: "103.14.89.23",
    target: "10.0.3.8",
    risk: "critical",
    payload: "GET /search?q=<script>alert(1)</script>",
    summary: "检测到高置信度 XSS 投递行为，建议立即启用 WAF 阻断并回溯同源会话。",
    timestamp: Math.floor(Date.now() / 1000) - 120,
    blocked: true,
  },
  {
    id: "A-2026-002",
    alertId: "",
    source: "45.91.233.11",
    target: "10.0.3.8",
    risk: "high",
    payload: "id=1 UNION SELECT username,password FROM users--",
    summary: "疑似 SQLi 探测，包含 UNION SELECT 特征词，建议临时拉黑源 IP。",
    timestamp: Math.floor(Date.now() / 1000) - 540,
    blocked: false,
  },
  {
    id: "A-2026-003",
    alertId: "",
    source: "91.200.47.9",
    target: "10.0.3.8",
    risk: "medium",
    payload: "nmap -sS -Pn -p 21,22,80,443",
    summary: "端口扫描特征命中，当前为中风险，建议观察是否持续升高。",
    timestamp: Math.floor(Date.now() / 1000) - 980,
    blocked: false,
  },
];

const RISK_STYLE: Record<AlertRisk, string> = {
  critical: "bg-rose-500",
  high: "bg-orange-400",
  medium: "bg-amber-300",
  low: "bg-emerald-300",
};

function TopMetric({ title, value, pulse }: { title: string; value: string; pulse?: boolean }) {
  return (
    <Card className="p-4">
      <p className="text-xs text-cyan-100/70">{title}</p>
      <div className="mt-2 flex items-center gap-2">
        <p className="text-2xl font-semibold text-cyan-50">{value}</p>
        {pulse ? <span className="h-2.5 w-2.5 rounded-full bg-rose-500 animate-ping" /> : null}
      </div>
    </Card>
  );
}

function formatLoadError(message: string): string {
  if (message.includes("401")) {
    return "会话失效，请重新登录";
  }
  return `配置同步失败：${message}`;
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
  return [
    "[INFO] CyberSentinel terminal online",
    "[INFO] 可用命令: help, stats, tail, block <ip>, clear",
  ];
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

export default function DashboardClient({ backendAccessToken, backendBaseUrl, userEmail }: DashboardClientProps) {
  const [route, setRoute] = useState<RouteKey>("overview");
  const [alerts, setAlerts] = useState<AlertItem[]>(DEMO_ALERTS);
  const [selected, setSelected] = useState<AlertItem | null>(DEMO_ALERTS[0] || null);

  const [config, setConfig] = useState<PersistedUserConfig | null>(null);
  const [configDraft, setConfigDraft] = useState<ConfigDraft>({
    ai_provider: "openai",
    model: "gpt-4o-mini",
    base_url: "",
    api_key: "",
  });
  const [configStatus, setConfigStatus] = useState("正在同步配置...");

  const [copilotMessages, setCopilotMessages] = useState<CopilotMessage[]>([]);
  const [copilotInput, setCopilotInput] = useState("");
  const [copilotSending, setCopilotSending] = useState(false);
  const [copilotHint, setCopilotHint] = useState("通用咨询模式");
  const activeCopilotRequestId = useRef(0);

  const [terminalLogs, setTerminalLogs] = useState<string[]>(buildTerminalBootstrapLines());
  const [terminalInput, setTerminalInput] = useState("");
  const [reportMarkdown, setReportMarkdown] = useState<string>(() => buildReportMarkdown(DEMO_ALERTS));
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
    const total = alerts.length;
    const high = alerts.filter((a) => a.risk === "high" || a.risk === "critical").length;
    const blocked = alerts.filter((a) => a.blocked).length;
    return { total, high, blocked };
  }, [alerts]);

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

    for (const line of lines) {
      if (token !== reportTypingToken.current) {
        return;
      }
      current.push(line);
      setReportMarkdown(current.join("\n"));
      await new Promise((resolve) => {
        window.setTimeout(resolve, line.startsWith("#") ? 80 : 26);
      });
    }

    if (token === reportTypingToken.current) {
      setReportTyping(false);
    }
  }

  async function refreshReportWithTypewriter() {
    const next = buildReportMarkdown(alerts);
    await typewriteReport(next);
  }

  function handleTerminalSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const command = terminalInput;
    setTerminalInput("");

    const outputLines = runTerminalCommand(command, alerts);
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

  async function loadUserConfig(signal?: AbortSignal) {
    const response = await fetch(`${backendBaseUrl}/user/config`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${backendAccessToken}`,
      },
      credentials: "include",
      cache: "no-store",
      signal,
    });

    const data = (await response.json().catch(() => ({}))) as PersistedUserConfig & { detail?: string };
    if (!response.ok) {
      throw new Error(data.detail || `HTTP ${response.status}`);
    }

    setConfig(data);
    setConfigDraft({
      ai_provider: data.ai_provider || "openai",
      model: data.model || "gpt-4o-mini",
      base_url: data.base_url || "",
      api_key: "",
    });
    setConfigStatus("配置已同步");
  }

  async function loadAlerts(signal?: AbortSignal) {
    const response = await fetch(`${backendBaseUrl}/alerts?limit=100`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${backendAccessToken}`,
      },
      credentials: "include",
      cache: "no-store",
      signal,
    });

    if (!response.ok) {
      const payload = (await response.json().catch(() => ({}))) as { detail?: string };
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }

    const payload = (await response.json().catch(() => ({}))) as { items?: BackendAlertItem[] };
    const items = Array.isArray(payload.items) ? payload.items : [];
    if (items.length === 0) {
      setAlerts(DEMO_ALERTS);
      return;
    }

    const mapped = items.map(mapBackendAlert).reverse();
    setAlerts(mapped);

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
    const controller = new AbortController();
    setConfigStatus("正在同步配置...");

    loadUserConfig(controller.signal).catch((error: unknown) => {
      if (controller.signal.aborted) {
        return;
      }
      const message = error instanceof Error ? error.message : String(error);
      setConfigStatus(formatLoadError(message));
    });

    loadAlerts(controller.signal).catch(() => {
      if (controller.signal.aborted) {
        return;
      }
      setAlerts(DEMO_ALERTS);
      setSelected(DEMO_ALERTS[0] || null);
    });

    const timer = window.setInterval(() => {
      loadAlerts().catch(() => undefined);
    }, ALERTS_POLL_MS);

    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, [backendAccessToken, backendBaseUrl]);

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
    const response = await fetch(`${backendBaseUrl}/site/health`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${backendAccessToken}`,
      },
      credentials: "include",
      signal,
    });

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
      const response = await fetch(`${backendBaseUrl}/site/target`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${backendAccessToken}`,
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
      const response = await fetch(`${backendBaseUrl}/site/proxy${path}`, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${backendAccessToken}`,
        },
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
      const response = await fetch(`${backendBaseUrl}/threats/confirm`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${backendAccessToken}`,
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
      const response = await fetch(`${backendBaseUrl}/user/config`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${backendAccessToken}`,
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
    const controller = new AbortController();
    pingSiteHealth(controller.signal).catch(() => {
      if (controller.signal.aborted) {
        return;
      }
      setSiteHealthUi({ tone: "offline", text: "离线" });
    });
    startSiteHealthPolling();

    return () => {
      controller.abort();
      if (siteHealthTimer.current) {
        window.clearInterval(siteHealthTimer.current);
        siteHealthTimer.current = null;
      }
    };
  }, [backendAccessToken, backendBaseUrl]);

  useEffect(() => {
    setReportMarkdown(buildReportMarkdown(alerts));
  }, [alerts]);

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
      const next: CopilotMessage[] = [
        ...prev,
        { role: "user", content: message },
        { role: "assistant", content: "" },
      ];
      return next.slice(-COPILOT_HISTORY_LIMIT);
    });

    setCopilotInput("");
    setCopilotSending(true);

    try {
      const response = await fetch(`${backendBaseUrl}/copilot/stream`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${backendAccessToken}`,
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
    try {
      await loadUserConfig();
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      setConfigStatus(formatLoadError(message));
    }
  }

  async function handleSaveConfig() {
    setConfigStatus("正在保存配置...");
    const body: Record<string, unknown> = {
      ai_provider: configDraft.ai_provider,
      model: configDraft.model,
      base_url: configDraft.base_url,
    };
    if (configDraft.api_key.trim()) {
      body.api_key = configDraft.api_key.trim();
    }

    try {
      const response = await fetch(`${backendBaseUrl}/user/config`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${backendAccessToken}`,
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
    }
  }

  async function handleTestConfig() {
    setConfigStatus("正在测试多模型连通性...");
    const body: Record<string, unknown> = {
      ai_provider: configDraft.ai_provider,
      model: configDraft.model,
      base_url: configDraft.base_url,
    };
    if (configDraft.api_key.trim()) {
      body.api_key = configDraft.api_key.trim();
    }

    try {
      const response = await fetch(`${backendBaseUrl}/llm/test`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${backendAccessToken}`,
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
    }
  }

  function handleCopilotSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendCopilotMessage(copilotInput);
  }

  return (
    <div className="min-h-screen bg-background text-cyan-50">
      <div className="pointer-events-none fixed inset-0 opacity-20 [background-image:radial-gradient(circle_at_1px_1px,rgba(103,232,249,.35)_1px,transparent_0)] [background-size:18px_18px]" />

      <main className="relative mx-auto flex min-h-screen max-w-[1440px] gap-3 p-4">
        <aside className="w-64 rounded-2xl border border-cyan-300/20 bg-slate-950/70 p-3 backdrop-blur">
          <div className="mb-4 flex items-center gap-2 rounded-xl border border-cyan-400/30 bg-cyan-500/10 p-3">
            <Siren className="h-4 w-4 text-cyan-300" />
            <div>
              <p className="text-sm font-semibold">AI-CyberSentinel</p>
              <p className="text-[11px] text-cyan-100/60">赛博指挥中心</p>
            </div>
          </div>

          <nav className="space-y-1">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const active = route === item.key;
              return (
                <button
                  key={item.key}
                  onClick={() => setRoute(item.key)}
                  className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition ${
                    active ? "bg-cyan-500/20 text-cyan-100" : "text-cyan-100/70 hover:bg-cyan-500/10"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </button>
              );
            })}
          </nav>
        </aside>

        <section className="flex-1 space-y-3">
          <div className="grid grid-cols-4 gap-3">
            <TopMetric title="告警总数" value={String(counters.total)} />
            <TopMetric title="高危告警" value={String(counters.high)} pulse />
            <TopMetric title="自动拦截" value={String(counters.blocked)} />
            <TopMetric title="当前账号" value={userEmail || "unknown"} />
          </div>

          <motion.div
            key={route}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
            className="grid grid-cols-[1.3fr_1fr] gap-3"
          >
            <Card className="h-[68vh] overflow-hidden p-0">
              <div className="flex items-center justify-between border-b border-cyan-200/20 px-4 py-3 text-sm text-cyan-100/80">
                <span>实时告警流</span>
                <Button variant="outline" size="sm" onClick={() => void loadAlerts()}>
                  刷新
                </Button>
              </div>
              <div className="h-[calc(68vh-56px)] space-y-2 overflow-auto p-3">
                {alerts.map((item) => (
                  <button
                    key={item.id}
                    className="w-full rounded-xl border border-cyan-200/20 bg-slate-900/60 p-3 text-left transition hover:bg-slate-800/80"
                    onClick={() => setSelected(item)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="text-xs text-cyan-100/70">{item.id}</div>
                      <span className={`h-2.5 w-2.5 rounded-full ${RISK_STYLE[item.risk]} animate-pulse`} />
                    </div>
                    <p className="mt-2 text-sm">
                      {item.source} → {item.target}
                    </p>
                    <p className="mt-1 line-clamp-1 text-xs text-cyan-100/60">{item.payload}</p>
                  </button>
                ))}
              </div>
            </Card>

            <Card className="h-[68vh] p-4">
              <div className="mb-3 flex items-center gap-2 text-sm text-cyan-100/80">
                <Bot className="h-4 w-4" />
                多模型路由配置
              </div>
              <p className="text-xs text-cyan-100/60">{configStatus}</p>

              <div className="mt-3 space-y-2 rounded-xl border border-cyan-200/20 bg-slate-900/40 p-3 text-xs text-cyan-50/90">
                <label className="block space-y-1">
                  <span className="text-cyan-100/60">Provider</span>
                  <select
                    value={configDraft.ai_provider}
                    onChange={(event) => setConfigDraft((prev) => ({ ...prev, ai_provider: event.target.value }))}
                    className="w-full rounded bg-slate-900 px-2 py-1.5 text-cyan-50 outline-none ring-1 ring-cyan-300/20"
                  >
                    {PROVIDERS.map((provider) => (
                      <option key={provider} value={provider}>
                        {provider}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="block space-y-1">
                  <span className="text-cyan-100/60">Model</span>
                  <input
                    value={configDraft.model}
                    onChange={(event) => setConfigDraft((prev) => ({ ...prev, model: event.target.value }))}
                    className="w-full rounded bg-slate-900 px-2 py-1.5 text-cyan-50 outline-none ring-1 ring-cyan-300/20"
                  />
                </label>

                <label className="block space-y-1">
                  <span className="text-cyan-100/60">Base URL</span>
                  <input
                    value={configDraft.base_url}
                    onChange={(event) => setConfigDraft((prev) => ({ ...prev, base_url: event.target.value }))}
                    className="w-full rounded bg-slate-900 px-2 py-1.5 text-cyan-50 outline-none ring-1 ring-cyan-300/20"
                  />
                </label>

                <label className="block space-y-1">
                  <span className="text-cyan-100/60">API Key（可选覆盖）</span>
                  <input
                    type="password"
                    value={configDraft.api_key}
                    onChange={(event) => setConfigDraft((prev) => ({ ...prev, api_key: event.target.value }))}
                    placeholder={config?.has_api_key ? "已配置，留空表示不修改" : "输入新的 API Key"}
                    className="w-full rounded bg-slate-900 px-2 py-1.5 text-cyan-50 outline-none ring-1 ring-cyan-300/20"
                  />
                </label>

                <div className="text-cyan-100/60">当前密钥状态：{config?.has_api_key ? config.api_key_masked : "未配置"}</div>
              </div>

              <div className="mt-3 flex flex-wrap gap-2">
                <Button variant="outline" size="sm" onClick={handleSaveConfig}>
                  保存配置
                </Button>
                <Button variant="outline" size="sm" onClick={handleTestConfig}>
                  测试路由
                </Button>
                <Button variant="outline" size="sm" onClick={handleRefreshConfig}>
                  重新同步
                </Button>
              </div>
            </Card>
          </motion.div>

          <div className="grid grid-cols-2 gap-3">
            <Card className="h-[32vh] p-4">
              <div className="mb-3 flex items-center justify-between text-sm text-cyan-100/80">
                <div className="flex items-center gap-2">
                  <TerminalSquare className="h-4 w-4" />
                  溯源终端
                </div>
              </div>

              <pre className="h-[calc(32vh-96px)] overflow-auto whitespace-pre-wrap rounded bg-slate-900/60 p-2 font-mono text-xs leading-5 text-cyan-100/80">
                {terminalLogs.join("\n")}
              </pre>

              <form onSubmit={handleTerminalSubmit} className="mt-2 flex items-center gap-2">
                <input
                  value={terminalInput}
                  onChange={(event) => setTerminalInput(event.target.value)}
                  placeholder="输入命令：help / stats / tail / block <ip> / clear"
                  className="flex-1 rounded bg-slate-900 px-3 py-2 text-xs text-cyan-50 outline-none ring-1 ring-cyan-300/20"
                />
                <Button type="submit" size="sm" disabled={!terminalInput.trim()}>
                  执行
                </Button>
              </form>
            </Card>

            <Card className="h-[32vh] p-4">
              <div className="mb-3 flex items-center justify-between text-sm text-cyan-100/80">
                <div className="flex items-center gap-2">
                  <Radar className="h-4 w-4" />
                  安全日报
                </div>
                <Button variant="outline" size="sm" onClick={() => void refreshReportWithTypewriter()}>
                  <RefreshCw className={`mr-1 h-3.5 w-3.5 ${reportTyping ? "animate-spin" : ""}`} />
                  刷新
                </Button>
              </div>

              <pre className="h-[calc(32vh-64px)] overflow-auto whitespace-pre-wrap rounded bg-slate-900/60 p-3 text-xs leading-5 text-cyan-100/85">
                {reportMarkdown}
              </pre>
            </Card>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <Card className="h-[24vh] p-4">
              <div className="mb-2 flex items-center gap-2 text-sm text-cyan-100/80">
                <Globe className="h-4 w-4" />
                站点监测
              </div>

              <div className="space-y-2 text-xs text-cyan-100/75">
                <div className="flex items-center justify-between rounded bg-slate-900/40 px-2 py-1.5">
                  <span>状态</span>
                  <span
                    className={
                      siteHealthUi.tone === "online"
                        ? "text-emerald-300"
                        : siteHealthUi.tone === "warning"
                          ? "text-amber-300"
                          : "text-rose-300"
                    }
                  >
                    {siteHealthUi.text}
                  </span>
                </div>

                <input
                  value={siteTargetInput}
                  onChange={(event) => setSiteTargetInput(event.target.value)}
                  placeholder="https://example.com"
                  className="w-full rounded bg-slate-900 px-3 py-2 text-xs text-cyan-50 outline-none ring-1 ring-cyan-300/20"
                />

                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={() => void handleSaveSiteTarget()}
                  disabled={siteTargetSaving || !siteTargetInput.trim()}
                >
                  保存目标
                </Button>

                <div className="line-clamp-2 text-[11px] text-cyan-100/55">
                  {siteHealth?.url ? `当前目标: ${siteHealth.url}` : "当前目标: 未设置"}
                </div>
              </div>
            </Card>

            <Card className="h-[24vh] p-4">
              <div className="mb-2 flex items-center gap-2 text-sm text-cyan-100/80">
                <Shield className="h-4 w-4" />
                代理与WAF
              </div>

              <div className="space-y-2 text-xs text-cyan-100/75">
                <input
                  value={proxyPathInput}
                  onChange={(event) => setProxyPathInput(event.target.value)}
                  placeholder="/"
                  className="w-full rounded bg-slate-900 px-3 py-2 text-xs text-cyan-50 outline-none ring-1 ring-cyan-300/20"
                />

                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={() => void handleTestSiteProxy()}
                  disabled={proxyTesting}
                >
                  {proxyTesting ? "测试中..." : "测试代理链路"}
                </Button>

                <div className="rounded bg-slate-900/40 px-2 py-1.5 text-[11px] text-cyan-100/60">
                  路径支持 URL 或相对路径，命中策略会返回 403。
                </div>
              </div>
            </Card>

            <Card className="h-[24vh] p-4">
              <div className="mb-2 flex items-center gap-2 text-sm text-cyan-100/80">
                <ShieldCheck className="h-4 w-4" />
                告警确认与语音
              </div>

              <div className="space-y-2 text-xs text-cyan-100/75">
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={() => void handleConfirmThreat()}
                  disabled={confirmingThreat || !selected?.alertId}
                >
                  {confirmingThreat ? "确认中..." : "确认威胁入库"}
                </Button>

                <div
                  className={`rounded px-2 py-1.5 text-[11px] ${
                    threatStatusTone === "ok"
                      ? "bg-emerald-500/10 text-emerald-200"
                      : threatStatusTone === "error"
                        ? "bg-rose-500/10 text-rose-200"
                        : "bg-slate-900/40 text-cyan-100/70"
                  }`}
                >
                  {threatStatus}
                </div>

                <Button variant="outline" size="sm" className="w-full" onClick={() => void handleToggleVoiceAlert()}>
                  {config?.alert_voice_enabled ? (
                    <>
                      <VolumeX className="mr-1 h-3.5 w-3.5" />
                      关闭语音预警
                    </>
                  ) : (
                    <>
                      <Volume2 className="mr-1 h-3.5 w-3.5" />
                      开启语音预警
                    </>
                  )}
                </Button>
              </div>
            </Card>
          </div>
        </section>
      </main>

      <AnimatePresence>
        {selected ? (
          <motion.aside
            initial={{ x: 460, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 460, opacity: 0 }}
            transition={{ duration: 0.22 }}
            className="fixed right-0 top-0 z-50 h-full w-[460px] border-l border-cyan-300/30 bg-slate-950/95 p-4 backdrop-blur"
          >
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold">Security Copilot</h3>
              <Button variant="outline" size="sm" onClick={() => setSelected(null)}>
                关闭
              </Button>
            </div>

            <Card className="mb-3 p-3">
              <p className="text-xs text-cyan-100/70">告警上下文</p>
              <p className="mt-1 text-xs text-cyan-100/80">{copilotHint}</p>
              <p className="mt-2 rounded bg-slate-900 p-2 text-xs text-cyan-100/80">{selected.payload || "无 payload"}</p>
              <div className="mt-2 flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    void sendCopilotMessage("请分析这条攻击告警，输出风险判断、处置优先级和可执行防御动作。")
                  }
                >
                  快速分析
                </Button>
              </div>
            </Card>

            <Card className="flex h-[calc(100%-180px)] flex-col p-3">
              <div className="mb-2 text-xs text-cyan-100/60">对话</div>
              <div className="mb-3 flex-1 space-y-2 overflow-auto rounded bg-slate-900/40 p-2">
                {copilotMessages.length === 0 ? (
                  <div className="rounded border border-cyan-300/20 p-2 text-xs text-cyan-100/70">
                    请输入安全问题，或点击“快速分析”让 Copilot 带告警上下文回答。
                  </div>
                ) : (
                  copilotMessages.map((item, index) => (
                    <div
                      key={`${item.role}-${index}`}
                      className={`rounded p-2 text-xs leading-5 ${
                        item.role === "user"
                          ? "ml-6 bg-cyan-500/15 text-cyan-50"
                          : "mr-6 border border-cyan-300/20 bg-slate-900 text-cyan-100"
                      }`}
                    >
                      {item.content || (copilotSending && index === copilotMessages.length - 1 ? "思考中..." : "")}
                    </div>
                  ))
                )}
              </div>

              <form onSubmit={handleCopilotSubmit} className="flex items-center gap-2">
                <input
                  value={copilotInput}
                  onChange={(event) => setCopilotInput(event.target.value)}
                  placeholder="输入安全问题，例如：这条告警要先做什么？"
                  className="flex-1 rounded bg-slate-900 px-3 py-2 text-xs text-cyan-50 outline-none ring-1 ring-cyan-300/20"
                  disabled={copilotSending}
                />
                <Button type="submit" size="sm" disabled={copilotSending || !copilotInput.trim()}>
                  <SendHorizonal className="h-4 w-4" />
                </Button>
              </form>
            </Card>
          </motion.aside>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
