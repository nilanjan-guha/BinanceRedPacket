import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        # Launch Chromium with your persistent profile
        context = await p.chromium.launch_persistent_context(
            user_data_dir="./binance_browser_profile",
            headless=False,
            viewport={"width": 1280, "height": 850},
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else await context.new_page()
        
        # Navigate to the official Binance Pay dashboard
        print("Opening Binance Pay...")
        await page.goto("https://www.binance.com/en/my/pay", timeout=60000)
        
        print("\n" + "="*60)
        print("BROWSER IS READY!")
        print("1. Log in to your Binance account in the opened window.")
        print("2. Check where the 'Crypto Box' or 'Send Cash' tab is.")
        print("3. Notice the exact URL in the address bar.")
        print("="*60 + "\n")
        
        # Keep open until you press Enter in terminal
        input("Press Enter in this terminal once you have navigated to the Crypto Box page...")
        
        current_url = page.url
        print(f"\nCaptured Current URL: {current_url}")
        await context.close()

if __name__ == "__main__":
    asyncio.run(main())

