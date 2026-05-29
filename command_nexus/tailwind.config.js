/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        nx: {
          bg:       '#070d1a',
          sidebar:  '#060b16',
          card:     '#0d1830',
          border:   '#1a3352',
          bordHi:   '#0ea5e9',
          cyan:     '#06b6d4',
          cyanDim:  '#0891b2',
          orange:   '#f97316',
          text:     '#e2e8f0',
          muted:    '#64748b',
          dim:      '#334155',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
}
