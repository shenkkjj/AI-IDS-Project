"use client";

import IncidentSection from "@/components/dashboard/IncidentSection";
import SectionHeading from "@/components/dashboard/SectionHeading";
import type { IncidentsController } from "@/hooks/useIncidents";

export interface DashboardIncidentWorkspaceSectionProps {
  incidents: IncidentsController;
}

export default function DashboardIncidentWorkspaceSection({
  incidents,
}: DashboardIncidentWorkspaceSectionProps) {
  return (
    <div className="mt-8 sm:mt-14" data-testid="dashboard-section-incidents">
      <SectionHeading
        index="§ 03.7"
        title="安全事件 / 案件工作台"
        description="把分散告警归并为可追踪案件,推进处置状态、记录备注并保留脱敏审计时间线。"
      />
      <div className="p-6 bg-bg-raised border-l border-accent rounded-md">
        <IncidentSection incidents={incidents} />
      </div>
    </div>
  );
}
