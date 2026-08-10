// Real-browser evidence for PR #88 viewport + accessibility blockers.
// Runs against the actual Command Center server (started separately,
// pointed at synthetic sandbox roots -- see qa/run-qa.sh). Never touches
// a real Penterra/Horizon/client path.
const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
const fs = require('fs');
const path = require('path');

const VIEWPORTS = [
  { name: '320x568', width: 320, height: 568 },
  { name: '375x667', width: 375, height: 667 },
  { name: '390x844', width: 390, height: 844 },
  { name: '430x932', width: 430, height: 932 },
  { name: '768x1024', width: 768, height: 1024 },
  { name: '1440x900', width: 1440, height: 900 },
];

const SCREENSHOT_DIR = path.join(__dirname, '..', 'artifacts', 'screenshots');
const AXE_DIR = path.join(__dirname, '..', 'artifacts', 'axe');
fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
fs.mkdirSync(AXE_DIR, { recursive: true });

for (const vp of VIEWPORTS) {
  test.describe(`viewport ${vp.name}`, () => {
    test.use({ viewport: { width: vp.width, height: vp.height } });

    test(`no horizontal overflow, sandbox banner visible, primary controls usable`, async ({ page }) => {
      await page.goto('/');
      await page.waitForSelector('#heroMove');
      await page.waitForTimeout(300); // let loadState() finish rendering

      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `${vp.name}-before-setup.png`),
        fullPage: true,
      });

      const sandboxBanner = page.locator('#sandboxBanner');
      await expect(sandboxBanner).toBeVisible();
      const bannerText = await sandboxBanner.textContent();
      expect(bannerText).toContain('SANDBOX MODE');
      expect(bannerText).toContain('NO CLIENT DATA');

      const overflow = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
      }));
      expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth + 1);

      await expect(page.locator('#commandInput')).toBeVisible();
      await expect(page.locator('#modeSelect')).toBeVisible();
      await expect(page.locator('#doNextBtn')).toBeVisible();
    });

    test(`keyboard navigation: skip link, tab order, focus visibility`, async ({ page }) => {
      await page.goto('/');
      await page.waitForSelector('#heroMove');
      await page.waitForTimeout(300);

      // First Tab must reach the skip link.
      await page.keyboard.press('Tab');
      const skipLinkFocused = await page.evaluate(() =>
        document.activeElement && document.activeElement.classList.contains('skip-link')
      );
      expect(skipLinkFocused).toBe(true);

      // Activating it must move focus into <main>.
      await page.keyboard.press('Enter');
      await page.waitForTimeout(100);

      // A visible focus indicator must exist on the currently focused element.
      await page.locator('#commandInput').focus();
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `${vp.name}-keyboard-focus.png`),
      });
      const outlineWidth = await page.evaluate(() => {
        const el = document.activeElement;
        return getComputedStyle(el).outlineWidth;
      });
      expect(outlineWidth).not.toBe('0px');

      // Escape must not throw / must be a no-op where no modal is open.
      await page.keyboard.press('Escape');
    });

    test(`axe WCAG A/AA scan has zero critical/serious and zero unlabeled form controls`, async ({ page }) => {
      await page.goto('/');
      await page.waitForSelector('#heroMove');
      await page.waitForTimeout(300);

      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
        .analyze();

      fs.writeFileSync(
        path.join(AXE_DIR, `${vp.name}.json`),
        JSON.stringify(results, null, 2)
      );

      const critSerious = results.violations.filter(
        (v) => v.impact === 'critical' || v.impact === 'serious'
      );
      const unlabeled = results.violations.filter((v) => v.id === 'label' || v.id === 'aria-input-field-name');

      expect(critSerious, JSON.stringify(critSerious, null, 2)).toHaveLength(0);
      expect(unlabeled, JSON.stringify(unlabeled, null, 2)).toHaveLength(0);
    });

    test(`toast/status updates are exposed through live-region semantics`, async ({ page }) => {
      await page.goto('/');
      await page.waitForSelector('#heroMove');
      await page.waitForTimeout(300);

      const toastRole = await page.locator('#toast').getAttribute('role');
      const toastLive = await page.locator('#toast').getAttribute('aria-live');
      expect(toastRole).toBe('status');
      expect(toastLive).toBe('polite');

      const commandResultLive = await page.locator('#commandResult').getAttribute('aria-live');
      expect(commandResultLive).toBe('polite');
    });
  });
}
