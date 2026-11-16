import { defineConfig, devices } from '@playwright/test';
export default defineConfig({
  testDir: './e2e', timeout: 45000, workers: 1,
  use: { baseURL: 'http://127.0.0.1:5173', channel: 'msedge', headless: true },
  outputDir: '../.runtime/browser-results',
  webServer: { command: 'npm run dev', url: 'http://127.0.0.1:5173', reuseExistingServer: true, timeout: 20000 },
  projects: [{ name: 'desktop', use: { viewport: { width: 1440, height: 1000 } } },
             { name: 'mobile', use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } }],
});
