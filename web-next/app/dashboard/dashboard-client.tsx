"use client";

import { useMemo, useState, useEffect } from "react";
import dynamic from "next/dynamic";
import { motion, AnimatePresence } from "framer-motion";
import {
  LogOut,
  Sun,
  Moon,
  Bell,
  RefreshCw,
} from "lucide-react";
import { signOut } from "next-auth/react";

import StatsCards from "@/components/dashboard/StatsCards";
import AttackLogTable from "@/components/dashboard/AttackLogTable";
import HackerTerminal from "@/components/dashboard/HackerTerminal";
import SecurityTimeline from "@/components/dashboard/SecurityTimeline";
import { Button } from "@/components/ui/button";

// Heavy components are code-split. Recharts (~45KB gzip) only loads when
// the user navigates to overview/monitor routes; the LLM streaming panel
// and its streaming client SDK only load when copilot is rendered.
const AttackTrendChart = dynamic(
  () => import("@/components/dashboard/AttackTrendChart"),
  { ssr: false, loading: () => <div className="h-full bg-bg-raised/40 animate-pulse" /> },
);
const SourcePieChart = dynamic(
  () => import("@/components/dashboard/SourcePieChart"),
  { ssr: false, loading: () => <div className="h-full bg-bg-raised/40 animate-pulse" /> },
);
const CopilotPanel = dynamic(
  () => import("@/components/dashboard/CopilotPanel"),
  { ssr: false, loading: () => <div className="h-full bg-bg-raised/40 animate-pulse" /> },
);
import { useDesktopNotify } from "@/hooks/useDesktopNotify";
import { useTheme } from "@/contexts/ThemeContext";
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

import type { RouteKey } from "@/types/route";

const PROVIDERS = ["custom"] as const;

