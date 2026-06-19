import type { RouteKey } from "@/types/route";

export type DashboardRouteMeta = {
  key: RouteKey;
  label: string;
  index: string;
  description: string;
};

export const DASHBOARD_NAV_ITEMS: DashboardRouteMeta[] = [
  {
    key: "overview",
    label: "概览",
    index: "01",
    description: "全局安全态势、实时告警、AI 助手、配置与日报的综合视图。",
  },
  {
    key: "monitor",
    label: "监测",
    index: "02",
    description: "聚焦告警流、趋势图、终端输出与安全运营时间线。",
  },
  {
    key: "incidents",
    label: "案件",
    index: "03",
    description: "把分散告警归并为可追踪案件，推进处置状态并导出证据报告。",
  },
  {
    key: "waf",
    label: "WAF 管理",
    index: "04",
    description: "配置受保护站点、测试代理链路并确认威胁入库。",
  },
  {
    key: "ai",
    label: "AI 配置",
    index: "05",
    description: "管理 Copilot 会话、模型路由、Webhook 与通知渠道。",
  },
  {
    key: "report",
    label: "安全日报",
    index: "06",
    description: "查看由真实告警派生的安全日报与态势摘要。",
  },
];

export const DASHBOARD_ROUTE_META: Record<RouteKey, DashboardRouteMeta> =
  DASHBOARD_NAV_ITEMS.reduce(
    (acc, item) => {
      acc[item.key] = item;
      return acc;
    },
    {} as Record<RouteKey, DashboardRouteMeta>
  );

export function getDashboardRouteMeta(route: RouteKey): DashboardRouteMeta {
  return DASHBOARD_ROUTE_META[route];
}
