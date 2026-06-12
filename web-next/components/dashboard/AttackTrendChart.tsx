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
    hour12: false,
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
      <div className="h-full min-h-[180px] flex items-center justify-center text-ink-tertiary text-xs font-mono">
        暂无趋势数据
      </div>
    );
  }

  const latestIndex = data.length - 1;

  const renderLatestDot = (props: { cx?: number; cy?: number; index?: number }) => {
    const { cx, cy, index } = props;
    if (typeof cx !== "number" || typeof cy !== "number" || index !== latestIndex) {
      return null;
    }
    return (
      <g>
        <circle
          cx={cx}
          cy={cy}
          r={4}
          fill="none"
          stroke="#5E6AD2"
          strokeWidth={1.2}
          className="animate-ripple-out"
        />
        <circle
          cx={cx}
          cy={cy}
          r={4}
          fill="none"
          stroke="#5E6AD2"
          strokeWidth={1.2}
          className="animate-ripple-out"
          style={{ animationDelay: "400ms" }}
        />
        <circle cx={cx} cy={cy} r={3.5} fill="#5E6AD2" className="animate-fade-soft" style={{ animationDelay: "700ms" }} />
        <circle cx={cx} cy={cy} r={1.5} fill="#FFFFFF" className="animate-fade-soft" style={{ animationDelay: "750ms" }} />
      </g>
    );
  };

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 8, right: 12, left: -8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="2 4" stroke="#E5E1D5" vertical={false} />
        <XAxis
          dataKey="time"
          tick={{ fontSize: 10, fill: "#8A8A86", fontFamily: "JetBrains Mono" }}
          axisLine={{ stroke: "#E5E1D5" }}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 10, fill: "#8A8A86", fontFamily: "JetBrains Mono" }}
          axisLine={false}
          tickLine={false}
          allowDecimals={false}
        />
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
          labelStyle={{ color: "#8A8A86" }}
        />
        <Line
          type="monotone"
          dataKey="total"
          stroke="#5E6AD2"
          strokeWidth={1.5}
          dot={renderLatestDot}
          name="总计"
        />
        <Line
          type="monotone"
          dataKey="critical"
          stroke="#B91C1C"
          strokeWidth={1}
          dot={false}
          name="严重"
        />
        <Line
          type="monotone"
          dataKey="high"
          stroke="#B45309"
          strokeWidth={1}
          dot={false}
          name="高危"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
