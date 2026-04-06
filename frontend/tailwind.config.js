/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        /* Core Dark Theme */
        'bg-primary': '#000000',
        'bg-secondary': '#0a0a0a',
        'bg-card': '#0f0f0f',
        'bg-card-hover': '#161616',
        'bg-input': '#141414',
        
        /* Trading Dark */
        'trading-dark': '#000000',
        'trading-card': '#0f0f0f',
        'trading-border': '#1a1a1a',
        
        /* Accent Colors */
        'accent-primary': '#00bfff',
        'accent-success': '#00ff9c',
        'accent-danger': '#ff4d4f',
        'accent-warning': '#facc15',
        'accent-purple': '#a855f7',
        
        /* TradingView-style */
        'profit-green': '#00ff9c',
        'loss-red': '#ff4d4f',
        'accent-blue': '#00bfff',
        
        /* Text */
        'text-primary': '#ffffff',
        'text-secondary': '#a0a0a0',
        'text-muted': '#666666',
        
        /* Borders */
        'border-default': '#1a1a1a',
        'border-subtle': '#252525',
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
      boxShadow: {
        'glow-primary': '0 0 10px rgba(0, 191, 255, 0.4)',
        'glow-success': '0 0 10px rgba(0, 255, 156, 0.4)',
        'glow-danger': '0 0 10px rgba(255, 77, 79, 0.4)',
        'glow-purple': '0 0 10px rgba(168, 85, 247, 0.4)',
      },
      animation: {
        'pulse-glow': 'pulse-glow 2s infinite',
      },
      keyframes: {
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 5px rgba(0, 191, 255, 0.4)' },
          '50%': { boxShadow: '0 0 20px rgba(0, 191, 255, 0.6)' },
        },
      },
    },
  },
  plugins: [],
}