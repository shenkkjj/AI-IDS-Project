"use client";

import dynamic from "next/dynamic";
import SectionHeading from "@/components/dashboard/SectionHeading";
import type { AlertItem } from "@/types/alert";

const AttackTrendChart = dynamic(
  () => import("@/components/dashboard/AttackTrendChart"),
  { ssr: false, loading: () => <div className="h-full bg-bg-raised/40 animate-pulse" /> }
);

const SourcePieChart = dynamic(
  () => import("@/components/dashboard/SourcePieChart"),
  { ssr: false, loading: () => <div className="h-full bg-bg-raised/40 animate-pulse" /> }
);

export interface DashboardTrendsSectionProps {
  alerts: AlertItem[];
}

export default function DashboardTrendsSection({
  alerts,
}: DashboardTrendsSectionProps) {
  return (
    <div className="mt-14" data-testid="dashboard-section-trends">
      <SectionHeading
        index="§ 01"
        title="攻击趋势与分布"
        description="近 24 时段攻击曲线 + 风险级别与来源 TOP 6"
      />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="h-[300px]">
          <AttackTrendChart alerts={alerts} />
        </div>
        <div className="h-[300px]">
          <SourcePieChart alerts={alerts} />
        </div>
      </div>
    </div>
  );
}
