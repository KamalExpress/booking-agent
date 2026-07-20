const { chromium } = require('@playwright/test');
require('dotenv').config();
(async () => {
    const browser = await chromium.launch({ headless: false }); // headless false to bypass WAF
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto('https://keagent-staging.alamiaconnect.com/login');
    await page.fill('input[id="email"]', process.env.TENANT_ADMIN_EMAIL);
    await page.fill('input[id="password"]', process.env.TENANT_ADMIN_PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/', {timeout: 10000});
    await page.goto('https://keagent-staging.alamiaconnect.com/tenants/1');
    await page.waitForTimeout(2000);
    const content = await page.content();
    console.log(content.includes('Portal Accounts Health') ? 'FOUND' : 'NOT_FOUND');
    console.log('Title:', await page.title());
    await page.screenshot({ path: 'debug_screenshot.png' });
    await browser.close();
})();
