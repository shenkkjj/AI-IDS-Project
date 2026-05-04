"use client";

import { useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

type AlertRisk = "critical" | "high" | "medium" | "low";

type AlertItem = {
  id: string;
  alertId: string;
  source: string;
  target: string;
  risk: AlertRisk;
  payload: string;
  summary: string;
  timestamp: number | null;
  blocked: boolean;
};

type TrendPoint = {
  time: string;
  total: number;
  critical: number;
  high: number;
};

function formatTimeLabel(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function AttackTrendChart({ alerts }: { alerts: AlertItem[] }) {
  const data: TrendPoint[] = useMemo(() => {
    const valid = alerts.filter((a) => Number.isFinite(a.timestamp) && (a.timestamp ?? 0) > 0);
    if (valid.length === 0) return [];

    const sorted = [...valid].sort((a, b) => (a.timestamp ?? 0) - (b.timestamp ?? 0));
    const buckets = new Map<number, TrendPoint>();

    for (const item of sorted) {
      const bucket = Math.floor((item.timestamp ?? 0) / 300) * 300;
      if (!buckets.has(bucket)) {
        buckets.set(bucket, { time: formatTimeLabel(bucket), total: 0, critical: 0, high: 0 });
      }
      const p = buckets.get(bucket)!;
      p.total++;
      if (item.risk === "critical") p.critical++;
      if (item.risk === "high") p.high++;
    }

    return Array.from(buckets.values()).slice(-24);
  }, [alerts]);

  if (data.length === 0) {
    return (
      <div className="h-full min-h-[180px] flex items-center justify-center text-cyber-text/50 text-xs">
        暂无趋势数据
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,245,255,0.08)" />
        <XAxis
          dataKey="time"
          tick={{ fontSize: 10, fill: "rgba(200,220,240,0.6)" }}
          axisLine={{ stroke: "rgba(0,245,255,0.15)" }}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 10, fill: "rgba(200,220,240,0.6)" }}
          axisLine={false}
          tickLine={false}
          allowDecimals={false}
        />
        <Tooltip
          contentStyle={{
            background: "rgba(0,0,0,0.85)",
            border: "1px solid rgba(0,245,255,0.3)",
            fontSize: 12,
            color: "#c8dcf0",
          }}
        />
        <Line
          type="monotone"
          dataKey="total"
          stroke="rgba(0,245,255,0.7)"
          strokeWidth={1.5}
          dot={false}
          name="总计"
        />
        <Line
          type="monotone"
          dataKey="critical"
          stroke="rgba(255,50,50,0.7)"
          strokeWidth={1.5}
          dot={false}
          name="严重"
        />
        <Line
          type="monotone"
          dataKey="high"
          stroke="rgba(255,180,0,0.7)"
          strokeWidth={1.5}
          dot={false}
          name="高危"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
