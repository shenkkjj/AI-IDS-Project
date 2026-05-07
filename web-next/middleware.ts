import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const SECURITY_HEADERS: Record<string, string> = {
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "X-XSS-Protection": "1; mode=block",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
  "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' ws: wss:; font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
};

const ALLOWED_ORIGINS = new Set(
  (process.env.ALLOWED_ORIGINS || "http://127.0.0.1:3000,http://localhost:3000")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
);

function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  const decodedPathname = decodeURIComponent(pathname);
  if (
    decodedPathname.includes("..") ||
    decodedPathname.includes("\\") ||
    decodedPathname.includes("\0")
  ) {
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
