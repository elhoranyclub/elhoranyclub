/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: ["./templates/**/*.html"],
  theme: {
    extend: {
      fontFamily: {
        cairo: ["Cairo", "Segoe UI", "system-ui", "sans-serif"],
      },
      colors: {
        brand: {
          navy: "var(--brand-navy)",
          deep: "var(--brand-navy-deep)",
          gold: "var(--brand-gold)",
          green: "var(--brand-green)",
        },
      },
    },
  },
  plugins: [],
};
