"use client";

import { useEffect, useState, useCallback } from "react";
import { Check, Loader2, Sparkles, RefreshCw, Unlink } from "lucide-react";
import {
  INCIDENT_SEVERITY_OPTIONS,
  INCIDENT_STATUS_OPTIONS,
  type IncidentDetailResponse,
  type IncidentEvent,
  type IncidentSeverity,
  type IncidentStatus,
  type IncidentLinkedAlert,
} from "@/types/incident";
import IncidentTimeline from "./IncidentTimeline";
import IncidentLinkedAlerts from "./IncidentLinkedAlerts";
import StatusView from "./StatusView";

const NOTE_MAX_LENGTH = 1000;
const SUMMARY_MAX_LENGTH = 1000;
const TITLE_MAX_LENGTH = 120;

export interface IncidentDetailPanelProps {
  detail: IncidentDetailResponse;
  actionState: "idle" | "saving" | "error";
  error: string | null;
  onUpdate: (input: {
    status?: IncidentStatus | null;
    severity?: IncidentSeverity | null;
    title?: string | null;
    summary?: string | null;
    note?: string | null;
  }) => Promise<{ ok: boolean; error?: string }>;
  onLinkAlert: (alertId: string) => Promise<{
    ok: boolean;
    error?: string;
  }>;
  onUnlinkAlert: (alertId: string) => Promise<{
    ok: boolean;
    error?: string;
  }>;
  onRefresh: () => void;
}

