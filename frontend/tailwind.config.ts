import type { Config } from "tailwindcss";

/**
 * Palette is defined here as tokens and nowhere else — components must
 * reference these names, never raw hex.
 *
 * - teal        app bar, primary buttons, positive/receivable amounts
 * - teal.wash   subtle tints and selected states
 * - peacock     secondary actions, links, receipt/payment rows
 * - gold        badges and small highlights only, never a button or background
 * - danger      cancelled documents and payable amounts ONLY (never warnings
 *               in peacock, never decorative)
 *
 * Page background stays white. Colour belongs on bars, buttons and amounts.
 */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        teal: {
          DEFAULT: "#0F6E56",
          wash: "#E1F5EE",
        },
        peacock: {
          DEFAULT: "#185FA5",
        },
        gold: {
          DEFAULT: "#BA7517",
        },
        danger: {
          DEFAULT: "#B3261E",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
