"use client";

import type { Session } from "next-auth";
import { QueryClientProvider } from "@tanstack/react-query";
import { SessionProvider } from "next-auth/react";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { LocaleProvider } from "@/contexts/LocaleContext";
import { getQueryClient } from "@/lib/queryClient";

// NEXT-01: 接受 root layout 通过服务端 auth() 解析出来的 session, 直接喂给
// SessionProvider, 避免 next-auth 5 beta + Next.js 15 dev 下 useSession() 一直
// 卡在 status='loading' 的兼容性问题. 注意: 这只是给客户端 hooks 一个初始
// 快照, /dashboard 自身已经走服务端 auth() 放行, 不再依赖该值做安全决策.
export function Providers({
  children,
  session,
}: {
  children: React.ReactNode;
  session?: Session | null;
}) {
  const queryClient = getQueryClient();
  return (
    <QueryClientProvider client={queryClient}>
      <SessionProvider
        session={session ?? undefined}
        refetchOnWindowFocus={false}
        refetchInterval={0}
      >
        <LocaleProvider>
          <ThemeProvider>
            {children}
          </ThemeProvider>
        </LocaleProvider>
      </SessionProvider>
    </QueryClientProvider>
  );
}
