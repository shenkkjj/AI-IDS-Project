const API_BASE = "http://127.0.0.1:8000";

const wsStatusEl = document.getElementById("wsStatus");
const uptimeStatusEl = document.getElementById("uptimeStatus");

const alertListEl = document.getElementById("alertList");
const monitorBodyEl = document.getElementById("monitorBody");
const blockedCountEl = document.getElementById("blockedCount");
const blockedListEl = document.getElementById("blockedList");
const attackMatrixEl = document.getElementById("attackMatrix");

const geoListEl = document.getElementById("geoList");
const mapSvgEl = document.getElementById("mapSvg");

const metricTotalEl = document.getElementById("metricTotal");
const metricHighRiskEl = document.getElementById("metricHighRisk");
const metricBlockedEl = document.getElementById("metricBlocked");
const metricSourcesEl = document.getElementById("metricSources");
const metricLatestEl = document.getElementById("metricLatest");

const terminalLogEl = document.getElementById("terminalLog");
const terminalFormEl = document.getElementById("terminalForm");
const terminalInputEl = document.getElementById("terminalInput");

const providerInput = document.getElementById("providerInput");
const apiKeyInput = document.getElementById("apiKeyInput");
const baseUrlInput = document.getElementById("baseUrlInput");
const modelInput = document.getElementById("modelInput");
const saveSiteTargetBtn = document.getElementById("saveSiteTargetBtn");
const siteTargetInput = document.getElementById("siteTargetInput");
const saveConfigBtn = document.getElementById("saveConfigBtn");
const testConfigBtn = document.getElementById("testConfigBtn");
const testSiteProxyBtn = document.getElementById("testSiteProxyBtn");
const configStatusEl = document.getElementById("configStatus");
const confirmThreatBtn = document.getElementById("confirmThreatBtn");
const threatStatusEl = document.getElementById("threatStatus");

const reportMarkdownEl = document.getElementById("reportMarkdown");
const refreshReportBtn = document.getElementById("refreshReportBtn");

const copilotDrawerEl = document.getElementById("copilotDrawer");
const copilotContentEl = document.getElementById("copilotContent");
const closeCopilotBtn = document.getElementById("closeCopilotBtn");

const copilotWidgetEl = document.getElementById("copilotWidget");
const copilotToggleBtn = document.getElementById("copilotToggleBtn");
const copilotPanelEl = document.getElementById("copilotPanel");
const copilotContextHintEl = document.getElementById("copilotContextHint");
const copilotMessagesEl = document.getElementById("copilotMessages");
const copilotFormEl = document.getElementById("copilotForm");
const copilotInputEl = document.getElementById("copilotInput");
const copilotSendBtn = document.getElementById("copilotSendBtn");

const voiceToggleBtn = document.getElementById("voiceToggleBtn");
const voiceStatusEl = document.getElementById("voiceStatus");

const authEmailInput = document.getElementById("authEmailInput");
const authPasswordInput = document.getElementById("authPasswordInput");
const authOtpInput = document.getElementById("authOtpInput");
const authNewPasswordInput = document.getElementById("authNewPasswordInput");

const registerBtn = document.getElementById("registerBtn");
const loginBtn = document.getElementById("loginBtn");
const requestOtpBtn = document.getElementById("requestOtpBtn");
const verifyOtpBtn = document.getElementById("verifyOtpBtn");
const requestResetBtn = document.getElementById("requestResetBtn");
const confirmResetBtn = document.getElementById("confirmResetBtn");
const logoutBtn = document.getElementById("logoutBtn");
const authHintEl = document.getElementById("authHint");

const authButtons = Array.from(document.querySelectorAll(".auth-btn[data-auth]"));

const navButtons = Array.from(document.querySelectorAll(".nav-btn"));
const routePanels = Array.from(document.querySelectorAll(".route-panel"));

const MAX_ALERTS = 200;
const SITE_HEALTH_URL = `${API_BASE}/site/health`;
const SITE_HEALTH_INTERVAL_MS = 20000;
const COPILOT_HISTORY_LIMIT = 16;
const COPILOT_HISTORY_REQUEST_LIMIT = 10;

const GEO_POINTS = [
  { name: "北京", x: 850, y: 140 },
  { name: "上海", x: 880, y: 180 },
  { name: "深圳", x: 860, y: 220 },
  { name: "新加坡", x: 790, y: 265 },
  { name: "东京", x: 930, y: 150 },
  { name: "首尔", x: 900, y: 145 },
  { name: "孟买", x: 710, y: 230 },
  { name: "迪拜", x: 640, y: 200 },
  { name: "法兰克福", x: 540, y: 140 },
  { name: "伦敦", x: 510, y: 125 },
  { name: "纽约", x: 280, y: 145 },
  { name: "洛杉矶", x: 140, y: 170 },
  { name: "圣保罗", x: 320, y: 300 },
  { name: "约翰内斯堡", x: 560, y: 320 },
  { name: "悉尼", x: 920, y: 340 },
];

const state = {
  alerts: [],
  alertIds: new Set(),
  selectedIndex: -1,
  activeRoute: "overview",
  voiceEnabled: false,
  currentUser: null,
  authToken: "",
  copilotSelectedAlertId: "",
  copilotHistory: [],
};

let reconnectTimer = null;
let siteHealthTimer = null;
let currentReportTypingToken = 0;
let activeCopilotRequestId = 0;

function toFiniteNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return null;
  }
  return number;
}

