"use client";

import { useMemo, useState, type MouseEvent } from "react";
import { getSession, signIn, signOut, useSession } from "next-auth/react";
import { useRouter } from "next/navigation";

function getLoginErrorMessage(errorCode: string): string {
  if (errorCode === "CredentialsSignin") {
    return "登录失败：邮箱或密码错误";
  }
  if (errorCode === "Configuration") {
    return "登录失败：认证服务暂不可用，请稍后重试";
  }
  return "登录失败：请稍后重试";
}

type LoginState = "idle" | "loading" | "success" | "error";

async function waitForSessionReady(maxAttempts = 8, intervalMs = 250): Promise<boolean> {
  for (let i = 0; i < maxAttempts; i += 1) {
    const session = await getSession();
    if (session?.user) {
      return true;
    }
    await new Promise((resolve) => {
      window.setTimeout(resolve, intervalMs);
    });
  }
  return false;
}

export default function HomePage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [loginState, setLoginState] = useState<LoginState>("idle");
  const [eyePos, setEyePos] = useState({ x: 0, y: 0 });

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

  function handleMouseMove(event: MouseEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width - 0.5) * 10;
    const y = ((event.clientY - rect.top) / rect.height - 0.5) * 10;
    setEyePos({ x, y });
  }

  async function handleCredentialsLogin(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setLoginState("loading");
    setMessage("");

    try {
      const result = await signIn("credentials", {
        email,
        password,
        redirect: false,
      });

      if (result?.error) {
        setLoginState("error");
        setMessage(getLoginErrorMessage(result.error));
        return;
      }

      if (!result?.ok) {
        setLoginState("error");
        setMessage("登录失败：认证流程未完成");
        return;
      }

      const ready = await waitForSessionReady();
      if (!ready) {
        setLoginState("error");
        setMessage("登录失败：会话未建立，请重试");
        return;
      }

      setLoginState("success");
      setMessage("登录成功，正在进入控制台...");
      router.push("/dashboard");
      router.refresh();
    } catch {
      setLoginState("error");
      setMessage("登录失败：请稍后重试");
    } finally {
      setLoading(false);
    }
  }

  async function handleOAuthLogin(provider: "github" | "google") {
    const providerEnabled = provider === "github" ? canUseGitHub : canUseGoogle;
    if (!providerEnabled) {
      setLoginState("error");
      setMessage(`登录失败：${provider === "github" ? "GitHub" : "Google"} OAuth 未配置`);
      return;
    }

    setMessage("");
    setLoginState("loading");
    await signIn(provider, { callbackUrl: "/dashboard" });
  }

  async function handleLogout() {
    await signOut({ redirect: false });
    setMessage("已退出");
    setLoginState("idle");
    router.refresh();
  }

  return (
    <div
      className="min-h-screen w-full flex flex-col items-center justify-center p-4 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-[#111] via-cyber-bg to-cyber-bg"
      onMouseMove={handleMouseMove}
    >
      <div className="w-full max-w-5xl grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="bg-black/40 backdrop-blur-lg border border-cyber-cyan/40 p-8 shadow-neon-cyan rounded-lg">
          <div className="mb-8">
            <h1 className="text-3xl font-bold tracking-widest text-cyber-cyan uppercase">
              AI-CyberSentinel <span className="text-cyber-orange">Auth</span>
            </h1>
            <p className="text-cyber-text/70 text-sm mt-2">{statusText}</p>
            <p className="text-cyber-text/50 text-xs mt-1">NextAuth.js 前端鉴权层，后端会话与用户配置由 FastAPI 维护。</p>
          </div>

          <div className="flex justify-center mb-8">
            <svg viewBox="0 0 220 220" className="w-48 h-48 overflow-visible drop-shadow-[0_0_15px_rgba(0,245,255,0.3)]">
              <g id="blue-data-core" fill="#0055FF">
                <circle cx="110" cy="110" r="76" opacity="0.15" className="animate-pulse" />
                <circle cx="110" cy="110" r="52" opacity="0.28" />
              </g>

              <g id="yellow-crypto-module" fill="#EAB308">
                <rect x="78" y="164" width="64" height="18" rx="6" />
                {loginState === "loading" ? <rect x="90" y="170" width="40" height="6" rx="3" fill="#00F5FF" /> : null}
              </g>

              <g id="purple-hacker-drone" fill="#A855F7">
                <rect x="38" y="36" width="144" height="22" rx="2" />
                <rect x="50" y="30" width="22" height="6" fill="#00F5FF" />
                <rect x="148" y="30" width="22" height="6" fill="#00F5FF" />
                {loginState === "error" ? (
                  <rect x="104" y="44" width="12" height="4" fill="#FF8A00" />
                ) : (
                  <rect x="104" y="44" width="12" height="4" fill="#00F5FF" />
                )}
              </g>

              <g id="orange-cyborg-head" fill="#FF8A00">
                <path d="M66 66 L154 66 L166 130 L110 156 L54 130 Z" stroke="#050505" strokeWidth="2" />
                <rect x="94" y="136" width="32" height="6" fill="#050505" />

                <g className="transition-all duration-100 ease-out">
                  <rect x={72 + eyePos.x} y={84 + eyePos.y} width="26" height={showPassword ? 18 : 5} fill="#00F5FF" />
                  <rect x={122 + eyePos.x} y={84 + eyePos.y} width="26" height={showPassword ? 18 : 5} fill="#00F5FF" />
                </g>

                {loginState === "success" ? (
                  <rect x="96" y="122" width="28" height="4" fill="#00F5FF" />
                ) : loginState === "error" ? (
                  <rect x="96" y="128" width="28" height="4" fill="#F43F5E" />
                ) : null}
              </g>
            </svg>
          </div>

          {isAuthenticated ? (
            <div className="space-y-4">
              <button
                type="button"
                className="w-full bg-cyber-cyan/10 border border-cyber-cyan text-cyber-cyan hover:bg-cyber-cyan hover:text-cyber-bg font-bold py-2 px-4 transition-all duration-300"
                onClick={() => router.push("/dashboard")}
              >
                进入控制台
              </button>
              <button
                type="button"
                className="w-full border border-cyber-orange text-cyber-orange hover:bg-cyber-orange hover:text-white py-2 text-sm transition-all"
                onClick={handleLogout}
              >
                退出
              </button>
            </div>
          ) : (
            <form onSubmit={handleCredentialsLogin} className="space-y-5">
              <div>
                <label className="block text-xs text-cyber-cyan mb-1 uppercase tracking-wider">邮箱</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="w-full bg-cyber-bg/50 border border-cyber-cyan/30 text-cyber-text p-2 focus:outline-none focus:border-cyber-cyan focus:shadow-neon-cyan transition-all rounded"
                  placeholder="operator@nexus.com"
                />
              </div>

              <div>
                <label className="block text-xs text-cyber-cyan mb-1 uppercase tracking-wider">密码</label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    required
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    className="w-full bg-cyber-bg/50 border border-cyber-cyan/30 text-cyber-text p-2 pr-10 focus:outline-none focus:border-cyber-cyan focus:shadow-neon-cyan transition-all rounded"
                    placeholder="••••••••"
                  />
                  <button
                    type="button"
                    className="absolute right-2 top-2 text-cyber-cyan hover:text-cyber-orange transition-colors"
                    onClick={() => setShowPassword(!showPassword)}
                    aria-label={showPassword ? "隐藏密码" : "显示密码"}
                  >
                    {showPassword ? "隐" : "显"}
                  </button>
                </div>
              </div>

              {message ? (
                <div
                  className={`text-xs text-center font-bold tracking-wide border p-2 ${
                    loginState === "error"
                      ? "text-red-400 border-red-500/50 bg-red-500/10"
                      : "text-cyber-cyan border-cyber-cyan/50 bg-cyber-cyan/10"
                  }`}
                >
                  {message}
                </div>
              ) : null}

              <button
                type="submit"
                disabled={loading || loginState === "success"}
                className="w-full bg-cyber-cyan/10 border border-cyber-cyan text-cyber-cyan hover:bg-cyber-cyan hover:text-cyber-bg font-bold py-2 px-4 transition-all duration-300 disabled:opacity-50"
              >
                {loading ? "登录中..." : loginState === "success" ? "已授权" : "登录"}
              </button>
            </form>
          )}
        </section>

        {!isAuthenticated ? (
          <section className="bg-black/40 backdrop-blur-lg border border-cyber-purple/40 p-8 rounded-lg">
            <h3 className="text-cyber-purple uppercase tracking-wider text-sm mb-4">OAuth 登录（FastAPI /auth/login/oauth）</h3>
            <div className="flex gap-4">
              <button
                type="button"
                onClick={() => handleOAuthLogin("github")}
                title={canUseGitHub ? "" : "请配置 AUTH_GITHUB_ID/AUTH_GITHUB_SECRET"}
                className={`flex-1 border border-cyber-purple py-2 text-sm transition-all text-center ${
                  canUseGitHub
                    ? "text-cyber-purple hover:bg-cyber-purple hover:text-white"
                    : "text-cyber-purple/50 hover:bg-cyber-purple/20"
                }`}
              >
                GitHub 登录
              </button>
              <button
                type="button"
                onClick={() => handleOAuthLogin("google")}
                title={canUseGoogle ? "" : "请配置 AUTH_GOOGLE_ID/AUTH_GOOGLE_SECRET"}
                className={`flex-1 border border-cyber-orange py-2 text-sm transition-all text-center ${
                  canUseGoogle
                    ? "text-cyber-orange hover:bg-cyber-orange hover:text-white"
                    : "text-cyber-orange/50 hover:bg-cyber-orange/20"
                }`}
              >
                Google 登录
              </button>
            </div>
            <p className="small mt-4 text-cyber-text/50">若按钮不可用，请在 web-next/.env.local 中配置对应 OAuth 变量。</p>
          </section>
        ) : null}
      </div>
    </div>
  );
}
