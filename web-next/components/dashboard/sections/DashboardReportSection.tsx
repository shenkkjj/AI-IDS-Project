"use client";

import SectionHeading from "@/components/dashboard/SectionHeading";

export interface DashboardReportSectionProps {
  markdown: string;
}

export default function DashboardReportSection({
  markdown,
}: DashboardReportSectionProps) {
  return (
    <div className="mt-14" data-testid="dashboard-section-report">
      <SectionHeading
        index="§ 07"
        title="日报摘要"
        description="当前告警态势汇总"
      />
      <div className="p-6 bg-bg-raised border-l border-accent rounded-md">
        <pre className="whitespace-pre-wrap text-xs leading-6 text-ink-secondary font-mono overflow-y-auto max-h-[480px]">
          {markdown}
        </pre>
      </div>
    </div>
  );
}
