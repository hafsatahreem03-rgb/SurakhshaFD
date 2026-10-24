/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "Segoe UI", "system-ui", "sans-serif"] },
      colors: {
        navy: { 50: "#eef3fb", 100: "#d6e2f5", 200: "#adc4ea", 300: "#7c9fd9", 400: "#4c76c2", 500: "#2d58a6", 600: "#1f4485", 700: "#17356a", 800: "#0f2a57", 900: "#0b2047", 950: "#071533" },
        teal: { 50: "#ecfdf9", 100: "#cffaef", 200: "#a0f2df", 300: "#64e3cb", 400: "#2ccbb1", 500: "#12b09a", 600: "#0b8e7e", 700: "#0d7166", 800: "#0f5a52", 900: "#114a45" },
      },
      boxShadow: { card: "0 1px 2px rgba(11,32,71,.06), 0 4px 16px rgba(11,32,71,.06)" },
      keyframes: { fadein: { from: { opacity: 0, transform: "translateY(4px)" }, to: { opacity: 1, transform: "none" } } },
      animation: { fadein: "fadein .25s ease-out" },
    },
  },
  plugins: [],
};