function formatError(error) {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function normalizeRisk(risk) {
  const value = String(risk || "unknown").trim().toLowerCase();
  if (value === "critical" || value === "high" || value === "medium" || value === "low") {
    return value;
  }
  return "unknown";
}

function isHighRisk(riskLevel) {
  return riskLevel === "high" || riskLevel === "critical";
}

function classifyAttack(rawAlert) {
  const payload = String(rawAlert?.payload || "").toLowerCase();
  if (payload.includes("union select") || payload.includes(" or 1=1") || payload.includes("drop table")) {
    return "SQL 注入";
  }
  if (payload.includes("<script") || payload.includes("onerror=") || payload.includes("javascript:")) {
    return "XSS";
  }
  if (payload.includes("nmap") || payload.includes("awvs") || payload.includes("masscan") || payload.includes("scan")) {
    return "自动化扫描";
  }
  if (payload.includes("login") || payload.includes("password") || payload.includes("auth failed")) {
    return "暴力破解";
  }
  return "异常流量";
}

function escapeHtml(input) {
  return String(input)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatTime(ts) {
  const value = toFiniteNumber(ts);
  if (value === null || value <= 0) {
    return "--";
  }
  return new Date(value * 1000).toLocaleString();
}

function markdownToHtml(markdown) {
  const escaped = escapeHtml(markdown || "");
  const lines = escaped.split("\n");
  const out = [];
  let inList = false;

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();

    if (!line.trim()) {
      if (inList) {
        out.push("</ul>");
        inList = false;
      }
      out.push("<br/>");
      continue;
    }

    if (line.startsWith("### ")) {
      if (inList) {
        out.push("</ul>");
        inList = false;
      }
      out.push(`<h3>${line.slice(4)}</h3>`);
      continue;
    }

    if (line.startsWith("## ")) {
      if (inList) {
        out.push("</ul>");
        inList = false;
      }
      out.push(`<h2>${line.slice(3)}</h2>`);
      continue;
    }

    if (line.startsWith("# ")) {
      if (inList) {
        out.push("</ul>");
        inList = false;
      }
      out.push(`<h1>${line.slice(2)}</h1>`);
      continue;
    }

    if (line.startsWith("- ")) {
      if (!inList) {
        out.push("<ul>");
        inList = true;
      }
      out.push(`<li>${line.slice(2)}</li>`);
      continue;
    }

    if (inList) {
      out.push("</ul>");
      inList = false;
    }

    const inlineCode = line.replace(/`([^`]+)`/g, "<code>$1</code>");
    out.push(`<p>${inlineCode}</p>`);
  }

  if (inList) {
    out.push("</ul>");
  }

  return out.join("\n");
}

function normalizeList(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item) => String(item || "").trim() !== "").map((item) => String(item));
}

function listToMarkdownLines(list) {
  if (!Array.isArray(list) || list.length === 0) {
    return "- 无";
  }
  return list.map((item) => `- ${item}`).join("\n");
}

function safeObject(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value;
}

function normalizeCopilotRole(role) {
  return role === "assistant" ? "assistant" : "user";
}

function copyHistoryForRequest() {
  const history = state.copilotHistory.slice(-COPILOT_HISTORY_REQUEST_LIMIT);
  return history.map((item) => ({ role: normalizeCopilotRole(item.role), content: String(item.content || "") }));
}

function pushCopilotHistory(role, content) {
  const text = String(content || "").trim();
  if (!text) {
    return;
  }

  state.copilotHistory = [...state.copilotHistory, { role: normalizeCopilotRole(role), content: text }].slice(-COPILOT_HISTORY_LIMIT);
}

function ensureCopilotPanelOpen() {
  copilotPanelEl.classList.add("open");
  copilotWidgetEl.classList.add("expanded");
}

function toggleCopilotPanel() {
  const willOpen = !copilotPanelEl.classList.contains("open");
  copilotPanelEl.classList.toggle("open", willOpen);
  copilotWidgetEl.classList.toggle("expanded", willOpen);
}

function setCopilotContextHint(alert) {
  if (!alert || !alert.alert_id) {
    state.copilotSelectedAlertId = "";
    copilotContextHintEl.textContent = "通用咨询模式";
    return;
  }

  const source = String(alert.raw_alert?.source_ip || "?");
  const destination = String(alert.raw_alert?.destination_ip || "?");
  state.copilotSelectedAlertId = String(alert.alert_id);
  copilotContextHintEl.textContent = `告警上下文: ${source} → ${destination}`;
}

function renderCopilotMessages() {
  copilotMessagesEl.innerHTML = "";
  if (state.copilotHistory.length === 0) {
    const empty = document.createElement("div");
    empty.className = "copilot-msg assistant";
    empty.innerHTML = '<div class="copilot-msg-body empty-cell">请输入安全问题，或点击告警自动带上下文</div>';
    copilotMessagesEl.appendChild(empty);
    return;
  }

  state.copilotHistory.forEach((item) => {
    const message = document.createElement("div");
    message.className = `copilot-msg ${item.role}`;

    const body = document.createElement("div");
    body.className = "copilot-msg-body";
    body.textContent = item.content;

    message.appendChild(body);
    copilotMessagesEl.appendChild(message);
  });

  copilotMessagesEl.scrollTop = copilotMessagesEl.scrollHeight;
}

function appendStreamingAssistantPlaceholder() {
  const message = document.createElement("div");
  message.className = "copilot-msg assistant";

  const body = document.createElement("div");
  body.className = "copilot-msg-body";
  body.textContent = "";

  message.appendChild(body);
  copilotMessagesEl.appendChild(message);
  copilotMessagesEl.scrollTop = copilotMessagesEl.scrollHeight;
  return body;
}

function parseSseBuffer(buffer) {
  const events = [];
  let rest = String(buffer || "").replaceAll("\r\n", "\n");

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
      .filter((line) => line !== "");

    if (lines.length === 0) {
      continue;
    }

    let event = "message";
    const dataLines = [];

    lines.forEach((line) => {
      if (line.startsWith("event:")) {
        event = line.slice(6).trim() || "message";
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim());
      }
    });

    events.push({ event, dataText: dataLines.join("\n") });
  }

  return { events, rest };
}

function safeParseSseData(dataText) {
  const text = String(dataText || "").trim();
  if (!text) {
    return {};
  }

  try {
    const parsed = JSON.parse(text);
    return safeObject(parsed);
  } catch {
    return {};
  }
}

async function sendCopilotMessage(messageText, options = {}) {
  const message = String(messageText || "").trim();
  if (!message) {
    return;
  }

  if (!state.currentUser) {
    const errText = "请先登录后再使用 Security Copilot";
    pushCopilotHistory("assistant", errText);
    renderCopilotMessages();
    ensureCopilotPanelOpen();
    return;
  }

  const requestId = ++activeCopilotRequestId;
  const alertId = options.alertId || state.copilotSelectedAlertId || "";
  const historyForRequest = copyHistoryForRequest();

  pushCopilotHistory("user", message);
  renderCopilotMessages();
  ensureCopilotPanelOpen();

  const assistantBody = appendStreamingAssistantPlaceholder();
  let assistantContent = "";

  copilotInputEl.disabled = true;
  copilotSendBtn.disabled = true;

  try {
    const response = await fetch(`${API_BASE}/copilot/stream`, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(state.authToken ? { Authorization: `Bearer ${state.authToken}` } : {}),
      },
      body: JSON.stringify({
        message,
        alert_id: alertId || null,
        history: historyForRequest,
      }),
    });

    if (!response.ok || !response.body) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || `HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (requestId !== activeCopilotRequestId) {
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
          const errorData = safeParseSseData(eventItem.dataText);
          throw new Error(String(errorData.message || "流式响应错误"));
        }

        const data = safeParseSseData(eventItem.dataText);
        const token = String(data.token || "");
        if (!token) {
          continue;
        }

        assistantContent += token;
        assistantBody.textContent = assistantContent;
        copilotMessagesEl.scrollTop = copilotMessagesEl.scrollHeight;
      }
    }

    const finalParsed = parseSseBuffer(buffer);
    for (const eventItem of finalParsed.events) {
      if (eventItem.event === "error") {
        const errorData = safeParseSseData(eventItem.dataText);
        throw new Error(String(errorData.message || "流式响应错误"));
      }
      if (eventItem.event !== "done") {
        const data = safeParseSseData(eventItem.dataText);
        const token = String(data.token || "");
        if (token) {
          assistantContent += token;
        }
      }
    }

    if (!assistantContent.trim()) {
      assistantContent = "模型未返回内容，请稍后重试。";
      assistantBody.textContent = assistantContent;
    }

    pushCopilotHistory("assistant", assistantContent);
    renderCopilotMessages();
  } catch (error) {
    const errText = `请求失败: ${formatError(error)}`;
    assistantBody.textContent = errText;
    pushCopilotHistory("assistant", errText);
    renderCopilotMessages();
  } finally {
    if (requestId === activeCopilotRequestId) {
      copilotInputEl.disabled = false;
      copilotSendBtn.disabled = false;
      copilotInputEl.focus();
    }
  }
}

