import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { auth } from "@/auth";

const SECURITY_HEADERS: Record<string, string> = {
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
  "Content-Security-Policy": [
    "default-src 'self'",
    "script-src 'self' 'unsafe-eval'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "connect-src 'self'",
    "font-src 'self'",
    "frame-ancestors 'none'",
  ].join("; "),
};

async function middleware(request: NextRequest) {
  const authResponse = await auth(request as unknown as Parameters<typeof auth>[0]);
  const response = authResponse instanceof Response ? authResponse : NextResponse.next();

  for (const [key, value] of Object.entries(SECURITY_HEADERS)) {
    response.headers.set(key, value);
  }

  const pathname = request.nextUrl.pathname;
  if (pathname.includes("..") || pathname.includes("\\") || pathname.includes("\0")) {
    return new NextResponse(null, { status: 400 });
  }

  return response;
}

export { middleware };

export const config = {
  matcher: ["/dashboard/:path*", "/api/backend/:path*"],
};
