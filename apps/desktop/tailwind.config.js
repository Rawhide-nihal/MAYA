/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        mayaDark: "#070b14",
        mayaCard: "rgba(13, 21, 39, 0.72)",
        mayaBlue: "#2563eb",
        mayaCyan: "#22d3ee"
      }
    },
  },
  plugins: [],
}