function mapPointForIp(ip) {
  const text = String(ip || "0.0.0.0");
  let hash = 0;
  for (let index = 0; index < text.length; index += 1) {
    hash = (hash * 31 + text.charCodeAt(index)) >>> 0;
  }
  return GEO_POINTS[hash % GEO_POINTS.length];
}

function mapPointForDestination(ip) {
  if (!ip || ip === "127.0.0.1" || ip === "localhost") {
    return { name: "受保护站点", x: 880, y: 180 };
  }
  return mapPointForIp(ip);
}

function setWsStatus(status) {
  wsStatusEl.classList.remove("status-online", "status-connecting", "status-offline");
  if (status === "online") {
    wsStatusEl.textContent = "在线";
    wsStatusEl.classList.add("status-online");
    return;
  }
  if (status === "connecting") {
    wsStatusEl.textContent = "连接中";
    wsStatusEl.classList.add("status-connecting");
    return;
  }
  wsStatusEl.textContent = "离线";
  wsStatusEl.classList.add("status-offline");
}

function setUptimeStatus(stateTone = "offline", customText = "") {
  uptimeStatusEl.classList.remove("status-online", "status-connecting", "status-offline");
  const label = String(customText || "").trim();

  if (stateTone === "online") {
    uptimeStatusEl.textContent = label || "正常";
    uptimeStatusEl.classList.add("status-online");
    return;
  }

  if (stateTone === "warning") {
    uptimeStatusEl.textContent = label || "预警";
    uptimeStatusEl.classList.add("status-connecting");
    return;
  }

  uptimeStatusEl.textContent = label || "异常";
  uptimeStatusEl.classList.add("status-offline");
}

function mapSiteHealthToUptime(health) {
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

function setConfigStatus(text, isError = false) {
  configStatusEl.textContent = text;
  configStatusEl.style.color = isError ? "#fecaca" : "#8ea2ca";
}

function setThreatStatus(text, tone = "default") {
  threatStatusEl.textContent = text;
  threatStatusEl.classList.remove("ok", "error");
  if (tone === "ok") {
    threatStatusEl.classList.add("ok");
  }
  if (tone === "error") {
    threatStatusEl.classList.add("error");
  }
}

function selectedAlert() {
  if (state.selectedIndex < 0 || state.selectedIndex >= state.alerts.length) {
    return null;
  }
  return state.alerts[state.selectedIndex] || null;
}

function openCopilot(alertData) {
  if (!alertData) {
    return;
  }
  const markdown = toMarkdown(alertData);
  copilotContentEl.innerHTML = markdownToHtml(markdown);
  copilotDrawerEl.classList.add("open");
  setCopilotContextHint(alertData);
  ensureCopilotPanelOpen();
}

function closeCopilot() {
  copilotDrawerEl.classList.remove("open");
}

function syncThreatActionState() {
  const current = selectedAlert();
  const canConfirm = Boolean(current?.alert_id);
  confirmThreatBtn.disabled = !canConfirm;
  if (!canConfirm) {
    setThreatStatus("请选择一条告警后可确认入库");
    return;
  }

  const raw = current.raw_alert || {};
  setThreatStatus(`当前选中: ${raw.source_ip || "?"} → ${raw.destination_ip || "?"}`);
}

function pushTerminalLog(text, tone = "normal") {
  const now = new Date().toLocaleTimeString();
  const prefix = tone === "warn" ? "[WARN]" : tone === "error" ? "[ERR ]" : "[INFO]";
  terminalLogEl.textContent += `${now} ${prefix} ${text}\n`;
  terminalLogEl.scrollTop = terminalLogEl.scrollHeight;
}

function initTerminal() {
  pushTerminalLog("CyberSentinel terminal online");
  pushTerminalLog("可用命令: help, stats, tail, block <ip>, clear");
}

function runTerminalCommand(rawCommand) {
  const text = String(rawCommand || "").trim();
  if (!text) {
    return;
  }

  pushTerminalLog(`$ ${text}`);

  if (text === "help") {
    pushTerminalLog("help | stats | tail | block <ip> | clear");
    return;
  }

  if (text === "stats") {
    const total = state.alerts.length;
    const blocked = state.alerts.filter((item) => item.raw_alert?.blocked).length;
    const high = state.alerts.filter((item) => item._ui?.highRisk).length;
    pushTerminalLog(`alerts=${total} high=${high} blocked=${blocked}`);
    return;
  }

  if (text === "tail") {
    const latest = state.alerts.slice(0, 3);
    if (latest.length === 0) {
      pushTerminalLog("暂无告警");
      return;
    }
    latest.forEach((item) => {
      pushTerminalLog(`${formatTime(item.raw_alert?.timestamp)} ${item.raw_alert?.source_ip || "?"} -> ${item.raw_alert?.destination_ip || "?"} ${item._ui?.risk_level || "unknown"}`);
    });
    return;
  }

  if (text.startsWith("block ")) {
    const ip = text.slice(6).trim();
    if (!ip) {
      pushTerminalLog("用法: block <ip>", "warn");
      return;
    }
    pushTerminalLog(`已提交模拟封禁规则: ${ip}`);
    return;
  }

  if (text === "clear") {
    terminalLogEl.textContent = "";
    return;
  }

  pushTerminalLog(`未知命令: ${text}`, "warn");
}

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(state.authToken ? { Authorization: `Bearer ${state.authToken}` } : {}),
      ...(options.headers || {}),
    },
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = data.detail || `HTTP ${response.status}`;
    throw new Error(message);
  }
  return data;
}

function getAuthInputValues() {
  return {
    email: authEmailInput.value.trim(),
    password: authPasswordInput.value,
    otpCode: authOtpInput.value.trim(),
    newPassword: authNewPasswordInput.value,
  };
}

// 警告: URL hash token 传递方案仅用于开发调试
// 生产环境应使用 httpOnly cookie，避免 token 通过 URL 泄露
// 迁移指南: 使用 Next.js 前端的 NextAuth.js 方案替代
function initAuthTokenBridge() {
  const hash = window.location.hash.startsWith("#") ? window.location.hash.slice(1) : "";
  const params = new URLSearchParams(hash);
  const hashToken = String(params.get("access_token") || "").trim();
  const storedToken = String(sessionStorage.getItem("access_token") || "").trim();
  const nextToken = hashToken || storedToken;

  if (!nextToken) {
    return;
  }

  state.authToken = nextToken;
  sessionStorage.setItem("access_token", nextToken);

  if (hashToken) {
    history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
  }
}

