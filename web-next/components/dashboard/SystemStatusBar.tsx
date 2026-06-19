"use client";

import { Bell, LogOut, Moon, Sun } from "lucide-react";
import { signOut } from "next-auth/react";
import { DASHBOARD_NAV_ITEMS } from "@/constants/dashboardRoutes";
import { useTheme } from "@/contexts/ThemeContext";
import { useDesktopNotify } from "@/hooks/useDesktopNotify";
import type { RouteKey } from "@/types/route";

/**
 * 顶栏 + 路由头 + 配置状态条。
 *
 * 接管了原 dashboard-client 中:
 *  - LOGO / WS 在线指示 / 桌面通知按钮 / 主题切换 / 退出登录
 *  - 路由头 (index / label / 当前时间 / description)
 *  - 配置状态条
 *
 * 桌面 / 移动两套 nav 内部一并处理。
 */

export interface SystemStatusBarProps {
  userEmail: string;
  wsConnected: boolean;
  route: RouteKey;
  onChangeRoute: (route: RouteKey) => void;
  statusMessage: string;
  routeIndex: string;
  routeLabel: string;
  routeDescription: string;
  pageFocus: "ALL SYSTEMS" | "FOCUSED VIEW";
}

export default function SystemStatusBar({
  userEmail,
  wsConnected,
  route,
  onChangeRoute,
  statusMessage,
  routeIndex,
  routeLabel,
  routeDescription,
  pageFocus,
}: SystemStatusBarProps) {
  const { theme, toggleTheme } = useTheme();
  const { requestPermission } = useDesktopNotify();

  return (
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
            {DASHBOARD_NAV_ITEMS.map((item) => {
              const active = route === item.key;
              return (
                <button
                  key={item.key}
                  data-testid={`dashboard-route-desktop-${item.key}`}
                  data-dashboard-route={item.key}
                  aria-current={active ? "page" : undefined}
                  onClick={() => onChangeRoute(item.key)}
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
            data-testid="ws-status"
            data-connected={wsConnected || undefined}
            className={`hidden sm:flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-[0.15em] ${
              wsConnected ? "text-success" : "text-danger"
            }`}
          >
            {wsConnected ? (
              <span className="relative flex items-center justify-center w-2.5 h-2.5">
                <span className="absolute inset-0 rounded-full bg-success animate-pulse-soft" />
                <span className="relative w-1 h-1 rounded-full bg-success" />
              </span>
            ) : (
              <span className="w-1 h-1 rounded-full bg-danger" />
            )}
            {wsConnected ? "WS · 在线" : "WS · 离线"}
          </div>
          <button
            onClick={() => void requestPermission()}
            className="p-1.5 text-ink-secondary hover:text-ink transition-colors"
            title="启用桌面通知"
            aria-label="启用桌面通知"
            type="button"
          >
            <Bell className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={toggleTheme}
            className="p-1.5 text-ink-secondary hover:text-ink transition-colors"
            title={theme === "light" ? "切换为深色主题" : "切换为浅色主题"}
            aria-label={theme === "light" ? "切换为深色主题" : "切换为浅色主题"}
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
            aria-label="退出登录"
            type="button"
          >
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* 移动端 tab */}
      <div className="md:hidden border-t border-line-subtle overflow-x-auto">
        <div className="flex gap-4 px-4 py-2 min-w-max">
          {DASHBOARD_NAV_ITEMS.map((item) => {
            const active = route === item.key;
            return (
              <button
                key={item.key}
                data-testid={`dashboard-route-mobile-${item.key}`}
                data-dashboard-route={item.key}
                aria-current={active ? "page" : undefined}
                onClick={() => onChangeRoute(item.key)}
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

      {/* 页面标题区 */}
      <div className="max-w-[1320px] mx-auto px-6 sm:px-10 py-6 border-b border-line">
        <div className="flex items-baseline justify-between flex-wrap gap-3 mb-3">
          <div className="flex items-baseline gap-3">
            <span className="text-[11px] font-mono uppercase tracking-[0.2em] text-accent">
              {routeIndex} / {routeLabel}
            </span>
            <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-ink-tertiary">
              {pageFocus}
            </span>
          </div>
          <span className="text-[10px] font-mono text-ink-tertiary">
            {new Date().toLocaleString("zh-CN", { hour12: false })}
          </span>
        </div>
        <h1 className="font-display text-4xl sm:text-5xl text-ink leading-tight tracking-tight">
          {routeLabel}
        </h1>
        <p className="text-sm text-ink-secondary mt-2 max-w-2xl">
          {routeDescription}
        </p>
      </div>

      {/* 状态条 */}
      <div className="max-w-[1320px] mx-auto px-6 sm:px-10 py-3 text-[11px] font-mono text-ink-secondary flex items-center gap-2 border-b border-line-subtle">
        <span
          className={`w-1 h-1 rounded-full ${
            wsConnected ? "bg-accent" : "bg-warning"
          }`}
        />
        {statusMessage}
      </div>
    </header>
  );
}
