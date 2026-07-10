# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "playwright",
# ]
# ///
import asyncio
from playwright.async_api import async_playwright
import os

async def capture():
    async with async_playwright() as p:
        # Launch browser headless for server env
        browser = await p.chromium.launch(headless=True)
        # Context with HAR recording
        context = await browser.new_context(
            record_har_path="portalmind/research/initial_load.har"
        )
        page = await context.new_page()
        
        print("Navigating to https://pk-gr-services.gvcworld.eu ...")
        try:
            await page.goto("https://pk-gr-services.gvcworld.eu", wait_until="networkidle")
        except Exception as e:
            print(f"Error during navigation: {e}")
            
        print("Waiting a few seconds for any deferred requests...")
        await page.wait_for_timeout(3000)
        
        print("Saving DOM snapshot...")
        html = await page.content()
        with open("portalmind/research/dom_initial.html", "w", encoding="utf-8") as f:
            f.write(html)
            
        print("Taking screenshot...")
        await page.screenshot(path="portalmind/research/screenshot_initial.png")
        
        await context.close()
        await browser.close()
        print("Initial capture complete.")

if __name__ == "__main__":
    # Ensure playwright browsers are installed
    os.system("playwright install chromium")
    asyncio.run(capture())
