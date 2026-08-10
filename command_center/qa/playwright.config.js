// @ts-check
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  timeout: 30000,
  retries: 0,
  reporter: [['list']],
  use: {
    // Never fetches -- points at a locally-started server on a synthetic
    // sandbox root, never any real Penterra/Horizon/client path.
    baseURL: process.env.DATABOSSX_QA_BASE_URL || 'http://127.0.0.1:8765',
    trace: 'off',
    launchOptions: process.env.DATABOSSX_QA_CHROMIUM_PATH
      ? { executablePath: process.env.DATABOSSX_QA_CHROMIUM_PATH }
      : {},
  },
});
