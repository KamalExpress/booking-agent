const { test, expect } = require('@playwright/test');

test.describe('Tenant Admin Testing Workflow', () => {

  test('0.1 Prerequisites: Log in as TENANT_ADMIN', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[name="email"]', process.env.TENANT_ADMIN_EMAIL);
    await page.fill('input[name="password"]', process.env.TENANT_ADMIN_PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/', { timeout: 10000 });
  });

  test.describe('1. Dashboard Views', () => {
    test('1.1 Action: Navigate to PWA Dashboard', async ({ page }) => {
      // Re-login inside block if session isn't persisted (Playwright usually needs this unless using state)
      await page.goto('/login');
      await page.fill('input[name="email"]', process.env.TENANT_ADMIN_EMAIL);
      await page.fill('input[name="password"]', process.env.TENANT_ADMIN_PASSWORD);
      await page.click('button[type="submit"]');

      await page.goto('/');
      await expect(page.locator('text="Visa Slots Monitor"')).toBeVisible();
      await expect(page.locator('text="Monitoring Confidence"')).toBeVisible();
    });

    test('1.2 Action: Navigate to Asset Burn Dashboard', async ({ page }) => {
      // Re-login
      await page.goto('/login');
      await page.fill('input[name="email"]', process.env.TENANT_ADMIN_EMAIL);
      await page.fill('input[name="password"]', process.env.TENANT_ADMIN_PASSWORD);
      await page.click('button[type="submit"]');

      // Tenant 2 is Kausar Trade Agency (assuming ID 1 is system core)
      await page.goto('/tenants/2');
      await expect(page.locator('text="Kausar Trade Agency"')).toBeVisible();
      // Asset Burn Indicators exist on this page
      await expect(page.locator('text="Account Health"')).toBeVisible();
      await expect(page.locator('text="Proxy Health"')).toBeVisible();
    });
  });

  test.describe('2. Staff Management', () => {
    test('2.1 Expected Result: Ensure Tenant Admin cannot grant SUPER_ADMIN', async ({ page }) => {
      await page.goto('/login');
      await page.fill('input[name="email"]', process.env.TENANT_ADMIN_EMAIL);
      await page.fill('input[name="password"]', process.env.TENANT_ADMIN_PASSWORD);
      await page.click('button[type="submit"]');

      // Attempt to view users list (usually /staff or /users in UI, assuming /staff)
      await page.goto('/staff');
      const superAdminOption = page.locator('select[name="role"] option[value="SUPER_ADMIN"]');
      await expect(superAdminOption).toHaveCount(0);
    });
  });
});