export default function IncidentDetailPanel({
  detail,
  actionState,
  error,
  onUpdate,
  onLinkAlert,
  onUnlinkAlert,
  onRefresh,
}: IncidentDetailPanelProps) {
  const [status, setStatus] = useState<IncidentStatus>(detail.incident.status);
  const [severity, setSeverity] = useState<IncidentSeverity>(
    detail.incident.severity
  );
  const [title, setTitle] = useState<string>(detail.incident.title);
  const [summary, setSummary] = useState<string>(detail.incident.summary ?? "");
  const [note, setNote] = useState<string>("");
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [linkInput, setLinkInput] = useState<string>("");

  // 切换 incident 时同步本地 state
  useEffect(() => {
    setStatus(detail.incident.status);
    setSeverity(detail.incident.severity);
    setTitle(detail.incident.title);
    setSummary(detail.incident.summary ?? "");
    setNote("");
    setSaveMessage(null);
    setLinkInput("");
  }, [detail.incident.incident_id, detail.incident.status, detail.incident.severity, detail.incident.title, detail.incident.summary]);

  const dirty =
    status !== detail.incident.status ||
    severity !== detail.incident.severity ||
    title !== detail.incident.title ||
    summary !== (detail.incident.summary ?? "") ||
    note.trim().length > 0;

  const handleSave = useCallback(async () => {
    const result = await onUpdate({
      status,
      severity,
      title,
      summary: summary.trim() || null,
      note: note.trim() || null,
    });
    if (result.ok) {
      setNote("");
      setSaveMessage("已保存");
      window.setTimeout(() => setSaveMessage(null), 2200);
    } else {
      setSaveMessage(result.error || "保存失败");
    }
  }, [onUpdate, status, severity, title, summary, note]);

  const handleLink = useCallback(async () => {
    const value = linkInput.trim();
    if (!value) return;
    const result = await onLinkAlert(value);
    if (result.ok) {
      setLinkInput("");
    } else {
      setSaveMessage(result.error || "关联失败");
    }
  }, [linkInput, onLinkAlert]);

  const handleUnlink = useCallback(
    async (alertId: string) => {
      const result = await onUnlinkAlert(alertId);
      if (!result.ok) {
        setSaveMessage(result.error || "移出失败");
      }
    },
    [onUnlinkAlert]
  );

  const handleCopilot = useCallback(() => {
    const summary = buildCopilotPrompt(detail);
    // 写入 sessionStorage,让 CopilotSection 读取
    try {
      window.sessionStorage.setItem("incident_copilot_prompt", summary);
      window.sessionStorage.setItem(
        "incident_copilot_meta",
        JSON.stringify({
          incident_id: detail.incident.incident_id,
          title: detail.incident.title,
        })
      );
    } catch {
      // ignore sessionStorage 失败
    }
    // 触发自定义事件,dashboard-client 可监听
    window.dispatchEvent(
      new CustomEvent("incident:copilot", {
        detail: { prompt: summary, incidentId: detail.incident.incident_id },
      })
    );
  }, [detail]);

  const saving = actionState === "saving";

  return (
    <div
      data-testid="incident-detail-panel"
      data-incident-id={detail.incident.incident_id}
      className="border-l border-accent bg-bg-raised flex flex-col"
    >
      <div className="px-5 py-4 border-b border-line flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-accent mb-1">
            {detail.incident.incident_id}
          </div>
          <h2 className="font-display text-xl text-ink break-words">
            {detail.incident.title}
          </h2>
          {detail.incident.summary ? (
            <p className="mt-1 text-xs text-ink-secondary break-words">
              {detail.incident.summary}
            </p>
          ) : null}
        </div>
        <button
          type="button"
          onClick={onRefresh}
          data-testid="incident-detail-refresh"
          className="text-[10px] font-mono uppercase tracking-[0.15em] text-accent hover:text-accent-hover inline-flex items-center gap-1"
        >
          <RefreshCw className="w-3 h-3" />
          刷新
        </button>
      </div>

      {/* 字段编辑区 */}
      <div className="px-5 py-4 border-b border-line space-y-3">
        {/* 状态 */}
        <div>
          <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary mb-1.5">
            状态
          </div>
          <div
            role="radiogroup"
            aria-label="事件状态"
            className="flex flex-wrap gap-1"
          >
            {INCIDENT_STATUS_OPTIONS.map((option) => {
              const isActive = status === option.value;
              const activeTone: Record<typeof option.tone, string> = {
                danger: "bg-danger-soft text-danger border-danger",
                warning: "bg-warning-soft text-warning border-warning",
                info: "bg-info-soft text-info border-info",
                success: "bg-success-soft text-success border-success",
                default: "bg-accent-soft text-accent border-accent",
              };
              return (
                <button
                  key={option.value}
                  type="button"
                  role="radio"
                  aria-checked={isActive}
                  data-testid={`incident-status-${option.value}`}
                  onClick={() => setStatus(option.value)}
                  className={`px-2 py-1 text-[11px] font-mono uppercase tracking-[0.1em] border transition-colors ${
                    isActive
                      ? activeTone[option.tone]
                      : "border-line text-ink-tertiary hover:text-ink hover:border-ink-tertiary"
                  }`}
                >
                  {option.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* 严重度 */}
        <div>
          <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary mb-1.5">
            严重度
          </div>
          <div
            role="radiogroup"
            aria-label="事件严重度"
            className="flex flex-wrap gap-1"
          >
            {INCIDENT_SEVERITY_OPTIONS.map((option) => {
              const isActive = severity === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  role="radio"
                  aria-checked={isActive}
                  data-testid={`incident-severity-${option.value}`}
                  onClick={() => setSeverity(option.value)}
                  className={`px-2 py-1 text-[11px] font-mono uppercase tracking-[0.1em] border transition-colors ${
                    isActive
                      ? "bg-accent-soft text-accent border-accent"
                      : "border-line text-ink-tertiary hover:text-ink hover:border-ink-tertiary"
                  }`}
                >
                  {option.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* 标题 + 摘要 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary mb-1.5">
              标题（{title.length}/{TITLE_MAX_LENGTH}）
            </label>
            <input
              data-testid="incident-title-input"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value.slice(0, TITLE_MAX_LENGTH))}
              className="w-full bg-transparent text-ink text-sm py-1.5 px-0 border-0 border-b border-line focus:outline-none focus:border-accent transition-colors"
            />
          </div>
          <div>
            <label className="block text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary mb-1.5">
              摘要（{summary.length}/{SUMMARY_MAX_LENGTH}）
            </label>
            <textarea
              data-testid="incident-summary-input"
              value={summary}
              onChange={(e) =>
                setSummary(e.target.value.slice(0, SUMMARY_MAX_LENGTH))
              }
              rows={2}
              className="w-full bg-transparent text-ink text-xs leading-relaxed py-1.5 px-0 border-0 border-b border-line focus:outline-none focus:border-accent transition-colors resize-y min-h-[40px]"
            />
          </div>
        </div>

        {/* 处置备注 */}
        <div>
          <label className="block text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary mb-1.5">
            处置备注（{note.length}/{NOTE_MAX_LENGTH}）
          </label>
          <textarea
            data-testid="incident-note-input"
            value={note}
            onChange={(e) =>
              setNote(e.target.value.slice(0, NOTE_MAX_LENGTH))
            }
            rows={2}
            placeholder="例如:已加入同源 IP 监控,WAF 持续拦截,待后续人工复盘"
            className="w-full bg-transparent text-ink text-xs leading-relaxed py-1.5 px-0 border-0 border-b border-line focus:outline-none focus:border-accent transition-colors resize-y min-h-[40px] placeholder:text-ink-tertiary"
          />
        </div>

        {/* 错误 / 成功提示 + 保存按钮 */}
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="text-[10px] font-mono text-ink-tertiary">
            {saveMessage ? saveMessage : error ? `错误: ${error}` : ""}
          </div>
          <button
            type="button"
            data-testid="incident-save"
            onClick={() => void handleSave()}
            disabled={!dirty || saving}
            className={`px-3 py-1.5 text-[10px] font-mono uppercase tracking-[0.15em] border transition-colors inline-flex items-center gap-1.5 ${
              dirty
                ? "border-accent text-accent hover:bg-accent-soft"
                : "border-line text-ink-tertiary"
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {saving ? (
              <>
                <Loader2 className="w-3 h-3 animate-spin" />
                保存中
              </>
            ) : (
              <>
                <Check className="w-3 h-3" />
                保存处置
              </>
            )}
          </button>
        </div>
      </div>

      {/* 关联告警 */}
      <div className="px-5 py-4 border-b border-line">
        <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary mb-2">
          关联告警
        </div>
        <IncidentLinkedAlerts
          alerts={detail.linked_alerts}
          onUnlink={handleUnlink}
        />
        {/* 加入告警 */}
        <div className="mt-3 flex items-center gap-2">
          <input
            data-testid="incident-link-input"
            type="text"
            value={linkInput}
            onChange={(e) => setLinkInput(e.target.value)}
            placeholder="输入 alert_id 加入案件"
            className="flex-1 bg-transparent text-ink text-xs py-1.5 px-0 border-0 border-b border-line focus:outline-none focus:border-accent transition-colors placeholder:text-ink-tertiary"
          />
          <button
            type="button"
            data-testid="incident-link-submit"
            onClick={() => void handleLink()}
            disabled={!linkInput.trim() || saving}
            className="px-2.5 py-1 text-[10px] font-mono uppercase tracking-[0.15em] border border-accent text-accent hover:bg-accent-soft transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            加入
          </button>
        </div>
      </div>

      {/* 事件时间线 */}
      <div className="px-5 py-4">
        <div className="flex items-center justify-between gap-2 mb-2">
          <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary">
            事件时间线
          </div>
          <button
            type="button"
            data-testid="incident-copilot"
            onClick={handleCopilot}
            className="text-[10px] font-mono uppercase tracking-[0.15em] text-accent hover:text-accent-hover inline-flex items-center gap-1"
          >
            <Sparkles className="w-3 h-3" />
            用 AI 分析案件
          </button>
        </div>
        <IncidentTimeline events={detail.events} />
      </div>
    </div>
  );
}

/**
 * 把 incident 摘要拼成 Copilot 用户消息(前端拼接,不走后端 incident-aware contract)。
 *
 * 包含:
 * - incident id / title / severity / status / 关联告警数 / 最多 5 条告警摘要
 * - 明确要求输出:风险、证据、影响、下一步处置
 *
 * 不得包含:secret / system prompt / stack trace / 完整 payload。
 */
function buildCopilotPrompt(detail: IncidentDetailResponse): string {
  const lines: string[] = [];
  const inc = detail.incident;
  lines.push(`请分析以下安全案件 (incident_id=${inc.incident_id}):`);
  lines.push(`- 标题: ${inc.title}`);
  lines.push(`- 严重度: ${inc.severity}`);
  lines.push(`- 状态: ${inc.status}`);
  lines.push(`- 关联告警数: ${inc.alert_count}`);
  if (inc.summary) {
    lines.push(`- 摘要: ${inc.summary}`);
  }
  if (inc.created_from_alert_id) {
    lines.push(`- 首条告警 id: ${inc.created_from_alert_id}`);
  }
  lines.push("");
  lines.push("关联告警(最多 5 条):");
  const top = detail.linked_alerts.slice(0, 5);
  if (top.length === 0) {
    lines.push("- (无)");
  } else {
    for (const a of top) {
      const src = a.raw_alert?.source_ip ?? "?";
      const dst = a.raw_alert?.destination_ip ?? "?";
      const risk = a.llm_analysis?.risk_level ?? "unknown";
      const summary = (a.llm_analysis?.summary ?? "").toString().slice(0, 120);
      lines.push(`- ${a.alert_id} ${src} → ${dst} (risk=${risk}) ${summary}`);
    }
  }
  lines.push("");
  lines.push("请按以下结构输出:");
  lines.push("1. 风险: 简要说明该案件的潜在威胁等级和影响面");
  lines.push("2. 证据: 列出支撑判断的关键告警和模式");
  lines.push("3. 影响: 当前/潜在业务影响范围");
  lines.push("4. 下一步处置: 给出 3-5 条可立即执行的建议动作");
  return lines.join("\n");
}

export { buildCopilotPrompt };
