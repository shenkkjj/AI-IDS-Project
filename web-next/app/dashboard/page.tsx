"use client";

import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Shield, Loader2 } from "lucide-react";
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
      <div className="min-h-screen bg-background text-text flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 text-primary animate-spin mx-auto mb-3" />
          <div className="text-sm text-text-secondary">正在加载会话...</div>
        </div>
      </div>
    );
  }

  if (!session?.user || showUnauthorized) {
    return (
      <div className="min-h-screen bg-background text-text flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 bg-danger-subtle rounded-full flex items-center justify-center mx-auto mb-3">
            <Shield className="w-6 h-6 text-danger" />
          </div>
          <div className="text-lg font-semibold mb-1">访问受限</div>
          <div className="text-sm text-text-secondary mb-4">未登录或会话已过期</div>
          <div className="text-xs text-text-tertiary mb-4">2秒后自动跳转...</div>
          <button
            onClick={() => router.push("/")}
            className="px-4 py-2 bg-primary text-white text-sm rounded-apple hover:bg-primary-hover transition-colors"
          >
            立即返回登录
          </button>
        </div>
      </div>
    );
  }

  const user = session.user as { email?: string; name?: string; role?: string };

  return (
    <DashboardClient
      userEmail={String(user.email || "")}
      userRole={String(user.role || "analyst")}
    />
  );
}
