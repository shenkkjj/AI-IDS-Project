"use client";

import type { ReactNode } from "react";

export interface SectionHeadingProps {
  index: string;
  title: string;
  description?: string;
  action?: ReactNode;
}

export default function SectionHeading({
  index,
  title,
  description,
  action,
}: SectionHeadingProps) {
  return (
    <div className="flex items-baseline justify-between mb-6 pb-3 border-b border-line">
      <div>
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-accent mb-1.5">
          {index}
        </div>
        <h2 className="font-display text-2xl text-ink tracking-tight">{title}</h2>
        {description ? (
          <p className="text-xs text-ink-secondary mt-1">{description}</p>
        ) : null}
      </div>
      {action}
    </div>
  );
}
