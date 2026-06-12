"use client";

import { useEffect, useState, useRef } from "react";

type StatsCardsProps = {
  stats: {
    alertsTotal: number;
    highRiskTotal: number;
    blockedTotal: number;
    siteHealthText: string;
  };
};

function useCountUp(target: number, duration = 1200) {
  const [count, setCount] = useState(0);
  const prevTarget = useRef(0);
  const startTime = useRef<number | null>(null);

  useEffect(() => {
    if (target === prevTarget.current) return;
    prevTarget.current = target;
    startTime.current = null;

    const animate = (timestamp: number) => {
      if (!startTime.current) startTime.current = timestamp;
      const progress = Math.min((timestamp - startTime.current) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setCount(Math.floor(eased * target));

      if (progress < 1) {
        requestAnimationFrame(animate);
      }
    };

    requestAnimationFrame(animate);
  }, [target, duration]);

  return count;
}

interface CardConfig {
  label: string;
  value: string;
  tone: "default" | "warning" | "danger" | "success";
  index: string;
}

export default function StatsCards({ stats }: StatsCardsProps) {
  const alertsCount = useCountUp(stats.alertsTotal);
  const highRiskCount = useCountUp(stats.highRiskTotal);
  const blockedCount = useCountUp(stats.blockedTotal);

  const cards: CardConfig[] = [
    {
      label: "总告警",
      value: String(alertsCount),
      tone: "warning",
      index: "01",
    },
    {
      label: "高危告警",
      value: String(highRiskCount),
      tone: "danger",
      index: "02",
    },
    {
      label: "已拦截",
      value: String(blockedCount),
      tone: "success",
      index: "03",
    },
    {
      label: "站点状态",
      value: stats.siteHealthText,
      tone: "default",
      index: "04",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-line border border-line">
      {cards.map((card, index) => (
        <div
          key={card.label}
          className="bg-bg-raised p-6 sm:p-8"
          style={{
            animation: `fade-soft 320ms ${index * 60}ms cubic-bezier(0.16, 1, 0.3, 1) both`,
          }}
        >
          <div className="flex items-baseline justify-between mb-6">
            <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-ink-tertiary">
              {card.index}
            </span>
            <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary">
              {card.label}
            </span>
          </div>
          <div
            className={`font-display text-3xl sm:text-4xl md:text-5xl tracking-tight tabular-nums leading-none ${
              card.tone === "danger"
                ? "text-danger"
                : card.tone === "warning"
                  ? "text-warning"
                  : card.tone === "success"
                    ? "text-success"
                    : "text-ink"
            }`}
          >
            {card.value}
          </div>
        </div>
      ))}
    </div>
  );
}
