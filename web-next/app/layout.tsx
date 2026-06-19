import type { Metadata, Viewport } from "next";
import { auth } from "@/lib/auth";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI-CyberSentinel · SOC",
  description: "智能入侵检测与防御系统",
  manifest: "/manifest.json",
  applicationName: "AI-CyberSentinel",
  appleWebApp: {
    capable: true,
    title: "AI-CyberSentinel",
    statusBarStyle: "black-translucent",
  },
  formatDetection: { telephone: false, email: false, address: false },
};

export const viewport: Viewport = {
  themeColor: "#0a0a0a",
  colorScheme: "dark light",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
};

// NEXT-01: 在 Server Component 里用 auth() 解析当前 session, 透传给
// Providers -> SessionProvider 的 session prop. 这避免了 next-auth 5 beta +
// Next.js 15 dev mode 下 useSession() 永远卡在 status='loading' 的阻塞.
// 这会让 root layout 动态化, 但本应用是登录态 SOC 控制台, 可以接受.
export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  return (
    <html lang="zh-CN" className="light">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
        />
        <link rel="icon" href="/icon-192.png" type="image/png" />
        <link rel="apple-touch-icon" href="/icon-192.png" />
      </head>
      <body className="min-h-screen bg-bg text-ink font-sans antialiased">
        <Providers session={session}>{children}</Providers>
        <script
          // Register the service worker for PWA support. Failed registration
          // (e.g. private mode, unsupported browser) is silently ignored.
          dangerouslySetInnerHTML={{
            __html: `if ('serviceWorker' in navigator) { window.addEventListener('load', () => { navigator.serviceWorker.register('/sw.js').catch(() => {}); }); }`,
          }}
        />
      </body>
    </html>
  );
}
