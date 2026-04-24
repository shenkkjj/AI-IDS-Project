import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#070B16",
        panel: "#0F172A",
        cyber: "#22D3EE",
        danger: "#F43F5E",
      },
      boxShadow: {
        neon: "0 0 24px rgba(34,211,238,.35)",
      },
    },
  },
  plugins: [],
};

export default config;
