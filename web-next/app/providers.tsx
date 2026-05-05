"use client";

import { SessionProvider } from "next-auth/react";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { LocaleProvider } from "@/contexts/LocaleContext";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider refetchOnWindowFocus={false} refetchInterval={0}>
      <LocaleProvider>
        <ThemeProvider>
          {children}
        </ThemeProvider>
      </LocaleProvider>
    </SessionProvider>
  );
}