function setAuthHint(text, isError = false) {
  authHintEl.textContent = text;
  authHintEl.style.color = isError ? "#fecaca" : "#8ea2ca";
}

function setUserSession(payload) {
  const user = payload?.user || null;
  const config = payload?.config || null;
  const token = String(payload?.access_token || "").trim();
  state.currentUser = user;

  if (!user) {
    state.authToken = "";
    sessionStorage.removeItem("access_token");
    setAuthHint("未登录，配置不会持久化");
    setCopilotContextHint(null);
    setUptimeStatus("offline", "未登录");
    return;
  }

  if (token) {
    state.authToken = token;
    sessionStorage.setItem("access_token", token);
  }

  setAuthHint(`已登录：${user.email}（${user.auth_provider}）`);
  if (config) {
    providerInput.value = String(config.ai_provider || "openai");
    baseUrlInput.value = config.base_url || "";
    modelInput.value = config.model || "";
    apiKeyInput.value = "";
    const provider = String(config.ai_provider || "openai");
    setConfigStatus(`已恢复用户配置: ${provider} / ${config.model || "未设置"}，API Key: ${config.has_api_key ? "已配置" : "未配置"}`);
    if (typeof config.alert_voice_enabled === "boolean") {
      state.voiceEnabled = config.alert_voice_enabled;
      voiceToggleBtn.textContent = state.voiceEnabled ? "关闭语音预警" : "开启语音预警";
      voiceStatusEl.textContent = `语音预警：${state.voiceEnabled ? "开启" : "关闭"}`;
    }
  }
}

async function loadSession() {
  try {
    const session = await apiRequest("/auth/session", { method: "GET" });
    setUserSession(session);
  } catch {
    setUserSession(null);
  }
}

