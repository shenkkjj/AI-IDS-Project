"use client";

import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import StatusView, { buildRetryAction } from "./StatusView";

/**
 * 告警区：左侧列表 + 右侧详情。
 *
 * 接管了原 § 02 段中分散的 loading/empty/error 三态,
 * 现在统一由 StatusView 渲染。
 *
 * 不在内部做 fetch/refresh；调用方传入 `loadState` 即可。
 */
export interface AlertSectionProps {
  loadState: "loading" | "ready" | "empty" | "error";
  wsConnected: boolean;
  totalAlerts: number;
  totalPages: number;
  page: number;
  listSlot: ReactNode;
  detailSlot: ReactNode;
  onPrevPage: () => void;
  onNextPage: () => void;
  onRefresh: () => void;
  onRetry?: () => void;
  /** 顶部右侧 demo flow 工具条 */
  toolbarSlot: ReactNode;
}

function isOfflineTone(wsConnected: boolean, loadState: AlertSectionProps["loadState"]) {
  return !wsConnected && loadState === "error";
}

export default function AlertSection({
  loadState,
  wsConnected,
  totalAlerts,
  totalPages,
  page,
  listSlot,
  detailSlot,
  onPrevPage,
  onNextPage,
  onRefresh,
  onRetry,
  toolbarSlot,
}: AlertSectionProps) {
  const offline = isOfflineTone(wsConnected, loadState);
  const showEmpty = !offline && loadState === "empty";
  const showError = !offline && loadState === "error";
  const showLoading = loadState === "loading";

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <div className="lg:col-span-2 min-h-[480px] flex flex-col">
        <div className="flex items-center justify-between gap-3 mb-4">
          <div className="flex items-baseline gap-2 min-w-0">
            <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary">
              实时告警流
            </span>
            <span className="text-[10px] font-mono text-ink-tertiary">
              · {totalAlerts} 条 · {wsConnected ? "WebSocket 实时" : "轮询刷新"}
            </span>
          </div>
          <div className="flex items-center gap-2 min-w-0">{toolbarSlot}</div>
        </div>

        <div className="flex-1 min-h-0 border-t border-line flex flex-col">
          {offline ? (
            <StatusView
              tone="offline"
              title="WebSocket 已断开"
              description="实时通道不可用,正在以轮询模式刷新告警。可点击刷新手动拉取最新。"
              action={buildRetryAction(onRefresh, "刷新告警")}
              minHeight={320}
            />
          ) : showLoading ? (
            <StatusView tone="loading" title="告警加载中..." minHeight={320} />
          ) : showError ? (
            <StatusView
              tone="error"
              title="告警加载失败"
              description="请检查登录态与后端服务。点击重试将重新拉取最近 100 条告警。"
              action={buildRetryAction(onRetry || onRefresh)}
              minHeight={320}
            />
          ) : showEmpty ? (
            <StatusView
              tone="empty"
              title="暂无告警"
              description="系统当前没有检测到异常流量。可以使用右侧的「触发 Demo 攻击」按钮快速验证告警链路。"
              action={buildRetryAction(onRefresh, "重新拉取")}
              minHeight={320}
            />
          ) : (
            <div className="flex-1 flex flex-col min-h-0">
              <div className="flex-1 min-h-0 overflow-y-auto">{listSlot}</div>
              {totalPages > 1 ? (
                <div className="flex items-center justify-center gap-4 pt-4 mt-4 border-t border-line-subtle text-xs">
                  <button
                    onClick={onPrevPage}
                    disabled={page === 0}
                    className="text-ink-secondary hover:text-ink disabled:opacity-30 transition-colors font-mono"
                  >
                    ← 上一页
                  </button>
                  <span className="font-mono text-ink-tertiary tabular-nums">
                    {page + 1} / {totalPages}
                  </span>
                  <button
                    onClick={onNextPage}
                    disabled={page >= totalPages - 1}
                    className="text-ink-secondary hover:text-ink disabled:opacity-30 transition-colors font-mono"
                  >
                    下一页 →
                  </button>
                </div>
              ) : null}
            </div>
          )}
        </div>
      </div>

      <div className="min-h-[480px] flex flex-col">
        {showError ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 text-sm text-danger">
            <span>告警加载失败</span>
            <Button variant="outline" size="sm" onClick={onRetry || onRefresh}>
              重试
            </Button>
          </div>
        ) : showLoading ? (
          <StatusView tone="loading" title="告警详情加载中..." minHeight={420} />
        ) : showEmpty ? (
          <StatusView tone="empty" title="暂无告警可分析" minHeight={420} />
        ) : (
          detailSlot
        )}
      </div>
    </div>
  );
}
