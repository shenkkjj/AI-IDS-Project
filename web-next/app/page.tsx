"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { getSession, signIn, signOut, useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, Shield, Mail, Lock, Terminal, Fingerprint, ArrowRight, UserPlus, KeyRound, ChevronLeft } from "lucide-react";
import AnimatedCharacters from "./components/animated-characters/AnimatedCharacters";

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

// Matrix Rain Component
function MatrixRain() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    const chars = "01アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン";
    const fontSize = 14;
    const columns = canvas.width / fontSize;
    const drops: number[] = Array(Math.floor(columns)).fill(1);

    const draw = () => {
      ctx.fillStyle = "rgba(0, 0, 0, 0.05)";
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      ctx.fillStyle = "#00ff41";
      ctx.font = `${fontSize}px monospace`;

      drops.forEach((drop, i) => {
        const char = chars[Math.floor(Math.random() * chars.length)];
        ctx.fillText(char, i * fontSize, drop * fontSize);

        if (drop * fontSize > canvas.height && Math.random() > 0.975) {
          drops[i] = 0;
        }
        drops[i] += 1;
      });
    };

    const interval = setInterval(draw, 35);

    const handleResize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    window.addEventListener("resize", handleResize);

    return () => {
      clearInterval(interval);
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  return <canvas ref={canvasRef} className="fixed inset-0 z-0 opacity-30" />;
}

// Circuit Board Background
function CircuitBackground() {
  return (
    <div className="fixed inset-0 z-0 opacity-10 pointer-events-none">
      <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern id="circuit" x="0" y="0" width="100" height="100" patternUnits="userSpaceOnUse">
            <path d="M10 10 L30 10 L30 30 L50 30" fill="none" stroke="#00ff41" strokeWidth="0.5" />
            <circle cx="10" cy="10" r="2" fill="#00ff41" />
            <circle cx="30" cy="30" r="2" fill="#00ff41" />
            <circle cx="50" cy="30" r="2" fill="#00ff41" />
            <path d="M60 60 L80 60 L80 80 L100 80" fill="none" stroke="#9d4edd" strokeWidth="0.5" />
            <circle cx="60" cy="60" r="2" fill="#9d4edd" />
            <circle cx="80" cy="80" r="2" fill="#9d4edd" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#circuit)" />
      </svg>
    </div>
  );
}

// Glitch Text Effect
function GlitchText({ text, className = "" }: { text: string; className?: string }) {
  return (
    <div className={`relative inline-block ${className}`}>
      <span className="relative z-10">{text}</span>
      <span className="absolute top-0 left-0 text-red-500/40" style={{ clipPath: "inset(0 0 55% 0)", transform: "translateX(1px)" }}>
        {text}
      </span>
      <span className="absolute top-0 left-0 text-cyan-400/40" style={{ clipPath: "inset(55% 0 0 0)", transform: "translateX(-1px)" }}>
        {text}
      </span>
    </div>
  );
}

// Iris Scanner Component
function IrisScanner({ scanning }: { scanning: boolean }) {
  return (
    <div className="relative w-24 h-24 mx-auto mb-4">
      <div className={`absolute inset-0 rounded-full border-2 ${scanning ? "border-cyan-400 animate-pulse" : "border-cyan-900"}`}>
        <div className={`absolute inset-2 rounded-full border ${scanning ? "border-cyan-300" : "border-cyan-950"}`} />
        <div className={`absolute inset-4 rounded-full border-2 ${scanning ? "border-cyan-200" : "border-cyan-950"}`} />
        <div className="absolute inset-0 flex items-center justify-center">
          <Fingerprint className={`w-8 h-8 ${scanning ? "text-cyan-400 animate-pulse" : "text-cyan-800"}`} />
        </div>
      </div>
      {scanning && (
        <div className="absolute inset-0 rounded-full bg-cyan-400/10 animate-ping" />
      )}
      <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 text-xs font-mono text-cyan-600">
        {scanning ? "扫描中..." : "待命"}
      </div>
    </div>
  );
}

