/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          50: '#f0f0ff',
          100: '#e0e0ff',
          500: '#3636A2',
          700: '#16136F',
          900: '#0d0b4a',
        },
      },
    },
  },
  plugins: [],
}
