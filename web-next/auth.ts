import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { cookies } from "next/headers";
import { BACKEND_BASE_URL } from "@/lib/utils";

type BackendUser = {
  id: number | string;
  email: string;
  display_name?: string | null;
  auth_provider?: string | null;
};

type BackendAuthPayload = {
  user?: BackendUser;
  access_token?: string;
};

type AuthUser = {
  id: string;
  email: string;
  name: string;
  authProvider: string;
  backendAccessToken: string;
};

type BackendRequestError = Error & {
  status?: number;
};

function isBackendRequestError(error: unknown): error is BackendRequestError {
  if (!(error instanceof Error)) {
    return false;
  }
  return "status" in error;
}

async function backendPost<T>(path: string, payload: Record<string, unknown>): Promise<T> {
  const response = await fetch(`${BACKEND_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const data = (await response.json().catch(() => ({}))) as T & { detail?: string };
  if (!response.ok) {
    const message = (data as { detail?: string }).detail || `HTTP ${response.status}`;
    const error: BackendRequestError = new Error(message);
    error.status = response.status;
    throw error;
  }
  return data;
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  trustHost: process.env.NODE_ENV === "development",
  session: { strategy: "jwt" },
  pages: { signIn: "/" },
  providers: [
    Credentials({
      name: "邮箱密码",
      credentials: {
        email: { label: "邮箱", type: "email" },
        password: { label: "密码", type: "password" },
      },
      authorize: async (credentials) => {
        const email = String(credentials?.email || "").trim();
        const password = String(credentials?.password || "");
        if (!email || !password) {
          return null;
        }

        let payload: BackendAuthPayload;
        try {
          payload = await backendPost<BackendAuthPayload>("/auth/login/password", {
            email,
            password,
          });
        } catch (error: unknown) {
          if (isBackendRequestError(error) && error.status === 401) {
            return null;
          }
          console.error("[auth] backend login failed:", error);
          return null;
        }

        if (!payload.user?.id || !payload.access_token) {
          return null;
        }

        const result: AuthUser = {
          id: String(payload.user.id),
          email: payload.user.email,
          name: payload.user.display_name || payload.user.email,
          authProvider: payload.user.auth_provider || "password",
          backendAccessToken: payload.access_token,
        };
        // SECURITY: Set the backend access_token as an httpOnly cookie so the API proxy can read it.
        // This keeps the token out of client-side JavaScript while allowing the proxy to forward it.
        try {
          const cookieStore = await cookies();
          cookieStore.set("access_token", payload.access_token, {
            httpOnly: true,
            secure: process.env.NODE_ENV === "production",
            sameSite: "lax",
            path: "/",
            maxAge: 60 * 60 * 24 * 7, // 7 days
          });
        } catch (e) {
          console.error("[auth] failed to set access_token cookie:", e);
        }
        return result;
      },
    }),
  ],
  callbacks: {
    jwt: async ({ token, user }) => {
      if (user) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const u = user as any;
        return {
          ...token,
          sub: String(u.id || token.sub || ""),
          email: u.email || token.email,
          name: u.name || token.name,
          authProvider: u.authProvider || token.authProvider,
          access_token: u.backendAccessToken || (token as any).access_token,
        };
      }
      return token;
    },
    session: async ({ session, token }) => {
      if (session.user) {
        session.user.id = token.sub || "";
        session.user.authProvider = String(token.authProvider || "");
        (session.user as any).access_token = (token as any).access_token || "";
      }
      return session;
    },
  },
});
