# Tailwind build

`article_detail.html`, `user_dashboard.html`, and `cart.html` used to pull
`https://cdn.tailwindcss.com` — a ~400 KB script that compiles Tailwind in the
browser on every page load. It is explicitly not meant for production: it
blocks rendering, it cannot be cached as CSS, and the styles only exist after
JavaScript has run, which hurts LCP and causes layout shift.

The generated stylesheets (`static/css/article.css`, `static/css/dashboard.css`, `static/css/cart.css`)
are committed, so **no build step is required to run or deploy the project**.

Re-run the build only when you add or change Tailwind utility classes in those
three templates:

```bash
npm install tailwindcss@3.4.17
npx tailwindcss -c tools/tailwind/tw.article.js   -i tools/tailwind/entry.css -o static/css/article.css   --minify
npx tailwindcss -c tools/tailwind/tw.dashboard.js -i tools/tailwind/entry.css -o static/css/dashboard.css --minify
npx tailwindcss -c tools/tailwind/tw.cart.js      -i tools/tailwind/entry.css -o static/css/cart.css      --minify
```

The `theme.extend` blocks in `tw.*.js` mirror the inline `tailwind.config`
objects that used to sit in each template — keep them in sync if the palette
changes.
