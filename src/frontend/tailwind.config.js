/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        canvas: "#090a0f",
        surface: {
          DEFAULT: "#131722",
          elevated: "#1e293b",
          highlight: "#262f45",
        },
        brand: {
          red: "#d81f26",
          redHover: "#e50914",
          redMuted: "rgba(216, 31, 38, 0.15)",
        },
        cinema: {
          gold: "#eab308",
          cyan: "#06b6d4",
          emerald: "#10b981",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
      },
      boxShadow: {
        "cinema-glow": "0 0 35px -5px rgba(216, 31, 38, 0.3)",
        "card-elevation": "0 10px 25px -5px rgba(0, 0, 0, 0.7)",
      },
      backgroundImage: {
        "hero-gradient": "linear-gradient(to top, #090a0f 10%, rgba(9, 10, 15, 0.8) 50%, rgba(9, 10, 15, 0.2) 100%)",
        "card-gradient": "linear-gradient(to top, rgba(9, 10, 15, 0.95) 0%, rgba(9, 10, 15, 0.4) 60%, transparent 100%)",
      },
    },
  },
  plugins: [],
};

