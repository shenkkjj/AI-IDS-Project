"use client";

import SecurityTimelinePanel from "@/components/dashboard/SecurityTimelinePanel";
import SectionHeading from "@/components/dashboard/SectionHeading";
import type { SecurityTimelineItem } from "@/types/securityTimeline";

export interface DashboardSecurityTimelineSectionProps {
  items: SecurityTimelineItem[];
  loadState: "loading" | "ready" | "empty" | "error";
  degraded: boolean;
  limit: number;
  offline: boolean;
  onRefresh: () => void;
}

export default function DashboardSecurityTimelineSection({
  items,
  loadState,
  degraded,
  limit,
  offline,
  onRefresh,
}: DashboardSecurityTimelineSectionProps) {
  return (
    <div className="mt-14" data-testid="dashboard-section-security-timeline">
      <SectionHeading
        index="§ 03.5"
        title="安全运营时间线"
        description="Demo 攻击 / Copilot / 护栏 / 认证 / 配置摘要"
      />
      <div className="min-h-[280px]">
        <SecurityTimelinePanel
          items={items}
          loadState={loadState}
          degraded={degraded}
          limit={limit}
          offline={offline}
          onRefresh={onRefresh}
        />
      </div>
    </div>
  );
}
