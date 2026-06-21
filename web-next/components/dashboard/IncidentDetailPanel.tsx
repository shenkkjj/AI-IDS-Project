"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Check,
  Clipboard,
  ClipboardCheck,
  Download,
  FileSearch,
  Loader2,
  Sparkles,
  RefreshCw,
  Unlink,
} from "lucide-react";
import {
  INCIDENT_SEVERITY_OPTIONS,
  INCIDENT_STATUS_OPTIONS,
  type IncidentDetailResponse,
  type IncidentEvent,
  type IncidentReportMeta,
  type IncidentSeverity,
  type IncidentStatus,
  type IncidentLinkedAlert,
} from "@/types/incident";
import IncidentTimeline from "./IncidentTimeline";
import IncidentLinkedAlerts from "./IncidentLinkedAlerts";
import IncidentReportPreview from "./IncidentReportPreview";
import IncidentEvidencePackChecklist from "./IncidentEvidencePackChecklist";
import StatusView from "./StatusView";

const NOTE_MAX_LENGTH = 1000;
const SUMMARY_MAX_LENGTH = 1000;
const TITLE_MAX_LENGTH = 120;
// M3-05: "用 AI 分析案件" 短意图;不再把 incident 详情拼进 message。
// 后端会通过 incident_id 走 owner 隔离并构造受控 context_block。
const INCIDENT_COPILOT_SHORT_PROMPT =
  "请分析当前安全案件,给出风险、证据、影响和下一步处置。";

const PREVIEW_HEADINGS = (
  "# 案件证据报告\n## 1. 案件摘要\n## 2. 关联告警\n## 3. 案件时间线\n## 4. 安全与脱敏说明"
);

function createReportPreviewMarkdown(markdown: string): string {
  const safeMarkdown = markdown.slice(0, 20000);
  const lines = safeMarkdown.split(/\r?\n/);
  const payloadIndex = lines.findIndex((line) => line.includes("payload_preview"));
  const payloadWindow =
    payloadIndex >= 0
      ? lines
          .slice(Math.max(0, payloadIndex - 8), Math.min(lines.length, payloadIndex + 18))
          .join("\n")
      : safeMarkdown.slice(0, 1400);
  const securityIndex = lines.findIndex((line) => line.includes("安全与脱敏说明"));
  const securityWindow =
    securityIndex >= 0
      ? lines.slice(securityIndex, Math.min(lines.length, securityIndex + 8)).join("\n")
      : "## 4. 安全与脱敏说明\n报告已脱敏并按后端策略截断。";
  return [PREVIEW_HEADINGS, payloadWindow, securityWindow]
    .filter(Boolean)
    .join("\n\n")
    .slice(0, 1800);
}

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
  /**
   * M3-07: 拉取案件证据报告(Markdown 字符串 + filename),由父组件注入。
   * 不消费 payload / note 全文,只接后端脱敏后的 markdown。
   */
  onLoadReport: (incidentId: string) => Promise<{
    ok: boolean;
    incidentId?: string;
    filename?: string;
    markdown?: string;
    meta?: IncidentReportMeta;
    error?: string;
  }>;
}

