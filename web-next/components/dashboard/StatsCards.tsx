"use client";

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
      color: "text-[#FF9500]",
      bg: "bg-[#FFF4E5]",
      icon: "⚠️"
    },
    { 
      label: "高危告警", 
      value: String(stats.highRiskTotal), 
      color: "text-[#FF3B30]",
      bg: "bg-[#FFE5E3]",
      icon: "🔴"
    },
    { 
      label: "自动拦截", 
      value: String(stats.blockedTotal), 
      color: "text-[#34C759]",
      bg: "bg-[#E5F8EA]",
      icon: "🛡️"
    },
    { 
      label: "站点状态", 
      value: stats.siteHealthText, 
      color: "text-[#0071E3]",
      bg: "bg-[#E8F4FD]",
      icon: "📊"
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {cards.map((card) => (
        <div
          key={card.label}
          className="bg-white rounded-[18px] shadow-card p-5 flex flex-col justify-center items-start hover:shadow-card-hover transition-shadow"
        >
          <div className="flex items-center gap-2 mb-3">
            <div className={`w-8 h-8 ${card.bg} rounded-[10px] flex items-center justify-center text-sm`}>
              {card.icon}
            </div>
            <span className="text-xs font-medium text-[#86868B] uppercase tracking-wider">{card.label}</span>
          </div>
          <span className={`text-2xl md:text-3xl font-bold tracking-tight ${card.color}`}>{card.value}</span>
        </div>
      ))}
    </div>
  );
}
