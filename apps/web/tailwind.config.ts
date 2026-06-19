import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          900: "#0F1A2E",
          800: "#1B2A4A",
          700: "#253A5E",
          600: "#2F4A72",
          100: "#E8ECF2",
        },
        gold: {
          500: "#D4A843",
          400: "#E4BE5A",
          100: "#FDF6E3",
          50: "#FFFDF7",
        },
        surface: "#FFFFFF",
        bg: "#F7F8FA",
      },
      fontFamily: {
        sans: ["var(--font-plus-jakarta)", "system-ui", "sans-serif"],
      },
      width: {
        sidebar: "260px",
      },
      borderRadius: {
        sm: "6px",
        md: "10px",
        lg: "14px",
        xl: "18px",
      },
      boxShadow: {
        sm: "0 1px 2px rgba(15,26,46,0.05)",
        md: "0 2px 8px rgba(15,26,46,0.08)",
        lg: "0 4px 20px rgba(15,26,46,0.10)",
      },
    },
  },
  plugins: [],
};

export default config;