const NAV_ITEMS: { key: RouteKey; label: string; index: string }[] = [
  { key: "overview", label: "概览", index: "01" },
  { key: "monitor", label: "监测", index: "02" },
  { key: "waf", label: "WAF 管理", index: "03" },
  { key: "ai", label: "AI 配置", index: "04" },
  { key: "report", label: "安全日报", index: "05" },
];

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
        {description && (
          <p className="text-xs text-ink-secondary mt-1">{description}</p>
        )}
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
  const { theme, toggleTheme } = useTheme();
  const { requestPermission } = useDesktopNotify();

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

  const currentRoute = NAV_ITEMS.find((item) => item.key === route);

  async function handleTriggerDemoAttack() {
    try {
      const result = await alertsCtx.triggerDemoAttack("sql_injection");
      const alert = result.alert;
      terminalCtx.appendLogs([
        `Demo 攻击已触发: ${alert.source} -> ${alert.target}`,
        `告警 ${alert.alertId || alert.id} 已进入 Dashboard，可在 AI 助手中分析。`,
        result.copilot?.ready
          ? `Copilot 已就绪: ${result.copilot.provider || "custom"} ${result.copilot.model || ""}`.trim()
          : `Copilot 降级态: ${result.copilot?.next_action || "请先配置 API Key 与 Base URL。"}`,
      ], "success");
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      terminalCtx.appendLogs([`Demo 攻击触发失败: ${message}`], "error");
      configCtx.setStatus(formatLoadError(message));
    }
  }

  function handleAnalyzeSelectedAlert() {
    if (!alertsCtx.selected) return;
    void copilotCtx.sendMessage("请分析当前选中的安全告警，给出风险等级、证据、影响范围和三条立即处置建议。");
  }

  return (
    <div className="min-h-screen bg-bg text-ink">
      {/* ---------- 顶栏 ---------- */}
      <header className="border-b border-line bg-bg">
        <div className="max-w-[1320px] mx-auto px-6 sm:px-10 h-16 flex items-center justify-between gap-6">
          <div className="flex items-baseline gap-6 min-w-0">
            <div className="flex items-baseline gap-2 shrink-0">
              <span className="font-display text-base text-ink">AI-CyberSentinel</span>
              <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-ink-tertiary">
                SOC
              </span>
            </div>
            <nav className="hidden md:flex items-center gap-5">
              {NAV_ITEMS.map((item) => {
                const active = route === item.key;
                return (
                  <button
                    key={item.key}
                    onClick={() => setRoute(item.key)}
                    className={`text-xs font-mono uppercase tracking-[0.1em] transition-colors flex items-center gap-1.5 ${
                      active ? "text-accent" : "text-ink-secondary hover:text-ink"
                    }`}
                  >
                    <span className="opacity-50">{item.index}</span>
                    {item.label}
                  </button>
                );
              })}
            </nav>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <div
              className={`hidden sm:flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-[0.15em] ${
                alertsCtx.wsConnected ? "text-success" : "text-danger"
              }`}
            >
              {alertsCtx.wsConnected ? (
                <span className="relative flex items-center justify-center w-2.5 h-2.5">
                  <span className="absolute inset-0 rounded-full bg-success animate-pulse-soft" />
                  <span className="relative w-1 h-1 rounded-full bg-success" />
                </span>
              ) : (
                <span className="w-1 h-1 rounded-full bg-danger" />
              )}
              {alertsCtx.wsConnected ? "WS · 在线" : "WS · 离线"}
            </div>
            <button
              onClick={requestPermission}
              className="p-1.5 text-ink-secondary hover:text-ink transition-colors"
              title="启用桌面通知"
            >
              <Bell className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={toggleTheme}
              className="p-1.5 text-ink-secondary hover:text-ink transition-colors"
              type="button"
            >
              {theme === "light" ? <Moon className="w-3.5 h-3.5" /> : <Sun className="w-3.5 h-3.5" />}
            </button>
            <div className="w-px h-4 bg-line mx-1 hidden sm:block" />
            <span className="text-[10px] font-mono text-ink-tertiary hidden md:inline max-w-[180px] truncate">
              {userEmail}
            </span>
            <button
              onClick={() => signOut({ callbackUrl: "/" })}
              className="p-1.5 text-ink-secondary hover:text-danger transition-colors"
              title="退出登录"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* 移动端 tab */}
        <div className="md:hidden border-t border-line-subtle overflow-x-auto">
          <div className="flex gap-4 px-4 py-2 min-w-max">
            {NAV_ITEMS.map((item) => {
              const active = route === item.key;
              return (
                <button
                  key={item.key}
                  onClick={() => setRoute(item.key)}
                  className={`text-[10px] font-mono uppercase tracking-[0.15em] transition-colors flex items-center gap-1.5 whitespace-nowrap ${
                    active ? "text-accent" : "text-ink-secondary"
                  }`}
                >
                  <span className="opacity-50">{item.index}</span>
                  {item.label}
                </button>
              );
            })}
          </div>
        </div>
      </header>

      {/* ---------- 主内容 ---------- */}
      <AnimatePresence mode="wait">
        <motion.main
          key={route}
          initial={false}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="max-w-[1320px] mx-auto px-6 sm:px-10 py-10 sm:py-14"
        >
          {/* 页面标题区 — 强 typography 主导 */}
          <div className="mb-10 pb-6 border-b border-line">
            <div className="flex items-baseline justify-between flex-wrap gap-3 mb-3">
              <div className="flex items-baseline gap-3">
                <span className="text-[11px] font-mono uppercase tracking-[0.2em] text-accent">
                  {currentRoute?.index} / {currentRoute?.label}
                </span>
                <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-ink-tertiary">
                  {isOverviewRoute ? "ALL SYSTEMS" : "FOCUSED VIEW"}
                </span>
              </div>
              <span className="text-[10px] font-mono text-ink-tertiary">
                {new Date().toLocaleString("zh-CN", { hour12: false })}
              </span>
            </div>
            <h1 className="font-display text-4xl sm:text-5xl text-ink leading-tight tracking-tight">
              {currentRoute?.label}
            </h1>
            <p className="text-sm text-ink-secondary mt-2 max-w-2xl">
              {routeDescription(route)}
            </p>
          </div>

          {/* 状态条 */}
          <div className="mb-10 text-[11px] font-mono text-ink-secondary flex items-center gap-2">
            <span className="w-1 h-1 rounded-full bg-accent" />
            {configCtx.status}
          </div>

          {/* 统计卡片 */}
          <StatsCards stats={counters} />

          {/* 图表区（概览/监测） */}
          {(isOverviewRoute || isMonitorRoute) && (
            <div className="mt-12">
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

          {/* 告警流 + AI 助手（概览/监测） */}
          {(isOverviewRoute || isMonitorRoute) && (
            <div className="mt-14">
              <SectionHeading
                index="§ 02"
                title="实时告警与 AI 助手"
                description={`共 ${alertsCtx.alerts.length} 条告警 · ${alertsCtx.wsConnected ? "WebSocket 实时" : "轮询刷新"}`}
                action={
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => void handleTriggerDemoAttack()}
                      disabled={alertsCtx.demoState === "running"}
                      data-testid="trigger-demo-attack"
                      className="text-[10px] font-mono uppercase tracking-[0.15em] text-accent hover:text-accent-hover disabled:opacity-30 transition-colors"
                    >
                      {alertsCtx.demoState === "running"
                        ? "触发中"
                        : alertsCtx.demoState === "success"
                          ? "Demo 已生成"
                          : alertsCtx.demoState === "error"
                            ? "重试 Demo"
                            : "触发 Demo 攻击"}
                    </button>
                    <span className="hidden xl:inline max-w-[360px] truncate text-[10px] font-mono text-ink-tertiary">
                      {alertsCtx.demoMessage}
                    </span>
                    <button
                      onClick={() => {
                        const link = document.createElement("a");
                        link.href = "/api/backend/export/alerts?limit=1000";
                        link.download = "alerts.csv";
                        link.click();
                      }}
                      className="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-secondary hover:text-ink transition-colors"
                    >
                      导出 CSV
                    </button>
                    <button
                      onClick={() => {
                        alertsCtx.loadAlerts({ showLoading: true }).catch(() => {});
                      }}
                      className="text-[10px] font-mono uppercase tracking-[0.15em] text-accent hover:text-accent-hover transition-colors"
                    >
                      刷新
                    </button>
                  </div>
                }
              />
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div className="lg:col-span-2 min-h-[480px] flex flex-col">
                  {alertsCtx.loadState === "loading" ? (
                    <div className="flex-1 flex items-center justify-center text-ink-secondary text-sm">
                      <span className="font-mono text-xs">加载中...</span>
                    </div>
                  ) : alertsCtx.loadState === "error" ? (
                    <div className="flex-1 flex flex-col items-center justify-center gap-3 text-sm text-danger">
                      <span>告警加载失败</span>
                      <Button variant="outline" size="sm" onClick={() => void alertsCtx.loadAlerts()}>
                        重试
                      </Button>
                    </div>
                  ) : alertsCtx.loadState === "empty" ? (
                    <div className="flex-1 flex items-center justify-center text-ink-tertiary text-sm">
                      暂无告警
                    </div>
                  ) : (
                    <div className="flex-1 flex flex-col">
                      <AttackLogTable
                        logs={alertsCtx.paginatedAlerts}
                        highlightId={selectedLogId}
                        selectedId={selectedLogId}
                        onSelect={alertsCtx.handleSelectLog}
                        newIds={alertsCtx.newAlertIds}
                      />
                      {alertsCtx.totalPages > 1 && (
                        <div className="flex items-center justify-center gap-4 pt-4 mt-4 border-t border-line-subtle text-xs">
                          <button
                            onClick={() => alertsCtx.setPage(Math.max(0, alertsCtx.page - 1))}
                            disabled={alertsCtx.page === 0}
                            className="text-ink-secondary hover:text-ink disabled:opacity-30 transition-colors font-mono"
                          >
                            ← 上一页
                          </button>
                          <span className="font-mono text-ink-tertiary tabular-nums">
                            {alertsCtx.page + 1} / {alertsCtx.totalPages}
                          </span>
                          <button
                            onClick={() => alertsCtx.setPage(Math.min(alertsCtx.totalPages - 1, alertsCtx.page + 1))}
                            disabled={alertsCtx.page >= alertsCtx.totalPages - 1}
                            className="text-ink-secondary hover:text-ink disabled:opacity-30 transition-colors font-mono"
                          >
                            下一页 →
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
                <div className="min-h-[480px] flex flex-col">
                  <CopilotPanel
                    messages={copilotCtx.messages}
                    draft={copilotCtx.input}
                    loading={copilotCtx.sending}
                    contextLabel={copilotCtx.hint}
                    onDraftChange={copilotCtx.setInput}
                    onSend={() => void copilotCtx.sendMessage(copilotCtx.input)}
                    onAnalyzeAlert={alertsCtx.selected ? handleAnalyzeSelectedAlert : undefined}
                  />
                </div>
              </div>
            </div>
          )}

          {/* 终端 + 日报（概览/监测） */}
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

          {/* 安全运营时间线（概览/监测） */}
          {(isOverviewRoute || isMonitorRoute) && (
            <div className="mt-14">
              <SectionHeading
                index="§ 03.5"
                title="安全运营时间线"
                description="Demo 攻击 / Copilot / 护栏 / 认证 / 配置摘要"
              />
              <div className="min-h-[280px]">
                <SecurityTimeline
                  items={securityTimelineCtx.items}
                  loadState={securityTimelineCtx.loadState}
                  degraded={securityTimelineCtx.degraded}
                  limit={securityTimelineCtx.limit}
                  onRefresh={() => void securityTimelineCtx.refresh()}
                />
              </div>
            </div>
          )}

          {/* 站点 + 代理 + 威胁确认（概览/WAF） */}
          {(isOverviewRoute || isWafRoute) && (
            <div className="mt-14">
              <SectionHeading
                index="§ 04"
                title="站点监测与威胁确认"
                description="配置受保护站点、测试 WAF 链路、确认告警入库"
              />
              <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                {/* 站点监测 */}
                <div className="space-y-5">
                  <div>
                    <FieldLabel>站点状态</FieldLabel>
                    <div className="text-2xl font-display text-ink">{siteHealthCtx.healthUi.text}</div>
                  </div>
                  <div>
                    <FieldLabel>目标 URL</FieldLabel>
                    <TextInput
                      value={siteHealthCtx.targetInput}
                      onChange={(event) => siteHealthCtx.setTargetInput(event.target.value)}
                      placeholder="https://example.com"
                    />
                  </div>
                  <button
                    onClick={() => void siteHealthCtx.saveTarget()}
                    disabled={siteHealthCtx.targetSaving || !siteHealthCtx.targetInput.trim()}
                    className="btn-outline w-full"
                  >
                    {siteHealthCtx.targetSaving ? "保存中..." : "保存目标"}
                  </button>
                  <div className="text-[10px] font-mono text-ink-tertiary">
                    {siteHealthCtx.health?.url ? `当前 · ${siteHealthCtx.health.url}` : "未设置"}
                  </div>
                </div>

                {/* 代理 WAF */}
                <div className="space-y-5">
                  <FieldLabel>代理与 WAF</FieldLabel>
                  <TextInput
                    value={siteHealthCtx.proxyPathInput}
                    onChange={(event) => siteHealthCtx.setProxyPathInput(event.target.value)}
                    placeholder="/"
                  />
                  <button
                    onClick={() => void siteHealthCtx.testProxy()}
                    disabled={siteHealthCtx.proxyTesting}
                    className="btn-outline w-full"
                  >
                    {siteHealthCtx.proxyTesting ? "测试中..." : "测试代理链路"}
                  </button>
                  <div className="text-[10px] font-mono text-ink-tertiary leading-relaxed">
                    路径支持 URL 或相对路径。
                    <br />
                    命中策略会返回 403。
                  </div>
                </div>

                {/* 威胁确认 */}
                <div className="space-y-5">
                  <FieldLabel>告警确认与语音</FieldLabel>
                  <button
                    onClick={() => void threatCtx.confirmThreat()}
                    disabled={threatCtx.confirming || !alertsCtx.selected?.alertId}
                    className="btn-outline w-full"
                  >
                    {threatCtx.confirming ? "确认中..." : "确认威胁入库"}
                  </button>
                  <div
                    className={`text-[11px] px-3 py-2.5 border-l-2 rounded-md ${
                      threatCtx.statusTone === "ok"
                        ? "border-success text-success bg-success-soft"
                        : threatCtx.statusTone === "error"
                          ? "border-danger text-danger bg-danger-soft"
                          : "border-line text-ink-secondary bg-bg-sunken"
                    }`}
                  >
                    {threatCtx.status}
                  </div>
                  <button
                    onClick={() => void threatCtx.toggleVoiceAlert()}
                    className="btn-ghost w-full"
                  >
                    {configCtx.config?.alert_voice_enabled ? "关闭语音预警" : "开启语音预警"}
                  </button>
                </div>
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
                      onChange={(event) => configCtx.setDraft((prev) => ({ ...prev, ai_provider: event.target.value }))}
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
                      onChange={(event) => configCtx.setDraft((prev) => ({ ...prev, model: event.target.value }))}
                      placeholder="gpt-4 / claude-3 ..."
                    />
                  </div>
                  <div>
                    <FieldLabel>Base URL</FieldLabel>
                    <TextInput
                      autoComplete="off"
                      value={configCtx.draft.base_url}
                      onChange={(event) => configCtx.setDraft((prev) => ({ ...prev, base_url: event.target.value }))}
                      placeholder="https://api.openai.com/v1"
                    />
                  </div>
                  <div>
                    <FieldLabel>API Key</FieldLabel>
                    <TextInput
                      type="password"
                      autoComplete="new-password"
                      value={configCtx.draft.api_key}
                      onChange={(event) => configCtx.setDraft((prev) => ({ ...prev, api_key: event.target.value }))}
                      placeholder={configCtx.config?.has_api_key ? "已配置，留空表示不修改" : "输入 API Key"}
                    />
                    <div className="text-[10px] font-mono text-ink-tertiary mt-1.5">
                      当前：{configCtx.config?.has_api_key ? configCtx.config.api_key_masked : "未配置"}
                    </div>
                  </div>
                  <div className="flex gap-2 flex-wrap pt-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void configCtx.saveConfig()}
                      disabled={configCtx.saving || configCtx.testing || configCtx.refreshing}
                    >
                      {configCtx.saving ? "保存中..." : "保存"}
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
                    <SessionRow label="告警总数" value={String(alertsCtx.alerts.length)} mono />
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
                      onChange={(event) => configCtx.setDraft((prev) => ({ ...prev, webhook_type: event.target.value }))}
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
                      onChange={(event) => configCtx.setDraft((prev) => ({ ...prev, webhook_url: event.target.value }))}
                      placeholder="https://oapi.dingtalk.com/robot/send?access_token=…"
                      disabled={configCtx.saving || configCtx.refreshing}
                    />
                    <div className="text-[10px] font-mono text-ink-tertiary mt-1.5 break-all">
                      当前：{configCtx.config?.webhook_url ? `${configCtx.config.webhook_type} · ${configCtx.config.webhook_url.slice(0, 60)}` : "未配置"}
                    </div>
                  </div>
                  <div className="flex gap-2 flex-wrap pt-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void configCtx.saveConfig()}
                      disabled={configCtx.saving || configCtx.refreshing || configCtx.webhookTesting}
                    >
                      {configCtx.saving ? "保存中..." : "保存"}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void configCtx.testWebhook()}
                      disabled={configCtx.saving || configCtx.refreshing || configCtx.webhookTesting}
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
                      customText={configCtx.config?.webhook_url ? "已配置" : "未配置"}
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
        className={`text-sm ${
          enabled ? "text-ink" : "text-ink-tertiary"
        }`}
      >
        {customText || (enabled ? "已开启" : "已关闭")}
      </span>
    </div>
  );
}
