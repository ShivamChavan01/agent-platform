/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#09090b",
          elevated: "#18181b",
          hover: "#27272a",
          active: "#3f3f46",
        },
        edge: {
          DEFAULT: "#27272a",
          subtle: "#1e1e22",
        },
        soft: {
          DEFAULT: "#f4f4f5",
          muted: "#a1a1aa",
          dim: "#71717a",
        },
        accent: {
          DEFAULT: "#60a5fa",
          emerald: "#34d399",
          rose: "#fb7185",
          amber: "#fbbf24",
          violet: "#a78bfa",
        },
        code: "#0c0c0e",
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      borderRadius: {
        sm: "6px",
        md: "10px",
        lg: "16px",
        xl: "20px",
      },
    },
  },
  plugins: [],
};
