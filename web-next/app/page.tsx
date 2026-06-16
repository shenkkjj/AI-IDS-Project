"use client";

import { useState, useCallback, useEffect, useMemo } from "react";
import { getSession, signIn, signOut, useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { LogOut, ArrowRight, AlertCircle, CheckCircle2 } from "lucide-react";

type AuthMode = "login" | "register" | "forgot" | "reset" | "otp-login";
type LoginState = "idle" | "loading" | "success" | "error";

function getLoginErrorMessage(errorCode: string): string {
  if (errorCode === "CredentialsSignin") return "凭证验证失败";
  if (errorCode === "Configuration") return "认证服务不可用";
  return "请稍后重试";
}

function flattenBackendDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) {
          return String((item as { msg?: unknown }).msg || "");
        }
        return "";
      })
      .filter(Boolean)
      .join("；");
  }
  if (detail && typeof detail === "object") {
    const value = detail as { detail?: unknown; msg?: unknown; message?: unknown };
    return flattenBackendDetail(value.detail || value.msg || value.message || "");
  }
  return "";
}

function sanitizeBackendError(detail: unknown): string {
  const text = flattenBackendDetail(detail);
  const lower = text.toLowerCase();
  if (lower.includes("already") || text.includes("已存在") || lower.includes("exists")) return "该邮箱已注册";
  if (lower.includes("weak") || text.includes("强度")) return "密码强度不足";
  if (lower.includes("email") && (lower.includes("valid") || lower.includes("reserved") || text.includes("邮箱"))) return "邮箱格式无效";
  if (lower.includes("invalid") || text.includes("无效")) return "输入信息无效";
  if (lower.includes("expired") || text.includes("过期")) return "验证码已过期，请重新获取";
  if (lower.includes("rate") || text.includes("频繁")) return "请求过于频繁，请稍后重试";
  if (text.includes("SMTP") || text.includes("邮件")) return "邮件服务未配置，请联系管理员或使用密码登录";
  return "操作失败，请稍后重试";
}

async function waitForSessionReady(maxAttempts = 8, intervalMs = 250): Promise<boolean> {
  for (let i = 0; i < maxAttempts; i += 1) {
    const session = await getSession();
    if (session?.user) return true;
    await new Promise((resolve) => window.setTimeout(resolve, intervalMs));
  }
  return false;
}

interface InputFieldProps {
  type: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  label: string;
  showToggle?: boolean;
  showValue?: boolean;
  onToggle?: () => void;
  maxLength?: number;
  inputMode?: React.HTMLAttributes<HTMLInputElement>["inputMode"];
  autoComplete?: string;
  disabled?: boolean;
}

function InputField({
  type,
  value,
  onChange,
  placeholder,
  label,
  showToggle,
  showValue,
  onToggle,
  maxLength,
  inputMode,
  autoComplete,
  disabled,
}: InputFieldProps) {
  const [focused, setFocused] = useState(false);
  const inputType = showToggle ? (showValue ? "text" : "password") : type;
  const isFilled = value.length > 0;

  return (
    <div>
      <label
        className={`block text-[11px] font-mono uppercase tracking-[0.15em] mb-1.5 transition-colors ${
          focused ? "text-accent" : isFilled ? "text-ink-secondary" : "text-ink-tertiary"
        }`}
      >
        {label}
      </label>
      <div className="relative">
        <input
          type={inputType}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          className="w-full bg-transparent text-ink text-base py-2.5 px-0 border-0 border-b border-line focus:outline-none focus:border-accent transition-colors duration-150 placeholder:text-ink-tertiary disabled:opacity-50 disabled:cursor-not-allowed"
          placeholder={placeholder}
          maxLength={maxLength}
          inputMode={inputMode}
          autoComplete={autoComplete}
        />
        {showToggle && onToggle && (
          <button
            type="button"
            onClick={onToggle}
            className="absolute right-0 top-1/2 -translate-y-1/2 text-ink-tertiary hover:text-ink-secondary text-xs font-mono uppercase tracking-wider transition-colors"
          >
            {showValue ? "隐藏" : "显示"}
          </button>
        )}
      </div>
    </div>
  );
}

