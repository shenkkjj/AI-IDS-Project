"use client";

export function SessionRow({
  label,
  value,
  tone,
  mono,
}: {
  label: string;
  value: string;
  tone?: "ok" | "error";
  mono?: boolean;
}) {
  return (
    <div className="py-3 flex items-baseline justify-between gap-4">
      <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary shrink-0">
        {label}
      </span>
      <span
        className={`text-sm text-right ${
          tone === "ok" ? "text-success" : tone === "error" ? "text-danger" : "text-ink"
        } ${mono ? "font-mono tabular-nums" : ""}`}
      >
        {value}
      </span>
    </div>
  );
}

export function ChannelRow({
  label,
  enabled,
  customText,
}: {
  label: string;
  enabled: boolean;
  customText?: string;
}) {
  return (
    <div className="py-3 flex items-baseline justify-between">
      <div className="flex items-center gap-2">
        <span className={`w-1 h-1 rounded-full ${enabled ? "bg-accent" : "bg-ink-tertiary"}`} />
        <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary">
          {label}
        </span>
      </div>
      <span
        className={`text-sm ${enabled ? "text-ink" : "text-ink-tertiary"}`}
      >
        {customText || (enabled ? "已开启" : "已关闭")}
      </span>
    </div>
  );
}
