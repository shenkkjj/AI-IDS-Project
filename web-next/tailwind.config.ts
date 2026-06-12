import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Mercury / Tailscale 暖白 paper
        bg: {
          DEFAULT: "#FBFAF7",       // 暖白主底
          raised: "#FFFFFF",         // 卡片 / 输入框背景
          sunken: "#F4F1E9",         // 凹陷 / 分组底
        },
        // Linear 紫单色 accent
        accent: {
          DEFAULT: "#5E6AD2",
          hover: "#4E5AC2",
          soft: "#EEEEFB",
        },
        // 近黑文字系统
        ink: {
          DEFAULT: "#0A0A0A",
          secondary: "#4A4A48",
          tertiary: "#8A8A86",
          inverse: "#FFFFFF",
        },
        // 暖灰分隔线
        line: {
          DEFAULT: "#E5E1D5",
          strong: "#D6D1C2",
          subtle: "#F0EDE3",
        },
        // 语义色（亮色背景上需要更深一档保证可读性）
        danger: "#B91C1C",
        warning: "#B45309",
        success: "#15803D",
        info: "#1D4ED8",
        // 软语义色（背景 tint）
        "danger-soft": "#FEF2F2",
        "warning-soft": "#FEF3C7",
        "success-soft": "#DCFCE7",
        "info-soft": "#EFF6FF",
      },
      fontFamily: {
        // 编辑感衬线 display — 2026 流行（Linear editorial、Vercel、Stripe 风都常见）
        display: ['"Instrument Serif"', '"Source Serif 4"', "Georgia", "serif"],
        serif: ['"Instrument Serif"', '"Source Serif 4"', "Georgia", "serif"],
        sans: [
          '"Inter"',
          '-apple-system',
          "BlinkMacSystemFont",
          '"Helvetica Neue"',
          '"PingFang SC"',
          '"Microsoft YaHei"',
          "sans-serif",
        ],
        mono: [
          '"JetBrains Mono"',
          '"SF Mono"',
          "ui-monospace",
          "Menlo",
          "monospace",
        ],
      },
      boxShadow: {
        // 极简阴影 — 仅在 modal / popover 出现
        sm: "0 1px 2px rgba(10, 10, 10, 0.04)",
        DEFAULT: "0 1px 3px rgba(10, 10, 10, 0.06)",
        md: "0 4px 12px rgba(10, 10, 10, 0.08)",
      },
      borderRadius: {
        none: "0",
        sm: "4px",
        DEFAULT: "6px",
        md: "8px",
        lg: "10px",
        xl: "12px",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "fade-soft": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-soft": {
          "0%": { transform: "scale(0.6)", opacity: "0.7" },
          "80%": { transform: "scale(2.4)", opacity: "0" },
          "100%": { transform: "scale(2.4)", opacity: "0" },
        },
        "ripple-out": {
          "0%": { transform: "scale(0.6)", opacity: "0.8" },
          "70%": { opacity: "0" },
          "100%": { transform: "scale(2.6)", opacity: "0" },
        },
      },
      animation: {
        "fade-in": "fade-in 240ms ease-out",
        "slide-up": "slide-up 320ms cubic-bezier(0.16, 1, 0.3, 1)",
        "fade-soft": "fade-soft 200ms ease-out",
        "pulse-soft": "pulse-soft 1800ms cubic-bezier(0.16, 1, 0.3, 1) infinite",
        "ripple-out": "ripple-out 1200ms cubic-bezier(0.16, 1, 0.3, 1) infinite",
      },
    },
  },
  plugins: [],
};

export default config;
