"use client";

import SectionHeading from "@/components/dashboard/SectionHeading";
import OperationalRunbookPanel from "@/components/dashboard/OperationalRunbookPanel";
import SystemStatusSection from "@/components/dashboard/SystemStatusSection";
import type {
  SiteTargetState,
  ThreatState,
} from "@/components/dashboard/SystemStatusSection";

export interface DashboardSystemStatusRouteSectionProps {
  siteTargetInput: string;
  onChangeTargetInput: (value: string) => void;
  onSaveTarget: () => void;
  targetSaving: boolean;
  siteState: SiteTargetState;
  proxyPathInput: string;
  onChangeProxyPath: (value: string) => void;
  onTestProxy: () => void;
  proxyTesting: boolean;
  threat: ThreatState;
  canConfirmThreat: boolean;
  onConfirmThreat: () => void;
  onToggleVoiceAlert: () => void;
  userEmail: string;
}

export default function DashboardSystemStatusRouteSection({
  siteTargetInput,
  onChangeTargetInput,
  onSaveTarget,
  targetSaving,
  siteState,
  proxyPathInput,
  onChangeProxyPath,
  onTestProxy,
  proxyTesting,
  threat,
  canConfirmThreat,
  onConfirmThreat,
  onToggleVoiceAlert,
  userEmail,
}: DashboardSystemStatusRouteSectionProps) {
  return (
    <div className="mt-14" data-testid="dashboard-section-system-status">
      <SectionHeading
        index="§ 04"
        title="站点监测与威胁确认"
        description="配置受保护站点、测试 WAF 链路、确认告警入库"
      />
      <SystemStatusSection
        siteTargetInput={siteTargetInput}
        onChangeTargetInput={onChangeTargetInput}
        onSaveTarget={onSaveTarget}
        targetSaving={targetSaving}
        siteState={siteState}
        proxyPathInput={proxyPathInput}
        onChangeProxyPath={onChangeProxyPath}
        onTestProxy={onTestProxy}
        proxyTesting={proxyTesting}
        threat={threat}
        canConfirmThreat={canConfirmThreat}
        onConfirmThreat={onConfirmThreat}
        onToggleVoiceAlert={onToggleVoiceAlert}
      />
      <div className="mt-8">
        <OperationalRunbookPanel siteState={siteState} userEmail={userEmail} />
      </div>
    </div>
  );
}