async function registerWithPassword() {
  const { email, password } = getAuthInputValues();
  if (!email || !password) {
    setAuthHint("请填写邮箱和密码", true);
    return;
  }
  const payload = await apiRequest("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setUserSession(payload);
}

async function loginWithPassword() {
  const { email, password } = getAuthInputValues();
  if (!email || !password) {
    setAuthHint("请填写邮箱和密码", true);
    return;
  }
  const payload = await apiRequest("/auth/login/password", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setUserSession(payload);
}

async function loginWithOAuth(provider) {
  const { email } = getAuthInputValues();
  if (!email) {
    setAuthHint("OAuth 模拟登录需要先填写邮箱", true);
    return;
  }
  const payload = await apiRequest("/auth/login/oauth", {
    method: "POST",
    body: JSON.stringify({
      provider,
      provider_user_id: `${provider}-${Date.now()}`,
      email,
      display_name: provider === "github" ? "GitHub 用户" : "Google 用户",
    }),
  });
  setUserSession(payload);
}

async function requestOtp() {
  const { email } = getAuthInputValues();
  if (!email) {
    setAuthHint("请输入邮箱后再发送 OTP", true);
    return;
  }
  await apiRequest("/auth/login/otp/request", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
  setAuthHint("OTP 已发送，请查收邮箱");
}

async function verifyOtpLogin() {
  const { email, otpCode } = getAuthInputValues();
  if (!email || !otpCode) {
    setAuthHint("请输入邮箱和 OTP", true);
    return;
  }
  const payload = await apiRequest("/auth/login/otp/verify", {
    method: "POST",
    body: JSON.stringify({ email, code: otpCode }),
  });
  setUserSession(payload);
}

async function requestPasswordReset() {
  const { email } = getAuthInputValues();
  if (!email) {
    setAuthHint("请输入邮箱后再发起重置", true);
    return;
  }
  await apiRequest("/auth/password/reset/request", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
  setAuthHint("重置验证码已发送");
}

async function confirmPasswordReset() {
  const { email, otpCode, newPassword } = getAuthInputValues();
  if (!email || !otpCode || !newPassword) {
    setAuthHint("请填写邮箱、验证码和新密码", true);
    return;
  }
  await apiRequest("/auth/password/reset/confirm", {
    method: "POST",
    body: JSON.stringify({ email, code: otpCode, new_password: newPassword }),
  });
  setAuthHint("密码重置成功，请使用新密码登录");
}

async function logout() {
  await apiRequest("/auth/logout", { method: "POST", body: JSON.stringify({}) });
  setUserSession(null);
  setAuthHint("已退出登录");
}

function buildFallbackId() {
  return `fallback-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function adaptIncomingAlert(data) {
  const payload = safeObject(data);
  const rawInput = safeObject(payload.raw_alert);
  const llmInput = safeObject(payload.llm_analysis);

  const alertId = String(payload.alert_id || "").trim() || buildFallbackId();
  const timestamp = toFiniteNumber(rawInput.timestamp) ?? toFiniteNumber(payload.processed_at) ?? Date.now() / 1000;

  const rawAlert = {
    ...rawInput,
    source_ip: String(rawInput.source_ip || "unknown"),
    destination_ip: String(rawInput.destination_ip || "unknown"),
    payload: String(rawInput.payload || ""),
    timestamp,
    model_probability: toFiniteNumber(rawInput.model_probability),
    blocked: Boolean(rawInput.blocked),
    block_expires_at: toFiniteNumber(rawInput.block_expires_at),
    feature_values: safeObject(rawInput.feature_values),
  };

  const llmAnalysis = {
    ...llmInput,
    risk_level: normalizeRisk(llmInput.risk_level),
    confidence: toFiniteNumber(llmInput.confidence),
    attack_intent: String(llmInput.attack_intent || "unknown"),
    summary: String(llmInput.summary || ""),
    evidence: normalizeList(llmInput.evidence),
    immediate_actions: normalizeList(llmInput.immediate_actions),
    short_term_actions: normalizeList(llmInput.short_term_actions),
    long_term_hardening: normalizeList(llmInput.long_term_hardening),
    false_positive_analysis: String(llmInput.false_positive_analysis || ""),
    iocs: {
      ips: normalizeList(safeObject(llmInput.iocs).ips),
      domains: normalizeList(safeObject(llmInput.iocs).domains),
      urls: normalizeList(safeObject(llmInput.iocs).urls),
      commands: normalizeList(safeObject(llmInput.iocs).commands),
      keywords: normalizeList(safeObject(llmInput.iocs).keywords),
    },
    mitre_attack: Array.isArray(llmInput.mitre_attack) ? llmInput.mitre_attack : [],
  };

  const attackType = classifyAttack(rawAlert);

  return {
    alert_id: alertId,
    raw_alert: rawAlert,
    llm_analysis: llmAnalysis,
    analysis_error: payload.analysis_error ? String(payload.analysis_error) : null,
    processed_at: toFiniteNumber(payload.processed_at) ?? Date.now() / 1000,
    _ui: {
      risk_level: llmAnalysis.risk_level,
      confidence: llmAnalysis.confidence,
      highRisk: isHighRisk(llmAnalysis.risk_level),
      attackType,
      sourcePoint: mapPointForIp(rawAlert.source_ip),
      targetPoint: mapPointForDestination(rawAlert.destination_ip),
    },
  };
}

function toMarkdown(alertData) {
  const raw = safeObject(alertData.raw_alert);
  const llm = safeObject(alertData.llm_analysis);
  const analysisError = alertData.analysis_error;

  const localRiskLines = [
    "## 本地检测结果",
    `- 模型异常概率: ${raw.model_probability ?? "N/A"}`,
    `- 已自动封禁: ${raw.blocked ? "是" : "否"}`,
    `- 封禁截止: ${formatTime(raw.block_expires_at)}`,
    `- 攻击类型: ${alertData._ui?.attackType || "异常流量"}`,
    "",
  ];

  if (analysisError) {
    return [
      "# 分析失败",
      "",
      ...localRiskLines,
      `- 错误: ${analysisError}`,
      "- 建议: 在『模型路由工厂』中填写 API Key / Base URL / 模型后再重试。",
      "",
      "## 原始告警",
      `- 源IP: ${raw.source_ip || ""}`,
      `- 目标IP: ${raw.destination_ip || ""}`,
      `- 时间: ${formatTime(raw.timestamp)}`,
      `- Payload: ${raw.payload || ""}`,
    ].join("\n");
  }

  const iocs = safeObject(llm.iocs);
  const mitre = Array.isArray(llm.mitre_attack) ? llm.mitre_attack : [];

  const mitreLines =
    mitre.length > 0
      ? mitre
          .map((item) => {
            const row = safeObject(item);
            return `- ${row.technique_id || "N/A"} ${row.technique_name || ""} (${row.tactic || ""}, 置信度: ${row.confidence ?? "N/A"})`;
          })
          .join("\n")
      : "- 无";

  return [
    "# Security Copilot 分析",
    "",
    ...localRiskLines,
    `## 总结\n${llm.summary || "无"}`,
    "",
    "## 风险与置信度",
    `- 风险等级: ${llm.risk_level || "unknown"}`,
    `- 置信度: ${llm.confidence ?? "N/A"}`,
    `- 攻击意图: ${llm.attack_intent || "unknown"}`,
    "",
    "## IOC",
    "### IP",
    listToMarkdownLines(iocs.ips),
    "### 域名",
    listToMarkdownLines(iocs.domains),
    "### URL",
    listToMarkdownLines(iocs.urls),
    "### 命令",
    listToMarkdownLines(iocs.commands),
    "### 关键词",
    listToMarkdownLines(iocs.keywords),
    "",
    "## MITRE ATT&CK",
    mitreLines,
    "",
    "## 证据",
    listToMarkdownLines(llm.evidence),
    "",
    "## 防御建议",
    "### 立即动作",
    listToMarkdownLines(llm.immediate_actions),
    "### 短期动作",
    listToMarkdownLines(llm.short_term_actions),
    "### 长期加固",
    listToMarkdownLines(llm.long_term_hardening),
    "",
    "## 原始告警",
    `- 源IP: ${raw.source_ip || ""}`,
    `- 目标IP: ${raw.destination_ip || ""}`,
    `- 时间: ${formatTime(raw.timestamp)}`,
    `- Payload: ${raw.payload || ""}`,
  ].join("\n");
}

function renderList() {
  alertListEl.innerHTML = "";

  if (state.alerts.length === 0) {
    const empty = document.createElement("li");
    empty.className = "alert-item";
    empty.innerHTML = '<div class="pair empty-cell">暂无告警</div>';
    alertListEl.appendChild(empty);
    return;
  }

  state.alerts.forEach((item, idx) => {
    const li = document.createElement("li");
    const activeClass = idx === state.selectedIndex ? " active" : "";
    const highClass = item._ui?.highRisk ? " high" : "";
    li.className = `alert-item${activeClass}${highClass}`;

    const raw = item.raw_alert || {};
    const risk = item._ui?.risk_level || "unknown";

    li.innerHTML = `
      <div class="meta">
        <span>${formatTime(raw.timestamp)}</span>
        <span>risk=${escapeHtml(risk)}</span>
      </div>
      <div class="pair">${escapeHtml(raw.source_ip || "?")} → ${escapeHtml(raw.destination_ip || "?")}</div>
    `;

    li.addEventListener("click", () => {
      state.selectedIndex = idx;
      renderList();
      syncThreatActionState();
      openCopilot(state.alerts[idx]);
      sendCopilotMessage("请分析这条攻击告警，输出风险判断、处置优先级和可执行防御动作。", {
        alertId: String(state.alerts[idx].alert_id || ""),
      });
    });

    alertListEl.appendChild(li);
  });
}

function renderMetrics() {
  const total = state.alerts.length;
  const highRisk = state.alerts.filter((item) => item._ui?.highRisk).length;
  const blocked = state.alerts.filter((item) => item.raw_alert?.blocked).length;
  const sourceSet = new Set(
    state.alerts.map((item) => String(item.raw_alert?.source_ip || "").trim()).filter((item) => item !== "")
  );

  let latestTimestamp = 0;
  for (const item of state.alerts) {
    const ts = toFiniteNumber(item.raw_alert?.timestamp);
    if (ts !== null && ts > latestTimestamp) {
      latestTimestamp = ts;
    }
  }

  metricTotalEl.textContent = String(total);
  metricHighRiskEl.textContent = String(highRisk);
  metricBlockedEl.textContent = String(blocked);
  metricSourcesEl.textContent = String(sourceSet.size);
  metricLatestEl.textContent = latestTimestamp > 0 ? formatTime(latestTimestamp) : "--";
}

function renderMonitorTable() {
  monitorBodyEl.innerHTML = "";

  if (state.alerts.length === 0) {
    const row = document.createElement("tr");
    row.innerHTML = '<td colspan="6" class="empty-cell">暂无告警</td>';
    monitorBodyEl.appendChild(row);
    return;
  }

  state.alerts.slice(0, 120).forEach((item) => {
    const row = document.createElement("tr");
    const raw = item.raw_alert || {};
    row.innerHTML = `
      <td>${escapeHtml(formatTime(raw.timestamp))}</td>
      <td>${escapeHtml(raw.source_ip || "")}</td>
      <td>${escapeHtml(raw.destination_ip || "")}</td>
      <td>${escapeHtml(item._ui?.risk_level || "unknown")}</td>
      <td>${escapeHtml(raw.model_probability ?? "N/A")}</td>
      <td>${escapeHtml(raw.blocked ? "blocked" : "observed")}</td>
    `;
    monitorBodyEl.appendChild(row);
  });
}

function renderWafView() {
  const blockedAlerts = state.alerts.filter((item) => item.raw_alert?.blocked);
  blockedCountEl.textContent = String(blockedAlerts.length);

  const sourceCount = new Map();
  blockedAlerts.forEach((item) => {
    const sourceIp = String(item.raw_alert?.source_ip || "unknown");
    sourceCount.set(sourceIp, (sourceCount.get(sourceIp) || 0) + 1);
  });

  blockedListEl.innerHTML = "";
  const ranking = Array.from(sourceCount.entries()).sort((a, b) => b[1] - a[1]).slice(0, 20);
  if (ranking.length === 0) {
    blockedListEl.innerHTML = '<li class="empty-cell">暂无拦截来源</li>';
  } else {
    ranking.forEach(([ip, count]) => {
      const li = document.createElement("li");
      li.textContent = `${ip} · ${count}`;
      blockedListEl.appendChild(li);
    });
  }

  const typeCount = new Map();
  state.alerts.forEach((item) => {
    const attackType = item._ui?.attackType || "异常流量";
    typeCount.set(attackType, (typeCount.get(attackType) || 0) + 1);
  });

  attackMatrixEl.innerHTML = "";
  const typeRanking = Array.from(typeCount.entries()).sort((a, b) => b[1] - a[1]);
  if (typeRanking.length === 0) {
    attackMatrixEl.innerHTML = '<li class="empty-cell">等待攻击样本...</li>';
  } else {
    typeRanking.forEach(([type, count]) => {
      const li = document.createElement("li");
      li.textContent = `${type} · ${count}`;
      attackMatrixEl.appendChild(li);
    });
  }
}

function renderMap() {
  mapSvgEl.innerHTML = "";
  geoListEl.innerHTML = "";

  if (state.alerts.length === 0) {
    geoListEl.innerHTML = '<li class="empty-cell">等待攻击轨迹...</li>';
    return;
  }

  const recent = state.alerts.slice(0, 18);
  recent.forEach((item) => {
    const source = item._ui?.sourcePoint;
    const target = item._ui?.targetPoint;
    if (!source || !target) {
      return;
    }

    const path = document.createElementNS("http://www.w3.org/2000/svg", "line");
    path.setAttribute("x1", String(source.x));
    path.setAttribute("y1", String(source.y));
    path.setAttribute("x2", String(target.x));
    path.setAttribute("y2", String(target.y));
    path.setAttribute("stroke", item._ui?.highRisk ? "#ef4444" : "#60a5fa");
    path.setAttribute("stroke-width", item._ui?.highRisk ? "1.8" : "1.1");
    path.setAttribute("stroke-opacity", "0.8");
    mapSvgEl.appendChild(path);

    const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    dot.setAttribute("cx", String(source.x));
    dot.setAttribute("cy", String(source.y));
    dot.setAttribute("r", item._ui?.highRisk ? "3.2" : "2.4");
    dot.setAttribute("fill", item._ui?.highRisk ? "#ef4444" : "#60a5fa");
    mapSvgEl.appendChild(dot);

    const geoItem = document.createElement("li");
    geoItem.textContent = `${source.name} → ${target.name} · ${item._ui?.attackType || "异常流量"} · ${item._ui?.risk_level || "unknown"}`;
    geoListEl.appendChild(geoItem);
  });
}

function computeTopRiskType() {
  const riskCount = new Map();
  state.alerts.forEach((item) => {
    const risk = item._ui?.risk_level || "unknown";
    riskCount.set(risk, (riskCount.get(risk) || 0) + 1);
  });
  const ranked = Array.from(riskCount.entries()).sort((a, b) => b[1] - a[1]);
  return ranked[0] || ["unknown", 0];
}

function computeTopSources(limit = 8) {
  const sourceCount = new Map();
  state.alerts.forEach((item) => {
    const sourceIp = String(item.raw_alert?.source_ip || "unknown");
    sourceCount.set(sourceIp, (sourceCount.get(sourceIp) || 0) + 1);
  });
  return Array.from(sourceCount.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([ip, count]) => `${ip} (${count})`);
}

async function typewriteReport(markdown) {
  currentReportTypingToken += 1;
  const token = currentReportTypingToken;

  const lines = markdown.split("\n");
  const currentLines = [];

  for (const line of lines) {
    if (token !== currentReportTypingToken) {
      return;
    }
    currentLines.push(line);
    reportMarkdownEl.innerHTML = markdownToHtml(currentLines.join("\n"));
    await new Promise((resolve) => {
      setTimeout(resolve, line.startsWith("#") ? 80 : 26);
    });
  }
}

function buildReportMarkdown() {
  const total = state.alerts.length;
  const highRisk = state.alerts.filter((item) => item._ui?.highRisk).length;
  const blocked = state.alerts.filter((item) => item.raw_alert?.blocked).length;
  const analysisErrorCount = state.alerts.filter((item) => item.analysis_error).length;
  const [topRisk, topRiskCount] = computeTopRiskType();
  const topSources = computeTopSources();
  const latestAlerts = state.alerts.slice(0, 5);

  return [
    "# 安全态势总结报告",
    `- 生成时间: ${new Date().toLocaleString()}`,
    `- 当前窗口告警总数: ${total}`,
    `- 高危告警: ${highRisk}`,
    `- 自动拦截: ${blocked}`,
    `- 分析失败: ${analysisErrorCount}`,
    "",
    "## 风险焦点",
    `- 最高频风险级别: ${topRisk} (${topRiskCount})`,
    "",
    "## 高频来源",
    listToMarkdownLines(topSources),
    "",
    "## 最近 5 条告警",
    latestAlerts.length > 0
      ? latestAlerts
          .map((item) => {
            const raw = item.raw_alert || {};
            return `- ${formatTime(raw.timestamp)} · ${raw.source_ip || "?"} → ${raw.destination_ip || "?"} · ${item._ui?.attackType || "异常流量"} · ${item._ui?.risk_level || "unknown"}`;
          })
          .join("\n")
      : "- 无",
  ].join("\n");
}

async function renderReport() {
  const markdown = buildReportMarkdown();
  await typewriteReport(markdown);
}

function renderDerivedViews() {
  renderMetrics();
  renderMonitorTable();
  renderWafView();
  renderMap();
  if (state.activeRoute === "reports") {
    renderReport();
  }
}

function setRoute(route) {
  state.activeRoute = route;

  navButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.route === route);
  });

  routePanels.forEach((panel) => {
    panel.classList.toggle("active", panel.id === `route-${route}`);
  });

  if (route === "reports") {
    renderReport();
  }
}

