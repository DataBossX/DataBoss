/*
 * Post-build QA for the DataBossX website. Run after `npm run build`:
 *
 *   npm run test:site
 *
 * Checks: required outputs, internal links, image alt text, per-page SEO
 * metadata, JSON-LD, security headers + CSP hash consistency, secret /
 * localhost / private-path scanning, performance budgets, reduced-motion
 * coverage, and basic HTML sanity. Exits non-zero on any failure.
 */
import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const dist = path.join(root, 'dist');

let failures = 0;
let checks = 0;
const fail = (msg) => {
  failures += 1;
  console.error(`  ✗ ${msg}`);
};
const ok = (msg) => console.log(`  ✓ ${msg}`);
const test = (name, cond, detail = '') => {
  checks += 1;
  cond ? ok(name) : fail(`${name}${detail ? ` — ${detail}` : ''}`);
};

const walk = (dir) =>
  readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    return entry.isDirectory() ? walk(full) : [full];
  });

if (!existsSync(dist)) {
  console.error('dist/ not found — run `npm run build` first.');
  process.exit(1);
}

const files = walk(dist);
const htmlFiles = files.filter((f) => f.endsWith('.html'));
const read = (f) => readFileSync(f, 'utf8');
const idsIn = (html) => new Set([...html.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]));

/* ---------------------------- required outputs ---------------------------- */
console.log('\nRequired outputs');
for (const required of [
  'index.html',
  'architecture.html',
  '404.html',
  'robots.txt',
  'sitemap-index.xml',
  '_headers',
  'favicon.svg',
  'og/databossx-og.png',
  'icons/icon-512.png',
  'icons/apple-touch-icon.png',
]) {
  test(`dist/${required} exists`, existsSync(path.join(dist, required)));
}

