"use client";

import { useState, useEffect, useCallback } from "react";
import { signIn } from "next-auth/react";
import {
  Shield,
  Eye,
  BarChart3,
  Settings,
  Mail,
  Lock,
  EyeOff,
  ArrowRight,
  UserPlus,
  ChevronLeft,
} from "lucide-react";
import AnimatedCharacters from "./components/animated-characters/AnimatedCharacters";

type RoleKey = "admin" | "analyst" | "viewer" | "operator";

interface RoleInfo {
  key: RoleKey;
  label: string;
  description: string;
  icon: React.ElementType;
  color: string;
  bg: string;
  border: string;
  email: string;
  password: string;
}

const ROLES: RoleInfo[] = [
  {
    key: "admin",
    label: "系统管理员",
    description: "全局配置、用户管理、系统监控",
    icon: Settings,
    color: "text-primary",
    bg: "bg-primary/10",
    border: "border-primary/20",
    email: "admin@cybersentinel.local",
    password: "Admin123",
  },
  {
    key: "analyst",
    label: "安全分析师",
    description: "告警分析、威胁研判、AI 助手",
    icon: BarChart3,
    color: "text-warning",
    bg: "bg-warning/10",
    border: "border-warning/20",
    email: "analyst@cybersentinel.local",
    password: "Analyst123",
  },
  {
    key: "viewer",
    label: "审计观察员",
    description: "只读访问、报表查看、日志审计",
    icon: Eye,
    color: "text-success",
    bg: "bg-success/10",
    border: "border-success/20",
    email: "viewer@cybersentinel.local",
    password: "Viewer123",
  },
  {
    key: "operator",
    label: "运维工程师",
    description: "站点管理、WAF 配置、代理测试",
    icon: Shield,
    color: "text-danger",
    bg: "bg-danger/10",
    border: "border-danger/20",
    email: "operator@cybersentinel.local",
    password: "Operator123",
  },
];

