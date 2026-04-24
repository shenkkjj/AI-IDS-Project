"use client";

import { useMemo, useState } from "react";
import { signIn, signOut, useSession } from "next-auth/react";
import { useRouter } from "next/navigation";

export default function HomePage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const isAuthenticated = status === "authenticated";
  const canUseGitHub = Boolean(process.env.NEXT_PUBLIC_AUTH_GITHUB_ENABLED === "true");
  const canUseGoogle = Boolean(process.env.NEXT_PUBLIC_AUTH_GOOGLE_ENABLED === "true");

  const statusText = useMemo(() => {
    if (status === "loading") {
      return "正在检查会话...";
    }
    if (isAuthenticated) {
      return `已登录：${session?.user?.email || "unknown"}`;
    }
    return "未登录";
  }, [status, isAuthenticated, session?.user?.email]);

  async function handleCredentialsLogin(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    const result = await signIn("credentials", {
      email,
      password,
      redirect: false,
    });
    setLoading(false);

    if (result?.error) {
      setMessage(`登录失败：${result.error}`);
      return;
    }

    setMessage("登录成功，正在进入控制台...");
    router.push("/dashboard");
    router.refresh();
  }

  async function handleOAuthLogin(provider: "github" | "google") {
    setMessage("");
    await signIn(provider, { callbackUrl: "/dashboard" });
  }

  async function handleLogout() {
    await signOut({ redirect: false });
    setMessage("已退出");
    router.refresh();
  }

  return (
    <main>
      <h1>AI-CyberSentinel Auth Gateway</h1>
      <p className="small">NextAuth.js 前端鉴权层，后端会话与用户配置由 FastAPI 维护。</p>

      <section className="card">
        <h3>会话状态</h3>
        <p>{statusText}</p>
        {isAuthenticated ? (
          <div className="row">
            <button type="button" onClick={() => router.push("/dashboard")}>进入控制台</button>
            <button type="button" className="secondary" onClick={handleLogout}>退出</button>
          </div>
        ) : null}
      </section>

      {!isAuthenticated ? (
        <section className="card">
          <h3>邮箱密码登录（FastAPI /auth/login/password）</h3>
          <form onSubmit={handleCredentialsLogin}>
            <label>
              邮箱
              <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
            </label>
            <label>
              密码
              <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
            </label>
            <button type="submit" disabled={loading}>{loading ? "登录中..." : "登录"}</button>
          </form>
        </section>
      ) : null}

      {!isAuthenticated ? (
        <section className="card">
          <h3>OAuth 登录（FastAPI /auth/login/oauth）</h3>
          <div className="row">
            <button
              type="button"
              onClick={() => handleOAuthLogin("github")}
              disabled={!canUseGitHub}
              title={canUseGitHub ? "" : "请配置 AUTH_GITHUB_ID/AUTH_GITHUB_SECRET"}
            >
              GitHub 登录
            </button>
            <button
              type="button"
              onClick={() => handleOAuthLogin("google")}
              disabled={!canUseGoogle}
              title={canUseGoogle ? "" : "请配置 AUTH_GOOGLE_ID/AUTH_GOOGLE_SECRET"}
            >
              Google 登录
            </button>
          </div>
          <p className="small">若按钮不可用，请在 web-next/.env.local 中配置对应 OAuth 变量。</p>
        </section>
      ) : null}

      {message ? (
        <section className="card">
          <h3>提示</h3>
          <p>{message}</p>
        </section>
      ) : null}
    </main>
  );
}