export default function HomePage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [otpRequestSent, setOtpRequestSent] = useState(false);
  const [otpEmailLocked, setOtpEmailLocked] = useState("");
  const [otpSending, setOtpSending] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [loginState, setLoginState] = useState<LoginState>("idle");
  const [lockedResetEmail, setLockedResetEmail] = useState("");

  const isAuthenticated = status === "authenticated";

  useEffect(() => {
    if (isAuthenticated) {
      router.push("/dashboard");
    }
  }, [isAuthenticated, router]);

  const handleCredentialsLogin = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      setLoading(true);
      setLoginState("loading");
      setMessage("");

      try {
        const result = await signIn("credentials", { email, password, redirect: false });

        if (result?.error) {
          setLoginState("error");
          setMessage(getLoginErrorMessage(result.error));
          return;
        }

        if (!result?.ok) {
          setLoginState("error");
          setMessage("认证流程未完成");
          return;
        }

        const ready = await waitForSessionReady();
        if (!ready) {
          setLoginState("error");
          setMessage("会话未建立，请刷新页面重试");
          return;
        }

        setLoginState("success");
        setMessage("登录成功，正在进入系统...");
        setTimeout(() => {
          router.push("/dashboard");
          router.refresh();
        }, 800);
      } catch {
        setLoginState("error");
        setMessage("请稍后重试");
      } finally {
        setLoading(false);
      }
    },
    [email, password, router],
  );

  const handleRegister = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      if (password !== confirmPassword) {
        setMessage("密码不匹配");
        return;
      }
      setLoading(true);
      setMessage("");

      try {
        const res = await fetch("/api/backend/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password, display_name: displayName || undefined }),
        });
        const data = await res.json();

        if (!res.ok) {
          setMessage(`注册失败: ${sanitizeBackendError(data.detail || "")}`);
          return;
        }

        setMessage("用户已创建，正在自动登录...");

        const loginResult = await signIn("credentials", {
          email,
          password,
          redirect: false,
        });

        if (loginResult?.ok) {
          const ready = await waitForSessionReady();
          if (ready) {
            router.push("/dashboard");
            return;
          }
        }

        setTimeout(() => setMode("login"), 1500);
      } catch {
        setMessage("网络错误，注册请求失败");
      } finally {
        setLoading(false);
      }
    },
    [email, password, confirmPassword, displayName, router],
  );

  const handleForgotPassword = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      setLoading(true);
      setMessage("");

      try {
        const res = await fetch("/api/backend/auth/password/reset/request", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email }),
        });
        const data = await res.json();

        if (!res.ok) {
          setMessage(`请求失败: ${sanitizeBackendError(data.detail || "")}`);
          return;
        }

        if (data.dev_code) {
          setMessage(`开发模式: 验证码为 ${data.dev_code}`);
        } else {
          setMessage("验证码已发送至邮箱");
        }
        setLockedResetEmail(email);
        setMode("reset");
      } catch {
        setMessage("网络错误，请求失败");
      } finally {
        setLoading(false);
      }
    },
    [email],
  );

  const handleResetPassword = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      if (!/^\d{4,6}$/.test(otpCode)) {
        setMessage("验证码必须为4-6位数字");
        return;
      }
      if (password !== confirmPassword) {
        setMessage("密码不匹配");
        return;
      }
      setLoading(true);
      setMessage("");

      try {
        const res = await fetch("/api/backend/auth/password/reset/confirm", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: lockedResetEmail || email, code: otpCode, new_password: password }),
        });
        const data = await res.json();

        if (!res.ok) {
          setMessage(`重置失败: ${sanitizeBackendError(data.detail || "")}`);
          return;
        }

        setMessage("密码已重置，正在自动登录...");

        const loginResult = await signIn("credentials", {
          email: lockedResetEmail || email,
          password,
          redirect: false,
        });

        if (loginResult?.ok) {
          const ready = await waitForSessionReady();
          if (ready) {
            router.push("/dashboard");
            return;
          }
        }

        setTimeout(() => setMode("login"), 1500);
      } catch {
        setMessage("网络错误，重置请求失败");
      } finally {
        setLoading(false);
      }
    },
    [email, lockedResetEmail, otpCode, password, confirmPassword, router],
  );

  const handleLogout = useCallback(async () => {
    await signOut({ redirect: false });
    setMessage("已退出登录");
    setLoginState("idle");
    router.refresh();
  }, [router]);

  const handleOtpRequest = useCallback(
    async (event?: React.FormEvent) => {
      if (event) event.preventDefault();
      const target = (otpRequestSent ? otpEmailLocked : email).trim().toLowerCase();
      if (!target) {
        setMessage("请输入邮箱");
        return;
      }
      setOtpSending(true);
      setLoading(true);
      setMessage("");
      try {
        const res = await fetch("/api/backend/auth/login/otp/request", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: target }),
        });
        const data = (await res.json().catch(() => ({}))) as { detail?: string; message?: string };
        if (!res.ok) {
          setMessage(`发送失败: ${sanitizeBackendError(data.detail || "")}`);
          return;
        }
        setOtpRequestSent(true);
        setOtpEmailLocked(target);
        setMessage(data.message || "验证码已发送至邮箱");
      } catch {
        setMessage("网络错误，验证码发送失败");
      } finally {
        setOtpSending(false);
        setLoading(false);
      }
    },
    [email, otpEmailLocked, otpRequestSent],
  );

  const handleOtpLogin = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      if (!/^\d{4,6}$/.test(otpCode)) {
        setMessage("验证码必须为4-6位数字");
        return;
      }
      setLoading(true);
      setLoginState("loading");
      setMessage("");
      try {
        const result = await signIn("credentials", {
          email: otpEmailLocked,
          otp: otpCode,
          redirect: false,
        });
        if (result?.error) {
          setLoginState("error");
          setMessage(sanitizeBackendError(getLoginErrorMessage(result.error)));
          return;
        }
        if (!result?.ok) {
          setLoginState("error");
          setMessage("认证流程未完成");
          return;
        }
        const ready = await waitForSessionReady();
        if (!ready) {
          setLoginState("error");
          setMessage("会话未建立，请刷新页面重试");
          return;
        }
        setLoginState("success");
        setMessage("登录成功，正在进入系统...");
        setTimeout(() => {
          router.push("/dashboard");
          router.refresh();
        }, 600);
      } catch {
        setLoginState("error");
        setMessage("请稍后重试");
      } finally {
        setLoading(false);
      }
    },
    [otpCode, otpEmailLocked, router],
  );

  const switchMode = (newMode: AuthMode) => {
    setMode(newMode);
    setMessage("");
    setLoginState("idle");
    setOtpRequestSent(false);
    setOtpEmailLocked("");
    setOtpCode("");
  };

  const getTitle = () => {
    switch (mode) {
      case "login": return "登录";
      case "register": return "注册";
      case "forgot": return "找回密码";
      case "reset": return "重置密码";
      case "otp-login": return otpRequestSent ? "输入验证码" : "邮箱验证码登录";
    }
  };

  const getEyebrow = () => {
    switch (mode) {
      case "login": return "01 / SIGN IN";
      case "register": return "02 / CREATE ACCOUNT";
      case "forgot": return "03 / RESET PASSWORD";
      case "reset": return "04 / NEW PASSWORD";
      case "otp-login": return "05 / ONE-TIME CODE";
    }
  };

  const getDescription = () => {
    switch (mode) {
      case "login": return "使用邮箱与密码进入 AI-CyberSentinel 防御中心。";
      case "register": return "创建新账号以访问 SOC 仪表板。";
      case "forgot": return "我们会将验证码发送至你的邮箱。";
      case "reset": return "输入邮箱中的验证码，并设置新密码。";
      case "otp-login": return otpRequestSent
        ? `验证码已发送至 ${otpEmailLocked || email}`
        : "无需密码，使用邮箱验证码直接登录。";
    }
  };

  /* ---------- 已登录视图 ---------- */
  if (isAuthenticated) {
    return (
      <div className="min-h-screen w-full flex items-center justify-center bg-bg">
        <motion.div
          initial={false}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.24 }}
          className="w-full max-w-md px-6"
        >
          <div className="text-[11px] font-mono uppercase tracking-[0.2em] text-accent mb-6">
            · 已登录
          </div>
          <h1 className="font-display text-5xl text-ink mb-2 leading-[1.05] tracking-tight">
            欢迎回来
          </h1>
          <p className="text-ink-secondary text-sm mb-10">
            {session?.user?.email || "unknown"}
          </p>
          <div className="space-y-3">
            <button onClick={() => router.push("/dashboard")} className="btn-primary w-full">
              进入控制台 <ArrowRight className="w-4 h-4" />
            </button>
            <button onClick={handleLogout} className="btn-ghost w-full">
              <LogOut className="w-4 h-4" /> 退出登录
            </button>
          </div>
        </motion.div>
      </div>
    );
  }

  /* ---------- 主视图 ---------- */
  return (
    <div className="min-h-screen w-full bg-bg">
      {/* 顶部 logo */}
      <header className="px-6 sm:px-10 py-6 flex items-center justify-between border-b border-line">
        <div className="flex items-baseline gap-3">
          <span className="font-display text-xl text-ink tracking-tight">AI-CyberSentinel</span>
          <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-ink-tertiary hidden sm:inline">
            SOC · v2
          </span>
        </div>
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-ink-tertiary">
          {new Date().toLocaleDateString("zh-CN", { year: "numeric", month: "short", day: "2-digit" })}
        </div>
      </header>

      {/* 主区域：单列居中 */}
      <main className="px-6 sm:px-10 py-12 sm:py-20">
        <div className="max-w-[440px] mx-auto">
          <AnimatePresence mode="wait">
            <motion.div
              key={`${mode}-header`}
              initial={false}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
              className="mb-10"
            >
              <div className="text-[11px] font-mono uppercase tracking-[0.2em] text-accent mb-3">
                {getEyebrow()}
              </div>
              <h1 className="font-display text-5xl sm:text-6xl text-ink leading-[1.02] tracking-tight mb-4">
                {getTitle()}
              </h1>
              <p className="text-ink-secondary text-sm leading-relaxed max-w-[360px]">
                {getDescription()}
              </p>
            </motion.div>
          </AnimatePresence>

          <AnimatePresence mode="wait">
            <motion.form
              key={mode}
              initial={false}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
              onSubmit={
                mode === "login"
                  ? handleCredentialsLogin
                  : mode === "register"
                    ? handleRegister
                    : mode === "forgot"
                      ? handleForgotPassword
                      : mode === "otp-login"
                        ? (otpRequestSent ? handleOtpLogin : handleOtpRequest)
                        : handleResetPassword
              }
              className="space-y-6"
            >
              {mode === "register" && (
                <InputField
                  type="text"
                  value={displayName}
                  onChange={setDisplayName}
                  placeholder="你的名字"
                  label="昵称（可选）"
                />
              )}

              <InputField
                type="email"
                value={
                  mode === "reset" && lockedResetEmail
                    ? lockedResetEmail
                    : mode === "otp-login" && otpRequestSent
                      ? otpEmailLocked
                      : email
                }
                onChange={
                  mode === "reset" && lockedResetEmail
                    ? () => {}
                    : mode === "otp-login" && otpRequestSent
                      ? () => {}
                      : setEmail
                }
                placeholder="you@company.com"
                label="邮箱"
                disabled={
                  (mode === "reset" && !!lockedResetEmail) ||
                  (mode === "otp-login" && otpRequestSent)
                }
              />

              {(mode === "reset" || (mode === "otp-login" && otpRequestSent)) && (
                <InputField
                  type="text"
                  value={otpCode}
                  onChange={(v: string) => setOtpCode(v.replace(/\D/g, "").slice(0, 6))}
                  placeholder="6 位数字"
                  label="验证码"
                  maxLength={6}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                />
              )}

              {(mode === "login" || mode === "register" || mode === "reset") && (
                <InputField
                  type="password"
                  value={password}
                  onChange={setPassword}
                  placeholder={mode === "register" ? "至少 8 位" : "输入密码"}
                  label="密码"
                  showToggle
                  showValue={showPassword}
                  onToggle={() => setShowPassword(!showPassword)}
                />
              )}

              {(mode === "register" || mode === "reset") && (
                <InputField
                  type="password"
                  value={confirmPassword}
                  onChange={setConfirmPassword}
                  placeholder="再次输入"
                  label="确认密码"
                  showToggle
                  showValue={showPassword}
                  onToggle={() => setShowPassword(!showPassword)}
                />
              )}

              {mode === "otp-login" && otpRequestSent && (
                <button
                  type="button"
                  onClick={() => {
                    setOtpCode("");
                    void handleOtpRequest();
                  }}
                  disabled={otpSending || loading}
                  className="text-xs text-ink-secondary hover:text-accent font-mono uppercase tracking-wider transition-colors disabled:opacity-50"
                >
                  {otpSending ? "重新发送中..." : "← 重新发送验证码"}
                </button>
              )}

              {/* 消息提示 */}
              <AnimatePresence>
                {message && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.16 }}
                    className={`text-xs px-3 py-2.5 flex items-start gap-2 overflow-hidden rounded-md ${
                      loginState === "error" || message.includes("失败") || message.includes("错误")
                        ? "text-danger bg-danger-soft border-l-2 border-danger"
                        : message.includes("成功")
                          ? "text-success bg-success-soft border-l-2 border-success"
                          : "text-warning bg-warning-soft border-l-2 border-warning"
                    }`}
                  >
                    {loginState === "error" || message.includes("失败") ? (
                      <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                    ) : (
                      <CheckCircle2 className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                    )}
                    <span>{message}</span>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* 提交按钮 */}
              <div className="pt-2">
                <button
                  type="submit"
                  disabled={loading || loginState === "success"}
                  className="btn-primary w-full"
                >
                  <span>
                    {loading ? "处理中..." : loginState === "success" ? "登录成功" : getTitle()}
                  </span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </motion.form>
          </AnimatePresence>

          {/* 模式切换链接 */}
          <div className="mt-10 pt-6 border-t border-line">
            <AnimatePresence mode="wait">
              {mode === "login" ? (
                <motion.div
                  key="login-links"
                  initial={false}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="flex flex-col gap-2.5 text-sm"
                >
                  <button
                    type="button"
                    onClick={() => switchMode("register")}
                    className="text-ink hover:text-accent text-left transition-colors flex items-center gap-2"
                  >
                    <span className="text-ink-tertiary font-mono text-xs">→</span>
                    创建新账号
                  </button>
                  <button
                    type="button"
                    onClick={() => switchMode("forgot")}
                    className="text-ink-secondary hover:text-ink text-left transition-colors flex items-center gap-2"
                  >
                    <span className="text-ink-tertiary font-mono text-xs">→</span>
                    忘记密码
                  </button>
                  <button
                    type="button"
                    onClick={() => switchMode("otp-login")}
                    className="text-ink-secondary hover:text-ink text-left transition-colors flex items-center gap-2"
                  >
                    <span className="text-ink-tertiary font-mono text-xs">→</span>
                    使用邮箱验证码登录
                  </button>
                </motion.div>
              ) : (
                <motion.button
                  key="back-link"
                  initial={false}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  type="button"
                  onClick={() => switchMode("login")}
                  className="text-ink-secondary hover:text-ink text-sm transition-colors flex items-center gap-2"
                >
                  <span className="text-ink-tertiary font-mono text-xs">←</span>
                  返回登录
                </motion.button>
              )}
            </AnimatePresence>
          </div>
        </div>
      </main>

      {/* 底部 — 极简 metadata */}
      <footer className="px-6 sm:px-10 py-6 mt-8 border-t border-line flex items-center justify-between text-[10px] font-mono uppercase tracking-[0.2em] text-ink-tertiary">
        <span>SECURE · ENCRYPTED · LOGGED</span>
        <span className="hidden sm:inline">© AI-CYBERSENTINEL</span>
      </footer>
    </div>
  );
}
