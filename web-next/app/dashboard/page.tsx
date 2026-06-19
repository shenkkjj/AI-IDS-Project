import { redirect } from "next/navigation";

import { auth } from "@/lib/auth";
import DashboardClient from "./dashboard-client";

// Server Component: 服务端用 auth() 决定是否放行 dashboard, 不再依赖客户端
// useSession() 的 hydration. 这样在 next-auth 5 beta + Next.js 15 dev 下,
// dashboard 不会卡在 'SYSTEM · LOADING' (NEXT-01).
//
// 安全约束:
// - 未登录 -> redirect("/"), 不暴露 dashboard 数据.
// - 不把 backendAccessToken / 完整 session 写入页面 DOM, 只把 email 透传给
//   DashboardClient (与原行为一致).
// - cookie / JWT session 仍由 NextAuth 管理, 不引入 storage.
export default async function DashboardPage() {
  const session = await auth();

  if (!session?.user) {
    redirect("/");
  }

  return <DashboardClient userEmail={String(session.user.email || "")} />;
}
