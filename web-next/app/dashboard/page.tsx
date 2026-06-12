"use client";

import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowRight } from "lucide-react";
import DashboardClient from "./dashboard-client";

export default function DashboardPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [showUnauthorized, setShowUnauthorized] = useState(false);

  useEffect(() => {
    if (status === "unauthenticated") {
      setShowUnauthorized(true);
      const timer = setTimeout(() => {
        router.push("/");
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [status, router]);

  if (status === "loading") {
    return (
      <div className="min-h-screen bg-bg text-ink flex items-center justify-center">
        <div className="text-center">
          <div className="text-[11px] font-mono uppercase tracking-[0.2em] text-accent mb-4">
            · 加载中
          </div>
          <div className="font-display text-3xl text-ink">初始化</div>
          <div className="text-xs text-ink-tertiary mt-2 font-mono">SYSTEM · LOADING</div>
        </div>
      </div>
    );
  }

  if (!session?.user || showUnauthorized) {
    return (
      <div className="min-h-screen bg-bg text-ink flex items-center justify-center">
        <div className="text-center max-w-sm mx-4">
          <div className="text-[11px] font-mono uppercase tracking-[0.2em] text-danger mb-4">
            · 拒绝访问
          </div>
          <div className="font-display text-4xl text-ink mb-2">401</div>
          <div className="text-sm text-ink-secondary mb-1">未登录或会话已过期</div>
          <div className="text-[10px] font-mono text-ink-tertiary mb-6">
            2 秒后自动跳转
          </div>
          <button onClick={() => router.push("/")} className="btn-primary">
            <ArrowRight className="w-3.5 h-3.5" /> 返回登录
          </button>
        </div>
      </div>
    );
  }

  return <DashboardClient userEmail={String(session.user.email || "")} />;
}
