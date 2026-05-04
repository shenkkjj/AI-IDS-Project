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

const COLORS: Record<string, string> = {
  critical: "rgba(255,50,50,0.85)",
  high: "rgba(255,180,0,0.85)",
  medium: "rgba(0,200,255,0.75)",
  low: "rgba(100,200,100,0.65)",
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
        color: COLORS[risk] || "#666",
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
      <div className="h-full min-h-[180px] flex items-center justify-center text-cyber-text/50 text-xs">
        暂无分布数据
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 h-full">
      <div className="flex-1 min-h-0">
        <div className="text-[10px] uppercase tracking-wider text-cyber-text/50 mb-1">风险级别分布</div>
        <ResponsiveContainer width="100%" height="85%">
          <PieChart>
            <Pie
              data={riskData}
              cx="50%"
              cy="50%"
              innerRadius={28}
              outerRadius={50}
              paddingAngle={3}
              dataKey="value"
            >
              {riskData.map((entry, index) => (
                <Cell key={index} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: "rgba(0,0,0,0.85)",
                border: "1px solid rgba(0,245,255,0.3)",
                fontSize: 12,
                color: "#c8dcf0",
              }}
            />
            <Legend
              wrapperStyle={{ fontSize: 10, color: "rgba(200,220,240,0.6)" }}
              iconSize={6}
              formatter={(value: string) => <span style={{ color: "rgba(200,220,240,0.7)" }}>{value}</span>}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="flex-1 min-h-0">
        <div className="text-[10px] uppercase tracking-wider text-cyber-text/50 mb-1">Top 攻击来源</div>
        <ResponsiveContainer width="100%" height="85%">
          <PieChart>
            <Pie
              data={sourceData}
              cx="50%"
              cy="50%"
              outerRadius={50}
              paddingAngle={2}
              dataKey="value"
              label={({ name, percent }) => {
                const n = String(name || "");
                const p = Number(percent || 0);
                const shortName = n.length > 10 ? n.slice(0, 10) + "…" : n;
                return `${shortName} ${(p * 100).toFixed(0)}%`;
              }}
              labelLine={{ stroke: "rgba(0,245,255,0.25)", strokeWidth: 0.5 }}
            >
              {sourceData.map((_, index) => (
                <Cell
                  key={index}
                  fill={`hsla(${(index * 57) % 360}, 60%, 55%, 0.75)`}
                />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: "rgba(0,0,0,0.85)",
                border: "1px solid rgba(0,245,255,0.3)",
                fontSize: 12,
                color: "#c8dcf0",
              }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
