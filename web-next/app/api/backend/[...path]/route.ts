import { NextRequest, NextResponse } from "next/server";
import { BACKEND_BASE_URL } from "@/lib/utils";

type ProxyMethod = "GET" | "POST" | "PUT";

const BACKEND_REQUEST_TIMEOUT_MS = 15000;
const COPILOT_STREAM_TIMEOUT_MS = 180000; // 3 minutes for copilot streaming

type RouteContext = {
  params: Promise<{ path?: string[] }>;
};

function joinBackendPath(path?: string[]): string {
  if (!Array.isArray(path)) return "/";
  const decoded = path
    .filter(Boolean)
    .map((segment) => {
      try {
        return decodeURIComponent(segment);
      } catch {
        return segment;
      }
    })
    .map((segment) => {
      try {
        return decodeURIComponent(segment);
      } catch {
        return segment;
      }
    })
    .filter((segment) => segment !== ".." && !segment.includes("\\") && !segment.includes("\0") && !segment.includes("/"));
  const resolved = decoded.reduce((acc, part) => {
    if (part === "..") { acc.pop(); }
    else if (part && part !== ".") { acc.push(part); }
    return acc;
  }, [] as string[]);
  const normalized = resolved.join("/").replace(/\/+/g, "/");
  return normalized ? `/${normalized}` : "/";
}

const PUBLIC_AUTH_PATHS = new Set([
  "/auth/register",
  "/auth/login/password",
  "/auth/login/otp/request",
  "/auth/login/otp/verify",
  "/auth/login/oauth",
  "/auth/password/reset/request",
  "/auth/password/reset/confirm",
]);

function isPublicAuthPath(backendPath: string): boolean {
  return PUBLIC_AUTH_PATHS.has(backendPath);
}

function validateOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  // For same-origin requests, Origin header may be omitted; require it for cross-origin
  if (!origin) {
    // Allow if it's a direct same-origin request (no Origin header on same-origin GET)
    const referer = request.headers.get("referer");
    if (!referer) return true; // Same-origin GET/HEAD often omits Origin
    try {
      const refererUrl = new URL(referer);
      const allowed = _allowedHosts();
      return allowed.some((host) => refererUrl.host === host);
    } catch {
      return false;
    }
  }
  try {
    const url = new URL(origin);
    const allowed = _allowedHosts();
    return allowed.some((host) => url.host === host);
  } catch {
    return false;
  }
}

function _allowedHosts(): string[] {
  return [
    process.env.NEXT_PUBLIC_APP_HOST,
    "localhost:3000", "127.0.0.1:3000",
    "localhost:3001", "127.0.0.1:3001",
    "localhost:3002", "127.0.0.1:3002",
    "localhost:3003", "127.0.0.1:3003",
  ].filter(Boolean) as string[];
}

function getAccessTokenFromCookie(request: NextRequest): string {
  const cookieHeader = request.headers.get("cookie") || "";
  const match = cookieHeader.match(/access_token=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

function getAccessTokenFromHeader(request: NextRequest): string {
  const authHeader = request.headers.get("authorization") || "";
  const match = authHeader.match(/^Bearer\s+(.+)$/i);
  return match ? match[1].trim() : "";
}

async function buildBackendRequest(method: ProxyMethod, request: NextRequest, backendPath: string): Promise<Response> {
  if (method !== "GET" && !validateOrigin(request)) {
    return NextResponse.json({ detail: "INVALID_ORIGIN" }, { status: 403 });
  }

  const isPublic = isPublicAuthPath(backendPath);
  const headers: Record<string, string> = {};

  if (!isPublic) {
    const accessToken = getAccessTokenFromCookie(request) || getAccessTokenFromHeader(request);
    if (!accessToken) {
      return NextResponse.json({ detail: "UNAUTHORIZED" }, { status: 401 });
    }
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  const url = new URL(request.url);
  const targetUrl = `${BACKEND_BASE_URL}${backendPath}${url.search}`;
  console.log("[proxy] targetUrl:", targetUrl, "headers:", Object.keys(headers));

  const contentType = request.headers.get("content-type");
  if (contentType) {
    headers["Content-Type"] = contentType;
  }

  const body = method === "GET" ? undefined : await request.text();
  const controller = new AbortController();
  
  // Use longer timeout for copilot streaming endpoints
  const isCopilotStream = backendPath.includes("/copilot/stream");
  const timeoutMs = isCopilotStream ? COPILOT_STREAM_TIMEOUT_MS : BACKEND_REQUEST_TIMEOUT_MS;
  
  const timeoutId = setTimeout(() => {
    controller.abort();
  }, timeoutMs);

  try {
    return await fetch(targetUrl, {
      method,
      headers,
      body,
      cache: "no-store",
      signal: controller.signal,
    });
  } catch (error: unknown) {
    console.error("[proxy] fetch failed:", targetUrl, error);
    if (error instanceof Error && error.name === "AbortError") {
      return NextResponse.json({ detail: "UPSTREAM_TIMEOUT" }, { status: 504 });
    }
    return NextResponse.json({ detail: "UPSTREAM_UNAVAILABLE" }, { status: 502 });
  } finally {
    clearTimeout(timeoutId);
  }
}

function toClientResponse(backendResponse: Response): Response {
  const contentType = backendResponse.headers.get("content-type") || "application/json; charset=utf-8";

  return new Response(backendResponse.body, {
    status: backendResponse.status,
    headers: {
      "Content-Type": contentType,
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
      "X-Frame-Options": "DENY",
    },
  });
}

export async function GET(request: NextRequest, context: RouteContext): Promise<Response> {
  const { path } = await context.params;
  const backendResponse = await buildBackendRequest("GET", request, joinBackendPath(path));
  return toClientResponse(backendResponse);
}

export async function POST(request: NextRequest, context: RouteContext): Promise<Response> {
  const { path } = await context.params;
  const backendResponse = await buildBackendRequest("POST", request, joinBackendPath(path));
  return toClientResponse(backendResponse);
}

export async function PUT(request: NextRequest, context: RouteContext): Promise<Response> {
  const { path } = await context.params;
  const backendResponse = await buildBackendRequest("PUT", request, joinBackendPath(path));
  return toClientResponse(backendResponse);
}
