const ROOT = require('path').resolve(__dirname, '../..');
module.exports = {
  content: [`${ROOT}/apps/home/templates/home/article_detail.html`],
  theme: {
    extend: {
      colors: {
        black: '#050507',
        deep: '#08080d',
        surface: '#0c0c13',
        card: '#101018',
        cardhover: '#14141e',
        white: '#f6f6f8',
        neon: '#4fd8ff',
        neon2: '#8b7bff',
        neon3: '#ff6cc4',
        gold: '#e9c97f',
      },
      fontFamily: {
        display: ['Vazirmatn', 'Space Grotesk', 'sans-serif'],
        body: ['Vazirmatn', 'Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'Vazirmatn', 'monospace'],
      },
    },
  },
  plugins: [],
};
