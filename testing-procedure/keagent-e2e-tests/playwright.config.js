// playwright.config.js
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  timeout: 450000, // Total timeout for each test execution
  use: {
    baseURL: 'https://keagent-staging.alamiaconnect.com', // Base URL configured here
    headless: true,
    viewport: { width: 1280, height: 720 },
    
    // --- TIMEOUT FIXES ---
    actionTimeout: 15000,      // Max time for clicks/fills (15s)
    navigationTimeout: 20000,  // Max time for page.goto() / redirects (20s)
  },
  
  // Custom assertion timeout (e.g. expect(locator).toBeVisible())
  expect: {
    timeout: 10000, // Wait up to 10 seconds for expectations to become true
  },
  
  reporter: [
    ['./reporters/custom-reporter.js'],
    ['json', { outputFile: 'test-results/results.json' }]
  ],
});