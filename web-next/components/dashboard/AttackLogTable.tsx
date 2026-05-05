"use client";

import { AnimatePresence, motion } from "framer-motion";

type AlertRisk = "critical" | "high" | "medium" | "low";

type AlertItem = {
  id: string;
  source: string;
  target: string;
  risk: AlertRisk;
  payload: string;
  summary: string;
  timestamp: number | null;
  blocked: boolean;
};

type AttackLogTableProps = {
  logs: AlertItem[];
  highlightId?: string;
  selectedId?: string;
  onSelect?: (id: string) => void;
};

function riskLabel(risk: AlertRisk): string {
  if (risk === "critical") return "严重";
  if (risk === "high") return "高危";
  if (risk === "medium") return "中危";
  return "低危";
}

function riskStyle(risk: AlertRisk): { bg: string; text: string; dot: string } {
  if (risk === "critical") return { bg: "bg-[#FFE5E3]", text: "text-[#FF3B30]", dot: "bg-[#FF3B30]" };
  if (risk === "high") return { bg: "bg-[#FFF4E5]", text: "text-[#FF9500]", dot: "bg-[#FF9500]" };
  if (risk === "medium") return { bg: "bg-[#FFF8E1]", text: "text-[#FFCC00]", dot: "bg-[#FFCC00]" };
  return { bg: "bg-[#E8F4FD]", text: "text-[#0071E3]", dot: "bg-[#0071E3]" };
}

function formatTimestamp(ts: number | null): string {
  if (!Number.isFinite(ts) || !ts || ts <= 0) {
    return "--";
  }
  return new Date(ts * 1000).toLocaleString();
}

export default function AttackLogTable({ logs, highlightId, selectedId, onSelect }: AttackLogTableProps) {
  return (
    <div className="bg-white rounded-[18px] shadow-card p-5 h-full flex flex-col">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-sm font-semibold text-[#1D1D1F] flex items-center gap-2">
          <span className="w-2 h-2 bg-[#0071E3] rounded-full" />
          入侵日志
        </h3>
        <span className="text-xs text-[#86868B] font-medium">实时监控</span>
      </div>

      <div className="flex-1 overflow-x-auto overflow-y-auto">
        <table className="w-full text-left text-xs md:text-sm whitespace-nowrap">
          <thead className="text-[#86868B] sticky top-0 bg-white z-10">
            <tr className="border-b border-[#E8E8ED]">
              <th className="py-3 px-2 font-medium">时间</th>
              <th className="py-3 px-2 font-medium">来源 IP</th>
              <th className="py-3 px-2 font-medium">目标</th>
              <th className="py-3 px-2 font-medium">载荷</th>
              <th className="py-3 px-2 font-medium">等级</th>
              <th className="py-3 px-2 font-medium">已拦截</th>
            </tr>
          </thead>
          <tbody>
            <AnimatePresence initial={false}>
              {logs.map((log) => {
                const style = riskStyle(log.risk);
                return (
                  <motion.tr
                    key={log.id}
                    initial={{ backgroundColor: log.id === highlightId ? "rgba(0,113,227,0.1)" : "transparent", opacity: 0.6 }}
                    animate={{
                      backgroundColor: selectedId === log.id ? "rgba(0,113,227,0.05)" : "transparent",
                      opacity: 1,
                    }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.5, ease: "easeOut" }}
                    className={`border-b border-[#F5F5F7] transition-colors ${
                      selectedId === log.id ? "" : "hover:bg-[#F5F5F7]/50"
                    } ${onSelect ? "cursor-pointer" : ""}`}
                    onClick={onSelect ? () => onSelect(log.id) : undefined}
                  >
                    <td className="py-3 px-2 text-[#86868B]">{formatTimestamp(log.timestamp)}</td>
                    <td className="py-3 px-2 font-medium text-[#1D1D1F]">{log.source}</td>
                    <td className="py-3 px-2 text-[#1D1D1F]">{log.target}</td>
                    <td className="py-3 px-2 max-w-[360px] overflow-hidden text-ellipsis text-[#86868B]">{log.payload || "--"}</td>
                    <td className="py-3 px-2">
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${style.bg} ${style.text}`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
                        {riskLabel(log.risk)}
                      </span>
                    </td>
                    <td className="py-3 px-2">
                      <span className={`text-xs font-medium ${log.blocked ? "text-[#34C759]" : "text-[#86868B]"}`}>
                        {log.blocked ? "是" : "否"}
                      </span>
                    </td>
                  </motion.tr>
                );
              })}
            </AnimatePresence>
          </tbody>
        </table>
        {logs.length === 0 ? (
          <div className="text-center text-[#A1A1A6] mt-8 text-sm py-12">
            <div className="w-12 h-12 bg-[#F5F5F7] rounded-full flex items-center justify-center mx-auto mb-3">
              <span className="text-xl">✅</span>
            </div>
            未检测到异常
          </div>
        ) : null}
      </div>
    </div>
  );
}
