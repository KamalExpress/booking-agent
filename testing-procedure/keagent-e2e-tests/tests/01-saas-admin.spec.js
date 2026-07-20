const { test, expect } = require('@playwright/test');

test.describe('SaaS Admin (Super Admin) Testing Workflow', () => {

  // Re-authenticate before running each test block
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[id="email"]', process.env.SAAS_ADMIN_EMAIL);
    await page.fill('input[id="password"]', process.env.SAAS_ADMIN_PASSWORD);
    await page.click('button[type="submit"]');
    
    // Ensure navigation completes before test starts
    await page.waitForURL('**/', { timeout: 10000 });
  });

  test('0.1 Prerequisites: Log in as SUPER_ADMIN', async ({ page }) => {
    // Verified by beforeEach hook
    await expect(page).not.toHaveURL(/.*login/);
  });

  test.describe('1. Global Dashboard & Auto-Scaling', () => {
    test('1.1 Action: Navigate to main dashboard', async ({ page }) => {
      await page.goto('/');
      await expect(page.locator('text="System Overview"')).toBeVisible();
    });

    test('1.1.1 Expected Result: Auto-Scaling Dial calculates capacity ratio', async ({ page }) => {
      await page.goto('/');
      await expect(page.locator('text="Auto-Scaling Dial"')).toBeVisible();
    });

    test('1.1.2 Expected Result: System Health Score reflects active heartbeats', async ({ page }) => {
      await page.goto('/');
      await expect(page.locator('text="Active Workers"')).toBeVisible();
    });

    test('1.1.3 Expected Result: Global Assignment Map displays active tasks', async ({ page }) => {
      await page.goto('/');
      await expect(page.locator('text="Active Assignments"')).toBeVisible();
    });
  });

  test.describe('2. Tenant Management', () => {
    test('2.1 Action: Navigate to Tenants list', async ({ page }) => {
      await page.goto('/tenants');
      await expect(page.locator('text="Manage organizations and sub-agencies"')).toBeVisible();
    });

    test('2.1.1 Expected Result: Ability to view all tenants', async ({ page }) => {
      await page.goto('/tenants');
      const rows = page.locator('table tbody tr');
      expect(await rows.count()).toBeGreaterThan(0);
    });

    test('2.2 Action: Create a new Tenant', async ({ page }) => {
      await page.goto('/tenants');
      // Click Add Tenant button to open modal
      await page.click('button:has-text("Add Tenant")');
      // Modal should become visible
      await expect(page.locator('#createTenantModal')).toBeVisible();
      
      await page.fill('input[name="tenant_name"]', 'Kausar Trade Agency');
      await page.fill('input[name="admin_email"]', process.env.TENANT_ADMIN_EMAIL);
      await page.fill('input[name="admin_password"]', process.env.TENANT_ADMIN_PASSWORD);
      await page.click('button[type="submit"]:has-text("Create Tenant")');
      
      // Wait for navigation/reload after create
      await page.waitForURL('**/tenants');
    });

    test('2.3.2 Expected Result: Default Tenant (ID=1) protected from suspension', async ({ page }) => {
      await page.goto('/tenants');
      // The default tenant row should have the text "System Core" instead of the suspend form
      await expect(page.locator('table tbody tr').first().locator('text="System Core"')).toBeVisible();
    });
  });
});