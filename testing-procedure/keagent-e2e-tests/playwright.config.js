// playwright.config.js
require('dotenv').config();
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  timeout: 450000, // Total timeout for each test execution
  workers: 1, // Force sequential execution so state flows from 01 -> 02 -> 03
  use: {
    baseURL: 'https://keagent-staging.alamiaconnect.com', // Base URL configured here
    headless: false,
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