/* ------------------------------ internal links ---------------------------- */
console.log('\nInternal links & assets');
const resolvable = (href) => {
  const clean = href.replace(/[#?].*$/, '');
  if (clean === '' || clean === '/') return true;
  const rel = clean.replace(/^\//, '');
  return (
    existsSync(path.join(dist, rel)) ||
    existsSync(path.join(dist, `${rel}.html`)) ||
    existsSync(path.join(dist, rel, 'index.html')) ||
    rel === 'sitemap-index.xml'
  );
};

for (const file of htmlFiles) {
  const html = read(file);
  const refs = [...html.matchAll(/(?:href|src)="([^"]+)"/g)].map((m) => m[1]);
  const broken = refs.filter(
    (r) => !r.startsWith('http') && !r.startsWith('mailto:') && !r.startsWith('#') && !resolvable(r)
  );
  test(
    `no broken internal refs in ${path.basename(file)}`,
    broken.length === 0,
    broken.join(', ')
  );

  const brokenFragments = refs
    .filter((ref) => ref.startsWith('#') || ref.startsWith('/#'))
    .filter((ref) => {
      const targetFile = ref.startsWith('/#') ? path.join(dist, 'index.html') : file;
      const fragment = decodeURIComponent(ref.slice(ref.indexOf('#') + 1));
      return fragment && !idsIn(read(targetFile)).has(fragment);
    });
  test(
    `same-page and root-page fragments resolve in ${path.basename(file)}`,
    brokenFragments.length === 0,
    brokenFragments.join(', ')
  );
}

/* ------------------------------- accessibility ---------------------------- */
console.log('\nAccessibility basics');
for (const file of htmlFiles) {
  const html = read(file);
  const name = path.basename(file);
  const imgsWithoutAlt = [...html.matchAll(/<img(?![^>]*\balt=)[^>]*>/g)];
  test(`all <img> in ${name} have alt`, imgsWithoutAlt.length === 0);
  test(`${name} has lang attribute`, /<html[^>]+lang="en"/.test(html));
  test(`${name} has exactly one <h1>`, (html.match(/<h1[\s>]/g) || []).length === 1);
  test(`${name} has skip link`, html.includes('Skip to main content'));
  const buttonsNoType = [...html.matchAll(/<button(?![^>]*\btype=)[^>]*>/g)];
  test(`buttons in ${name} declare a type`, buttonsNoType.length === 0);
  const unsafeBlankLinks = [...html.matchAll(/<a\b([^>]*)>/g)]
    .map(([, attrs]) => attrs)
    .filter((attrs) => /\btarget="_blank"/.test(attrs))
    .filter((attrs) => !/\brel="[^"]*\bnoopener\b[^"]*\bnoreferrer\b[^"]*"/.test(attrs));
  test(`target=_blank links in ${name} use noopener noreferrer`, unsafeBlankLinks.length === 0);
}

const css = files.filter((f) => f.endsWith('.css')).map(read).join('\n');
test('reduced-motion handling present in CSS', css.includes('prefers-reduced-motion'));
test('focus-visible styling present in CSS', css.includes('focus-visible'));

const sourceCss = read(path.join(root, 'src/styles/global.css'));
const faintTextColor = sourceCss.match(/--ink-faint:\s*(#[0-9a-f]{6})/i)?.[1];
const lightestFaintTextBackground = '#141c2c';
const toLinearChannel = (value) => {
  const normalized = value / 255;
  return normalized <= 0.04045
    ? normalized / 12.92
    : ((normalized + 0.055) / 1.055) ** 2.4;
};
const relativeLuminance = (hex) => {
  const channels = hex
    .match(/[0-9a-f]{2}/gi)
    .map((value) => toLinearChannel(parseInt(value, 16)));
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
};
const contrastRatio = (foreground, background) => {
  const values = [relativeLuminance(foreground), relativeLuminance(background)].sort(
    (a, b) => b - a
  );
  return (values[0] + 0.05) / (values[1] + 0.05);
};
const faintContrast = faintTextColor
  ? contrastRatio(faintTextColor, lightestFaintTextBackground)
  : 0;
test(
  `faint text token contrast ≥ 4.5:1 on lightest applicable panel (actual: ${faintContrast.toFixed(2)}:1)`,
  faintContrast >= 4.5,
  `${faintTextColor || 'token missing'} on ${lightestFaintTextBackground}`
);

const verifiedWalkthroughDestinations = new Set();
const misleadingCtas = htmlFiles.flatMap((file) =>
  [...read(file).matchAll(/<a\b([^>]*)>([\s\S]*?)<\/a>/g)]
    .filter(([, , label]) => /Request a Walkthrough/i.test(label.replace(/<[^>]+>/g, ' ')))
    .filter(([, attrs]) => {
      const href = attrs.match(/\bhref="([^"]+)"/)?.[1];
      return !href || !verifiedWalkthroughDestinations.has(href);
    })
    .map(() => path.basename(file))
);
test(
  'misleading “Request a Walkthrough” CTA is absent',
  misleadingCtas.length === 0,
  misleadingCtas.join(', ')
);

/* ---------------------------------- SEO ----------------------------------- */
console.log('\nSEO metadata');
for (const file of htmlFiles) {
  const html = read(file);
  const name = path.basename(file);
  test(`${name} title`, /<title>[^<]{10,70}<\/title>/.test(html));
  test(`${name} meta description`, /<meta name="description" content="[^"]{50,180}"/.test(html));
  test(`${name} canonical`, /<link rel="canonical" href="https:\/\/databossx\.com\//.test(html));
  test(`${name} og:title`, html.includes('property="og:title"'));
  test(`${name} og:image`, html.includes('property="og:image"'));
  test(`${name} twitter card`, html.includes('name="twitter:card"'));
  test(`${name} JSON-LD`, html.includes('application/ld+json'));
  test(`${name} viewport`, html.includes('name="viewport"'));
}
const sitemap = read(path.join(dist, 'sitemap-0.xml'));
test('sitemap lists homepage', sitemap.includes('https://databossx.com/'));
test('sitemap lists architecture page', sitemap.includes('https://databossx.com/architecture'));
test('robots.txt references sitemap', read(path.join(dist, 'robots.txt')).includes('Sitemap:'));

/* -------------------------------- security -------------------------------- */
console.log('\nSecurity');
const headers = read(path.join(dist, '_headers'));
for (const header of [
  'Content-Security-Policy',
  'Strict-Transport-Security',
  'X-Content-Type-Options',
  'Referrer-Policy',
  'Permissions-Policy',
  "frame-ancestors 'none'",
]) {
  test(`_headers sets ${header}`, headers.includes(header));
}

// CSP <-> inline-script consistency: every executable inline script must be
// covered by a sha256 hash present in the CSP.
const allowedHashes = [...headers.matchAll(/'sha256-([^']+)'/g)].map((m) => m[1]);
for (const file of htmlFiles) {
  const html = read(file);
  const inline = [...html.matchAll(/<script(?![^>]*\bsrc=)([^>]*)>([\s\S]*?)<\/script>/g)]
    .filter(([, attrs]) => !/type="application\/(ld\+)?json"/.test(attrs))
    .map(([, , body]) => body);
  const uncovered = inline.filter(
    (body) => !allowedHashes.includes(createHash('sha256').update(body).digest('base64'))
  );
  test(
    `inline scripts in ${path.basename(file)} covered by CSP hash`,
    uncovered.length === 0,
    'regenerate the sha256 in public/_headers'
  );
}

const textFiles = files.filter((f) => /\.(html|css|js|xml|txt|svg)$/.test(f));
const secretPatterns = [
  [/sk-[A-Za-z0-9]{20,}/, 'OpenAI-style key'],
  [/AKIA[0-9A-Z]{16}/, 'AWS access key'],
  [/ghp_[A-Za-z0-9]{30,}/, 'GitHub token'],
  [/AIza[0-9A-Za-z_-]{30,}/, 'Google API key'],
  [/-----BEGIN [A-Z ]*PRIVATE KEY-----/, 'private key material'],
  [/xox[baprs]-[A-Za-z0-9-]{10,}/, 'Slack token'],
];
const leakPatterns = [
  [/localhost(?::\d+)?/i, 'localhost reference'],
  [/127\.0\.0\.1/, 'loopback address'],
  [/(?:^|[^\w./-])\/home\/[a-z0-9_-]+\//i, 'private unix path'],
  [/[A-Z]:\\Users\\/i, 'private windows path'],
  [/\/Users\/[a-z0-9_-]+\//i, 'private mac path'],
];
for (const [pattern, label] of [...secretPatterns, ...leakPatterns]) {
  const hits = textFiles.filter((f) => pattern.test(read(f)));
  test(`no ${label} in built output`, hits.length === 0, hits.map((h) => path.relative(dist, h)).join(', '));
}
test('no source maps shipped', files.every((f) => !f.endsWith('.map')));

/* ------------------------------- performance ------------------------------ */
console.log('\nPerformance budgets');
const gzSize = (f) => gzipSync(readFileSync(f)).length;
const jsFiles = files.filter((f) => f.endsWith('.js'));
const jsGz = jsFiles.reduce((sum, f) => sum + gzSize(f), 0);
test(`total JS ≤ 170 KB gzip (actual: ${(jsGz / 1024).toFixed(1)} KB)`, jsGz <= 170 * 1024);

const cssGz = files.filter((f) => f.endsWith('.css')).reduce((s, f) => s + gzSize(f), 0);
const homeGz = gzSize(path.join(dist, 'index.html'));
const homeTransfer = homeGz + cssGz + jsGz;
test(
  `homepage transfer (html+css+js gzip) ≤ 2 MB (actual: ${(homeTransfer / 1024).toFixed(1)} KB)`,
  homeTransfer <= 2 * 1024 * 1024
);

const oversized = files.filter((f) => statSync(f).size > 500 * 1024);
test('no single asset over 500 KB', oversized.length === 0, oversized.join(', '));

/* --------------------------------- summary -------------------------------- */
console.log(`\n${checks} checks, ${failures} failure(s)`);
process.exit(failures === 0 ? 0 : 1);
