/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './renderer/index.html',
    './renderer/src/**/*.{js,jsx,ts,tsx}',
  ],
  darkMode: 'class', // Enable dark mode with class strategy
  theme: {
    extend: {},
  },
  plugins: [],
}

