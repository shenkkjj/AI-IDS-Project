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
        background: "#070B16",
        panel: "#0F172A",
        cyber: "#22D3EE",
        danger: "#F43F5E",
        "cyber-bg": "#050505",
        "cyber-cyan": "#00F5FF",
        "cyber-orange": "#FF8A00",
        "cyber-purple": "#A855F7",
        "cyber-text": "#E6F7FF",
      },
      boxShadow: {
        neon: "0 0 24px rgba(34,211,238,.35)",
        "neon-cyan": "0 0 10px rgba(0,245,255,0.45), 0 0 24px rgba(0,245,255,0.2)",
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
