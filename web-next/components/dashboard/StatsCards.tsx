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
    { label: "告警总数", value: String(stats.alertsTotal), color: "text-amber-400", border: "border-amber-400/30", bg: "bg-amber-400/5" },
    { label: "高危告警", value: String(stats.highRiskTotal), color: "text-rose-400", border: "border-rose-400/30", bg: "bg-rose-400/5" },
    { label: "自动拦截", value: String(stats.blockedTotal), color: "text-emerald-400", border: "border-emerald-400/30", bg: "bg-emerald-400/5" },
    { label: "站点状态", value: stats.siteHealthText, color: "text-cyber-cyan", border: "border-cyber-cyan/30", bg: "bg-cyber-cyan/5" },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {cards.map((card) => (
        <div
          key={card.label}
          className={`${card.bg} backdrop-blur border ${card.border} rounded-lg p-4 flex flex-col justify-center items-start hover:bg-white/[0.03] transition-colors relative overflow-hidden`}
        >
          <div className="absolute top-0 right-0 w-6 h-6 bg-gradient-to-bl from-white/[0.03] to-transparent" />
          <span className="text-xs uppercase tracking-widest text-slate-500 mb-2">{card.label}</span>
          <span className={`text-2xl md:text-3xl font-bold tracking-wider ${card.color}`}>{card.value}</span>
        </div>
      ))}
    </div>
  );
}
