"use client";

import { RefreshCw } from "lucide-react";
import HackerTerminal from "@/components/dashboard/HackerTerminal";
import SectionHeading from "@/components/dashboard/SectionHeading";

export interface DashboardTerminalReportSectionProps {
  logs: string[];
  markdown: string;
  typing: boolean;
  onCommand: (command: string) => void;
  onRefreshReport: () => void;
}

export default function DashboardTerminalReportSection({
  logs,
  markdown,
  typing,
  onCommand,
  onRefreshReport,
}: DashboardTerminalReportSectionProps) {
  return (
    <div className="mt-14" data-testid="dashboard-section-terminal-report">
      <SectionHeading
        index="§ 03"
        title="终端与安全日报"
        description="实时命令输出 + 告警日报"
        action={
          <button
            onClick={onRefreshReport}
            className="text-[10px] font-mono uppercase tracking-[0.15em] text-accent hover:text-accent-hover transition-colors flex items-center gap-1.5"
            type="button"
          >
            <RefreshCw className={`w-3 h-3 ${typing ? "animate-spin" : ""}`} />
            刷新日报
          </button>
        }
      />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="min-h-[320px]">
          <HackerTerminal lines={logs} onCommand={onCommand} />
        </div>
        <div className="min-h-[320px] p-5 bg-bg-raised border-l border-accent">
          <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-accent mb-3">
            日报 · 摘要
          </div>
          <pre className="whitespace-pre-wrap text-xs leading-6 text-ink-secondary font-mono overflow-y-auto max-h-[260px]">
            {markdown}
          </pre>
        </div>
      </div>
    </div>
  );
}
