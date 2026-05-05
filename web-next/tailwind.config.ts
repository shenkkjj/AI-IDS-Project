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
        background: "#0B0F1A",
        panel: "#111827",
        cyber: "#22D3EE",
        danger: "#F43F5E",
        "cyber-bg": "#0B0F1A",
        "cyber-cyan": "#22D3EE",
        "cyber-orange": "#F59E0B",
        "cyber-purple": "#8B5CF6",
        "cyber-text": "#E2E8F0",
      },
      boxShadow: {
        neon: "0 0 12px rgba(34,211,238,.2)",
        "neon-cyan": "0 0 6px rgba(34,211,238,0.25), 0 0 16px rgba(34,211,238,0.1)",
      },
      fontFamily: {
        mono: [
          "JetBrains Mono",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "Liberation Mono",
          "Courier New",
          "monospace",
        ],
      },
    },
  },
  plugins: [],
};

export default config;
