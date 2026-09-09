const ROOT = require('path').resolve(__dirname, '../..');
module.exports = {
  content: [`${ROOT}/apps/shop/templates/shop/cart.html`],
  theme: {
    extend: {
      colors: {
        base: '#0B0B0B',
        card: '#161616',
        card2: '#1C1C1C',
        line: '#282828',
        gold: '#D4AF37',
        goldlight: '#E8C766',
        cyan: '#22D3C8',
        mute: '#8A8A8A',
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'sans-serif'],
        body: ['"Vazirmatn"', 'Inter', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
    },
  },
  plugins: [],
};
