"use client";

import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import DashboardClient from "./dashboard-client";

export default function DashboardPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [showUnauthorized, setShowUnauthorized] = useState(false);

  useEffect(() => {
    if (status === "unauthenticated") {
      // Give a moment to show the unauthorized message before redirect
      setShowUnauthorized(true);
      const timer = setTimeout(() => {
        router.push("/");
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [status, router]);

  if (status === "loading") {
    return (
      <div className="min-h-screen bg-[#050a14] text-[#00f0ff] flex items-center justify-center font-mono">
        <div className="text-center">
          <div className="text-lg mb-2">SYSTEM INITIALIZING...</div>
          <div className="text-sm text-[#00f0ff]/60">正在加载会话...</div>
        </div>
      </div>
    );
  }

  if (!session?.user || showUnauthorized) {
    return (
      <div className="min-h-screen bg-[#050a14] text-[#00f0ff] flex items-center justify-center font-mono">
        <div className="text-center">
          <div className="text-lg mb-2">ACCESS DENIED</div>
          <div className="text-sm text-[#00f0ff]/60 mb-4">未登录或会话已过期</div>
          <div className="text-xs text-[#00f0ff]/40 mb-4">2秒后自动跳转...</div>
          <button
            onClick={() => router.push("/")}
            className="px-4 py-2 border border-[#00f0ff]/40 text-[#00f0ff] hover:bg-[#00f0ff]/10 transition-colors"
          >
            立即返回登录
          </button>
        </div>
      </div>
    );
  }

  return <DashboardClient userEmail={String(session.user.email || "")} />;
}
