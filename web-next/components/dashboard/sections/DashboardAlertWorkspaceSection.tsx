"use client";

import type { ReactNode } from "react";
import AlertSection from "@/components/dashboard/AlertSection";
import DemoFlowControls from "@/components/dashboard/DemoFlowControls";
import SectionHeading from "@/components/dashboard/SectionHeading";

export interface DashboardAlertWorkspaceSectionProps {
  loadState: "loading" | "ready" | "empty" | "error";
  wsConnected: boolean;
  totalAlerts: number;
  totalPages: number;
  page: number;
  selectedCountLabel: string;
  demoState: "idle" | "running" | "success" | "error";
  demoMessage: string;
  listSlot: ReactNode;
  detailSlot: ReactNode;
  onPrevPage: () => void;
  onNextPage: () => void;
  onRefresh: () => void;
  onRetry: () => void;
  onTriggerDemo: () => void;
  onExportCsv: () => void;
}

export default function DashboardAlertWorkspaceSection({
  loadState,
  wsConnected,
  totalAlerts,
  totalPages,
  page,
  selectedCountLabel,
  demoState,
  demoMessage,
  listSlot,
  detailSlot,
  onPrevPage,
  onNextPage,
  onRefresh,
  onRetry,
  onTriggerDemo,
  onExportCsv,
}: DashboardAlertWorkspaceSectionProps) {
  return (
    <div className="mt-14" data-testid="dashboard-section-alerts">
      <SectionHeading
        index="§ 02"
        title="实时告警、详情与 AI 助手"
        description={selectedCountLabel}
      />
      <AlertSection
        loadState={loadState}
        wsConnected={wsConnected}
        totalAlerts={totalAlerts}
        totalPages={totalPages}
        page={page}
        listSlot={listSlot}
        detailSlot={detailSlot}
        onPrevPage={onPrevPage}
        onNextPage={onNextPage}
        onRefresh={onRefresh}
        onRetry={onRetry}
        toolbarSlot={
          <DemoFlowControls
            demoState={demoState}
            demoMessage={demoMessage}
            onTriggerDemo={onTriggerDemo}
            onExportCsv={onExportCsv}
            onRefreshAlerts={onRefresh}
          />
        }
      />
    </div>
  );
}
