import NextAuth, { type DefaultSession } from "next-auth";

declare module "next-auth" {
  interface Session {
    backendAccessToken?: string;
    user: DefaultSession["user"] & {
      id?: string;
      authProvider?: string;
    };
  }

  interface User {
    authProvider?: string;
    backendAccessToken?: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    authProvider?: string;
    backendAccessToken?: string;
  }
}
