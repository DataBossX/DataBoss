/*
 * Capture QA screenshots of the running preview server.
 *
 *   npx astro preview &          # serves dist/ on :4321
 *   node scripts/screenshot.mjs <outputDir>
 *
 * Captures viewport-sized shots per section (full-page capture in headless
 * Chromium leaves unrasterized tiles on very tall pages) and fails if any
 * page throws a JavaScript runtime error.
 */
import { chromium } from 'playwright-core';
import { mkdirSync } from 'node:fs';
import path from 'node:path';

const out = process.argv[2] || 'screenshots';
mkdirSync(out, { recursive: true });
const base = 'http://127.0.0.1:4321';

const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium',
});

const homeAnchors = ['top', '#system', '#architecture', '#surfaces', '#provenance', '#use-cases', '#security', 'bottom'];

const jobs = [
  { page: 'home', url: '/', viewport: { width: 1440, height: 900 }, anchors: homeAnchors },
  { page: 'home-mobile', url: '/', viewport: { width: 390, height: 844 }, mobile: true, anchors: ['top', '#surfaces', '#provenance', 'bottom'] },
  { page: 'architecture', url: '/architecture', viewport: { width: 1440, height: 900 }, anchors: ['top', 'middle', 'bottom'] },
  { page: '404', url: '/missing-page', viewport: { width: 1440, height: 900 }, anchors: ['top'] },
];

const errors = [];
for (const job of jobs) {
  const context = await browser.newContext({
    viewport: job.viewport,
    isMobile: Boolean(job.mobile),
    hasTouch: Boolean(job.mobile),
    deviceScaleFactor: job.mobile ? 2 : 1,
  });
  const page = await context.newPage();
  page.on('pageerror', (err) => errors.push(`${job.page}: ${err.message}`));
  page.on('console', (msg) => {
    // The 404 QA shot intentionally requests a missing URL; the document's
    // own 404 status is expected, not a runtime error.
    if (msg.type() === 'error' && !msg.text().includes('status of 404')) {
      errors.push(`${job.page} console: ${msg.text()}`);
    }
  });
  await page.goto(base + job.url, { waitUntil: 'networkidle' });

  for (const anchor of job.anchors) {
    await page.evaluate((a) => {
      if (a === 'top') window.scrollTo(0, 0);
      else if (a === 'bottom') window.scrollTo(0, document.body.scrollHeight);
      else if (a === 'middle') window.scrollTo(0, document.body.scrollHeight / 2);
      else document.querySelector(a)?.scrollIntoView();
    }, anchor);
    await page.waitForTimeout(850);
    const suffix = anchor.replace(/[^a-z-]/gi, '') || 'top';
    await page.screenshot({ path: path.join(out, `${job.page}--${suffix}.png`) });
    console.log('wrote', `${job.page}--${suffix}.png`);
  }
  await context.close();
}

await browser.close();
if (errors.length) {
  console.error('\nJS runtime errors detected:');
  errors.forEach((e) => console.error(' -', e));
  process.exit(1);
}
console.log('\nNo JS runtime errors.');
