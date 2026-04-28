import { auth } from "@/auth";
import { getToken } from "next-auth/jwt";
import { NextRequest, NextResponse } from "next/server";
import { BACKEND_BASE_URL } from "@/lib/utils";

type ProxyMethod = "GET" | "POST" | "PUT";

const BACKEND_REQUEST_TIMEOUT_MS = 15000;
const AUTH_SECRET = process.env.AUTH_SECRET || process.env.NEXTAUTH_SECRET || "";

const WEAK_AUTH_SECRETS = new Set([
  "dev-secret-change-me",
  "change-me-to-a-long-random-secret",
  "changeme",
  "change-me",
  "default",
  "secret",
  "",
]);

if (WEAK_AUTH_SECRETS.has(AUTH_SECRET.toLowerCase())) {
  console.error(
    "FATAL: AUTH_SECRET is not set or uses a weak default value. " +
    "Please set a strong random secret in your environment variables."
  );
  if (process.env.NODE_ENV === "production") {
    process.exit(1);
  }
}

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
  "/site/health",
]);

function isPublicAuthPath(backendPath: string): boolean {
  return PUBLIC_AUTH_PATHS.has(backendPath);
}

function validateOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  if (!origin) return true;
  try {
    const url = new URL(origin);
    const allowed = [process.env.NEXT_PUBLIC_APP_HOST, "localhost:3000", "127.0.0.1:3000"].filter(Boolean);
    return allowed.some((host) => url.host === host);
  } catch {
    return false;
  }
}

async function buildBackendRequest(method: ProxyMethod, request: NextRequest, backendPath: string): Promise<Response> {
  if (method !== "GET" && !validateOrigin(request)) {
    return NextResponse.json({ detail: "INVALID_ORIGIN" }, { status: 403 });
  }

  const isPublic = isPublicAuthPath(backendPath);
  const headers: Record<string, string> = {};

  if (!isPublic) {
    const session = await auth();
    const accessToken = (session?.user as any)?.access_token || "";
    if (!accessToken) {
      return NextResponse.json({ detail: "UNAUTHORIZED" }, { status: 401 });
    }
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  const url = new URL(request.url);
  const targetUrl = `${BACKEND_BASE_URL}${backendPath}${url.search}`;

  const contentType = request.headers.get("content-type");
  if (contentType) {
    headers["Content-Type"] = contentType;
  }

  const body = method === "GET" ? undefined : await request.text();
  const controller = new AbortController();
  const timeoutId = setTimeout(() => {
    controller.abort();
  }, BACKEND_REQUEST_TIMEOUT_MS);

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
