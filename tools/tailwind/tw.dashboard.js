const ROOT = require('path').resolve(__dirname, '../..');
module.exports = {
  darkMode: 'class',
  content: [`${ROOT}/apps/accounts/templates/accounts/user_dashboard.html`],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: '#0A0A0F',
          surface: '#121218',
          elevated: '#1A1A23',
          line: '#26262F',
        },
        gold: { DEFAULT: '#C9A961', dim: '#8F7A46', bright: '#E4C77E' },
        cyan: { DEFAULT: '#4DD8E0', dim: '#2E8A90' },
        ink: { DEFAULT: '#F2F1ED', muted: '#9C9BA6', faint: '#5F5E68' },
        ok: '#4ADE80',
        warn: '#FBBF24',
        danger: '#F87171',
        info: '#60A5FA',
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'sans-serif'],
        body: ['Inter', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(201,169,97,0.15), 0 8px 30px -8px rgba(201,169,97,0.25)',
        card: '0 4px 24px -8px rgba(0,0,0,0.5)',
      },
    },
  },
  plugins: [],
};
