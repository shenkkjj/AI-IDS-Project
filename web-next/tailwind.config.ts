import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#F5F5F7",
        surface: "#FFFFFF",
        "surface-elevated": "#FFFFFF",
        "surface-subtle": "#F5F5F7",
        primary: "#0071E3",
        "primary-hover": "#0077ED",
        "primary-subtle": "#E8F4FD",
        danger: "#FF3B30",
        "danger-subtle": "#FFE5E3",
        success: "#34C759",
        "success-subtle": "#E5F8EA",
        warning: "#FF9500",
        "warning-subtle": "#FFF4E5",
        text: "#1D1D1F",
        "text-secondary": "#86868B",
        "text-tertiary": "#A1A1A6",
        border: "#D2D2D7",
        "border-subtle": "#E8E8ED",
        divider: "#E8E8ED",
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "SF Pro Display",
          "SF Pro Text",
          "Helvetica Neue",
          "Helvetica",
          "Arial",
          "sans-serif",
        ],
        mono: [
          "SF Mono",
          "SFMono-Regular",
          "ui-monospace",
          "Menlo",
          "Monaco",
          "Consolas",
          "Liberation Mono",
          "Courier New",
          "monospace",
        ],
      },
      boxShadow: {
        card: "0 0.5px 2px rgba(0,0,0,0.06), 0 2px 6px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.02)",
        "card-hover": "0 2px 8px rgba(0,0,0,0.08), 0 8px 24px rgba(0,0,0,0.06), 0 16px 48px rgba(0,0,0,0.03)",
        dropdown: "0 4px 16px rgba(0,0,0,0.12)",
        "apple-sm": "0 1px 2px rgba(0,0,0,0.04)",
        "apple-md": "0 2px 8px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04)",
        "apple-lg": "0 4px 12px rgba(0,0,0,0.08), 0 16px 48px rgba(0,0,0,0.04)",
      },
      borderRadius: {
        "apple-sm": "8px",
        "apple": "12px",
        "apple-lg": "18px",
        "apple-xl": "24px",
      },
    },
  },
  plugins: [],
};

export default config;
