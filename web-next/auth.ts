// Re-export from lib/auth.ts for backward compatibility
// NOTE: This file exists to avoid breaking imports.
// In NextAuth.js v5 + Next.js 15, importing auth config into
// middleware or client boundaries can cause "Connection closed" errors.
// Use lib/auth.ts for server-side auth() and handlers.
export { handlers, auth, signIn, signOut } from "@/lib/auth";
