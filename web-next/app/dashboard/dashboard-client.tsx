"use client";

import { useMemo, useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { RefreshCw, LogOut, Sun, Moon, Bell, Shield } from "lucide-react";
import { signOut } from "next-auth/react";

import StatsCards from "@/components/dashboard/StatsCards";
import AttackLogTable from "@/components/dashboard/AttackLogTable";
import HackerTerminal from "@/components/dashboard/HackerTerminal";
import CopilotPanel from "@/components/dashboard/CopilotPanel";
import AttackTrendChart from "@/components/dashboard/AttackTrendChart";
import SourcePieChart from "@/components/dashboard/SourcePieChart";
import { Button } from "@/components/ui/button";
import { useDesktopNotify } from "@/hooks/useDesktopNotify";
import { useTheme } from "@/contexts/ThemeContext";
import { useAlerts } from "@/hooks/useAlerts";
import { useConfig } from "@/hooks/useConfig";
import { useCopilot } from "@/hooks/useCopilot";
import { useTerminal } from "@/hooks/useTerminal";
import { useReport } from "@/hooks/useReport";
import { useSiteHealth } from "@/hooks/useSiteHealth";
import { useThreatConfirm } from "@/hooks/useThreatConfirm";
import { routeDescription } from "@/utils/routeUtils";
import { formatLoadError } from "@/utils/alertUtils";

import type { RouteKey } from "@/types/route";

const PROVIDERS = ["custom"] as const;
const NAV_ITEMS: { key: RouteKey; label: string; icon: string }[] = [
  { key: "overview", label: "概览", icon: "01" },
  { key: "monitor", label: "监测", icon: "02" },
  { key: "waf", label: "WAF 管理", icon: "03" },
  { key: "ai", label: "AI 配置", icon: "04" },
  { key: "report", label: "安全日报", icon: "05" },
];

type DashboardClientProps = {
  userEmail: string;
};

export default function DashboardClient({ userEmail }: DashboardClientProps) {
  const [route, setRoute] = useState<RouteKey>("overview");
  const { theme, toggleTheme } = useTheme();
  const { requestPermission } = useDesktopNotify();

  const alertsCtx = useAlerts();
  const configCtx = useConfig();
  const copilotCtx = useCopilot(alertsCtx.selected);
  const terminalCtx = useTerminal(alertsCtx.alerts);
  const reportCtx = useReport(alertsCtx.alerts);
  const siteHealthCtx = useSiteHealth(configCtx.setStatus);
  const threatCtx = useThreatConfirm(
    alertsCtx.selected,
    configCtx.config,
    configCtx.setConfig,
    configCtx.setStatus,
    terminalCtx.appendLogs,
    configCtx.refreshConfig,
  );

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

  const pageTransitionVariants = {
    hidden: { opacity: 0, y: 12 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.35, ease: "easeOut" as const } },
    exit: { opacity: 0, y: -8, transition: { duration: 0.2 } },
  };

  const contentItemVariants = {
    hidden: { opacity: 0, y: 16 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] as [number, number, number, number] },
    },
  };

  return (
    <div className="min-h-screen bg-background text-text">
      <motion.header
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
        className="sticky top-0 z-50 bg-surface/80 backdrop-blur-xl border-b border-border-subtle"
      >
        <div className="max-w-[1400px] mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <motion.div
              className="flex items-center gap-2.5"
              whileHover={{ scale: 1.02 }}
              transition={{ duration: 0.2 }}
            >
              <div className="w-8 h-8 bg-primary rounded-apple flex items-center justify-center">
                <Shield className="w-4 h-4 text-white" />
              </div>
              <span className="font-semibold text-text tracking-tight">AI-CyberSentinel</span>
            </motion.div>
            <nav className="hidden md:flex items-center gap-1">
              {NAV_ITEMS.map((item) => (
                <motion.button
                  key={item.key}
                  onClick={() => setRoute(item.key)}
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                  className={`px-4 py-2 rounded-apple text-sm font-medium transition-all ${
                    route === item.key
                      ? "bg-primary/10 text-primary"
                      : "text-text-secondary hover:text-text hover:bg-background"
                  }`}
                >
                  {item.label}
                </motion.button>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-2">
            <motion.div
              initial={false}
              animate={alertsCtx.wsConnected ? { scale: [1, 1.05, 1] } : {}}
              transition={{ repeat: Infinity, duration: 2 }}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium ${alertsCtx.wsConnected ? "bg-success-subtle text-success" : "bg-danger-subtle text-danger"}`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${alertsCtx.wsConnected ? "bg-success" : "bg-danger"}`} />
              {alertsCtx.wsConnected ? "在线" : "离线"}
            </motion.div>
            <motion.button
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.9 }}
              onClick={requestPermission}
              className="p-2 rounded-apple text-text-secondary hover:text-text hover:bg-background transition-colors"
              title="启用桌面通知"
            >
              <Bell className="w-4 h-4" />
            </motion.button>
            <button
              onClick={toggleTheme}
              className="p-2 rounded-apple text-text-secondary hover:text-text hover:bg-background transition-colors cursor-pointer"
              type="button"
            >
              {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
            <div className="w-px h-6 bg-border-subtle mx-1" />
            <span className="text-sm text-text-secondary hidden sm:block">{userEmail}</span>
            <motion.button
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.9 }}
              onClick={() => signOut({ callbackUrl: "/" })}
              className="p-2 rounded-apple text-text-secondary hover:text-danger hover:bg-danger-subtle transition-colors"
            >
              <LogOut className="w-4 h-4" />
            </motion.button>
          </div>
        </div>
      </motion.header>

      <div className="md:hidden bg-surface border-b border-border-subtle px-4 py-2 overflow-x-auto">
        <div className="flex gap-1 min-w-max">
          {NAV_ITEMS.map((item) => (
            <motion.button
              key={item.key}
              onClick={() => setRoute(item.key)}
              whileTap={{ scale: 0.95 }}
              className={`px-4 py-2 rounded-apple text-sm font-medium transition-all whitespace-nowrap ${
                route === item.key
                  ? "bg-primary/10 text-primary"
                  : "text-text-secondary"
              }`}
            >
              {item.label}
            </motion.button>
          ))}
        </div>
      </div>

      <AnimatePresence mode="wait">
        <motion.main
          key={route}
          variants={pageTransitionVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          className="max-w-[1400px] mx-auto px-6 py-8 space-y-6"
        >
          <motion.div variants={contentItemVariants}>
            <StatsCards stats={counters} />
          </motion.div>

          {(isOverviewRoute || isMonitorRoute) ? (
            <motion.div variants={contentItemVariants} className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              <motion.div
                whileHover={{ y: -2, transition: { duration: 0.2 } }}
                className="bg-surface rounded-apple-lg shadow-card p-5 h-[300px]"
              >
                <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">攻击趋势 (近24时段)</h3>
                <AttackTrendChart alerts={alertsCtx.alerts} />
              </motion.div>
              <motion.div
                whileHover={{ y: -2, transition: { duration: 0.2 } }}
                className="bg-surface rounded-apple-lg shadow-card p-5 h-[300px]"
              >
                <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">攻击分布</h3>
                <SourcePieChart alerts={alertsCtx.alerts} />
              </motion.div>
            </motion.div>
          ) : null}

          <motion.div variants={contentItemVariants} className="bg-surface rounded-apple shadow-card p-3 text-sm text-text-secondary">{configCtx.status}</motion.div>

          {!isOverviewRoute ? (
            <motion.div variants={contentItemVariants} className="bg-surface rounded-apple shadow-card p-4 text-sm text-text">
              当前标签页：{NAV_ITEMS.find((item) => item.key === route)?.label || route} · {routeDescription(route)}
            </motion.div>
          ) : null}

          {(isOverviewRoute || isMonitorRoute) ? (
            <motion.div variants={contentItemVariants} className="grid grid-cols-1 xl:grid-cols-3 gap-6 min-h-0 flex-1">
              <div className="xl:col-span-2 min-h-0 flex flex-col gap-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-text">实时告警流</h2>
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
                    >
                      导出CSV
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        alertsCtx.loadAlerts({ showLoading: true }).catch(() => {});
                      }}
                    >
                      刷新
                    </Button>
                  </div>
                </div>
                <div className="min-h-0 flex-1">
                  {alertsCtx.loadState === "loading" ? (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="h-full min-h-[220px] bg-surface rounded-apple-lg shadow-card flex items-center justify-center text-text-secondary text-sm"
                    >
                      <motion.div
                        animate={{ rotate: 360 }}
                        transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
                        className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full mr-2"
                      />
                      正在加载告警...
                    </motion.div>
                  ) : alertsCtx.loadState === "error" ? (
                    <div className="h-full min-h-[220px] bg-surface rounded-apple-lg shadow-card flex flex-col items-center justify-center gap-2 text-sm text-danger">
                      告警加载失败，请稍后重试
                      <Button variant="outline" size="sm" onClick={() => void alertsCtx.loadAlerts()}>
                        重试
                      </Button>
                    </div>
                  ) : alertsCtx.loadState === "empty" ? (
                    <div className="h-full min-h-[220px] bg-surface rounded-apple-lg shadow-card flex items-center justify-center text-text-secondary text-sm">
                      暂无告警
                    </div>
                  ) : (
                    <div className="flex flex-col h-full min-h-0">
                      <div className="flex-1 min-h-0">
                        <AttackLogTable
                          logs={alertsCtx.paginatedAlerts}
                          highlightId={selectedLogId}
                          selectedId={selectedLogId}
                          onSelect={alertsCtx.handleSelectLog}
                        />
                      </div>
                      {alertsCtx.totalPages > 1 && (
                        <div className="flex items-center justify-center gap-2 py-3">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => alertsCtx.setPage(Math.max(0, alertsCtx.page - 1))}
                            disabled={alertsCtx.page === 0}
                          >
                            上一页
                          </Button>
                          <span className="text-xs text-text-secondary">
                            {alertsCtx.page + 1} / {alertsCtx.totalPages}
                          </span>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => alertsCtx.setPage(Math.min(alertsCtx.totalPages - 1, alertsCtx.page + 1))}
                            disabled={alertsCtx.page >= alertsCtx.totalPages - 1}
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
                  messages={copilotCtx.messages}
                  draft={copilotCtx.input}
                  loading={copilotCtx.sending}
                  onDraftChange={copilotCtx.setInput}
                  onSend={() => void copilotCtx.sendMessage(copilotCtx.input)}
                />
              </div>
            </motion.div>
          ) : null}

          {(isOverviewRoute || isMonitorRoute) ? (
            <motion.div variants={contentItemVariants} className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              <motion.div
                whileHover={{ y: -2, transition: { duration: 0.2 } }}
                className="h-[320px]"
              >
                <HackerTerminal lines={terminalCtx.logs} onCommand={terminalCtx.executeCommand} />
              </motion.div>

              <motion.div
                whileHover={{ y: -2, transition: { duration: 0.2 } }}
                className="bg-surface rounded-apple-lg shadow-card p-5 h-[320px] overflow-y-auto"
              >
                <div className="mb-3 flex items-center justify-between text-sm text-text">
                  <span className="font-semibold">安全日报</span>
                  <Button variant="outline" size="sm" onClick={() => void reportCtx.refreshWithTypewriter()}>
                    <RefreshCw className={`mr-1 h-3.5 w-3.5 ${reportCtx.typing ? "animate-spin" : ""}`} />
                    刷新
                  </Button>
                </div>
                <pre className="whitespace-pre-wrap text-xs leading-5 text-text-secondary">{reportCtx.markdown}</pre>
              </motion.div>
            </motion.div>
          ) : null}

          {(isOverviewRoute || isWafRoute) ? (
            <motion.div variants={contentItemVariants} className="grid grid-cols-1 xl:grid-cols-3 gap-6">
              <motion.div
                whileHover={{ y: -3, transition: { duration: 0.2 } }}
                className="bg-surface rounded-apple-lg shadow-card p-5 space-y-3"
              >
                <h3 className="text-sm font-semibold text-text">站点监测</h3>
                <div className="text-xs text-text-secondary">状态: {siteHealthCtx.healthUi.text}</div>
                <input
                  value={siteHealthCtx.targetInput}
                  onChange={(event) => siteHealthCtx.setTargetInput(event.target.value)}
                  placeholder="https://example.com"
                  className="w-full bg-background border border-border-subtle rounded-apple text-text text-sm py-2.5 px-3 focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all"
                />
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={() => void siteHealthCtx.saveTarget()}
                  disabled={siteHealthCtx.targetSaving || !siteHealthCtx.targetInput.trim()}
                >
                  保存目标
                </Button>
                <div className="text-[11px] text-text-tertiary">{siteHealthCtx.health?.url ? `当前目标: ${siteHealthCtx.health.url}` : "当前目标: 未设置"}</div>
              </motion.div>

              <motion.div
                whileHover={{ y: -3, transition: { duration: 0.2 } }}
                className="bg-surface rounded-apple-lg shadow-card p-5 space-y-3"
              >
                <h3 className="text-sm font-semibold text-text">代理与 WAF</h3>
                <input
                  value={siteHealthCtx.proxyPathInput}
                  onChange={(event) => siteHealthCtx.setProxyPathInput(event.target.value)}
                  placeholder="/"
                  className="w-full bg-background border border-border-subtle rounded-apple text-text text-sm py-2.5 px-3 focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all"
                />
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={() => void siteHealthCtx.testProxy()}
                  disabled={siteHealthCtx.proxyTesting}
                >
                  {siteHealthCtx.proxyTesting ? "测试中..." : "测试代理链路"}
                </Button>
                <div className="text-[11px] text-text-tertiary">路径支持 URL 或相对路径，命中策略会返回 403。</div>
              </motion.div>

              <motion.div
                whileHover={{ y: -3, transition: { duration: 0.2 } }}
                className="bg-surface rounded-apple-lg shadow-card p-5 space-y-3"
              >
                <h3 className="text-sm font-semibold text-text">告警确认与语音</h3>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={() => void threatCtx.confirmThreat()}
                  disabled={threatCtx.confirming || !alertsCtx.selected?.alertId}
                >
                  {threatCtx.confirming ? "确认中..." : "确认威胁入库"}
                </Button>
                <div
                  className={`text-[11px] px-3 py-2 rounded-apple ${
                    threatCtx.statusTone === "ok"
                      ? "bg-success-subtle text-success"
                      : threatCtx.statusTone === "error"
                        ? "bg-danger-subtle text-danger"
                        : "bg-background text-text-secondary"
                  }`}
                >
                  {threatCtx.status}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={() => void threatCtx.toggleVoiceAlert()}
                >
                  {configCtx.config?.alert_voice_enabled ? "关闭语音预警" : "开启语音预警"}
                </Button>
              </motion.div>
            </motion.div>
          ) : null}

          {(isOverviewRoute || isAiRoute) ? (
            <motion.div variants={contentItemVariants} className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              <motion.div
                whileHover={{ y: -3, transition: { duration: 0.2 } }}
                className="bg-surface rounded-apple-lg shadow-card p-5 space-y-2"
              >
                <h3 className="text-sm font-semibold text-text">AI 路由配置</h3>
                <select
                  value={configCtx.draft.ai_provider}
                  onChange={(event) => configCtx.setDraft((prev) => ({ ...prev, ai_provider: event.target.value }))}
                  className="w-full bg-background border border-border-subtle rounded-apple text-text text-sm py-2.5 px-3"
                >
                  {PROVIDERS.map((provider) => (
                    <option key={provider} value={provider}>
                      {provider}
                    </option>
                  ))}
                </select>
                <input
                  autoComplete="off"
                  value={configCtx.draft.model}
                  onChange={(event) => configCtx.setDraft((prev) => ({ ...prev, model: event.target.value }))}
                  placeholder="Model"
                  className="w-full bg-background border border-border-subtle rounded-apple text-text text-sm py-2.5 px-3"
                />
                <input
                  autoComplete="off"
                  value={configCtx.draft.base_url}
                  onChange={(event) => configCtx.setDraft((prev) => ({ ...prev, base_url: event.target.value }))}
                  placeholder="Base URL"
                  className="w-full bg-background border border-border-subtle rounded-apple text-text text-sm py-2.5 px-3"
                />
                <input
                  type="password"
                  autoComplete="new-password"
                  value={configCtx.draft.api_key}
                  onChange={(event) => configCtx.setDraft((prev) => ({ ...prev, api_key: event.target.value }))}
                  placeholder={configCtx.config?.has_api_key ? "已配置，留空表示不修改" : "输入新的 API Key"}
                  className="w-full bg-background border border-border-subtle rounded-apple text-text text-sm py-2.5 px-3"
                />
                <div className="text-xs text-text-tertiary">当前密钥状态：{configCtx.config?.has_api_key ? configCtx.config.api_key_masked : "未配置"}</div>
                <div className="flex gap-2 flex-wrap">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void configCtx.saveConfig()}
                    disabled={configCtx.saving || configCtx.testing || configCtx.refreshing}
                  >
                    {configCtx.saving ? "保存中..." : "保存配置"}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void configCtx.testConfig()}
                    disabled={configCtx.saving || configCtx.testing || configCtx.refreshing}
                  >
                    {configCtx.testing ? "测试中..." : "测试路由"}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void configCtx.refreshConfig()}
                    disabled={configCtx.saving || configCtx.testing || configCtx.refreshing}
                  >
                    {configCtx.refreshing ? "同步中..." : "重新同步"}
                  </Button>
                </div>
              </motion.div>

              <motion.div
                whileHover={{ y: -3, transition: { duration: 0.2 } }}
                className="bg-surface rounded-apple-lg shadow-card p-5 space-y-2"
              >
                <h3 className="text-sm font-semibold text-text">当前会话</h3>
                <div className="text-sm text-text">用户: {userEmail || "unknown"}</div>
                <div className="text-xs text-text-secondary">上下文: {copilotCtx.hint}</div>
              </motion.div>
            </motion.div>
          ) : null}

          {(isOverviewRoute || isReportRoute) ? (
            <motion.div variants={contentItemVariants} className="bg-surface rounded-apple-lg shadow-card p-5">
              <h3 className="text-sm font-semibold text-text mb-2">日报摘要</h3>
              <pre className="whitespace-pre-wrap text-xs leading-5 text-text-secondary">{reportCtx.markdown}</pre>
            </motion.div>
          ) : null}
        </motion.main>
      </AnimatePresence>
    </div>
  );
}
