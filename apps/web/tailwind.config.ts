import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "#0C0F0A",
        panel: "#161616",
        border: "#2e2e2e",
        muted: "#9a9a9a",
        accent: "#000000",
        accentMuted: "#6b6b6b",
      },
    },
  },
  plugins: [],
};

export default config;
