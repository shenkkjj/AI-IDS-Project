"use client";

import { useState, useCallback, useEffect } from "react";
import { getSession, signIn, signOut, useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Eye, EyeOff, Shield, Mail, Lock, ArrowRight, UserPlus, KeyRound, ChevronLeft } from "lucide-react";

type AuthMode = "login" | "register" | "forgot" | "reset";
type LoginState = "idle" | "loading" | "success" | "error";

function getLoginErrorMessage(errorCode: string): string {
  if (errorCode === "CredentialsSignin") return "凭证验证失败";
  if (errorCode === "Configuration") return "认证服务不可用";
  return "请稍后重试";
}

function sanitizeBackendError(detail: string): string {
  if (detail.includes("already") || detail.includes("已存在") || detail.includes("exists")) return "该邮箱已注册";
  if (detail.includes("weak") || detail.includes("强度")) return "密码强度不足";
  if (detail.includes("invalid") || detail.includes("无效")) return "输入信息无效";
  if (detail.includes("expired") || detail.includes("过期")) return "验证码已过期，请重新获取";
  if (detail.includes("rate") || detail.includes("频繁")) return "请求过于频繁，请稍后重试";
  if (detail.includes("SMTP") || detail.includes("邮件")) return "邮件服务未配置，请联系管理员或使用密码登录";
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

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.1 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] as [number, number, number, number] },
  },
};

const leftPanelVariants = {
  hidden: { opacity: 0, x: -40 },
  visible: {
    opacity: 1,
    x: 0,
    transition: { duration: 0.7, ease: [0.25, 0.46, 0.45, 0.94] as [number, number, number, number] },
  },
};

const rightPanelVariants = {
  hidden: { opacity: 0, x: 40 },
  visible: {
    opacity: 1,
    x: 0,
    transition: { duration: 0.7, delay: 0.15, ease: [0.25, 0.46, 0.45, 0.94] as [number, number, number, number] },
  },
};

const circleVariants = {
  hidden: { scale: 0, opacity: 0 },
  visible: (i: number) => ({
    scale: 1,
    opacity: 1,
    transition: { duration: 1.2, delay: 0.3 + i * 0.2, ease: "easeOut" as const },
  }),
};

const formVariants = {
  hidden: { opacity: 0, y: 15 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: "easeOut" as const },
  },
  exit: {
    opacity: 0,
    y: -10,
    transition: { duration: 0.2 },
  },
};

