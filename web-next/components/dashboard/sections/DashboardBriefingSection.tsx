"use client";

import BriefingSection from "@/components/dashboard/BriefingSection";
import SectionHeading from "@/components/dashboard/SectionHeading";
import type { AlertItem } from "@/types/alert";

export interface DashboardBriefingSectionProps {
  alerts: AlertItem[];
}

export default function DashboardBriefingSection({
  alerts,
}: DashboardBriefingSectionProps) {
  return (
    <div className="mt-8 sm:mt-14" data-testid="dashboard-section-briefing">
      <SectionHeading
        index="§ 00"
        title="日 / 周安全简报"
        description="基于当前告警流自动派生的态势指标。所有数据均来自真实告警记录,严禁伪造。"
      />
      <div className="p-6 bg-bg-raised border-l border-accent rounded-md">
        <BriefingSection alerts={alerts} />
      </div>
    </div>
  );
}
