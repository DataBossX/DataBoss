# DataBossX website (v2 — cinematic scroll-driven)

The public marketing site for [databossx.com](https://databossx.com): a static-first
Astro project that tells the DataBossX story — documents in, evidence out, every
conclusion traceable to its source.

All product-surface data on the site is **synthetic**. This directory must never
contain client evidence, real hashes, credentials, or private runtime data
(see `docs/DATA_CLASSIFICATION_AND_PUBLICATION_POLICY.md` at the repo root).

## Stack

- [Astro](https://astro.build) 7, fully static output (no SSR adapter)
- Zero client frameworks; one ~2 KB enhancement script (`src/scripts/site.js`)
- All motion is CSS/SVG driven, with `prefers-reduced-motion` and no-JS fallbacks
- `@astrojs/sitemap` for sitemap generation
- `playwright-core` (dev-only) drives the pre-installed Chromium for QA
  screenshots and brand-asset generation — it never ships to the client

GSAP, ScrollTrigger, and Three.js were evaluated and **not** used: every
interaction here (scroll story, reveals, command core, architecture flow) is
implementable with position:sticky, IntersectionObserver, and CSS/SVG
animation, so the dependency and bundle cost was not justified.

## Commands

```bash
npm install          # install dependencies
npm run dev          # dev server on :4321
npm run build        # static build into dist/
npm run preview      # serve dist/ locally
npm run test:site    # deterministic post-build QA (requires a prior build)
npm test             # build + test:site

# occasional / manual
node scripts/make-assets.mjs                 # regenerate OG image + icons
node scripts/screenshot.mjs <outdir>         # QA screenshots (needs preview running)
npx lighthouse http://127.0.0.1:4321/ ...    # Lighthouse (not a committed dep)
```

`npm run test:site` covers: required outputs, broken internal links, image alt
text, heading structure, skip link, per-page SEO metadata (title, description,
canonical, Open Graph, Twitter, JSON-LD), sitemap/robots wiring, security
headers, CSP↔inline-script hash consistency, secret patterns, localhost and
private-path references, source-map exposure, and the performance budgets
(JS ≤ 170 KB gzip, page transfer ≤ 2 MB, single asset ≤ 500 KB).

## Layout

```
src/
  layouts/BaseLayout.astro      head/SEO/JSON-LD, header, footer, script
  pages/index.astro             homepage (hero → story → … → final CTA)
  pages/architecture.astro      technical overview ("View Architecture" target)
  pages/404.astro               custom 404
  components/
    CommandCore.astro           hero signature visual (SVG/CSS)
    ScrollStory.astro           six-stage pinned narrative (sticky, no hijack)
    ArchitectureFlow.astro      interactive six-node flow (hover/focus/tap)
    ProductPanel.astro          product-surface card shell
    ReleaseGate.astro           release checklist surface
    ProvenanceExplorer.astro    conclusion→source chain (differentiator)
    UseCaseGrid.astro           industry use cases
    MotionSection.astro         section shell with scroll reveal
    PerformanceFallback.astro   noscript notice
    SiteHeader.astro / SiteFooter.astro
  scripts/site.js               the only client JS (observers + interactions)
  styles/global.css             design tokens and shared styles
public/
  _headers                      security headers (CSP, HSTS, …) for the host
  robots.txt, favicon.svg, og/, icons/
scripts/
  test-site.mjs                 post-build QA suite
  screenshot.mjs                QA screenshots via local Chromium
  make-assets.mjs               OG image + icon generation
```

## Deployment

The build output is plain static files in `dist/` — any static host works.

**Branch preview configuration for Cloudflare Pages:**

- Root directory: `website`
- Build command: `npm ci && npm test && npm audit --audit-level=high`
- Output directory: `dist`
- Preview branch: `claude/cinematic-site-v2-f462hu`

Use the branch preview URL for this review. Do not merge to `main` merely to
obtain a preview. Do not attach a custom domain, change DNS, change
nameservers, or alter redirects or production settings. On the generated
preview URL, verify that `public/_headers` is honored by checking the response
headers, including the CSP. Production promotion remains blocked.

Before any future cutover, preserve or intentionally redirect these existing
production routes:

- `/`
- `/docs/`
- `/status/`
- `/contact/`
- `/get-started/`
- `/command-center/`
- `/privacy/`
- `/security/`

This repair does not implement the production migration or redirects.

If deploying behind nginx or another host instead, replicate the headers in
`public/_headers` in that host's configuration.

### Pre-promotion checklist

- `npm test` passes (build + deterministic QA checks)
- Preview URL verified: HTTPS, all three routes, redirects, headers
  (`curl -I` should show the CSP), mobile layout, reduced-motion behavior
- Lighthouse mobile + desktop on the preview
- No console errors (`node scripts/screenshot.mjs` fails on any)

### Rollback

Deploys are immutable per commit on Pages-style hosts: roll back by
re-promoting the previous deployment in the dashboard (or reverting the
merge commit and letting CI redeploy). The previous site, if any, remains
untouched at its current host until the domain is pointed at this project,
so DNS-level rollback is: point the domain back at the prior origin.