export default function IncidentDetailPanel({
  detail,
  actionState,
  error,
  onUpdate,
  onLinkAlert,
  onUnlinkAlert,
  onRefresh,
  onLoadReport,
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
    // M3-05: 不再把 incident 详情拼进 message;后端通过 incident_id 构造受控
    // context_block(走 server.services.copilot_service._load_incident_context),
    // 前端只发短意图 + incidentId。后端负责 owner 隔离 / 脱敏 / Guardrails / SSE 净化。
    window.dispatchEvent(
      new CustomEvent("incident:copilot", {
        detail: {
          prompt: INCIDENT_COPILOT_SHORT_PROMPT,
          incidentId: detail.incident.incident_id,
        },
      })
    );
  }, [detail.incident.incident_id]);

  // M3-07: 案件证据报告导出(复制 / 下载)。
  // - 不保存 markdown 到 React 长期 state;按按钮请求即可,避免大字符串滞留。
  // - 不在前端拼报告 / 不读 payload / note 全文,完全消费后端脱敏后的 markdown。
  // - navigator.clipboard 不可用时复制按钮失败但不崩溃。
  type ReportAction = "idle" | "loading" | "copied" | "downloaded" | "error";
  const [reportAction, setReportAction] = useState<ReportAction>("idle");
  const [reportMessage, setReportMessage] = useState<string | null>(null);
  const [reportPreviewLoading, setReportPreviewLoading] = useState(false);
  const [reportPreviewError, setReportPreviewError] = useState<string | null>(null);
  const [reportPreview, setReportPreview] = useState<{
    filename: string;
    meta: IncidentReportMeta;
    previewMarkdown: string;
    loadedAt: number;
  } | null>(null);

  useEffect(() => {
    if (reportAction === "copied" || reportAction === "downloaded") {
      const timer = window.setTimeout(() => {
        setReportAction("idle");
        setReportMessage(null);
      }, 2400);
      return () => window.clearTimeout(timer);
    }
    return undefined;
  }, [reportAction]);

  useEffect(() => {
    setReportPreview(null);
    setReportPreviewError(null);
    setReportPreviewLoading(false);
  }, [detail.incident.incident_id]);

  useEffect(() => {
    if (!reportPreview) return undefined;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setReportPreview(null);
        setReportPreviewError(null);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [reportPreview]);

  const handlePreviewReport = useCallback(async () => {
    if (reportPreviewLoading || reportAction === "loading") return;
    setReportPreviewLoading(true);
    setReportPreviewError(null);
    const result = await onLoadReport(detail.incident.incident_id);
    if (!result.ok || !result.filename || !result.markdown || !result.meta) {
      setReportPreview(null);
      setReportPreviewError("报告预览失败");
      setReportPreviewLoading(false);
      return;
    }
    setReportPreview({
      filename: result.filename,
      meta: result.meta,
      previewMarkdown: createReportPreviewMarkdown(result.markdown),
      loadedAt: Date.now(),
    });
    setReportPreviewLoading(false);
  }, [
    onLoadReport,
    detail.incident.incident_id,
    reportAction,
    reportPreviewLoading,
  ]);

  const handleReport = useCallback(
    async (action: "copy" | "download") => {
      if (reportAction === "loading") return;
      setReportAction("loading");
      setReportMessage("生成中");
      const result = await onLoadReport(detail.incident.incident_id);
      if (!result.ok || !result.markdown || !result.filename) {
        setReportAction("error");
        setReportMessage(result.error || "报告生成失败");
        return;
      }
      if (action === "copy") {
        if (
          typeof navigator !== "undefined" &&
          navigator.clipboard &&
          typeof navigator.clipboard.writeText === "function"
        ) {
          try {
            await navigator.clipboard.writeText(result.markdown);
            setReportAction("copied");
            setReportMessage("已复制");
            return;
          } catch {
            // 落到下面统一错误处理
          }
        }
        setReportAction("error");
        setReportMessage("复制失败");
        return;
      }
      // download:Blob + URL.createObjectURL
      try {
        const blob = new Blob([result.markdown], {
          type: "text/markdown;charset=utf-8",
        });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = result.filename;
        anchor.rel = "noopener";
        document.body.appendChild(anchor);
        anchor.click();
        document.body.removeChild(anchor);
        URL.revokeObjectURL(url);
        setReportAction("downloaded");
        setReportMessage("已下载");
      } catch {
        setReportAction("error");
        setReportMessage("下载失败");
      }
    },
    [onLoadReport, detail.incident.incident_id, reportAction]
  );

  const saving = actionState === "saving";
  const reportLoading = reportAction === "loading";

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

      <IncidentEvidencePackChecklist
        incident={detail.incident}
        linkedAlerts={detail.linked_alerts}
        events={detail.events}
        onLoadReport={onLoadReport}
      />

      {/* 事件时间线 */}
      <div className="px-5 py-4">
        <div className="flex items-center justify-between gap-2 mb-2 flex-wrap">
          <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary">
            事件时间线
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            {/* M3-07: 报告导出状态文案(短小,可重试) */}
            <span
              data-testid="incident-report-status"
              className="text-[10px] font-mono text-ink-tertiary"
              role="status"
              aria-live="polite"
            >
              {reportMessage || ""}
            </span>
            <button
              type="button"
              data-testid="incident-preview-report"
              onClick={() => void handlePreviewReport()}
              disabled={reportPreviewLoading || reportLoading}
              className="text-[10px] font-mono uppercase tracking-[0.15em] text-accent hover:text-accent-hover inline-flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
              aria-label="预览案件报告"
            >
              {reportPreviewLoading ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <FileSearch className="w-3 h-3" />
              )}
              {reportPreviewLoading ? "生成中" : "预览报告"}
            </button>
            <button
              type="button"
              data-testid="incident-copy-report"
              onClick={() => void handleReport("copy")}
              disabled={reportLoading}
              className="text-[10px] font-mono uppercase tracking-[0.15em] text-accent hover:text-accent-hover inline-flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
              aria-label="复制案件报告"
            >
              {reportLoading ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : reportAction === "copied" ? (
                <ClipboardCheck className="w-3 h-3" />
              ) : (
                <Clipboard className="w-3 h-3" />
              )}
              复制报告
            </button>
            <button
              type="button"
              data-testid="incident-download-report"
              onClick={() => void handleReport("download")}
              disabled={reportLoading}
              className="text-[10px] font-mono uppercase tracking-[0.15em] text-accent hover:text-accent-hover inline-flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
              aria-label="下载案件报告"
            >
              {reportLoading ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <Download className="w-3 h-3" />
              )}
              下载报告
            </button>
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
        </div>
        {reportPreviewError ? (
          <div
            data-testid="incident-report-preview-error"
            className="mb-3 border border-danger text-danger bg-danger-soft px-3 py-2 text-[11px] font-mono"
          >
            {reportPreviewError}
          </div>
        ) : null}
        {reportPreview ? (
          <IncidentReportPreview
            filename={reportPreview.filename}
            meta={reportPreview.meta}
            previewMarkdown={reportPreview.previewMarkdown}
            loadedAt={reportPreview.loadedAt}
            onClose={() => {
              setReportPreview(null);
              setReportPreviewError(null);
            }}
          />
        ) : null}
        <IncidentTimeline events={detail.events} />
      </div>
    </div>
  );
}

/**
 * M3-05: 案件 Copilot 入口。
 *
 * 不再把 incident 详情拼进 message;后端通过 incident_id 走
 * ``server.services.copilot_service._load_incident_context`` 构造受控
 * context_block。前端只发短意图 + incidentId,后端负责 owner 隔离 / 脱敏 /
 * Guardrails / SSE 净化。详见 ``docs/agent/M3_05_INCIDENT_AWARE_COPILOT_CONTRACT_TASK.md``。
 */
