/*
 * Generates the social-preview image and app icons from branded HTML
 * templates using the locally installed Chromium. Run manually when the
 * brand or headline changes:
 *
 *   node scripts/make-assets.mjs
 *
 * Outputs (committed to the repo so builds stay hermetic):
 *   public/og/databossx-og.png   1200x630
 *   public/icons/icon-512.png     512x512
 *   public/icons/apple-touch-icon.png  180x180
 */
import { chromium } from 'playwright-core';
import { mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
mkdirSync(path.join(root, 'public/og'), { recursive: true });
mkdirSync(path.join(root, 'public/icons'), { recursive: true });

const ogHtml = `<!doctype html><html><head><meta charset="utf-8"><style>
  * { margin: 0; box-sizing: border-box; }
  body {
    width: 1200px; height: 630px; overflow: hidden;
    background:
      radial-gradient(ellipse 80% 60% at 75% 20%, rgba(91,140,255,.14), transparent 65%),
      radial-gradient(ellipse 60% 50% at 15% 90%, rgba(157,140,255,.12), transparent 65%),
      #06080c;
    color: #e9eef7;
    font-family: system-ui, -apple-system, 'Segoe UI', sans-serif;
    display: flex; flex-direction: column; justify-content: center;
    padding: 90px; position: relative;
  }
  .grid {
    position: absolute; inset: 0;
    background-image:
      linear-gradient(to right, rgba(63,220,255,.05) 1px, transparent 1px),
      linear-gradient(to bottom, rgba(63,220,255,.05) 1px, transparent 1px);
    background-size: 48px 48px;
    mask-image: radial-gradient(ellipse 90% 80% at 50% 40%, black 30%, transparent 80%);
  }
  .brand { display: flex; align-items: center; gap: 18px; margin-bottom: 48px; }
  .mark { width: 54px; height: 54px; border: 3px solid #3fdcff; border-radius: 13px; position: relative; }
  .mark::before, .mark::after { content: ''; position: absolute; background: #3fdcff; border-radius: 2px; }
  .mark::before { left: 12px; right: 12px; top: 50%; height: 3px; margin-top: -1.5px; }
  .mark::after { top: 12px; bottom: 12px; left: 50%; width: 3px; margin-left: -1.5px; }
  .name { font-size: 34px; font-weight: 700; letter-spacing: .5px; }
  .name b { color: #3fdcff; }
  h1 { font-size: 92px; font-weight: 750; letter-spacing: -2.5px; line-height: 1.04; }
  h1 span {
    background: linear-gradient(100deg, #3fdcff, #5b8cff 55%, #9d8cff);
    -webkit-background-clip: text; background-clip: text; color: transparent;
  }
  .strap { margin-top: 44px; font-family: ui-monospace, Menlo, monospace; font-size: 24px; color: #9aa8bf; letter-spacing: 1px; }
</style></head><body>
  <div class="grid"></div>
  <div class="brand"><div class="mark"></div><div class="name">DataBoss<b>X</b></div></div>
  <h1>Your Data.<br><span>Under Command.</span></h1>
  <div class="strap">sources → evidence → provenance → agents → review → release</div>
</body></html>`;

const iconHtml = (size) => `<!doctype html><html><head><meta charset="utf-8"><style>
  * { margin: 0; }
  body { width: ${size}px; height: ${size}px; overflow: hidden;
    background: #06080c; display: grid; place-items: center; }
  .mark { width: ${size * 0.72}px; height: ${size * 0.72}px;
    border: ${size * 0.05}px solid #3fdcff; border-radius: ${size * 0.16}px; position: relative; }
  .mark::before, .mark::after { content: ''; position: absolute; background: #3fdcff; border-radius: ${size * 0.01}px; }
  .mark::before { left: 22%; right: 22%; top: 50%; height: ${size * 0.05}px; margin-top: ${-size * 0.025}px; }
  .mark::after { top: 22%; bottom: 22%; left: 50%; width: ${size * 0.05}px; margin-left: ${-size * 0.025}px; }
</style></head><body><div class="mark"></div></body></html>`;

const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium',
});

async function shoot(html, width, height, out) {
  const page = await browser.newPage({ viewport: { width, height } });
  await page.setContent(html, { waitUntil: 'networkidle' });
  await page.screenshot({ path: path.join(root, out) });
  await page.close();
  console.log('wrote', out);
}

await shoot(ogHtml, 1200, 630, 'public/og/databossx-og.png');
await shoot(iconHtml(512), 512, 512, 'public/icons/icon-512.png');
await shoot(iconHtml(180), 180, 180, 'public/icons/apple-touch-icon.png');
await browser.close();
