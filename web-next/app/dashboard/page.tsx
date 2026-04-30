"use client";

import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import DashboardClient from "./dashboard-client";

export default function DashboardPage() {
  const { data: session, status } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/");
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

  if (!session?.user) {
    return null;
  }

  return <DashboardClient userEmail={String(session.user.email || "")} />;
}
