import type { Metadata } from "next";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI-CyberSentinel Auth Gateway",
  description: "NextAuth.js 集成入口",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" className="dark">
      <body className="min-h-screen bg-cyber-bg text-cyber-text font-mono antialiased selection:bg-cyber-cyan/30">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