function InputField({
  type,
  value,
  onChange,
  placeholder,
  icon: Icon,
  showToggle,
  showValue,
  onToggle,
  maxLength,
  inputMode,
  autoComplete,
  disabled,
}: {
  type: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  icon: React.ElementType;
  showToggle?: boolean;
  showValue?: boolean;
  onToggle?: () => void;
  maxLength?: number;
  inputMode?: React.HTMLAttributes<HTMLInputElement>["inputMode"];
  autoComplete?: string;
  disabled?: boolean;
}) {
  const [focused, setFocused] = useState(false);

  return (
    <motion.div
      variants={itemVariants}
      className="relative"
    >
      <div className={`absolute left-4 top-1/2 -translate-y-1/2 transition-colors duration-300 ${focused ? "text-primary" : "text-text-tertiary"}`}>
        <Icon className="w-5 h-5" />
      </div>
      <input
        type={showToggle ? (showValue ? "text" : "password") : type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        className="w-full h-12 pl-12 pr-10 bg-surface border border-border-subtle rounded-apple text-text text-base placeholder:text-text-tertiary focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all duration-300"
        placeholder={placeholder}
        maxLength={maxLength}
        inputMode={inputMode}
        autoComplete={autoComplete}
      />
      {showToggle && onToggle && (
        <button
          type="button"
          onClick={onToggle}
          className="absolute right-4 top-1/2 -translate-y-1/2 text-text-tertiary hover:text-text transition-colors duration-200"
        >
          {showValue ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
        </button>
      )}
    </motion.div>
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
    [email, password, router]
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
    [email, password, confirmPassword, displayName, router]
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
    [email]
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
    [email, lockedResetEmail, otpCode, password, confirmPassword, router]
  );

  const handleLogout = useCallback(async () => {
    await signOut({ redirect: false });
    setMessage("已退出登录");
    setLoginState("idle");
    router.refresh();
  }, [router]);

  const switchMode = (newMode: AuthMode) => {
    setMode(newMode);
    setMessage("");
    setLoginState("idle");
  };

  const getTitle = () => {
    switch (mode) {
      case "login": return "登录";
      case "register": return "注册账号";
      case "forgot": return "找回密码";
      case "reset": return "重置密码";
    }
  };

  const getSubtitle = () => {
    switch (mode) {
      case "login": return "欢迎回到 AI-CyberSentinel";
      case "register": return "创建您的新账号";
      case "forgot": return "我们将向您的邮箱发送验证码";
      case "reset": return "请输入验证码和新密码";
    }
  };

  if (isAuthenticated) {
    return (
      <div className="min-h-screen w-full flex items-center justify-center bg-background">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
          className="bg-surface rounded-apple-lg shadow-card p-8 max-w-sm w-full mx-4 text-center"
        >
          <div className="w-16 h-16 bg-primary-subtle rounded-full flex items-center justify-center mx-auto mb-4">
            <Shield className="w-8 h-8 text-primary" />
          </div>
          <h2 className="text-xl font-semibold text-text mb-1">已登录</h2>
          <p className="text-text-secondary text-sm mb-6">{session?.user?.email || "unknown"}</p>
          <div className="space-y-3">
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              type="button"
              onClick={() => router.push("/dashboard")}
              className="w-full h-12 bg-primary hover:bg-primary-hover text-white font-medium rounded-apple transition-colors"
            >
              进入控制台
            </motion.button>
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              type="button"
              onClick={handleLogout}
              className="w-full h-12 bg-transparent hover:bg-background text-danger font-medium rounded-apple transition-colors"
            >
              退出登录
            </motion.button>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen w-full flex bg-background">
      {/* Left Panel - Branding */}
      <motion.div
        variants={leftPanelVariants}
        initial="hidden"
        animate="visible"
        className="hidden lg:flex lg:w-1/2 bg-primary relative flex-col justify-between p-12 text-white overflow-hidden"
      >
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="relative z-10"
        >
          <motion.div variants={itemVariants} className="flex items-center gap-3 mb-8">
            <div className="w-10 h-10 bg-white/20 rounded-apple flex items-center justify-center backdrop-blur-sm">
              <Shield className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-semibold tracking-tight">AI-CyberSentinel</span>
          </motion.div>
          <motion.h1 variants={itemVariants} className="text-4xl font-bold leading-tight mb-4">
            智能入侵检测
            <br />
            守护数字安全
          </motion.h1>
          <motion.p variants={itemVariants} className="text-white/70 text-lg max-w-md leading-relaxed">
            基于人工智能的实时威胁检测与防御系统，为您的网络资产提供全天候保护。
          </motion.p>
        </motion.div>

        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="relative z-10"
        >
          <motion.div variants={itemVariants} className="flex items-center gap-4 mb-4">
            <div className="w-12 h-12 bg-white/10 rounded-full flex items-center justify-center">
              <span className="text-2xl font-bold">99.9%</span>
            </div>
            <div>
              <div className="font-semibold">威胁检测率</div>
              <div className="text-white/60 text-sm">基于深度学习的实时分析</div>
            </div>
          </motion.div>
          <motion.div variants={itemVariants} className="flex items-center gap-4">
            <div className="w-12 h-12 bg-white/10 rounded-full flex items-center justify-center">
              <span className="text-2xl font-bold">&lt;1s</span>
            </div>
            <div>
              <div className="font-semibold">响应时间</div>
              <div className="text-white/60 text-sm">毫秒级威胁拦截</div>
            </div>
          </motion.div>
        </motion.div>

        {/* Decorative circles */}
        <motion.div
          custom={0}
          variants={circleVariants}
          initial="hidden"
          animate="visible"
          className="absolute top-1/4 right-0 w-[28rem] h-[28rem] bg-white/[0.08] rounded-full -translate-y-1/2 translate-x-1/3 blur-sm"
        />
        <motion.div
          custom={1}
          variants={circleVariants}
          initial="hidden"
          animate="visible"
          className="absolute bottom-0 left-1/4 w-72 h-72 bg-white/[0.06] rounded-full translate-y-1/3 blur-sm"
        />
        <motion.div
          custom={2}
          variants={circleVariants}
          initial="hidden"
          animate="visible"
          className="absolute top-1/2 left-1/2 w-48 h-48 bg-white/[0.04] rounded-full -translate-x-1/2 -translate-y-1/2"
        />
      </motion.div>

      {/* Right Panel - Form */}
      <motion.div
        variants={rightPanelVariants}
        initial="hidden"
        animate="visible"
        className="w-full lg:w-1/2 flex items-center justify-center p-6 lg:p-12"
      >
        <div className="w-full max-w-md">
          {/* Mobile Logo */}
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="lg:hidden flex items-center justify-center gap-2 mb-8"
          >
            <div className="w-8 h-8 bg-primary rounded-[10px] flex items-center justify-center">
              <Shield className="w-4 h-4 text-white" />
            </div>
            <span className="text-lg font-semibold text-text">AI-CyberSentinel</span>
          </motion.div>

          <AnimatePresence mode="wait">
            <motion.div
              key={mode}
              variants={formVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
              className="mb-8"
            >
              <h2 className="text-2xl font-semibold text-text mb-1">{getTitle()}</h2>
              <p className="text-text-secondary">{getSubtitle()}</p>
            </motion.div>
          </AnimatePresence>

          <AnimatePresence mode="wait">
            <motion.form
              key={mode}
              variants={formVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
              onSubmit={
                mode === "login"
                  ? handleCredentialsLogin
                  : mode === "register"
                  ? handleRegister
                  : mode === "forgot"
                  ? handleForgotPassword
                  : handleResetPassword
              }
              className="space-y-4"
            >
              {mode === "register" && (
                <InputField
                  type="text"
                  value={displayName}
                  onChange={setDisplayName}
                  placeholder="昵称（可选）"
                  icon={UserPlus}
                />
              )}

              <InputField
                type="email"
                value={mode === "reset" && lockedResetEmail ? lockedResetEmail : email}
                onChange={mode === "reset" && lockedResetEmail ? () => {} : setEmail}
                placeholder="邮箱地址"
                icon={Mail}
                disabled={mode === "reset" && !!lockedResetEmail}
              />

              {mode === "reset" && (
                <InputField
                  type="text"
                  value={otpCode}
                  onChange={(v: string) => setOtpCode(v.replace(/\D/g, "").slice(0, 6))}
                  placeholder="验证码（4-6位数字）"
                  icon={KeyRound}
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
                  placeholder="密码"
                  icon={Lock}
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
                  placeholder="确认密码"
                  icon={Lock}
                  showToggle
                  showValue={showPassword}
                  onToggle={() => setShowPassword(!showPassword)}
                />
              )}

              {/* Message */}
              <AnimatePresence>
                {message && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className={`text-sm px-4 py-3 rounded-apple overflow-hidden ${
                      loginState === "error" || message.includes("失败") || message.includes("错误")
                        ? "text-danger bg-danger-subtle"
                        : message.includes("成功") || message.includes("通过")
                        ? "text-success bg-success-subtle"
                        : "text-warning bg-warning-subtle"
                    }`}
                  >
                    {message}
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Submit Button */}
              <motion.button
                type="submit"
                disabled={loading || loginState === "success"}
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.98 }}
                className="w-full h-12 bg-primary hover:bg-primary-hover text-white font-medium rounded-apple transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-sm hover:shadow-md"
              >
                <span>{loading ? "处理中..." : loginState === "success" ? "登录成功" : getTitle()}</span>
                <motion.span
                  animate={loading ? { x: [0, 4, 0] } : {}}
                  transition={{ repeat: Infinity, duration: 1 }}
                >
                  <ArrowRight className="w-4 h-4" />
                </motion.span>
              </motion.button>
            </motion.form>
          </AnimatePresence>

          {/* Mode Switch Links */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
            className="mt-6 pt-6 border-t border-border-subtle space-y-3"
          >
            <AnimatePresence mode="wait">
              {mode === "login" ? (
                <motion.div
                  key="login-links"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="space-y-3"
                >
                  <motion.button
                    type="button"
                    onClick={() => switchMode("register")}
                    whileHover={{ x: 2 }}
                    className="w-full text-center text-primary hover:text-primary-hover text-sm font-medium transition-colors flex items-center justify-center gap-2"
                  >
                    <UserPlus className="w-4 h-4" />
                    <span>创建新账号</span>
                  </motion.button>
                  <motion.button
                    type="button"
                    onClick={() => switchMode("forgot")}
                    whileHover={{ x: 2 }}
                    className="w-full text-center text-text-secondary hover:text-text text-sm transition-colors flex items-center justify-center gap-2"
                  >
                    <KeyRound className="w-4 h-4" />
                    <span>忘记密码？</span>
                  </motion.button>
                </motion.div>
              ) : (
                <motion.button
                  key="back-link"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  type="button"
                  onClick={() => switchMode("login")}
                  whileHover={{ x: -2 }}
                  className="w-full text-center text-primary hover:text-primary-hover text-sm font-medium transition-colors flex items-center justify-center gap-2"
                >
                  <ChevronLeft className="w-4 h-4" />
                  <span>返回登录</span>
                </motion.button>
              )}
            </AnimatePresence>
          </motion.div>
        </div>
      </motion.div>
    </div>
  );
}
