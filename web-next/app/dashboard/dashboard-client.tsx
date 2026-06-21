"use client";

import { useMemo, useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

import StatsCards from "@/components/dashboard/StatsCards";
import AttackLogTable from "@/components/dashboard/AttackLogTable";
import AlertDetailPanel from "@/components/dashboard/AlertDetailPanel";
import SystemStatusBar from "@/components/dashboard/SystemStatusBar";
import DashboardAiConfigSection from "@/components/dashboard/sections/DashboardAiConfigSection";
import DashboardAlertWorkspaceSection from "@/components/dashboard/sections/DashboardAlertWorkspaceSection";
import DashboardBriefingSection from "@/components/dashboard/sections/DashboardBriefingSection";
import DashboardCopilotRouteSection from "@/components/dashboard/sections/DashboardCopilotRouteSection";
import DashboardIncidentWorkspaceSection from "@/components/dashboard/sections/DashboardIncidentWorkspaceSection";
import DashboardReportSection from "@/components/dashboard/sections/DashboardReportSection";
import DashboardSecurityTimelineSection from "@/components/dashboard/sections/DashboardSecurityTimelineSection";
import DashboardSystemStatusRouteSection from "@/components/dashboard/sections/DashboardSystemStatusRouteSection";
import DashboardTerminalReportSection from "@/components/dashboard/sections/DashboardTerminalReportSection";
import DashboardTrendsSection from "@/components/dashboard/sections/DashboardTrendsSection";
import DashboardWebhookSection from "@/components/dashboard/sections/DashboardWebhookSection";

import { useAlerts } from "@/hooks/useAlerts";
import { useConfig } from "@/hooks/useConfig";
import { useCopilot } from "@/hooks/useCopilot";
import { useTerminal } from "@/hooks/useTerminal";
import { useReport } from "@/hooks/useReport";
import { useSiteHealth } from "@/hooks/useSiteHealth";
import { useSecurityTimeline } from "@/hooks/useSecurityTimeline";
import { useThreatConfirm } from "@/hooks/useThreatConfirm";
import { useIncidents } from "@/hooks/useIncidents";
import { getDashboardRouteMeta } from "@/constants/dashboardRoutes";
import { formatLoadError } from "@/utils/alertUtils";
import { deriveAlertDetail } from "@/utils/alertBriefingUtils";
import type { IncidentSeverity } from "@/types/incident";

import type { RouteKey } from "@/types/route";

type DashboardClientProps = {
  userEmail: string;
};

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
  const incidentsCtx = useIncidents();

  // M3-04 / M3-05: 监听 "用 AI 分析案件" 自定义事件,触发 Copilot。
  // M3-05 起只发短意图 + incidentId,后端通过 incident_id 走 owner 隔离并构造
  // 受控 context_block(详见 docs/agent/M3_05_INCIDENT_AWARE_COPILOT_CONTRACT_TASK.md)。
  useEffect(() => {
    function handleCopilotEvent(event: Event) {
      const custom = event as CustomEvent<{ prompt?: string; incidentId?: string }>;
      const prompt = custom.detail?.prompt;
      if (!prompt) return;
      const incidentId = custom.detail?.incidentId;
      if (incidentId) {
        void copilotCtx.sendMessage(prompt, { incidentId });
      } else {
        void copilotCtx.sendMessage(prompt);
      }
      // 切到 AI/概览 让用户看到 Copilot 输出
      setRoute("ai");
    }
    window.addEventListener("incident:copilot", handleCopilotEvent);
    return () => window.removeEventListener("incident:copilot", handleCopilotEvent);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [copilotCtx.sendMessage]);

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
  const isIncidentsRoute = route === "incidents";
  const isWafRoute = route === "waf";
  const isAiRoute = route === "ai";
  const isReportRoute = route === "report";

  const currentRoute = getDashboardRouteMeta(route);

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

  // M3-04: 从当前告警创建案件
  const handleCreateIncidentFromAlert = async (input: {
    title: string;
    severity: IncidentSeverity;
    alert_id: string;
  }): Promise<boolean> => {
    const result = await incidentsCtx.createIncidentFromAlert({
      title: input.title,
      severity: input.severity,
      alert_id: input.alert_id,
    });
    if (result.ok) {
      // 切到案件视图
      setRoute("incidents");
      // 加载 detail 以便在案件列表选中
      if (result.incident) {
        await incidentsCtx.loadIncidentDetail(result.incident.incident_id, {
          eventLimit: 20,
        });
      }
      configCtx.setStatus(`已创建案件 ${result.incident?.incident_id ?? ""}`);
      return true;
    }
    configCtx.setStatus(`案件创建失败: ${result.error || "未知错误"}`);
    return false;
  };

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
        routeIndex={currentRoute.index}
        routeLabel={currentRoute.label}
        routeDescription={currentRoute.description}
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
          <div data-testid="dashboard-section-stats">
            <StatsCards stats={counters} />
          </div>

          <DashboardBriefingSection alerts={alertsCtx.alerts} />

          {(isOverviewRoute || isMonitorRoute) && (
            <DashboardTrendsSection alerts={alertsCtx.alerts} />
          )}

          {(isOverviewRoute || isMonitorRoute) && (
            <DashboardAlertWorkspaceSection
              loadState={alertsCtx.loadState}
              wsConnected={alertsCtx.wsConnected}
              totalAlerts={alertsCtx.alerts.length}
              totalPages={alertsCtx.totalPages}
              page={alertsCtx.page}
              selectedCountLabel={`共 ${alertsCtx.alerts.length} 条告警 · ${
                alertsCtx.wsConnected ? "WebSocket 实时" : "轮询刷新"
              }`}
              demoState={alertsCtx.demoState}
              demoMessage={alertsCtx.demoMessage}
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
                  onCreateIncidentFromAlert={handleCreateIncidentFromAlert}
                  creatingIncident={incidentsCtx.actionState === "saving"}
                />
              }
              onPrevPage={() => alertsCtx.setPage(Math.max(0, alertsCtx.page - 1))}
              onNextPage={() =>
                alertsCtx.setPage(Math.min(alertsCtx.totalPages - 1, alertsCtx.page + 1))
              }
              onRefresh={handleRefreshAlerts}
              onRetry={() => void alertsCtx.loadAlerts({ showLoading: true })}
              onTriggerDemo={() => void handleTriggerDemoAttack()}
              onExportCsv={handleExportCsv}
            />
          )}

          {(isOverviewRoute || isMonitorRoute) && (
            <DashboardTerminalReportSection
              logs={terminalCtx.logs}
              markdown={reportCtx.markdown}
              typing={reportCtx.typing}
              onCommand={terminalCtx.executeCommand}
              onRefreshReport={() => void reportCtx.refreshWithTypewriter()}
            />
          )}

          {(isOverviewRoute || isMonitorRoute) && (
            <DashboardSecurityTimelineSection
              items={securityTimelineCtx.items}
              loadState={securityTimelineCtx.loadState}
              degraded={securityTimelineCtx.degraded}
              limit={securityTimelineCtx.limit}
              offline={!alertsCtx.wsConnected && securityTimelineCtx.loadState === "error"}
              onRefresh={() => void securityTimelineCtx.refresh()}
            />
          )}

          {isIncidentsRoute && (
            <DashboardIncidentWorkspaceSection incidents={incidentsCtx} />
          )}

          {(isOverviewRoute || isWafRoute) && (
            <DashboardSystemStatusRouteSection
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
              userEmail={userEmail}
            />
          )}

          {(isOverviewRoute || isAiRoute) && (
            <DashboardCopilotRouteSection
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
          )}

          {(isOverviewRoute || isAiRoute) && (
            <DashboardAiConfigSection
              userEmail={userEmail}
              draft={configCtx.draft}
              config={configCtx.config}
              statusHint={copilotCtx.hint}
              wsConnected={alertsCtx.wsConnected}
              totalAlerts={alertsCtx.alerts.length}
              saving={configCtx.saving}
              testing={configCtx.testing}
              refreshing={configCtx.refreshing}
              onChangeDraft={configCtx.setDraft}
              onSaveConfig={() => void configCtx.saveConfig()}
              onTestConfig={() => void configCtx.testConfig()}
              onRefreshConfig={() => void configCtx.refreshConfig()}
            />
          )}

          {(isOverviewRoute || isAiRoute) && (
            <DashboardWebhookSection
              draft={configCtx.draft}
              config={configCtx.config}
              saving={configCtx.saving}
              refreshing={configCtx.refreshing}
              webhookTesting={configCtx.webhookTesting}
              onChangeDraft={configCtx.setDraft}
              onSaveConfig={() => void configCtx.saveConfig()}
              onTestWebhook={() => void configCtx.testWebhook()}
            />
          )}

          {(isOverviewRoute || isReportRoute) && (
            <DashboardReportSection markdown={reportCtx.markdown} />
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
