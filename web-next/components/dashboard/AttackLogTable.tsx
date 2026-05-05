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
  if (risk === "critical") return "CRITICAL";
  if (risk === "high") return "HIGH";
  if (risk === "medium") return "MEDIUM";
  return "LOW";
}

function riskClass(risk: AlertRisk): string {
  if (risk === "critical") return "text-rose-400 bg-rose-400/10";
  if (risk === "high") return "text-amber-400 bg-amber-400/10";
  if (risk === "medium") return "text-violet-400 bg-violet-400/10";
  return "text-cyan-400 bg-cyan-400/10";
}

function formatTimestamp(ts: number | null): string {
  if (!Number.isFinite(ts) || !ts || ts <= 0) {
    return "--";
  }
  return new Date(ts * 1000).toLocaleString();
}

export default function AttackLogTable({ logs, highlightId, selectedId, onSelect }: AttackLogTableProps) {
  return (
    <div className="bg-[#0F172A]/80 border border-slate-700/50 rounded-lg p-4 h-full flex flex-col">
      <div className="flex justify-between items-center mb-4 border-b border-slate-700/30 pb-2">
        <h3 className="text-cyber-cyan uppercase tracking-widest text-sm font-bold flex items-center gap-2">
          <span className="w-2 h-2 bg-cyber-cyan rounded-full animate-pulse" />
          Intrusion Logs
        </h3>
        <span className="text-xs text-slate-500">Live Capture</span>
      </div>

      <div className="flex-1 overflow-x-auto overflow-y-auto pr-2">
        <table className="w-full text-left text-xs md:text-sm whitespace-nowrap">
          <thead className="text-slate-500 sticky top-0 bg-[#0B0F1A] z-10">
            <tr>
              <th className="p-2 font-normal uppercase">Time</th>
              <th className="p-2 font-normal uppercase">Source IP</th>
              <th className="p-2 font-normal uppercase">Target</th>
              <th className="p-2 font-normal uppercase">Payload</th>
              <th className="p-2 font-normal uppercase">Severity</th>
              <th className="p-2 font-normal uppercase">Blocked</th>
            </tr>
          </thead>
          <tbody>
            <AnimatePresence initial={false}>
              {logs.map((log) => (
                <motion.tr
                  key={log.id}
                  initial={{ backgroundColor: log.id === highlightId ? "rgba(34,211,238,0.2)" : "transparent", opacity: 0.6 }}
                  animate={{
                    backgroundColor:
                      selectedId === log.id ? "rgba(34,211,238,0.06)" : "transparent",
                    opacity: 1,
                  }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.5, ease: "easeOut" }}
                  className={`border-b border-white/[0.03] transition-colors ${
                    selectedId === log.id ? "" : "hover:bg-white/[0.02]"
                  } ${onSelect ? "cursor-pointer" : ""}`}
                  onClick={onSelect ? () => onSelect(log.id) : undefined}
                >
                  <td className="p-2 text-slate-400">{formatTimestamp(log.timestamp)}</td>
                  <td className="p-2 font-bold text-amber-400/80">{log.source}</td>
                  <td className="p-2 text-slate-300">{log.target}</td>
                  <td className="p-2 max-w-[360px] overflow-hidden text-ellipsis text-slate-400">{log.payload || "--"}</td>
                  <td className="p-2">
                    <span className={`px-2 py-1 rounded text-xs tracking-wider ${riskClass(log.risk)}`}>{riskLabel(log.risk)}</span>
                  </td>
                  <td className="p-2 text-slate-400">{log.blocked ? "YES" : "NO"}</td>
                </motion.tr>
              ))}
            </AnimatePresence>
          </tbody>
        </table>
        {logs.length === 0 ? <div className="text-center text-slate-600 mt-8 text-sm">NO ANOMALIES DETECTED</div> : null}
      </div>
    </div>
  );
}
