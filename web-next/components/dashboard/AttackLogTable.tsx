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
  if (risk === "critical") return "text-red-500 bg-red-500/10";
  if (risk === "high") return "text-cyber-orange bg-cyber-orange/10";
  if (risk === "medium") return "text-cyber-purple bg-cyber-purple/10";
  return "text-cyber-cyan bg-cyber-cyan/10";
}

function formatTimestamp(ts: number | null): string {
  if (!Number.isFinite(ts) || !ts || ts <= 0) {
    return "--";
  }
  return new Date(ts * 1000).toLocaleString();
}

export default function AttackLogTable({ logs, highlightId, selectedId, onSelect }: AttackLogTableProps) {
  return (
    <div className="bg-black/40 border border-cyber-cyan/30 backdrop-blur p-4 h-full flex flex-col">
      <div className="flex justify-between items-center mb-4 border-b border-cyber-cyan/20 pb-2">
        <h3 className="text-cyber-cyan uppercase tracking-widest text-sm font-bold flex items-center gap-2">
          <span className="w-2 h-2 bg-cyber-cyan rounded-full animate-pulse" />
          Intrusion Logs
        </h3>
        <span className="text-xs text-cyber-text/50">Live Capture</span>
      </div>

      <div className="flex-1 overflow-x-auto overflow-y-auto pr-2">
        <table className="w-full text-left text-xs md:text-sm whitespace-nowrap">
          <thead className="text-cyber-text/50 sticky top-0 bg-cyber-bg z-10">
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
                  initial={{ backgroundColor: log.id === highlightId ? "rgba(0,245,255,0.35)" : "transparent", opacity: 0.6 }}
                  animate={{
                    backgroundColor:
                      selectedId === log.id ? "rgba(0,245,255,0.1)" : "transparent",
                    opacity: 1,
                  }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.7, ease: "easeOut" }}
                  className={`border-b border-white/5 transition-colors ${
                    selectedId === log.id ? "" : "hover:bg-white/5"
                  } ${onSelect ? "cursor-pointer" : ""}`}
                  onClick={onSelect ? () => onSelect(log.id) : undefined}
                >
                  <td className="p-2 text-cyber-text/70">{formatTimestamp(log.timestamp)}</td>
                  <td className="p-2 font-bold text-cyber-orange">{log.source}</td>
                  <td className="p-2">{log.target}</td>
                  <td className="p-2 max-w-[360px] overflow-hidden text-ellipsis">{log.payload || "--"}</td>
                  <td className="p-2">
                    <span className={`px-2 py-1 rounded text-xs tracking-wider ${riskClass(log.risk)}`}>{riskLabel(log.risk)}</span>
                  </td>
                  <td className="p-2">{log.blocked ? "YES" : "NO"}</td>
                </motion.tr>
              ))}
            </AnimatePresence>
          </tbody>
        </table>
        {logs.length === 0 ? <div className="text-center text-cyber-text/40 mt-8 text-sm">NO ANOMALIES DETECTED</div> : null}
      </div>
    </div>
  );
}
