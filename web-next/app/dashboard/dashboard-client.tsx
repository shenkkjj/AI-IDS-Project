"use client";

import { useMemo, useState, useEffect } from "react";
import dynamic from "next/dynamic";
import { motion, AnimatePresence } from "framer-motion";
import { RefreshCw } from "lucide-react";

import StatsCards from "@/components/dashboard/StatsCards";
import AttackLogTable from "@/components/dashboard/AttackLogTable";
import HackerTerminal from "@/components/dashboard/HackerTerminal";
import AlertSection from "@/components/dashboard/AlertSection";
import AlertDetailPanel from "@/components/dashboard/AlertDetailPanel";
import CopilotSection from "@/components/dashboard/CopilotSection";
import SecurityTimelinePanel from "@/components/dashboard/SecurityTimelinePanel";
import SystemStatusBar from "@/components/dashboard/SystemStatusBar";
import SystemStatusSection from "@/components/dashboard/SystemStatusSection";
import DemoFlowControls from "@/components/dashboard/DemoFlowControls";
import BriefingSection from "@/components/dashboard/BriefingSection";
import { Button } from "@/components/ui/button";

// Heavy components are code-split. Recharts (~45KB gzip) only loads when
// the user navigates to overview/monitor routes; the LLM streaming panel
// and its streaming client SDK only load when copilot is rendered.
const AttackTrendChart = dynamic(
  () => import("@/components/dashboard/AttackTrendChart"),
  { ssr: false, loading: () => <div className="h-full bg-bg-raised/40 animate-pulse" /> }
);
const SourcePieChart = dynamic(
  () => import("@/components/dashboard/SourcePieChart"),
  { ssr: false, loading: () => <div className="h-full bg-bg-raised/40 animate-pulse" /> }
);

import { useAlerts } from "@/hooks/useAlerts";
import { useConfig } from "@/hooks/useConfig";
import { useCopilot } from "@/hooks/useCopilot";
import { useTerminal } from "@/hooks/useTerminal";
import { useReport } from "@/hooks/useReport";
import { useSiteHealth } from "@/hooks/useSiteHealth";
import { useSecurityTimeline } from "@/hooks/useSecurityTimeline";
import { useThreatConfirm } from "@/hooks/useThreatConfirm";
import { routeDescription } from "@/utils/routeUtils";
import { formatLoadError } from "@/utils/alertUtils";
import { deriveAlertDetail } from "@/utils/alertBriefingUtils";

import type { RouteKey } from "@/types/route";

const NAV_ITEMS: { key: RouteKey; label: string; index: string }[] = [
  { key: "overview", label: "概览", index: "01" },
  { key: "monitor", label: "监测", index: "02" },
  { key: "waf", label: "WAF 管理", index: "03" },
  { key: "ai", label: "AI 配置", index: "04" },
  { key: "report", label: "安全日报", index: "05" },
];

const PROVIDERS = ["custom"] as const;

type DashboardClientProps = {
  userEmail: string;
};

/* ---------- 局部 UI 原子 ---------- */

function SectionHeading({
  index,
  title,
  description,
  action,
}: {
  index: string;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-baseline justify-between mb-6 pb-3 border-b border-line">
      <div>
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-accent mb-1.5">
          {index}
        </div>
        <h2 className="font-display text-2xl text-ink tracking-tight">{title}</h2>
        {description ? (
          <p className="text-xs text-ink-secondary mt-1">{description}</p>
        ) : null}
      </div>
      {action}
    </div>
  );
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <label className="block text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary mb-1.5">
      {children}
    </label>
  );
}

function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className="w-full bg-transparent text-ink text-sm py-2 px-0 border-0 border-b border-line focus:outline-none focus:border-accent transition-colors placeholder:text-ink-tertiary"
    />
  );
}

function SelectInput(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className="w-full bg-transparent text-ink text-sm py-2 px-0 border-0 border-b border-line focus:outline-none focus:border-accent transition-colors cursor-pointer"
    />
  );
}

/* ---------- 主组件 ---------- */

