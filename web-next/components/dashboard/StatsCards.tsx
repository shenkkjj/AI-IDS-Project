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
    { label: "告警总数", value: String(stats.alertsTotal), color: "text-cyber-orange", border: "border-cyber-orange/40" },
    { label: "高危告警", value: String(stats.highRiskTotal), color: "text-red-400", border: "border-red-400/40" },
    { label: "自动拦截", value: String(stats.blockedTotal), color: "text-green-400", border: "border-green-400/40" },
    { label: "站点状态", value: stats.siteHealthText, color: "text-cyber-cyan", border: "border-cyber-cyan/40" },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {cards.map((card) => (
        <div
          key={card.label}
          className={`bg-black/30 backdrop-blur border ${card.border} p-4 flex flex-col justify-center items-start hover:bg-black/50 transition-colors relative overflow-hidden`}
        >
          <div className="absolute top-0 right-0 w-8 h-8 bg-gradient-to-bl from-white/5 to-transparent" />
          <span className="text-xs uppercase tracking-widest text-cyber-text/60 mb-2">{card.label}</span>
          <span className={`text-2xl md:text-3xl font-bold tracking-wider ${card.color} drop-shadow-md`}>{card.value}</span>
        </div>
      ))}
    </div>
  );
}
