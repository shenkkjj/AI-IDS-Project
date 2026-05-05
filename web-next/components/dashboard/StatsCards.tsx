"use client";

import { AlertTriangle, ShieldCheck, Shield, Activity } from "lucide-react";

type StatsCardsProps = {
  stats: {
    alertsTotal: number;
    highRiskTotal: number;
    blockedTotal: number;
    siteHealthText: string;
  };
};

export default function StatsCards({ stats }: StatsCardsProps) {
  const cards = [
    {
      label: "告警总数",
      value: String(stats.alertsTotal),
      color: "text-warning",
      bg: "bg-warning-subtle",
      icon: AlertTriangle,
    },
    {
      label: "高危告警",
      value: String(stats.highRiskTotal),
      color: "text-danger",
      bg: "bg-danger-subtle",
      icon: ShieldCheck,
    },
    {
      label: "自动拦截",
      value: String(stats.blockedTotal),
      color: "text-success",
      bg: "bg-success-subtle",
      icon: Shield,
    },
    {
      label: "站点状态",
      value: stats.siteHealthText,
      color: "text-primary",
      bg: "bg-primary-subtle",
      icon: Activity,
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <div
            key={card.label}
            className="bg-surface rounded-apple-lg shadow-card p-5 flex flex-col justify-center items-start hover:shadow-card-hover transition-shadow duration-300"
          >
            <div className="flex items-center gap-2 mb-3">
              <div className={`w-8 h-8 ${card.bg} rounded-apple flex items-center justify-center`}>
                <Icon className={`w-4 h-4 ${card.color}`} />
              </div>
              <span className="text-xs font-medium text-text-secondary uppercase tracking-wider">
                {card.label}
              </span>
            </div>
            <span className={`text-2xl md:text-3xl font-bold tracking-tight ${card.color}`}>
              {card.value}
            </span>
          </div>
        );
      })}
    </div>
  );
}