// Terminal Input Component
function TerminalInput({
  type,
  value,
  onChange,
  placeholder,
  icon: Icon,
  showToggle,
  showValue,
  onToggle,
  onFocus,
  onBlur,
  maxLength,
  inputMode,
  autoComplete,
}: {
  type: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  icon: React.ElementType;
  showToggle?: boolean;
  showValue?: boolean;
  onToggle?: () => void;
  onFocus?: () => void;
  onBlur?: () => void;
  maxLength?: number;
  inputMode?: React.HTMLAttributes<HTMLInputElement>["inputMode"];
  autoComplete?: string;
}) {
  return (
    <div className="relative group">
      <div className="absolute left-3 top-1/2 -translate-y-1/2 text-cyan-700 group-focus-within:text-cyan-400 transition-colors">
        <Icon className="w-4 h-4" />
      </div>
      <div className="absolute left-8 top-1/2 -translate-y-1/2 text-cyan-600 font-mono text-sm pointer-events-none">
        {">"}
      </div>
      <input
        type={showToggle ? (showValue ? "text" : "password") : type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={onFocus}
        onBlur={onBlur}
        className="w-full h-12 pl-12 pr-10 bg-black/60 border border-cyan-900/50 rounded text-cyan-400 font-mono text-sm placeholder:text-cyan-900 focus:outline-none focus:border-cyan-500 focus:shadow-[0_0_15px_rgba(0,255,255,0.2)] transition-all"
        placeholder={placeholder}
        maxLength={maxLength}
        inputMode={inputMode}
        autoComplete={autoComplete}
      />
      {showToggle && onToggle && (
        <button
          type="button"
          onClick={onToggle}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-cyan-700 hover:text-cyan-400 transition-colors"
        >
          {showValue ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
        </button>
      )}
      <div className="absolute bottom-0 left-0 h-px w-0 group-focus-within:w-full bg-cyan-400 transition-all duration-500" />
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
  const [showPassword, setShowPassword] = useState(false);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [loginState, setLoginState] = useState<LoginState>("idle");
  const [isTyping, setIsTyping] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [activeCharacter, setActiveCharacter] = useState<string | null>(null);
  const hexStreamRef = useRef<HTMLDivElement>(null);
  const [lockedResetEmail, setLockedResetEmail] = useState("");

  const isAuthenticated = status === "authenticated";

  // Auto-redirect to dashboard when already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      router.push("/dashboard");
    }
  }, [isAuthenticated, router]);

  // Generate hex stream effect - using CSS animation for performance
  useEffect(() => {
    const el = hexStreamRef.current;
    if (!el) return;
    let frameId: number;
    const updateHex = () => {
      const hex = Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16).toUpperCase()).join("");
      if (el) el.textContent = hex;
      frameId = window.setTimeout(updateHex, 800);
    };
    updateHex();
    return () => window.clearTimeout(frameId);
  }, []);

  const handleCredentialsLogin = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      setLoading(true);
      setLoginState("loading");
      setMessage("");
      setScanning(true);

      try {
        const result = await signIn("credentials", { email, password, redirect: false });

        if (result?.error) {
          setLoginState("error");
          setMessage(getLoginErrorMessage(result.error));
          setScanning(false);
          return;
        }

        if (!result?.ok) {
          setLoginState("error");
          setMessage("认证流程未完成");
          setScanning(false);
          return;
        }

        const ready = await waitForSessionReady();
        if (!ready) {
          setLoginState("error");
          setMessage("会话未建立，请刷新页面重试");
          setScanning(false);
          return;
        }

        setLoginState("success");
        setMessage("验证通过，正在进入系统...");
        setTimeout(() => {
          router.push("/dashboard");
          router.refresh();
        }, 1000);
      } catch {
        setLoginState("error");
        setMessage("请稍后重试");
        setScanning(false);
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
          setMessage(`REGISTRATION_FAILED: ${sanitizeBackendError(data.detail || "")}`);
          return;
        }

        setMessage("REGISTRATION_SUCCESS: 用户已创建，正在自动登录...");

        // Auto-login after successful registration
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

        // Fallback: switch to login mode if auto-login fails
        setTimeout(() => setMode("login"), 1500);
      } catch {
        setMessage("NETWORK_ERROR: 注册请求失败");
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
          setMessage(`REQUEST_FAILED: ${sanitizeBackendError(data.detail || "")}`);
          return;
        }

        setMessage("验证码已发送至邮箱");
        setLockedResetEmail(email);
        setMode("reset");
      } catch {
        setMessage("NETWORK_ERROR: 请求失败");
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
          setMessage(`RESET_FAILED: ${sanitizeBackendError(data.detail || "")}`);
          return;
        }

        setMessage("RESET_SUCCESS: 密码已重置，正在自动登录...");

        // Auto-login after successful password reset
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
        setMessage("NETWORK_ERROR: 重置请求失败");
      } finally {
        setLoading(false);
      }
    },
    [email, lockedResetEmail, otpCode, password, confirmPassword]
  );

  const handleLogout = useCallback(async () => {
    await signOut({ redirect: false });
    setMessage("SESSION_TERMINATED: 已退出");
    setLoginState("idle");
    router.refresh();
  }, [router]);

  const switchMode = (newMode: AuthMode) => {
    setMode(newMode);
    setMessage("");
    setLoginState("idle");
    setScanning(false);
  };

  if (isAuthenticated) {
    return (
      <div className="min-h-screen w-full flex items-center justify-center bg-black relative overflow-hidden">
        <MatrixRain />
        <CircuitBackground />
        <div className="relative z-10 bg-black/80 border border-cyan-900/50 p-8 rounded-lg shadow-[0_0_40px_rgba(0,255,255,0.1)] max-w-md w-full mx-4 backdrop-blur-sm">
          <div className="text-center mb-6">
            <div className="w-16 h-16 bg-cyan-900/30 rounded-full flex items-center justify-center mx-auto mb-4 border border-cyan-500/30">
              <Shield className="w-8 h-8 text-cyan-400" />
            </div>
            <h2 className="text-2xl font-bold text-cyan-400 font-mono mb-2">SESSION_ACTIVE</h2>
            <p className="text-cyan-700 font-mono text-sm">{session?.user?.email || "unknown"}</p>
          </div>
          <div className="space-y-3">
            <button
              type="button"
              onClick={() => router.push("/dashboard")}
              className="w-full bg-cyan-900/50 hover:bg-cyan-800/50 text-cyan-400 font-mono py-3 px-4 rounded border border-cyan-700/50 transition-all duration-300 hover:shadow-[0_0_15px_rgba(0,255,255,0.2)]"
            >
              $ cd /dashboard
            </button>
            <button
              type="button"
              onClick={handleLogout}
              className="w-full bg-red-900/20 hover:bg-red-900/30 text-red-400 font-mono py-3 px-4 rounded border border-red-800/30 transition-all duration-300"
            >
              $ logout
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen w-full flex bg-black relative overflow-hidden">
      <MatrixRain />
      <CircuitBackground />

      {/* Floating hex stream */}
      <div ref={hexStreamRef} className="fixed top-4 left-4 z-20 font-mono text-xs text-cyan-900/40 break-all max-w-xs pointer-events-none" />

      {/* Left Panel - Characters */}
      <div className="hidden lg:flex lg:w-1/2 relative flex-col justify-end items-center pb-12 z-10 pointer-events-auto">
        <div className="absolute top-12 left-12 z-20 flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-cyan-900/30 border border-cyan-500/30 flex items-center justify-center backdrop-blur-sm">
            <Shield className="w-5 h-5 text-cyan-400" />
          </div>
          <span className="text-cyan-400 text-xl font-bold tracking-wide font-mono">AI-CyberSentinel</span>
        </div>

        <AnimatedCharacters
          isTyping={isTyping}
          showPassword={showPassword}
          passwordLength={password.length}
          activeCharacter={activeCharacter}
        />

        <div className="absolute bottom-4 left-12 z-20 flex items-center gap-6">
          <span className="text-cyan-800 text-xs font-mono">SECURE_TERMINAL_V2.4.1</span>
          <span className="text-cyan-800 text-xs font-mono">ENCRYPTION: AES-256</span>
        </div>
      </div>

      {/* Right Panel - Terminal Window */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-6 lg:p-12 relative z-20">
        <div className="w-full max-w-lg">
          {/* Mobile Logo */}
          <div className="lg:hidden flex items-center justify-center gap-2 mb-8">
            <div className="w-8 h-8 rounded-lg bg-cyan-900/30 border border-cyan-500/30 flex items-center justify-center">
              <Shield className="w-4 h-4 text-cyan-400" />
            </div>
            <span className="text-lg font-bold text-cyan-400 font-mono">AI-CyberSentinel</span>
          </div>

          {/* Terminal Header */}
          <div className="bg-cyan-950/80 border border-cyan-800/50 rounded-t-lg px-4 py-2 flex items-center justify-between backdrop-blur-sm">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-cyan-400" />
            <span className="text-cyan-400 font-mono text-sm">auth_terminal.exe</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-500/50" />
            <div className="w-3 h-3 rounded-full bg-yellow-500/50" />
            <div className="w-3 h-3 rounded-full bg-green-500/50" />
          </div>
        </div>

        {/* Terminal Body */}
        <div className="bg-black/90 border-x border-b border-cyan-800/50 rounded-b-lg p-6 backdrop-blur-sm shadow-[0_0_60px_rgba(0,255,255,0.08)]">
          {/* Iris Scanner */}
          <IrisScanner scanning={scanning} />

          {/* Title */}
          <div className="text-center mb-6">
            <GlitchText
              text={mode === "login" ? "身份验证" : mode === "register" ? "新用户注册" : mode === "forgot" ? "密码找回" : "重置密码"}
              className="text-xl font-bold text-cyan-400 font-mono"
            />
            <div className="text-cyan-700 font-mono text-xs mt-2">
              {mode === "login" && "安全访问终端 V2.4.1"}
              {mode === "register" && "创建新凭证"}
              {mode === "forgot" && "身份验证已启用"}
              {mode === "reset" && "输入新认证密钥"}
            </div>
          </div>

          {/* Form */}
          <form
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
              <TerminalInput
                type="text"
                value={displayName}
                onChange={setDisplayName}
                placeholder="输入昵称"
                icon={Terminal}
                onFocus={() => setIsTyping(true)}
                onBlur={() => setIsTyping(false)}
              />
            )}

            <TerminalInput
              type="email"
              value={mode === "reset" && lockedResetEmail ? lockedResetEmail : email}
              onChange={mode === "reset" && lockedResetEmail ? () => {} : setEmail}
              placeholder="输入邮箱地址"
              icon={Mail}
              onFocus={() => setIsTyping(true)}
              onBlur={() => setIsTyping(false)}
            />

            {mode === "reset" && (
              <TerminalInput
                type="text"
                value={otpCode}
                onChange={(v: string) => setOtpCode(v.replace(/\D/g, "").slice(0, 6))}
                placeholder="输入验证码 (4-6位数字)"
                icon={KeyRound}
                onFocus={() => setIsTyping(true)}
                onBlur={() => setIsTyping(false)}
                maxLength={6}
                inputMode="numeric"
                autoComplete="one-time-code"
              />
            )}

            {(mode === "login" || mode === "register" || mode === "reset") && (
              <TerminalInput
                type="password"
                value={password}
                onChange={setPassword}
                placeholder="输入密码"
                icon={Lock}
                showToggle
                showValue={showPassword}
                onToggle={() => setShowPassword(!showPassword)}
              />
            )}

            {(mode === "register" || mode === "reset") && (
              <TerminalInput
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
            {message && (
              <div
                className={`text-xs font-mono px-3 py-2 rounded border ${
                  loginState === "error" || message.includes("失败") || message.includes("错误")
                    ? "text-red-400 bg-red-950/30 border-red-800/50"
                    : message.includes("成功") || message.includes("通过")
                    ? "text-green-400 bg-green-950/30 border-green-800/50"
                    : "text-yellow-400 bg-yellow-950/30 border-yellow-800/50"
                }`}
              >
                <span className="opacity-50">{`>`}</span> {message}
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading || loginState === "success"}
              className="w-full h-12 bg-cyan-900/40 hover:bg-cyan-800/50 text-cyan-400 font-mono text-sm rounded border border-cyan-700/50 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-[0_0_20px_rgba(0,255,255,0.15)] flex items-center justify-center gap-2 group"
            >
              <span>{loading ? "处理中..." : loginState === "success" ? "验证通过" : "执行"}</span>
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </button>
          </form>

          {/* Mode Switch Links */}
          <div className="mt-6 pt-4 border-t border-cyan-900/30 space-y-2">
            {mode === "login" && (
              <>
                <button
                  type="button"
                  onClick={() => switchMode("register")}
                  className="w-full text-left text-cyan-700 hover:text-cyan-400 font-mono text-xs transition-colors flex items-center gap-2"
                >
                  <UserPlus className="w-3 h-3" />
                  <span>{`>`} 新用户注册</span>
                </button>
                <button
                  type="button"
                  onClick={() => switchMode("forgot")}
                  className="w-full text-left text-cyan-700 hover:text-cyan-400 font-mono text-xs transition-colors flex items-center gap-2"
                >
                  <KeyRound className="w-3 h-3" />
                  <span>{`>`} 密码找回</span>
                </button>
              </>
            )}

            {(mode === "register" || mode === "forgot" || mode === "reset") && (
              <button
                type="button"
                onClick={() => switchMode("login")}
                className="w-full text-left text-cyan-700 hover:text-cyan-400 font-mono text-xs transition-colors flex items-center gap-2"
              >
                <ChevronLeft className="w-3 h-3" />
                <span>{`>`} 返回登录</span>
              </button>
            )}
          </div>

          {/* Character selector hint */}
          <div className="mt-4 text-center">
            <div className="text-cyan-900 font-mono text-[10px]">
              点击守护者查看状态
            </div>
          </div>
        </div>

          {/* Bottom status bar */}
          <div className="mt-2 flex items-center justify-between text-cyan-900 font-mono text-[10px]">
            <span>加密: AES-256-GCM</span>
            <span className="animate-pulse">● 系统在线</span>
            <span>协议: HTTPS/TLS1.3</span>
          </div>
        </div>
      </div>
    </div>
  );
}
