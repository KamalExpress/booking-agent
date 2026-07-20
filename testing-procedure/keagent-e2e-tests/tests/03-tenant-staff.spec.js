const { test, expect } = require('@playwright/test');

test.describe('Tenant Staff (Travel Agent) Testing Workflow', () => {

  // Re-authenticate before running each test block
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    // Assuming staff@kausar.com is a standard STAFF account created during Tenant Admin testing
    await page.fill('input[name="email"]', process.env.TENANT_STAFF_EMAIL);
    await page.fill('input[name="password"]', process.env.TENANT_STAFF_PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/', { timeout: 10000 });
  });

  test.describe('1. Client Directory (Applicant Creation)', () => {
    test('1.1 Action: Navigate to Clients page and create Applicant', async ({ page }) => {
      // NOTE: This route may not exist yet in ui.py! (TDD approach)
      await page.goto('/clients');
      await expect(page.locator('text="Client Directory"')).toBeVisible();

      await page.click('button:has-text("Add Applicant")');
      await expect(page.locator('#createApplicantModal')).toBeVisible();

      // Fill standardized GVC form
      await page.fill('input[name="first_name"]', 'Ali');
      await page.fill('input[name="last_name"]', 'Raza');
      await page.fill('input[name="dateofbirth"]', '01/01/1990');
      await page.selectOption('select[name="gender"]', 'M');
      await page.fill('input[name="nationality"]', 'PAK');
      await page.fill('input[name="passport_number"]', 'AB1234567');
      await page.fill('input[name="passport_expiry"]', '01/01/2030');
      await page.fill('input[name="email"]', 'ali@example.com');
      await page.fill('input[name="phone_prefix"]', '+92');
      await page.fill('input[name="phone_number"]', '3001234567');
      
      await page.click('button[type="submit"]:has-text("Save Applicant")');
      
      // Verify row exists in table
      await page.waitForURL('**/clients');
      const tableText = await page.locator('table tbody').innerText();
      expect(tableText).toContain('Ali Raza');
      expect(tableText).toContain('AB1234567');
    });
  });

  test.describe('2. Pushing to the Waitlist', () => {
    test('2.1 Action: Assign Applicant to WaitlistQueue', async ({ page }) => {
      // NOTE: This route may not exist yet in ui.py! (TDD approach)
      await page.goto('/queue');
      await expect(page.locator('text="Queue Management"')).toBeVisible();

      await page.click('button:has-text("Add to Queue")');
      await expect(page.locator('#addToQueueModal')).toBeVisible();

      // Select applicant and visa center
      await page.selectOption('select[name="applicant_id"]', { label: 'Ali Raza - AB1234567' });
      await page.selectOption('select[name="visa_center_id"]', '138'); // Lahore
      await page.selectOption('select[name="appointment_type"]', '26'); // 26 - Short Term
      await page.click('button[type="submit"]:has-text("Enqueue")');

      // Verify row exists in waitlist table with PENDING status
      await page.waitForURL('**/queue');
      const pendingRow = page.locator('table tbody tr:has-text("Ali Raza")');
      await expect(pendingRow).toBeVisible();
      await expect(pendingRow.locator('text="PENDING"')).toBeVisible();
    });
  });
});