function speakAlertIfNeeded(alertData) {
  if (!state.voiceEnabled || !window.speechSynthesis) {
    return;
  }

  if (!alertData._ui?.highRisk) {
    return;
  }

  const raw = alertData.raw_alert || {};
  const utterance = new SpeechSynthesisUtterance(`高危攻击告警，来源 ${raw.source_ip || "未知"}，目标 ${raw.destination_ip || "未知"}`);
  utterance.lang = "zh-CN";
  utterance.rate = 1;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
}

function addAlert(alertData) {
  const adapted = adaptIncomingAlert(alertData);
  const alertId = String(adapted.alert_id || "");
  if (alertId && state.alertIds.has(alertId)) {
    return;
  }

  state.alerts = [adapted, ...state.alerts];
  if (alertId) {
    state.alertIds.add(alertId);
  }

  if (state.alerts.length > MAX_ALERTS) {
    const removed = state.alerts[state.alerts.length - 1];
    state.alerts = state.alerts.slice(0, MAX_ALERTS);
    const removedId = String(removed?.alert_id || "");
    if (removedId) {
      state.alertIds.delete(removedId);
    }
  }

  if (state.selectedIndex <= 0) {
    state.selectedIndex = 0;
  } else {
    state.selectedIndex = Math.min(state.selectedIndex + 1, state.alerts.length - 1);
  }

  renderList();
  syncThreatActionState();
  renderDerivedViews();

  const selected = selectedAlert();
  if (selected) {
    setCopilotContextHint(selected);
  }

  if (selected && state.activeRoute === "overview") {
    openCopilot(selected);
  }

  pushTerminalLog(`captured ${adapted.raw_alert?.source_ip || "?"} -> ${adapted.raw_alert?.destination_ip || "?"} (${adapted._ui?.attackType || "异常流量"})`);
  speakAlertIfNeeded(adapted);
}

