"use client";

import { useState } from "react";
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

  return (
    <div className="min-h-screen bg-background flex">
      {/* Left Panel - Branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-primary relative overflow-hidden flex-col justify-between p-12 text-white">
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 bg-white/20 rounded-apple flex items-center justify-center backdrop-blur-sm">
              <Shield className="w-5 h-5" />
            </div>
            <span className="text-xl font-semibold tracking-tight">AI-CyberSentinel</span>
          </div>
          <h1 className="text-4xl font-bold leading-tight mb-4">
            智能网络安全
            <br />
            态势感知平台
          </h1>
          <p className="text-white/70 text-base max-w-sm leading-relaxed">
            基于 AI 的实时入侵检测与防御系统，为您的数字资产提供全天候智能守护。
          </p>
        </div>

        <div className="relative z-10 space-y-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-white/10 rounded-apple flex items-center justify-center backdrop-blur-sm">
              <BarChart3 className="w-6 h-6" />
            </div>
            <div>
              <div className="font-semibold text-sm">实时威胁检测</div>
              <div className="text-white/60 text-xs">毫秒级响应，AI 驱动分析</div>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-white/10 rounded-apple flex items-center justify-center backdrop-blur-sm">
              <Shield className="w-6 h-6" />
            </div>
            <div>
              <div className="font-semibold text-sm">自动防御拦截</div>
              <div className="text-white/60 text-xs">WAF 规则 + 智能阻断</div>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-white/10 rounded-apple flex items-center justify-center backdrop-blur-sm">
              <Eye className="w-6 h-6" />
            </div>
            <div>
              <div className="font-semibold text-sm">全链路可视化</div>
              <div className="text-white/60 text-xs">攻击溯源，态势大屏</div>
            </div>
          </div>
        </div>

        {/* Decorative circles */}
        <div className="absolute top-1/4 right-0 w-[28rem] h-[28rem] bg-white/[0.08] rounded-full -translate-y-1/2 translate-x-1/3 blur-sm" />
        <div className="absolute bottom-0 left-1/4 w-72 h-72 bg-white/[0.06] rounded-full translate-y-1/3 blur-sm" />
        <div className="absolute top-1/2 left-1/2 w-48 h-48 bg-white/[0.04] rounded-full -translate-x-1/2 -translate-y-1/2" />
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
