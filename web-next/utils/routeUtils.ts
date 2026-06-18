import type { RouteKey } from "@/types/route";

export function routeDescription(route: RouteKey): string {
  if (route === "overview") return "总览态势、告警与联动操作";
  if (route === "monitor") return "实时监测与日志链路";
  if (route === "waf") return "WAF 与代理防护策略";
  if (route === "ai") return "AI 模型路由与参数配置";
  if (route === "incidents") return "安全事件 / 案件工作台";
  return "安全日报生成与归档";
}
