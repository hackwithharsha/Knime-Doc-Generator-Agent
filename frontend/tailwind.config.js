/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1C2321",
        paper: "#FBFAF7",
        mist: "#ECE9E2",
        line: "#D8D4C9",
        accent: {
          DEFAULT: "#1F4E79",
          dark: "#173D5F",
        },
        amber: "#9A6B14",
        moss: "#2F6846",
        rust: "#B00020",
      },
      fontFamily: {
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },
    },
  },
  plugins: [],
};
