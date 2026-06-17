"use client";

import { useMemo, useState } from "react";
import type { AlertBriefing } from "@/types/alertBriefing";
import { deriveBriefing } from "@/utils/alertBriefingUtils";
import type { AlertItem } from "@/types/alert";

/**
 * 日/周安全简报区。
 *
 * 严格基于传入的 `alerts` 派生指标；不允许内置 mock / 占位。
 * - window = 24h 时,给出"今日简报"
 * - window = 168h 时,给出"本周简报"
 *
 * 数据稀疏时显式提示"薄数据视图"或"暂无告警",不允许造假。
 */
export interface BriefingSectionProps {
  alerts: AlertItem[];
}

type Window = "24h" | "168h";

function bucketTone(count: number, max: number): string {
  if (max <= 0) return "bg-bg-sunken text-ink-tertiary";
  const ratio = count / max;
  if (ratio >= 0.75) return "bg-danger text-white";
  if (ratio >= 0.5) return "bg-warning text-white";
  if (ratio >= 0.25) return "bg-accent-soft text-accent";
  if (count > 0) return "bg-bg-sunken text-ink-secondary";
  return "bg-bg-sunken text-ink-tertiary";
}

function formatBlockRate(rate: number): string {
  return `${(rate * 100).toFixed(0)}%`;
}

