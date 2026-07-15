// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// Static-first marketing site for databossx.com.
// No SSR adapter, no client framework: every page is prerendered HTML,
// and the only JavaScript shipped is the small enhancement bundle in
// src/scripts/site.js (IntersectionObserver reveals, scroll-story stages,
// architecture-node focus handling). All motion falls back to a static
// layout under prefers-reduced-motion and when JS is unavailable.
export default defineConfig({
  site: 'https://databossx.com',
  trailingSlash: 'never',
  integrations: [sitemap()],
  build: {
    // Emit /architecture.html (not /architecture/index.html) so static hosts
    // serve the canonical, slash-less URL without a redirect hop.
    format: 'file',
    // Keep every stylesheet external so the Content-Security-Policy can use
    // style-src 'self' without 'unsafe-inline' (see public/_headers).
    inlineStylesheets: 'never',
  },
  vite: {
    build: {
      // Force the enhancement bundle to an external file (never inlined)
      // so script-src 'self' holds; the one remaining inline script (the
      // html.js class bootstrap) is allowed by hash in public/_headers.
      assetsInlineLimit: 0,
    },
  },
});