export default function LoginPage() {
  const [mode, setMode] = useState<"roles" | "form">("roles");
  const [selectedRole, setSelectedRole] = useState<RoleInfo | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [activeCharacter, setActiveCharacter] = useState<string | null>(null);

  function selectRole(role: RoleInfo) {
    setSelectedRole(role);
    setEmail(role.email);
    setPassword(role.password);
    setMode("form");
    setError("");
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);

    const result = await signIn("credentials", {
      email,
      password,
      redirect: false,
      callbackUrl: "/dashboard",
    });

    setLoading(false);

    if (result?.error) {
      setError("邮箱或密码错误");
      return;
    }

    window.location.href = result?.url || "/dashboard";
  }

  const handleCharacterClick = useCallback((character: string) => {
    setActiveCharacter(character);
    setTimeout(() => setActiveCharacter(null), 500);
  }, []);

  return (
    <div className="min-h-screen bg-background flex">
      {/* Left Panel - Characters + Branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-[#0a0a0f] relative overflow-hidden flex-col items-center justify-between py-12">
        {/* Top branding */}
        <div className="relative z-10 flex items-center gap-3">
          <div className="w-10 h-10 bg-primary/20 rounded-apple flex items-center justify-center backdrop-blur-sm border border-primary/30">
            <Shield className="w-5 h-5 text-primary" />
          </div>
          <span className="text-xl font-semibold tracking-tight text-white">AI-CyberSentinel</span>
        </div>

        {/* Animated Characters */}
        <div className="relative z-10 flex-1 flex items-center justify-center">
          <AnimatedCharacters
            isTyping={isTyping}
            showPassword={showPassword}
            passwordLength={password.length}
            activeCharacter={activeCharacter}
          />
        </div>

        {/* Bottom hint */}
        <div className="relative z-10 text-center">
          <p className="text-white/40 text-xs font-mono">点击守护者查看状态</p>
          <div className="flex items-center justify-center gap-6 mt-3 text-white/30 text-[10px] font-mono">
            <span>加密: AES-256-GCM</span>
            <span className="animate-pulse">● 系统在线</span>
            <span>协议: HTTPS/TLS1.3</span>
          </div>
        </div>

        {/* Background grid effect */}
        <div className="absolute inset-0 opacity-[0.03]" style={{
          backgroundImage: `linear-gradient(rgba(0,113,227,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(0,113,227,0.5) 1px, transparent 1px)`,
          backgroundSize: '40px 40px'
        }} />
      </div>

      {/* Right Panel */}
      <div className="flex-1 flex flex-col justify-center items-center p-6 lg:p-12">
        <div className="w-full max-w-md">
          {mode === "roles" ? (
            <>
              <div className="text-center mb-8">
                <h2 className="text-2xl font-semibold text-text mb-2">选择登录角色</h2>
                <p className="text-text-secondary text-sm">请选择您的身份进入系统</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {ROLES.map((role) => {
                  const Icon = role.icon;
                  return (
                    <button
                      key={role.key}
                      onClick={() => selectRole(role)}
                      className={`group relative bg-surface border-2 ${role.border} rounded-apple-lg p-5 text-left hover:shadow-card-hover transition-all duration-300 hover:-translate-y-0.5`}
                    >
                      <div className={`w-10 h-10 ${role.bg} rounded-apple flex items-center justify-center mb-3`}>
                        <Icon className={`w-5 h-5 ${role.color}`} />
                      </div>
                      <div className="font-semibold text-text text-sm mb-1">{role.label}</div>
                      <div className="text-text-secondary text-xs leading-relaxed">{role.description}</div>
                      <div className="absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity">
                        <ArrowRight className={`w-4 h-4 ${role.color}`} />
                      </div>
                    </button>
                  );
                })}
              </div>

              <div className="mt-8 text-center">
                <button
                  onClick={() => {
                    setSelectedRole(null);
                    setEmail("");
                    setPassword("");
                    setMode("form");
                    setError("");
                  }}
                  className="text-primary text-sm font-medium hover:underline"
                >
                  使用自定义账号登录
                </button>
              </div>
            </>
          ) : (
            <>
              <div className="mb-8">
                <button
                  onClick={() => setMode("roles")}
                  className="flex items-center gap-1 text-text-secondary text-sm mb-4 hover:text-text transition-colors"
                >
                  <ChevronLeft className="w-4 h-4" />
                  返回角色选择
                </button>
                <h2 className="text-2xl font-semibold text-text">
                  {selectedRole ? selectedRole.label : "账号登录"}
                </h2>
                <p className="text-text-secondary text-sm mt-1">
                  {selectedRole ? "已填充演示账号，直接登录即可" : "请输入您的邮箱和密码"}
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1.5">邮箱</label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-tertiary" />
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      onFocus={() => setIsTyping(true)}
                      onBlur={() => setIsTyping(false)}
                      placeholder="name@company.com"
                      className="w-full bg-background border border-border-subtle rounded-apple text-text text-sm py-2.5 pl-10 pr-3 focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1.5">密码</label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-tertiary" />
                    <input
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      onFocus={() => setIsTyping(true)}
                      onBlur={() => setIsTyping(false)}
                      placeholder="••••••••"
                      className="w-full bg-background border border-border-subtle rounded-apple text-text text-sm py-2.5 pl-10 pr-10 focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all"
                      required
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-text-tertiary hover:text-text transition-colors"
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {error && (
                  <div className="bg-danger-subtle text-danger text-sm px-3 py-2 rounded-apple">
                    {error}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-primary text-white font-medium text-sm py-2.5 rounded-apple hover:bg-primary-hover active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {loading ? "登录中..." : "登录"}
                  {!loading && <ArrowRight className="w-4 h-4" />}
                </button>
              </form>

              {!selectedRole && (
                <div className="mt-6 text-center">
                  <a
                    href="#"
                    className="inline-flex items-center gap-1.5 text-primary text-sm font-medium hover:underline"
                  >
                    <UserPlus className="w-4 h-4" />
                    注册新账号
                  </a>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
