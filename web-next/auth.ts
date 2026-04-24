import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import GitHub from "next-auth/providers/github";
import Google from "next-auth/providers/google";

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

const BACKEND_BASE_URL = (process.env.BACKEND_BASE_URL || "http://127.0.0.1:8000").trim().replace(/\/$/, "");

async function backendPost<T>(path: string, payload: Record<string, unknown>): Promise<T> {
  const response = await fetch(`${BACKEND_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const data = (await response.json().catch(() => ({}))) as T & { detail?: string };
  if (!response.ok) {
    const message = (data as { detail?: string }).detail || `HTTP ${response.status}`;
    throw new Error(message);
  }
  return data;
}

const oauthProviders = [];
if (process.env.AUTH_GITHUB_ID && process.env.AUTH_GITHUB_SECRET) {
  oauthProviders.push(GitHub);
}
if (process.env.AUTH_GOOGLE_ID && process.env.AUTH_GOOGLE_SECRET) {
  oauthProviders.push(Google);
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  trustHost: true,
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

        const payload = await backendPost<BackendAuthPayload>("/auth/login/password", {
          email,
          password,
        });

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
        return result;
      },
    }),
    ...oauthProviders,
  ],
  callbacks: {
    signIn: async ({ user, account }) => {
      if (!account) {
        return true;
      }
      if (account.provider !== "github" && account.provider !== "google") {
        return true;
      }
      if (!user.email || !account.providerAccountId) {
        return false;
      }

      const payload = await backendPost<BackendAuthPayload>("/auth/login/oauth", {
        provider: account.provider,
        provider_user_id: account.providerAccountId,
        email: user.email,
        display_name: user.name,
      });

      if (!payload.user?.id || !payload.access_token) {
        return false;
      }

      user.id = String(payload.user.id);
      user.authProvider = account.provider;
      user.backendAccessToken = payload.access_token;
      return true;
    },
    jwt: async ({ token, user, account }) => {
      if (user) {
        token.sub = String(user.id || token.sub || "");
        token.email = user.email || token.email;
        token.name = user.name || token.name;
        token.authProvider = user.authProvider || account?.provider || token.authProvider;
        token.backendAccessToken = user.backendAccessToken || token.backendAccessToken;
      }
      return token;
    },
    session: async ({ session, token }) => {
      if (session.user) {
        session.user.id = token.sub || "";
        session.user.authProvider = String(token.authProvider || "");
      }
      session.backendAccessToken = String(token.backendAccessToken || "");
      return session;
    },
  },
});