function connectWebSocket() {
  setWsStatus("connecting");
  const wsUrl = `${API_BASE.replace(/^http/, "ws")}/ws/alerts`;
  const socket = new WebSocket(wsUrl);

  socket.onopen = () => {
    setWsStatus("online");
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    pushTerminalLog("alert stream connected");
  };

  socket.onmessage = (event) => {
    try {
      const parsed = JSON.parse(event.data);
      addAlert(parsed);
    } catch {
      setConfigStatus("收到无效告警数据", true);
      pushTerminalLog("invalid alert payload received", "warn");
    }
  };

  socket.onerror = () => {
    setWsStatus("offline");
    pushTerminalLog("websocket error", "error");
  };

  socket.onclose = () => {
    setWsStatus("offline");
    pushTerminalLog("alert stream closed, retrying...", "warn");
    if (!reconnectTimer) {
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        connectWebSocket();
      }, 1500);
    }
  };
}

async function pingSiteHealth() {
  try {
    const response = await fetch(SITE_HEALTH_URL, {
      headers: {
        ...(state.authToken ? { Authorization: `Bearer ${state.authToken}` } : {}),
      },
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 401) {
        setUptimeStatus("offline", "未登录");
        return;
      }
      throw new Error(payload?.detail || `HTTP ${response.status}`);
    }

    const mapped = mapSiteHealthToUptime(payload);
    setUptimeStatus(mapped.tone, mapped.text);
  } catch {
    setUptimeStatus("offline", "离线");
  }
}

async function saveSiteTarget() {
  const rawUrl = String(siteTargetInput?.value || "").trim();
  if (!rawUrl) {
    setConfigStatus("请输入受保护站点 URL", true);
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
    setConfigStatus("站点 URL 无效，请输入 http(s) 地址", true);
    return;
  }

  saveSiteTargetBtn.disabled = true;
  setConfigStatus("正在保存站点...");

  try {
    await apiRequest("/site/target", {
      method: "POST",
      body: JSON.stringify({ url: normalizedUrl }),
    });
    siteTargetInput.value = normalizedUrl;
    setConfigStatus("站点保存成功，正在刷新健康状态");
    await pingSiteHealth();
  } catch (error) {
    setConfigStatus(`站点保存失败: ${formatError(error)}`, true);
  } finally {
    saveSiteTargetBtn.disabled = false;
  }
}

function startSiteHealthPolling() {
  pingSiteHealth();
  if (siteHealthTimer) {
    clearInterval(siteHealthTimer);
  }
  siteHealthTimer = setInterval(pingSiteHealth, SITE_HEALTH_INTERVAL_MS);
}

async function loadConfig() {
  setConfigStatus("正在加载配置...");
  try {
    const config = await apiRequest("/user/config", { method: "GET" });
    providerInput.value = String(config.ai_provider || "openai");
    baseUrlInput.value = config.base_url || "";
    modelInput.value = config.model || "";
    apiKeyInput.value = "";

    const apiKeyState = config.has_api_key ? "已配置" : "未配置";
    const provider = String(config.ai_provider || "openai");
    setConfigStatus(`配置已加载: ${provider} / ${config.model || "未设置"}，API Key: ${apiKeyState}`);

    if (typeof config.alert_voice_enabled === "boolean") {
      state.voiceEnabled = config.alert_voice_enabled;
      voiceToggleBtn.textContent = state.voiceEnabled ? "关闭语音预警" : "开启语音预警";
      voiceStatusEl.textContent = `语音预警：${state.voiceEnabled ? "开启" : "关闭"}`;
    }
  } catch (error) {
    setConfigStatus(`配置加载失败: ${formatError(error)}`, true);
  }
}

async function saveConfig() {
  const body = {};
  const provider = providerInput.value.trim();
  const apiKey = apiKeyInput.value.trim();
  const baseUrl = baseUrlInput.value.trim();
  const model = modelInput.value.trim();

  if (provider) {
    body.ai_provider = provider;
  }
  if (apiKey) {
    body.api_key = apiKey;
  }
  if (baseUrl) {
    body.base_url = baseUrl;
  }
  if (model) {
    body.model = model;
  }

  body.alert_voice_enabled = state.voiceEnabled;

  if (Object.keys(body).length === 0) {
    setConfigStatus("请至少填写一个配置项", true);
    return;
  }

  setConfigStatus("正在保存配置...");
  saveConfigBtn.disabled = true;

  try {
    const data = await apiRequest("/user/config", {
      method: "PUT",
      body: JSON.stringify(body),
    });

    apiKeyInput.value = "";
    const savedProvider = String(data.config?.ai_provider || provider || "custom");
    providerInput.value = savedProvider;
    setConfigStatus(`保存成功，当前路由: ${savedProvider} / ${data.config.model}`);
  } catch (error) {
    setConfigStatus(`保存失败: ${formatError(error)}`, true);
  } finally {
    saveConfigBtn.disabled = false;
  }
}

