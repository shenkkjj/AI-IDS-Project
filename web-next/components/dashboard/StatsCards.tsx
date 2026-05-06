"use client";

import { useEffect, useState, useRef } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, ShieldCheck, Shield, Activity } from "lucide-react";

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

const cardVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: {
      delay: i * 0.1,
      duration: 0.5,
      ease: [0.25, 0.46, 0.45, 0.94] as [number, number, number, number],
    },
  }),
};

export default function StatsCards({ stats }: StatsCardsProps) {
  const alertsCount = useCountUp(stats.alertsTotal);
  const highRiskCount = useCountUp(stats.highRiskTotal);
  const blockedCount = useCountUp(stats.blockedTotal);

  const cards = [
    {
      label: "告警总数",
      value: String(alertsCount),
      color: "text-warning",
      bg: "bg-warning-subtle",
      icon: AlertTriangle,
    },
    {
      label: "高危告警",
      value: String(highRiskCount),
      color: "text-danger",
      bg: "bg-danger-subtle",
      icon: ShieldCheck,
    },
    {
      label: "自动拦截",
      value: String(blockedCount),
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
      {cards.map((card, index) => {
        const Icon = card.icon;
        return (
          <motion.div
            key={card.label}
            custom={index}
            variants={cardVariants}
            initial="hidden"
            animate="visible"
            whileHover={{ y: -4, transition: { duration: 0.2 } }}
            className="bg-surface rounded-apple-lg shadow-card p-5 flex flex-col justify-center items-start hover:shadow-card-hover transition-shadow duration-300 cursor-default"
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
          </motion.div>
        );
      })}
    </div>
  );
}
