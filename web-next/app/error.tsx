"use client";

import { useEffect } from "react";

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
    <html lang="zh-CN" className="dark">
      <body className="min-h-screen bg-[#050a14] text-[#00f0ff] flex items-center justify-center font-mono">
        <div className="text-center max-w-md px-6">
          <div className="text-lg mb-4">CONNECTION INTERRUPTED</div>
          <div className="text-sm text-[#00f0ff]/60 mb-2">
            {error.digest ? `Ref: ${error.digest}` : "RSC 连接中断"}
          </div>
          <div className="text-xs text-[#00f0ff]/40 mb-6">
            点击重试，或刷新浏览器
          </div>
          <button
            onClick={reset}
            className="px-6 py-2 border border-[#00f0ff]/40 text-[#00f0ff] hover:bg-[#00f0ff]/10 transition-colors mr-3"
          >
            RETRY
          </button>
          <button
            onClick={() => window.location.reload()}
            className="px-6 py-2 border border-[#00f0ff]/40 text-[#00f0ff] hover:bg-[#00f0ff]/10 transition-colors"
          >
            RELOAD
          </button>
        </div>
      </body>
    </html>
  );
}
