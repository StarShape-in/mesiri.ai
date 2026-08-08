/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,jsx,ts,tsx}', './App.tsx'],
  presets: [require('nativewind/preset')],
  theme: {
    extend: {
      // Mirrors src/theme/tokens.ts `Colors` — keep the two in sync.
      colors: {
        primary: { DEFAULT: '#E8450F', light: '#FFF0EB', dark: '#C7380A' },
        navbg: '#1C1C2E',
        success: { DEFAULT: '#16A34A', light: '#F0FDF4' },
        warning: { DEFAULT: '#D97706', light: '#FFFBEB' },
        danger: { DEFAULT: '#DC2626', light: '#FEF2F2' },
        info: { DEFAULT: '#2563EB', light: '#EFF6FF' },
      },
    },
  },
  plugins: [],
};
