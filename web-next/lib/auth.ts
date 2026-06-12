import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";

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

const MIN_SECRET_LENGTH = 32;
const DEV_BUILD_TIME_PHASE = "phase-production-build";

function isBuildPhase(): boolean {
  return process.env.NEXT_PHASE === DEV_BUILD_TIME_PHASE;
}

function getAuthSecret(): string {
  const secret = process.env.AUTH_SECRET || process.env.NEXTAUTH_SECRET;

  if (secret) {
    if (secret.length < MIN_SECRET_LENGTH) {
      throw new Error(
        `[auth] AUTH_SECRET must be at least ${MIN_SECRET_LENGTH} characters long. ` +
          "Generate a strong random value (e.g. openssl rand -base64 48).",
      );
    }
    return secret;
  }

  // Allow omission only during the static build phase so CI/SSG builds do not
  // require a live secret. Any other runtime path must fail fast.
  if (isBuildPhase()) {
    return "build-time-placeholder-not-a-real-secret-" + "x".repeat(48);
  }

  throw new Error(
    "[auth] AUTH_SECRET (or NEXTAUTH_SECRET) is required. " +
      "Set it to a strong random value (min 32 chars) before starting. " +
      "Generate one with: openssl rand -base64 48",
  );
}

export const {
  handlers,
  auth,
  signIn,
  signOut,
} = NextAuth({
  trustHost: process.env.NODE_ENV === "development",
  secret: getAuthSecret(),
  session: { strategy: "jwt" },
  pages: { signIn: "/" },
  events: {
    signOut: async (message) => {
      const accessToken = "token" in message && message.token
        ? (message.token as Record<string, unknown>)?.access_token
        : undefined;
      if (typeof accessToken !== "string" || !accessToken) return;
      try {
        await fetch(`${BACKEND_BASE_URL}/auth/logout`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
        });
      } catch {
        // best-effort: backend logout failure should not block client sign-out
      }
    },
  },
  providers: [
    Credentials({
      name: "邮箱密码 / OTP",
      credentials: {
        email: { label: "邮箱", type: "email" },
        password: { label: "密码", type: "password" },
        otp: { label: "邮箱验证码", type: "text" },
      },
      authorize: async (credentials) => {
        const email = String(credentials?.email || "").trim();
        const password = String(credentials?.password || "");
        const otp = String(credentials?.otp || "").trim();
        if (!email) return null;

        let payload: BackendAuthPayload;
        try {
          if (otp) {
            payload = await backendPost<BackendAuthPayload>("/auth/login/otp/verify", {
              email,
              code: otp,
            });
          } else if (password) {
            payload = await backendPost<BackendAuthPayload>("/auth/login/password", {
              email,
              password,
            });
          } else {
            return null;
          }
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
          authProvider: payload.user.auth_provider || (otp ? "otp" : "password"),
          backendAccessToken: payload.access_token,
        };

        return result;
      },
    }),
  ],
  callbacks: {
    jwt: async ({ token, user }) => {
      if (user) {
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
      }
      return session;
    },
  },
});
