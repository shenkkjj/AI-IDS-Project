"use client";

import CopilotSection from "@/components/dashboard/CopilotSection";
import SectionHeading from "@/components/dashboard/SectionHeading";
import type { CopilotMessage } from "@/types/copilot";

export interface DashboardCopilotRouteSectionProps {
  messages: CopilotMessage[];
  draft: string;
  sending: boolean;
  contextLabel?: string;
  degraded?: boolean;
  offline: boolean;
  onDraftChange: (value: string) => void;
  onSend: () => void;
  onAnalyzeAlert?: () => void;
}

export default function DashboardCopilotRouteSection({
  messages,
  draft,
  sending,
  contextLabel,
  degraded = false,
  offline,
  onDraftChange,
  onSend,
  onAnalyzeAlert,
}: DashboardCopilotRouteSectionProps) {
  return (
    <div className="mt-14" data-testid="dashboard-section-copilot">
      <SectionHeading
        index="§ 04.5"
        title="AI 助手上下文"
        description="Copilot 当前上下文、降级态与会话摘要"
      />
      <div className="min-h-[480px]">
        <CopilotSection
          messages={messages}
          draft={draft}
          sending={sending}
          contextLabel={contextLabel}
          degraded={degraded}
          offline={offline}
          onDraftChange={onDraftChange}
          onSend={onSend}
          onAnalyzeAlert={onAnalyzeAlert}
        />
      </div>
    </div>
  );
}
