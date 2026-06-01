import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
    "./store/**/*.{ts,tsx}",
    "./hooks/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Base dark slate
        slate: {
          850: "#172033",
          900: "#0f1729",
          925: "#0b1120",
          950: "#070d1a",
        },
        // Warmth-based accents
        heat: {
          hot: "#10b981",      // emerald-500
          "hot-dim": "#065f46", // emerald-800
          warm: "#f59e0b",     // amber-500
          "warm-dim": "#92400e", // amber-800
          cold: "#3b82f6",     // blue-500
          "cold-dim": "#1e3a8a", // blue-800
          new: "#8b5cf6",      // violet-500
          "new-dim": "#4c1d95", // violet-900
        },
        // Brand accent
        brand: {
          DEFAULT: "#10b981",
          light: "#34d399",
          dark: "#059669",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      animation: {
        "pulse-glow": "pulse-glow 2s ease-in-out infinite",
        "slide-in": "slide-in 0.3s ease-out",
        "slide-up": "slide-up 0.3s ease-out",
        "fade-in": "fade-in 0.2s ease-out",
        "typing-dot": "typing-dot 1.4s infinite ease-in-out",
      },
      keyframes: {
        "pulse-glow": {
          "0%, 100%": { opacity: "1", boxShadow: "0 0 0 0 rgba(16, 185, 129, 0)" },
          "50%": { opacity: "0.9", boxShadow: "0 0 20px 4px rgba(16, 185, 129, 0.3)" },
        },
        "slide-in": {
          "0%": { transform: "translateX(100%)", opacity: "0" },
          "100%": { transform: "translateX(0)", opacity: "1" },
        },
        "slide-up": {
          "0%": { transform: "translateY(10px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "typing-dot": {
          "0%, 80%, 100%": { transform: "scale(0.6)", opacity: "0.4" },
          "40%": { transform: "scale(1)", opacity: "1" },
        },
      },
      boxShadow: {
        glow: "0 0 20px rgba(16, 185, 129, 0.15)",
        "glow-amber": "0 0 20px rgba(245, 158, 11, 0.15)",
      },
    },
  },
  plugins: [],
};

export default config;
