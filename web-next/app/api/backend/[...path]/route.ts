import { auth } from "@/auth";
import { getToken } from "next-auth/jwt";
import { NextResponse } from "next/server";

type ProxyMethod = "GET" | "POST" | "PUT";

const BACKEND_BASE_URL = (process.env.BACKEND_BASE_URL || "http://127.0.0.1:8000").trim().replace(/\/$/, "");
const BACKEND_REQUEST_TIMEOUT_MS = 15000;
const AUTH_SECRET = process.env.AUTH_SECRET || process.env.NEXTAUTH_SECRET || "";

type RouteContext = {
  params: Promise<{ path?: string[] }>;
};

function joinBackendPath(path?: string[]): string {
  const joined = Array.isArray(path) ? path.filter(Boolean).join("/") : "";
  return joined ? `/${joined}` : "/";
}

async function buildBackendRequest(method: ProxyMethod, request: Request, backendPath: string): Promise<Response> {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ detail: "UNAUTHORIZED" }, { status: 401 });
  }

  if (!AUTH_SECRET) {
    return NextResponse.json({ detail: "AUTH_SECRET_MISSING" }, { status: 500 });
  }

  const jwtToken = await getToken({ req: request, secret: AUTH_SECRET });
  const token = String(jwtToken?.backendAccessToken || "").trim();
  if (!token) {
    return NextResponse.json({ detail: "UNAUTHORIZED" }, { status: 401 });
  }

  const url = new URL(request.url);
  const targetUrl = `${BACKEND_BASE_URL}${backendPath}${url.search}`;

  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
  };

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
    },
  });
}

export async function GET(request: Request, context: RouteContext): Promise<Response> {
  const { path } = await context.params;
  const backendResponse = await buildBackendRequest("GET", request, joinBackendPath(path));
  return toClientResponse(backendResponse);
}

export async function POST(request: Request, context: RouteContext): Promise<Response> {
  const { path } = await context.params;
  const backendResponse = await buildBackendRequest("POST", request, joinBackendPath(path));
  return toClientResponse(backendResponse);
}

export async function PUT(request: Request, context: RouteContext): Promise<Response> {
  const { path } = await context.params;
  const backendResponse = await buildBackendRequest("PUT", request, joinBackendPath(path));
  return toClientResponse(backendResponse);
}
