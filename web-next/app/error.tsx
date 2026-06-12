"use client";

import { useEffect } from "react";
import { RefreshCw } from "lucide-react";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[error-boundary] caught:", error);
  }, [error]);

  return (
    <div className="min-h-screen bg-bg text-ink flex items-center justify-center px-6">
      <div className="max-w-md w-full">
        <div className="text-[11px] font-mono uppercase tracking-[0.2em] text-danger mb-4">
          · 错误
        </div>
        <h1 className="font-display text-5xl text-ink leading-tight tracking-tight mb-3">
          连接中断
        </h1>
        <p className="text-sm text-ink-secondary mb-1">
          {error.digest ? `Ref: ${error.digest}` : "RSC 连接中断"}
        </p>
        <p className="text-[10px] font-mono text-ink-tertiary mb-8">
          点击重试，或刷新浏览器
        </p>
        <button onClick={reset} className="btn-primary">
          <RefreshCw className="w-3.5 h-3.5" /> 重试
        </button>
      </div>
    </div>
  );
}
