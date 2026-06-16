"use client";

import { useState } from "react";

/**
 * Demo Flow 工具条：触发 Demo 攻击 / 刷新 / 导出 CSV。
 *
 * - 接收 `state` 渲染对应按钮文案,避免 dashboard-client 内嵌条件判断。
 * - 接收 `message` 显示在右侧（可选）。
 * - 不在内部发请求；事件向上传递给 dashboard-client。
 */
export interface DemoFlowControlsProps {
  /** 当前 demo 状态机 */
  demoState: "idle" | "running" | "success" | "error";
  /** 状态机对应的提示文本,会被截断显示在右侧 */
  demoMessage: string;
  /** 触发 demo 攻击 */
  onTriggerDemo: () => void;
  /** 导出 CSV */
  onExportCsv: () => void;
  /** 手动刷新告警 */
  onRefreshAlerts: () => void;
}

export default function DemoFlowControls({
  demoState,
  demoMessage,
  onTriggerDemo,
  onExportCsv,
  onRefreshAlerts,
}: DemoFlowControlsProps) {
  const [expanded, setExpanded] = useState(false);
  const triggerLabel =
    demoState === "running"
      ? "触发中"
      : demoState === "success"
        ? "Demo 已生成"
        : demoState === "error"
          ? "重试 Demo"
          : "触发 Demo 攻击";

  return (
    <div className="flex items-center gap-3 min-w-0">
      <button
        onClick={onTriggerDemo}
        disabled={demoState === "running"}
        data-testid="trigger-demo-attack"
        className="text-[10px] font-mono uppercase tracking-[0.15em] text-accent hover:text-accent-hover disabled:opacity-30 transition-colors"
      >
        {triggerLabel}
      </button>
      <button
        onClick={onExportCsv}
        data-testid="export-alerts-csv"
        className="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-secondary hover:text-ink transition-colors"
      >
        导出 CSV
      </button>
      <button
        onClick={onRefreshAlerts}
        data-testid="refresh-alerts"
        className="text-[10px] font-mono uppercase tracking-[0.15em] text-accent hover:text-accent-hover transition-colors"
      >
        刷新
      </button>
      <button
        onClick={() => setExpanded((prev) => !prev)}
        className="hidden xl:inline text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary hover:text-ink-secondary transition-colors"
        type="button"
        aria-label="显示或隐藏 demo 状态消息"
      >
        {expanded ? "收起" : "详情"}
      </button>
      <span
        className={`hidden ${expanded ? "xl:inline" : "xl:inline"} max-w-[280px] truncate text-[10px] font-mono text-ink-tertiary`}
        title={demoMessage}
      >
        {demoMessage}
      </span>
    </div>
  );
}
