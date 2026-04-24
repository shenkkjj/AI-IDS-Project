import { auth } from "@/auth";
import { redirect } from "next/navigation";
import DashboardClient from "./dashboard-client";

const BACKEND_BASE_URL = (process.env.BACKEND_BASE_URL || "http://127.0.0.1:8000").trim().replace(/\/$/, "");

export default async function DashboardPage() {
  const session = await auth();
  const token = String(session?.backendAccessToken || "").trim();
  if (!session?.user || !token) {
    redirect("/");
  }

  return (
    <DashboardClient
      backendAccessToken={token}
      backendBaseUrl={BACKEND_BASE_URL}
      userEmail={String(session.user.email || "")}
    />
  );
}