function BriefingBody({ briefing }: { briefing: AlertBriefing }) {
  const maxBucket = useMemo(
    () => briefing.buckets.reduce((max, b) => Math.max(max, b.count), 0),
    [briefing.buckets]
  );

  return (
    <div className="space-y-6">
      {/* 数据稀疏提示 */}
      {briefing.note ? (
        <div
          data-testid="briefing-note"
          className="text-[11px] text-ink-secondary px-3 py-2 border-l-2 border-warning bg-warning-soft"
        >
          {briefing.note}
        </div>
      ) : null}

      {/* 顶部 4 张小卡：总数 / 高危 / 已拦截 / 拦截率 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-line border border-line">
        <MetricCell label="窗口内告警" value={String(briefing.total)} tone="default" />
        <MetricCell
          label="高危 / 严重"
          value={String(briefing.highRisk)}
          tone={briefing.highRisk > 0 ? "danger" : "default"}
        />
        <MetricCell
          label="已拦截"
          value={String(briefing.blocked)}
          tone={briefing.blocked > 0 ? "success" : "default"}
        />
        <MetricCell
          label="拦截率"
          value={formatBlockRate(briefing.blockRate)}
          tone={
            briefing.blockRate >= 0.8
              ? "success"
              : briefing.blockRate >= 0.5
                ? "warning"
                : briefing.total > 0
                  ? "danger"
                  : "default"
          }
        />
      </div>

      {/* 研判计数卡：待研判 / 研判中 / 已闭环 */}
      <div
        data-testid="briefing-triage-counts"
        className="grid grid-cols-2 md:grid-cols-3 gap-px bg-line border border-line"
      >
        <MetricCell
          label="待研判 / 研判中"
          value={String(briefing.triageOpen)}
          tone={briefing.triageOpen > 0 ? "warning" : "default"}
        />
        <MetricCell
          label="已闭环"
          value={String(briefing.triageClosed)}
          tone={briefing.triageClosed > 0 ? "success" : "default"}
        />
        <MetricCell
          label="研判状态分布"
          value={
            briefing.triageBreakdown.length === 0
              ? "—"
              : briefing.triageBreakdown
                  .map((item) => `${item.label.slice(0, 2)} ${item.count}`)
                  .join(" · ")
          }
          tone="default"
        />
      </div>

      {/* 风险分布 + 来源 TOP */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <SubBlock title="风险分布">
          {briefing.riskBreakdown.length === 0 ? (
            <EmptyRow text="暂无数据" />
          ) : (
            <ul className="space-y-1.5">
              {briefing.riskBreakdown.map((item) => (
                <li
                  key={item.risk}
                  className="flex items-center justify-between text-xs"
                >
                  <span className="text-ink-secondary">{item.label}</span>
                  <span className="font-mono text-ink">{item.count}</span>
                </li>
              ))}
            </ul>
          )}
        </SubBlock>

        <SubBlock title="攻击来源 TOP">
          {briefing.topSources.length === 0 ? (
            <EmptyRow text="暂无数据" />
          ) : (
            <ol className="space-y-1.5">
              {briefing.topSources.map((item, index) => (
                <li
                  key={item.source}
                  className="flex items-center justify-between text-xs"
                >
                  <span className="text-ink-secondary font-mono truncate max-w-[60%]">
                    {index + 1}. {item.source}
                  </span>
                  <span className="font-mono text-ink">{item.count}</span>
                </li>
              ))}
            </ol>
          )}
        </SubBlock>
      </div>

      {/* 攻击类别 */}
      <SubBlock title="主要攻击类别">
        {briefing.topAttackClass.length === 0 ? (
          <EmptyRow text="暂无数据" />
        ) : (
          <div className="flex flex-wrap gap-2">
            {briefing.topAttackClass.map((item) => (
              <span
                key={item.class}
                className="inline-flex items-center gap-1.5 text-[11px] font-mono px-2 py-1 border border-line text-ink-secondary"
              >
                {item.class}
                <span className="text-ink">{item.count}</span>
              </span>
            ))}
          </div>
        )}
      </SubBlock>

      {/* 时间桶 */}
      <SubBlock
        title={
          briefing.windowHours === 24 ? "近 24 小时（按小时）" : "近 7 天（按天）"
        }
      >
        {briefing.buckets.length === 0 ? (
          <EmptyRow text="暂无时间桶" />
        ) : (
          <div className="flex items-end gap-1 h-[80px]">
            {briefing.buckets.map((bucket, index) => (
              <div
                key={`${bucket.time}-${index}`}
                className="flex-1 flex flex-col items-center gap-1 min-w-0"
              >
                <div
                  className={`w-full text-[10px] font-mono text-center rounded-sm ${bucketTone(
                    bucket.count,
                    maxBucket
                  )}`}
                  style={{ height: `${Math.max(4, (bucket.count / Math.max(1, maxBucket)) * 60)}px` }}
                  title={`${bucket.time} · ${bucket.count} 条`}
                />
                <span className="text-[9px] font-mono text-ink-tertiary truncate w-full text-center">
                  {bucket.time}
                </span>
              </div>
            ))}
          </div>
        )}
      </SubBlock>

      {/* 最近告警 */}
      <SubBlock title="最近告警">
        {briefing.latestAlerts.length === 0 ? (
          <EmptyRow text="窗口内暂无告警" />
        ) : (
          <ul className="space-y-1.5 text-xs">
            {briefing.latestAlerts.map((alert) => (
              <li
                key={alert.id}
                className="flex items-baseline justify-between gap-3 border-b border-line-subtle pb-1 last:border-b-0"
              >
                <span className="font-mono text-ink-secondary truncate">
                  {alert.source} → {alert.target}
                </span>
                <span className="font-mono text-ink-tertiary shrink-0">
                  {alert.risk} · {alert.blocked ? "已拦截" : "未拦截"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </SubBlock>
    </div>
  );
}

function MetricCell({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "default" | "danger" | "warning" | "success";
}) {
  const valueClass =
    tone === "danger"
      ? "text-danger"
      : tone === "warning"
        ? "text-warning"
        : tone === "success"
          ? "text-success"
          : "text-ink";
  return (
    <div className="bg-bg-raised p-4 sm:p-5">
      <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary mb-2">
        {label}
      </div>
      <div className={`font-display text-2xl sm:text-3xl tabular-nums leading-none ${valueClass}`}>
        {value}
      </div>
    </div>
  );
}

function SubBlock({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary">
        {title}
      </div>
      <div>{children}</div>
    </section>
  );
}

function EmptyRow({ text }: { text: string }) {
  return <div className="text-xs text-ink-tertiary">{text}</div>;
}

export default function BriefingSection({ alerts }: BriefingSectionProps) {
  const [window, setWindow] = useState<Window>("24h");
  const windowHours: 24 | 168 = window === "24h" ? 24 : 168;
  const briefing = useMemo(() => deriveBriefing(alerts, windowHours), [alerts, windowHours]);

  return (
    <div data-testid="alert-briefing" className="space-y-4">
      <div className="flex items-baseline justify-between flex-wrap gap-3">
        <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary">
          {briefing.windowLabel} · 简报
        </div>
        <div className="flex items-center gap-3" role="tablist" aria-label="简报窗口">
          <button
            type="button"
            role="tab"
            aria-selected={window === "24h"}
            onClick={() => setWindow("24h")}
            className={`text-[10px] font-mono uppercase tracking-[0.15em] transition-colors ${
              window === "24h" ? "text-accent" : "text-ink-tertiary hover:text-ink"
            }`}
          >
            今日
          </button>
          <span className="text-ink-tertiary text-[10px]">·</span>
          <button
            type="button"
            role="tab"
            aria-selected={window === "168h"}
            onClick={() => setWindow("168h")}
            className={`text-[10px] font-mono uppercase tracking-[0.15em] transition-colors ${
              window === "168h" ? "text-accent" : "text-ink-tertiary hover:text-ink"
            }`}
          >
            本周
          </button>
        </div>
      </div>
      <BriefingBody briefing={briefing} />
    </div>
  );
}
