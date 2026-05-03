import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const SECURITY_HEADERS: Record<string, string> = {
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
};

const ALLOWED_ORIGINS = new Set([
  "http://127.0.0.1:3000",
  "http://localhost:3000",
]);

function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  if (pathname.includes("..") || pathname.includes("\\") || pathname.includes("\0")) {
    return new NextResponse(null, { status: 400 });
  }

  if (pathname.startsWith("/api/")) {
    const origin = request.headers.get("origin");
    if (origin && !ALLOWED_ORIGINS.has(origin)) {
      return NextResponse.json({ error: "forbidden" }, { status: 403 });
    }
  }

  const response = NextResponse.next();
  for (const [key, value] of Object.entries(SECURITY_HEADERS)) {
    response.headers.set(key, value);
  }
  return response;
}

export { middleware };

export const config = {
  matcher: ["/dashboard/:path*", "/api/backend/:path*"],
};