export default function DashboardClient({ userEmail }: DashboardClientProps) {
  const [route, setRoute] = useState<RouteKey>("overview");
  // M3-03: 自增触发 AlertTriageHistory 重新拉取(保存成功 / 切换告警)
  const [triageHistoryRefreshKey, setTriageHistoryRefreshKey] = useState(0);

  const alertsCtx = useAlerts();
  const configCtx = useConfig();
  const copilotCtx = useCopilot(alertsCtx.selected);
  const terminalCtx = useTerminal(alertsCtx.alerts);
  const reportCtx = useReport(alertsCtx.alerts);
  const siteHealthCtx = useSiteHealth(configCtx.setStatus);
  const securityTimelineCtx = useSecurityTimeline();
  const threatCtx = useThreatConfirm(
    alertsCtx.selected,
    configCtx.config,
    configCtx.setConfig,
    configCtx.setStatus,
    terminalCtx.appendLogs,
    configCtx.refreshConfig
  );

  // 切换告警时让 history 重新拉取
  useEffect(() => {
    setTriageHistoryRefreshKey((prev) => prev + 1);
  }, [alertsCtx.selected?.id]);

  useEffect(() => {
    configCtx.loadConfig().catch((error: unknown) => {
      const message = error instanceof Error ? error.message : String(error);
      configCtx.setStatus(formatLoadError(message));
    });
  }, []);

  const counters = useMemo(() => {
    return {
      alertsTotal: alertsCtx.alerts.length,
      highRiskTotal: alertsCtx.alerts.filter((a) => a.risk === "high" || a.risk === "critical").length,
      blockedTotal: alertsCtx.alerts.filter((a) => a.blocked).length,
      siteHealthText: siteHealthCtx.healthUi.text,
    };
  }, [alertsCtx.alerts, siteHealthCtx.healthUi.text]);

  const selectedLogId = alertsCtx.selected?.id;
  const isOverviewRoute = route === "overview";
  const isMonitorRoute = route === "monitor";
  const isWafRoute = route === "waf";
  const isAiRoute = route === "ai";
  const isReportRoute = route === "report";

  const currentRoute = NAV_ITEMS.find((item) => item.key === route);

  const alertDetail = useMemo(
    () => deriveAlertDetail(alertsCtx.selected),
    [alertsCtx.selected]
  );

  async function handleTriggerDemoAttack() {
    try {
      const result = await alertsCtx.triggerDemoAttack("sql_injection");
      const alert = result.alert;
      terminalCtx.appendLogs(
        [
          `Demo 攻击已触发: ${alert.source} -> ${alert.target}`,
          `告警 ${alert.alertId || alert.id} 已进入 Dashboard，可在 AI 助手中分析。`,
          result.copilot?.ready
            ? `Copilot 已就绪: ${result.copilot.provider || "custom"} ${result.copilot.model || ""}`.trim()
            : `Copilot 降级态: ${result.copilot?.next_action || "请先配置 API Key 与 Base URL。"}`,
        ],
        "success"
      );
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      terminalCtx.appendLogs([`Demo 攻击触发失败: ${message}`], "error");
      configCtx.setStatus(formatLoadError(message));
    }
  }

  function handleExportCsv() {
    const link = document.createElement("a");
    link.href = "/api/backend/export/alerts?limit=1000";
    link.download = "alerts.csv";
    link.click();
  }

  function handleRefreshAlerts() {
    alertsCtx.loadAlerts({ showLoading: true }).catch(() => {});
  }

  function handleAnalyzeSelectedAlert() {
    if (!alertsCtx.selected) return;
    void copilotCtx.sendMessage(
      "请分析当前选中的安全告警，给出风险等级、证据、影响范围和三条立即处置建议。"
    );
  }

  const handleTriageSubmit = async (input: {
    status: import("@/types/alert").AlertTriageStatus;
    disposition: string | null;
    analyst_note: string | null;
  }): Promise<boolean> => {
    const alertId = alertsCtx.selected?.alertId || alertsCtx.selected?.id;
    if (!alertId) return false;
    const result = await alertsCtx.updateTriage({
      alertId,
      status: input.status,
      disposition: input.disposition,
      analyst_note: input.analyst_note,
    });
    if (!result.ok) {
      configCtx.setStatus(`研判保存失败: ${result.error || "未知错误"}`);
      return false;
    }
    // M3-03: 触发研判历史重新拉取
    setTriageHistoryRefreshKey((prev) => prev + 1);
    configCtx.setStatus("研判已保存");
    return true;
  };

  return (
    <div className="min-h-screen bg-bg text-ink">
      <SystemStatusBar
        userEmail={userEmail}
        wsConnected={alertsCtx.wsConnected}
        route={route}
        onChangeRoute={setRoute}
        statusMessage={configCtx.status}
        routeIndex={currentRoute?.index || "00"}
        routeLabel={currentRoute?.label || ""}
        routeDescription={routeDescription(route)}
        pageFocus={isOverviewRoute ? "ALL SYSTEMS" : "FOCUSED VIEW"}
      />

      <AnimatePresence mode="wait">
        <motion.main
          key={route}
          initial={false}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="max-w-[1320px] mx-auto px-6 sm:px-10 py-10 sm:py-14"
        >
          {/* 统计卡片 */}
          <StatsCards stats={counters} />

          {/* 日/周安全简报 */}
          <div className="mt-14">
            <SectionHeading
              index="§ 00"
              title="日 / 周安全简报"
              description="基于当前告警流自动派生的态势指标。所有数据均来自真实告警记录,严禁伪造。"
            />
            <div className="p-6 bg-bg-raised border-l border-accent rounded-md">
              <BriefingSection alerts={alertsCtx.alerts} />
            </div>
          </div>

          {/* 攻击趋势与分布 */}
          {(isOverviewRoute || isMonitorRoute) && (
            <div className="mt-14">
              <SectionHeading
                index="§ 01"
                title="攻击趋势与分布"
                description="近 24 时段攻击曲线 + 风险级别与来源 TOP 6"
              />
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div className="h-[300px]">
                  <AttackTrendChart alerts={alertsCtx.alerts} />
                </div>
                <div className="h-[300px]">
                  <SourcePieChart alerts={alertsCtx.alerts} />
                </div>
              </div>
            </div>
          )}

          {/* 告警流 + 详情 + AI 助手 */}
          {(isOverviewRoute || isMonitorRoute) && (
            <div className="mt-14">
              <SectionHeading
                index="§ 02"
                title="实时告警、详情与 AI 助手"
                description={`共 ${alertsCtx.alerts.length} 条告警 · ${alertsCtx.wsConnected ? "WebSocket 实时" : "轮询刷新"}`}
              />
              <AlertSection
                loadState={alertsCtx.loadState}
                wsConnected={alertsCtx.wsConnected}
                totalAlerts={alertsCtx.alerts.length}
                totalPages={alertsCtx.totalPages}
                page={alertsCtx.page}
                listSlot={
                  <AttackLogTable
                    logs={alertsCtx.paginatedAlerts}
                    highlightId={selectedLogId}
                    selectedId={selectedLogId}
                    onSelect={alertsCtx.handleSelectLog}
                    newIds={alertsCtx.newAlertIds}
                  />
                }
                detailSlot={
                  <AlertDetailPanel
                    detail={alertDetail}
                    alertId={alertsCtx.selected?.alertId || alertsCtx.selected?.id}
                    onAnalyzeInCopilot={handleAnalyzeSelectedAlert}
                    onTriageSubmit={handleTriageSubmit}
                    offline={!alertsCtx.wsConnected && alertsCtx.loadState === "error"}
                    loadHistory={alertsCtx.loadTriageHistory}
                    historyRefreshKey={triageHistoryRefreshKey}
                    historyLimit={5}
                  />
                }
                onPrevPage={() => alertsCtx.setPage(Math.max(0, alertsCtx.page - 1))}
                onNextPage={() =>
                  alertsCtx.setPage(Math.min(alertsCtx.totalPages - 1, alertsCtx.page + 1))
                }
                onRefresh={handleRefreshAlerts}
                onRetry={() => void alertsCtx.loadAlerts({ showLoading: true })}
                toolbarSlot={
                  <DemoFlowControls
                    demoState={alertsCtx.demoState}
                    demoMessage={alertsCtx.demoMessage}
                    onTriggerDemo={() => void handleTriggerDemoAttack()}
                    onExportCsv={handleExportCsv}
                    onRefreshAlerts={handleRefreshAlerts}
                  />
                }
              />
            </div>
          )}

          {/* 终端 + 日报 */}
          {(isOverviewRoute || isMonitorRoute) && (
            <div className="mt-14">
              <SectionHeading
                index="§ 03"
                title="终端与安全日报"
                description="实时命令输出 + 告警日报"
                action={
                  <button
                    onClick={() => void reportCtx.refreshWithTypewriter()}
                    className="text-[10px] font-mono uppercase tracking-[0.15em] text-accent hover:text-accent-hover transition-colors flex items-center gap-1.5"
                    type="button"
                  >
                    <RefreshCw className={`w-3 h-3 ${reportCtx.typing ? "animate-spin" : ""}`} />
                    刷新日报
                  </button>
                }
              />
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div className="min-h-[320px]">
                  <HackerTerminal lines={terminalCtx.logs} onCommand={terminalCtx.executeCommand} />
                </div>
                <div className="min-h-[320px] p-5 bg-bg-raised border-l border-accent">
                  <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-accent mb-3">
                    日报 · 摘要
                  </div>
                  <pre className="whitespace-pre-wrap text-xs leading-6 text-ink-secondary font-mono overflow-y-auto max-h-[260px]">
                    {reportCtx.markdown}
                  </pre>
                </div>
              </div>
            </div>
          )}

          {/* 安全运营时间线 */}
          {(isOverviewRoute || isMonitorRoute) && (
            <div className="mt-14">
              <SectionHeading
                index="§ 03.5"
                title="安全运营时间线"
                description="Demo 攻击 / Copilot / 护栏 / 认证 / 配置摘要"
              />
              <div className="min-h-[280px]">
                <SecurityTimelinePanel
                  items={securityTimelineCtx.items}
                  loadState={securityTimelineCtx.loadState}
                  degraded={securityTimelineCtx.degraded}
                  limit={securityTimelineCtx.limit}
                  offline={!alertsCtx.wsConnected && securityTimelineCtx.loadState === "error"}
                  onRefresh={() => void securityTimelineCtx.refresh()}
                />
              </div>
            </div>
          )}

          {/* 站点 + 代理 + 威胁确认 */}
          {(isOverviewRoute || isWafRoute) && (
            <div className="mt-14">
              <SectionHeading
                index="§ 04"
                title="站点监测与威胁确认"
                description="配置受保护站点、测试 WAF 链路、确认告警入库"
              />
              <SystemStatusSection
                siteTargetInput={siteHealthCtx.targetInput}
                onChangeTargetInput={siteHealthCtx.setTargetInput}
                onSaveTarget={() => void siteHealthCtx.saveTarget()}
                targetSaving={siteHealthCtx.targetSaving}
                siteState={{
                  text: siteHealthCtx.healthUi.text,
                  tone: siteHealthCtx.healthUi.tone,
                  url: siteHealthCtx.health?.url,
                }}
                proxyPathInput={siteHealthCtx.proxyPathInput}
                onChangeProxyPath={siteHealthCtx.setProxyPathInput}
                onTestProxy={() => void siteHealthCtx.testProxy()}
                proxyTesting={siteHealthCtx.proxyTesting}
                threat={{
                  status: threatCtx.status,
                  statusTone: threatCtx.statusTone,
                  confirming: threatCtx.confirming,
                  voiceEnabled: Boolean(configCtx.config?.alert_voice_enabled),
                }}
                canConfirmThreat={Boolean(alertsCtx.selected?.alertId)}
                onConfirmThreat={() => void threatCtx.confirmThreat()}
                onToggleVoiceAlert={() => void threatCtx.toggleVoiceAlert()}
              />
            </div>
          )}

          {/* AI 助手统一显示区（概览/AI） */}
          {(isOverviewRoute || isAiRoute) && (
            <div className="mt-14">
              <SectionHeading
                index="§ 04.5"
                title="AI 助手上下文"
                description="Copilot 当前上下文、降级态与会话摘要"
              />
              <div className="min-h-[480px]">
                <CopilotSection
                  messages={copilotCtx.messages}
                  draft={copilotCtx.input}
                  sending={copilotCtx.sending}
                  contextLabel={copilotCtx.hint}
                  degraded={false}
                  offline={!alertsCtx.wsConnected}
                  onDraftChange={copilotCtx.setInput}
                  onSend={() => void copilotCtx.sendMessage(copilotCtx.input)}
                  onAnalyzeAlert={
                    alertsCtx.selected ? handleAnalyzeSelectedAlert : undefined
                  }
                />
              </div>
            </div>
          )}

          {/* AI 路由配置 + 当前会话（概览/AI） */}
          {(isOverviewRoute || isAiRoute) && (
            <div className="mt-14">
              <SectionHeading
                index="§ 05"
                title="AI 路由配置"
                description="自定义模型、API 密钥、会话上下文"
              />
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div className="space-y-5">
                  <div>
                    <FieldLabel>Provider</FieldLabel>
                    <SelectInput
                      value={configCtx.draft.ai_provider}
                      onChange={(event) =>
                        configCtx.setDraft((prev) => ({ ...prev, ai_provider: event.target.value }))
                      }
                    >
                      {PROVIDERS.map((provider) => (
                        <option key={provider} value={provider}>
                          {provider}
                        </option>
                      ))}
                    </SelectInput>
                  </div>
                  <div>
                    <FieldLabel>Model</FieldLabel>
                    <TextInput
                      autoComplete="off"
                      value={configCtx.draft.model}
                      onChange={(event) =>
                        configCtx.setDraft((prev) => ({ ...prev, model: event.target.value }))
                      }
                      placeholder="gpt-4 / claude-3 ..."
                    />
                  </div>
                  <div>
                    <FieldLabel>Base URL</FieldLabel>
                    <TextInput
                      autoComplete="off"
                      value={configCtx.draft.base_url}
                      onChange={(event) =>
                        configCtx.setDraft((prev) => ({ ...prev, base_url: event.target.value }))
                      }
                      placeholder="https://api.openai.com/v1"
                    />
                  </div>
                  <div>
                    <FieldLabel>API Key</FieldLabel>
                    <TextInput
                      type="password"
                      autoComplete="new-password"
                      value={configCtx.draft.api_key}
                      onChange={(event) =>
                        configCtx.setDraft((prev) => ({ ...prev, api_key: event.target.value }))
                      }
                      placeholder={
                        configCtx.config?.has_api_key
                          ? "已配置,留空表示不修改"
                          : "输入 API Key"
                      }
                    />
                    <div className="text-[10px] font-mono text-ink-tertiary mt-1.5">
                      当前:
                      {configCtx.config?.has_api_key
                        ? configCtx.config.api_key_masked
                        : "未配置"}
                    </div>
                  </div>
                  <div className="flex gap-2 flex-wrap pt-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void configCtx.saveConfig()}
                      disabled={
                        configCtx.saving || configCtx.testing || configCtx.refreshing
                      }
                    >
                      {configCtx.saving ? "保存中..." : "保存"}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void configCtx.testConfig()}
                      disabled={
                        configCtx.saving || configCtx.testing || configCtx.refreshing
                      }
                    >
                      {configCtx.testing ? "测试中..." : "测试路由"}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void configCtx.refreshConfig()}
                      disabled={
                        configCtx.saving || configCtx.testing || configCtx.refreshing
                      }
                    >
                      {configCtx.refreshing ? "同步中..." : "重新同步"}
                    </Button>
                  </div>
                </div>

                <div className="space-y-5">
                  <FieldLabel>当前会话</FieldLabel>
                  <div className="divide-y divide-line-subtle">
                    <SessionRow label="用户" value={userEmail || "unknown"} />
                    <SessionRow label="上下文" value={copilotCtx.hint} />
                    <SessionRow
                      label="WS 连接"
                      value={alertsCtx.wsConnected ? "已连接" : "已断开"}
                      tone={alertsCtx.wsConnected ? "ok" : "error"}
                    />
                    <SessionRow
                      label="告警总数"
                      value={String(alertsCtx.alerts.length)}
                      mono
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Webhook + 通知状态（概览/AI） */}
          {(isOverviewRoute || isAiRoute) && (
            <div className="mt-14">
              <SectionHeading
                index="§ 06"
                title="Webhook 通知与渠道状态"
                description="高危告警触发时自动推送到外部通道"
              />
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div className="space-y-5">
                  <div>
                    <FieldLabel>类型</FieldLabel>
                    <SelectInput
                      value={configCtx.draft.webhook_type}
                      onChange={(event) =>
                        configCtx.setDraft((prev) => ({
                          ...prev,
                          webhook_type: event.target.value,
                        }))
                      }
                      disabled={configCtx.saving || configCtx.refreshing}
                    >
                      <option value="generic">通用 Webhook (JSON)</option>
                      <option value="dingtalk">钉钉机器人 (Markdown)</option>
                      <option value="feishu">飞书机器人 (Interactive Card)</option>
                    </SelectInput>
                  </div>
                  <div>
                    <FieldLabel>URL</FieldLabel>
                    <TextInput
                      autoComplete="off"
                      value={configCtx.draft.webhook_url}
                      onChange={(event) =>
                        configCtx.setDraft((prev) => ({
                          ...prev,
                          webhook_url: event.target.value,
                        }))
                      }
                      placeholder="https://oapi.dingtalk.com/robot/ send?access_token=…"
                      disabled={configCtx.saving || configCtx.refreshing}
                    />
                    <div className="text-[10px] font-mono text-ink-tertiary mt-1.5 break-all">
                      当前:
                      {configCtx.config?.webhook_url
                        ? `${configCtx.config.webhook_type} · ${configCtx.config.webhook_url.slice(0, 60)}`
                        : "未配置"}
                    </div>
                  </div>
                  <div className="flex gap-2 flex-wrap pt-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void configCtx.saveConfig()}
                      disabled={
                        configCtx.saving ||
                        configCtx.refreshing ||
                        configCtx.webhookTesting
                      }
                    >
                      {configCtx.saving ? "保存中..." : "保存"}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void configCtx.testWebhook()}
                      disabled={
                        configCtx.saving ||
                        configCtx.refreshing ||
                        configCtx.webhookTesting
                      }
                    >
                      {configCtx.webhookTesting ? "测试中..." : "发送测试"}
                    </Button>
                  </div>
                </div>

                <div className="space-y-5">
                  <FieldLabel>通知渠道状态</FieldLabel>
                  <div className="divide-y divide-line-subtle">
                    <ChannelRow
                      label="邮件告警"
                      enabled={Boolean(configCtx.config?.alert_email_enabled)}
                    />
                    <ChannelRow
                      label="语音预警"
                      enabled={Boolean(configCtx.config?.alert_voice_enabled)}
                    />
                    <ChannelRow
                      label="Webhook"
                      enabled={Boolean(configCtx.config?.webhook_url)}
                      customText={
                        configCtx.config?.webhook_url ? "已配置" : "未配置"
                      }
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* 日报摘要（概览/报告） */}
          {(isOverviewRoute || isReportRoute) && (
            <div className="mt-14">
              <SectionHeading
                index="§ 07"
                title="日报摘要"
                description="当前告警态势汇总"
              />
              <div className="p-6 bg-bg-raised border-l border-accent rounded-md">
                <pre className="whitespace-pre-wrap text-xs leading-6 text-ink-secondary font-mono overflow-y-auto max-h-[480px]">
                  {reportCtx.markdown}
                </pre>
              </div>
            </div>
          )}
        </motion.main>
      </AnimatePresence>

      {/* 底部 */}
      <footer className="border-t border-line mt-20">
        <div className="max-w-[1320px] mx-auto px-6 sm:px-10 py-6 flex items-center justify-between text-[10px] font-mono uppercase tracking-[0.2em] text-ink-tertiary">
          <span>SECURE · ENCRYPTED · LOGGED</span>
          <span>AI-CYBERSENTINEL · v2</span>
        </div>
      </footer>
    </div>
  );
}

/* ---------- 子组件 ---------- */

function SessionRow({
  label,
  value,
  tone,
  mono,
}: {
  label: string;
  value: string;
  tone?: "ok" | "error";
  mono?: boolean;
}) {
  return (
    <div className="py-3 flex items-baseline justify-between gap-4">
      <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary shrink-0">
        {label}
      </span>
      <span
        className={`text-sm text-right ${
          tone === "ok" ? "text-success" : tone === "error" ? "text-danger" : "text-ink"
        } ${mono ? "font-mono tabular-nums" : ""}`}
      >
        {value}
      </span>
    </div>
  );
}

function ChannelRow({
  label,
  enabled,
  customText,
}: {
  label: string;
  enabled: boolean;
  customText?: string;
}) {
  return (
    <div className="py-3 flex items-baseline justify-between">
      <div className="flex items-center gap-2">
        <span className={`w-1 h-1 rounded-full ${enabled ? "bg-accent" : "bg-ink-tertiary"}`} />
        <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary">
          {label}
        </span>
      </div>
      <span
        className={`text-sm ${enabled ? "text-ink" : "text-ink-tertiary"}`}
      >
        {customText || (enabled ? "已开启" : "已关闭")}
      </span>
    </div>
  );
}
