import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: {
          DEFAULT: "#F1EBDF",
          raised: "#F8F4EB",
          inset: "#E7E0D2",
        },
        ink: {
          DEFAULT: "#171410",
          muted: "#5E574C",
          faint: "#8A8276",
        },
        rule: "#D3CBBC",
        crimson: {
          DEFAULT: "#9B2032",
          dark: "#7A1826",
          soft: "#F3E4E6",
        },
        navy: {
          DEFAULT: "#1A2744",
          mid: "#2C3C5E",
        },
        gold: "#B0894F",
      },
      fontFamily: {
        serif: ["var(--font-serif)", "Georgia", "serif"],
        sans: ["var(--font-sans)", "Segoe UI", "sans-serif"],
      },
      boxShadow: {
        hairline: "0 1px 0 rgba(23, 20, 16, 0.06)",
        desk: "0 12px 40px rgba(23, 20, 16, 0.08)",
      },
    },
  },
  plugins: [],
};

export default config;
