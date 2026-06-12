"use client";

import { useMemo } from "react";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

type AlertItem = {
  id: string;
  source: string;
  target: string;
  risk: string;
};

// Mercury 暖色 + Linear 紫的克制 palette
const COLORS: Record<string, string> = {
  critical: "#B91C1C",
  high: "#B45309",
  medium: "#1D4ED8",
  low: "#15803D",
};

const RISK_LABELS: Record<string, string> = {
  critical: "严重",
  high: "高危",
  medium: "中危",
  low: "低危",
};

export default function SourcePieChart({ alerts }: { alerts: AlertItem[] }) {
  const riskData = useMemo(() => {
    if (alerts.length === 0) return [];
    const counter = new Map<string, number>();
    for (const item of alerts) {
      counter.set(item.risk, (counter.get(item.risk) || 0) + 1);
    }
    return Array.from(counter.entries())
      .map(([risk, count]) => ({
        name: RISK_LABELS[risk] || risk,
        value: count,
        color: COLORS[risk] || "#8A8A86",
      }))
      .sort((a, b) => b.value - a.value);
  }, [alerts]);

  const sourceData = useMemo(() => {
    if (alerts.length === 0) return [];
    const counter = new Map<string, number>();
    for (const item of alerts) {
      const src = item.source || "unknown";
      counter.set(src, (counter.get(src) || 0) + 1);
    }
    const top = Array.from(counter.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6);
    const other = Array.from(counter.entries())
      .slice(6)
      .reduce((sum, [, c]) => sum + c, 0);
    const result = top.map(([name, value]) => ({ name, value }));
    if (other > 0) result.push({ name: "其他", value: other });
    return result;
  }, [alerts]);

  if (alerts.length === 0) {
    return (
      <div className="h-full min-h-[180px] flex items-center justify-center text-ink-tertiary text-xs font-mono">
        暂无分布数据
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 h-full">
      <div className="flex-1 min-h-0">
        <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary mb-1">
          风险级别
        </div>
        <ResponsiveContainer width="100%" height="85%">
          <PieChart>
            <Pie
              data={riskData}
              cx="50%"
              cy="50%"
              innerRadius={36}
              outerRadius={60}
              paddingAngle={2}
              dataKey="value"
              stroke="#FBFAF7"
              strokeWidth={2}
            >
              {riskData.map((entry, index) => (
                <Cell key={index} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: "#FFFFFF",
                border: "1px solid #E5E1D5",
                borderRadius: "6px",
                fontSize: 11,
                color: "#0A0A0A",
                fontFamily: "JetBrains Mono",
                boxShadow: "0 4px 12px rgba(10, 10, 10, 0.08)",
              }}
            />
            <Legend
              wrapperStyle={{ fontSize: 10, color: "#4A4A48", fontFamily: "JetBrains Mono" }}
              iconSize={6}
              formatter={(value: string) => <span style={{ color: "#4A4A48" }}>{value}</span>}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="flex-1 min-h-0">
        <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary mb-1">
          Top 攻击来源
        </div>
        <ResponsiveContainer width="100%" height="85%">
          <PieChart>
            <Pie
              data={sourceData}
              cx="50%"
              cy="50%"
              outerRadius={60}
              paddingAngle={1}
              dataKey="value"
              stroke="#FBFAF7"
              strokeWidth={1}
              label={({ name, percent }) => {
                const n = String(name || "");
                const p = Number(percent || 0);
                const shortName = n.length > 10 ? n.slice(0, 10) + "…" : n;
                return `${shortName} ${(p * 100).toFixed(0)}%`;
              }}
              labelLine={{ stroke: "#D6D1C2", strokeWidth: 0.5 }}
            >
              {sourceData.map((_, index) => (
                <Cell
                  key={index}
                  fill={`hsla(${(index * 47 + 25) % 360}, 30%, 50%, 0.85)`}
                />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: "#FFFFFF",
                border: "1px solid #E5E1D5",
                borderRadius: "6px",
                fontSize: 11,
                color: "#0A0A0A",
                fontFamily: "JetBrains Mono",
                boxShadow: "0 4px 12px rgba(10, 10, 10, 0.08)",
              }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
