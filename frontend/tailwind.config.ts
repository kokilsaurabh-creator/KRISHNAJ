import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        cream: "#faf7f2",
        maroon: "#7a1f3d",
        gold: "#b8860b",
      },
      fontFamily: {
        tabular: ["'Inter'", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
