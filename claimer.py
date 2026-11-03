import os
import asyncio
import logging
from playwright.async_api import async_playwright, BrowserContext, Page

logger = logging.getLogger("BinanceClaimer")

class BinanceClaimer:
    def __init__(self, profile_dir: str, target_url: str, headless: bool = False):
        self.profile_dir = os.path.abspath(profile_dir)
        self.target_url = target_url
        self.headless = headless
        self.playwright = None
        self.context: BrowserContext = None
        self.page: Page = None
        self.lock = asyncio.Lock()

    async def start(self):
        """Initializes the persistent browser session."""
        logger.info(f"Launching Playwright with profile stored at: {self.profile_dir}")
        self.playwright = await async_playwright().start()
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.profile_dir,
            headless=self.headless,
            viewport={"width": 1280, "height": 800},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
        )
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        
        logger.info(f"Navigating to Binance Crypto Box: {self.target_url}")
        try:
            await self.page.goto(self.target_url, timeout=60000)
            logger.info("Page loaded. If you are not logged in, please complete the login in the opened browser window.")
        except Exception as e:
            logger.warning(f"Initial navigation encountered an error or timeout: {e}")

    async def claim_code(self, code: str) -> dict:
        """
        Submits an 8-character Crypto Box code into the input field and clicks Claim.
        Uses an asyncio Lock so claims are processed sequentially.
        """
        async with self.lock:
            logger.info(f"Attempting to claim code: {code}")
            try:
                # 1. Accept/Dismiss cookie banner if present
                cookie_btn = self.page.locator("#onetrust-accept-btn-handler")
                if await cookie_btn.is_visible():
                    await cookie_btn.click(timeout=1000)
            except Exception:
                pass

            try:
                # 2. Look for the Crypto Box code input field
                # Binance commonly uses an input with placeholder 'Crypto Box Code' or input[type='text']
                input_selector = (
                    "input[placeholder*='Crypto Box' i], "
                    "input[placeholder*='code' i], "
                    "input[placeholder*='Red Packet' i], "
                    "input[type='text']"
                )
                
                input_elem = self.page.locator(input_selector).first
                await input_elem.wait_for(state="visible", timeout=7000)
                
                # Clear and type the code
                await input_elem.click()
                await input_elem.fill("")
                await input_elem.fill(code)

                # 3. Locate and click the Claim / Open button
                claim_btn = self.page.locator(
                    "button:has-text('Claim'), "
                    "button:has-text('Open'), "
                    "button[data-bn-type='button']:has-text('Claim')"
                ).first
                
                await claim_btn.wait_for(state="visible", timeout=3000)
                await claim_btn.click()
                logger.info(f"Submitted claim button for code: {code}")

                # 4. Wait briefly for confirmation/result popup or message
                await asyncio.sleep(2)

                # Check for common status messages or modal dialogs
                result_text = "Submitted (Check browser UI for modal confirmation)"
                try:
                    dialog = self.page.locator("[role='dialog'], .bn-modal, .bn-message").first
                    if await dialog.is_visible():
                        result_text = await dialog.inner_text()
                except Exception:
                    pass

                logger.info(f"Result for {code}: {result_text}")
                return {"code": code, "status": "submitted", "detail": result_text}

            except Exception as e:
                logger.error(f"Failed to submit code {code}: {e}")
                return {"code": code, "status": "error", "detail": str(e)}

    async def close(self):
        """Closes browser session."""
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("Claimer browser session closed.")

