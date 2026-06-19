"use client";

import { useEffect } from "react";
import type { IncidentsController } from "@/hooks/useIncidents";
import IncidentList from "./IncidentList";
import IncidentDetailPanel from "./IncidentDetailPanel";
import StatusView from "./StatusView";
import type { IncidentSeverity, IncidentStatus } from "@/types/incident";

/**
 * 安全事件 / 案件工作台 (M3-04, M3-09 单一事实源版本)。
 *
 * M3-09: incident state 由 dashboard-client.tsx 父层持有(`useIncidents()`),
 * 通过 props 注入,确保从告警创建案件后,列表 / selectedIncident / detail /
 * 报告导出共享同一份 state,不再需要 E2E 点击 incident-list-item 兜底。
 */
export interface IncidentSectionProps {
  /** 父层共享的 incidents controller(必传)。 */
  incidents: IncidentsController;
  /** 起始选中的 incident_id(由父组件控制,如从告警详情跳转) */
  initialIncidentId?: string | null;
  /** "创建案件"快捷入口的回调,父组件可提供"从选中告警创建"的能力 */
  renderCreateShortcut?: (args: {
    defaultTitle: string;
    defaultSeverity: IncidentSeverity;
    onCreate: (input: {
      title: string;
      summary?: string | null;
      severity: IncidentSeverity;
      alert_id?: string | null;
    }) => Promise<boolean>;
  }) => React.ReactNode;
}

export default function IncidentSection({
  incidents,
  initialIncidentId,
  renderCreateShortcut,
}: IncidentSectionProps) {
  // 初次进入加载列表(父层可能已经创建过案件并乐观写入 incidentItems,
  // 这里仍刷新以保持服务端一致)。
  useEffect(() => {
    void incidents.loadIncidents({ limit: 50 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 选中 / 切换 incident 时加载 detail。
  // M3-09: 已经 ready 且 id 一致时跳过,避免重复拉取造成闪烁。
  useEffect(() => {
    const id = incidents.selectedIncident?.incident_id || initialIncidentId;
    if (!id) return;
    if (
      incidents.detail?.incident.incident_id === id &&
      incidents.detailState === "ready"
    ) {
      return;
    }
    void incidents.loadIncidentDetail(id, { eventLimit: 20 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    incidents.selectedIncident?.incident_id,
    initialIncidentId,
    incidents.detail?.incident.incident_id,
    incidents.detailState,
  ]);

  return (
    <div
      data-testid="incident-section"
      className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-6"
    >
      <div className="space-y-4">
        {/* 顶部工具栏 */}
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-accent mb-1">
              CASES
            </div>
            <h3 className="font-display text-lg text-ink">案件列表</h3>
          </div>
          <button
            type="button"
            data-testid="incident-refresh"
            onClick={() => void incidents.loadIncidents({ limit: 50 })}
            className="text-[10px] font-mono uppercase tracking-[0.15em] text-accent hover:text-accent-hover border border-line px-2 py-1 transition-colors"
            disabled={incidents.loadState === "loading"}
          >
            {incidents.loadState === "loading" ? "加载中" : "刷新"}
          </button>
        </div>

        {/* 创建入口(由父组件注入;默认不渲染) */}
        {renderCreateShortcut
          ? renderCreateShortcut({
              defaultTitle: "新案件",
              defaultSeverity: "medium",
              onCreate: async (input) => {
                const result = await incidents.createIncidentFromAlert(input);
                if (result.ok) {
                  await incidents.loadIncidentDetail(
                    result.incident!.incident_id,
                    { eventLimit: 20 }
                  );
                }
                return result.ok;
              },
            })
          : null}

        <IncidentList
          items={incidents.incidentItems}
          loadState={incidents.loadState}
          selectedId={incidents.selectedIncident?.incident_id ?? null}
          onSelect={(incident) => {
            incidents.setSelectedIncident(incident);
          }}
        />
      </div>

      <div>
        {incidents.detailState === "loading" ? (
          <StatusView
            tone="empty"
            title="加载中"
            description="正在加载案件详情…"
            minHeight={260}
          />
        ) : incidents.detail && incidents.selectedIncident ? (
          <IncidentDetailPanel
            detail={incidents.detail}
            actionState={incidents.actionState}
            error={incidents.error}
            onUpdate={(input) =>
              incidents.updateIncident(
                incidents.selectedIncident!.incident_id,
                input
              )
            }
            onLinkAlert={(alertId) =>
              incidents.linkAlert(incidents.selectedIncident!.incident_id, alertId)
            }
            onUnlinkAlert={(alertId) =>
              incidents.unlinkAlert(
                incidents.selectedIncident!.incident_id,
                alertId
              )
            }
            onRefresh={() =>
              incidents.loadIncidentDetail(
                incidents.selectedIncident!.incident_id,
                { eventLimit: 20 }
              )
            }
            onLoadReport={(incidentId) =>
              incidents.loadIncidentReport(incidentId)
            }
          />
        ) : (
          <StatusView
            tone="empty"
            title="未选择案件"
            description="从左侧列表中选择一条案件,或创建一个新案件以开始工作。"
            minHeight={260}
          />
        )}
      </div>
    </div>
  );
}

export type IncidentStatusFilter = IncidentStatus | "all";