async function testConfig() {
  const body = {};
  const provider = providerInput.value.trim();
  const apiKey = apiKeyInput.value.trim();
  const baseUrl = baseUrlInput.value.trim();
  const model = modelInput.value.trim();

  if (provider) {
    body.ai_provider = provider;
  }
  if (apiKey) {
    body.api_key = apiKey;
  }
  if (baseUrl) {
    body.base_url = baseUrl;
  }
  if (model) {
    body.model = model;
  }

  setConfigStatus("正在测试模型连接...");
  testConfigBtn.disabled = true;

  try {
    const response = await fetch(`${API_BASE}/llm/test`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(state.authToken ? { Authorization: `Bearer ${state.authToken}` } : {}),
      },
      body: JSON.stringify(body),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `HTTP ${response.status}`);
    }

    const latency = data.result?.latency_ms ?? "?";
    const resultProvider = String(data.provider || provider || "custom");
    setConfigStatus(`模型连接成功: ${resultProvider}，延迟 ${latency}ms`);
  } catch (error) {
    setConfigStatus(`模型连接失败: ${formatError(error)}`, true);
  } finally {
    testConfigBtn.disabled = false;
  }
}

async function testSiteProxy() {
  setConfigStatus("正在测试代理链路...");
  testSiteProxyBtn.disabled = true;

  try {
    const response = await fetch(`${API_BASE}/site/proxy/`, {
      method: "GET",
      headers: {
        ...(state.authToken ? { Authorization: `Bearer ${state.authToken}` } : {}),
      },
      credentials: "include",
    });

    const bodyText = await response.text();
    const brief = bodyText.slice(0, 80).replace(/\s+/g, " ").trim();

    if (response.status === 401) {
      setConfigStatus("代理测试失败: 请先登录", true);
      return;
    }

    if (response.status === 403) {
      setConfigStatus("代理测试命中 WAF 拦截（403）");
      return;
    }

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    setConfigStatus(`代理测试成功: HTTP ${response.status}${brief ? ` · ${brief}` : ""}`);
  } catch (error) {
    setConfigStatus(`代理测试失败: ${formatError(error)}`, true);
  } finally {
    testSiteProxyBtn.disabled = false;
  }
}


async function confirmThreat() {
  const current = selectedAlert();
  const alertId = String(current?.alert_id || "").trim();
  if (!alertId) {
    setThreatStatus("当前告警没有 alert_id，无法确认", "error");
    return;
  }

  confirmThreatBtn.disabled = true;
  setThreatStatus("正在确认并写入新威胁库...");

  try {
    const response = await fetch(`${API_BASE}/threats/confirm`, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(state.authToken ? { Authorization: `Bearer ${state.authToken}` } : {}),
      },
      body: JSON.stringify({
        alert_id: alertId,
        label: "user_confirmed_threat",
      }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `HTTP ${response.status}`);
    }

    setThreatStatus(`确认成功，已写入: ${data.saved_to}`, "ok");
    pushTerminalLog(`threat ${alertId} confirmed`);
  } catch (error) {
    setThreatStatus(`确认失败: ${formatError(error)}`, "error");
  } finally {
    confirmThreatBtn.disabled = !Boolean(selectedAlert()?.alert_id);
  }
}

function initRouteSwitching() {
  navButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const route = button.dataset.route;
      if (!route) {
        return;
      }
      setRoute(route);
    });
  });
}

function initAuthActions() {
  registerBtn.addEventListener("click", async () => {
    try {
      await registerWithPassword();
      await loadConfig();
    } catch (error) {
      setAuthHint(`注册失败: ${formatError(error)}`, true);
    }
  });

  loginBtn.addEventListener("click", async () => {
    try {
      await loginWithPassword();
      await loadConfig();
    } catch (error) {
      setAuthHint(`登录失败: ${formatError(error)}`, true);
    }
  });

  requestOtpBtn.addEventListener("click", async () => {
    try {
      await requestOtp();
    } catch (error) {
      setAuthHint(`发送 OTP 失败: ${formatError(error)}`, true);
    }
  });

  verifyOtpBtn.addEventListener("click", async () => {
    try {
      await verifyOtpLogin();
      await loadConfig();
    } catch (error) {
      setAuthHint(`OTP 登录失败: ${formatError(error)}`, true);
    }
  });

  requestResetBtn.addEventListener("click", async () => {
    try {
      await requestPasswordReset();
    } catch (error) {
      setAuthHint(`重置码发送失败: ${formatError(error)}`, true);
    }
  });

  confirmResetBtn.addEventListener("click", async () => {
    try {
      await confirmPasswordReset();
    } catch (error) {
      setAuthHint(`密码重置失败: ${formatError(error)}`, true);
    }
  });

  logoutBtn.addEventListener("click", async () => {
    try {
      await logout();
      setConfigStatus("未登录，无法加载用户配置", true);
      await pingSiteHealth();
    } catch (error) {
      setAuthHint(`退出失败: ${formatError(error)}`, true);
    }
  });

  authButtons.forEach((button) => {
    button.addEventListener("click", async () => {
      const provider = button.dataset.auth;
      if (!provider) {
        return;
      }
      try {
        await loginWithOAuth(provider);
        await loadConfig();
      } catch (error) {
        setAuthHint(`OAuth 登录失败: ${formatError(error)}`, true);
      }
    });
  });
}

function initAuthSimulation() {
  authButtons.forEach((button) => {
    button.addEventListener("click", () => {
      authButtons.forEach((candidate) => {
        candidate.classList.toggle("active", candidate === button);
      });
    });
  });
}

function initCopilotDrawer() {
  closeCopilotBtn.addEventListener("click", closeCopilot);
  copilotToggleBtn.addEventListener("click", toggleCopilotPanel);

  copilotFormEl.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = copilotInputEl.value;
    copilotInputEl.value = "";
    await sendCopilotMessage(text);
  });
}

function initVoiceToggle() {
  voiceToggleBtn.addEventListener("click", () => {
    state.voiceEnabled = !state.voiceEnabled;
    voiceToggleBtn.textContent = state.voiceEnabled ? "关闭语音预警" : "开启语音预警";
    voiceStatusEl.textContent = `语音预警：${state.voiceEnabled ? "开启" : "关闭"}`;
  });
}

function initTerminalInput() {
  terminalFormEl.addEventListener("submit", (event) => {
    event.preventDefault();
    const command = terminalInputEl.value;
    terminalInputEl.value = "";
    runTerminalCommand(command);
  });
}

async function bootstrapSession() {
  await loadSession();
  if (!state.currentUser) {
    setConfigStatus("未登录，无法加载用户配置", true);
    await pingSiteHealth();
    return;
  }
  await loadConfig();
  await pingSiteHealth();
}

saveConfigBtn.addEventListener("click", saveConfig);
testConfigBtn.addEventListener("click", testConfig);
testSiteProxyBtn.addEventListener("click", testSiteProxy);
saveSiteTargetBtn.addEventListener("click", saveSiteTarget);
confirmThreatBtn.addEventListener("click", confirmThreat);
refreshReportBtn.addEventListener("click", renderReport);

initRouteSwitching();
initAuthActions();
initAuthSimulation();
initCopilotDrawer();
initVoiceToggle();
initTerminalInput();

initAuthTokenBridge();

setRoute("overview");
renderList();
renderDerivedViews();
syncThreatActionState();
initTerminal();
connectWebSocket();
bootstrapSession();
startSiteHealthPolling();
