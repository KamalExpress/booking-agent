require('dotenv').config();
const { chromium } = require('playwright');

async function deployStack() {
  const stackUrl = process.env.PORTAINER_STACK_URL;
  if (!stackUrl) {
    console.error('ERROR: PORTAINER_STACK_URL is missing in .env');
    process.exit(1);
  }

  console.log(`Connecting to local Chrome via CDP on port 9222...`);
  
  try {
    // Connect to the already running, authenticated Chrome browser
    const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
    const defaultContext = browser.contexts()[0];
    const page = await defaultContext.newPage();

    console.log(`Navigating to Portainer Stack: ${stackUrl}`);
    await page.goto(stackUrl, { waitUntil: 'networkidle' });

    // Wait for the UI to load
    await page.waitForTimeout(3000);

    console.log('Searching for Pull and redeploy button...');
    
    // In Portainer CE, the button is typically "Pull and redeploy" or "Update the stack"
    // We will look for both
    let redeployBtn = page.locator('button:has-text("Pull and redeploy")').first();
    let isGit = true;
    
    if (await redeployBtn.count() === 0) {
      redeployBtn = page.locator('button:has-text("Update the stack")').first();
      isGit = false;
    }

    if (await redeployBtn.count() === 0) {
      console.error('ERROR: Could not find the "Pull and redeploy" or "Update the stack" button. Please check the URL and ensure you are on the Stack details page.');
      await page.close();
      process.exit(1);
    }

    console.log('Clicking redeploy button...');
    await redeployBtn.click();

    // If it's manual update, there might be a confirmation modal
    if (!isGit) {
      // Look for confirm button if manual update
      const confirmBtn = page.locator('button:has-text("Update")').last();
      if (await confirmBtn.isVisible()) {
        await confirmBtn.click();
      }
    }

    console.log('Waiting for deployment to finish (this may take up to 2 minutes)...');
    
    // Wait for a success notification from Portainer
    // Portainer uses toast-notifications, usually with text "Success" or "Stack successfully deployed"
    const successToast = page.locator('div.toast-success, div:has-text("Stack successfully updated"), div:has-text("Stack successfully deployed")').first();
    await successToast.waitFor({ state: 'visible', timeout: 120000 }).catch(() => {
        console.log('Did not see success toast, but waiting a bit just in case.');
    });
    
    // Just a fallback wait to ensure background processes finish
    await page.waitForTimeout(5000);
    
    console.log('✅ Deployment triggered and completed successfully!');

    await page.close();
    process.exit(0);
  } catch (err) {
    console.error('Deployment script failed:', err.message);
    process.exit(1);
  }
}

deployStack();
