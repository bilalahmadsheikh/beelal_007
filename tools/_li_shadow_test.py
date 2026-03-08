"""Test: dispatch_event directly on shadow DOM element via Playwright."""
import asyncio
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'd:/beelal_007')

from playwright.async_api import async_playwright
from tools.linkedin_playwright_poster import _load_linkedin_cookies

EDITOR_SEL = 'div[contenteditable="true"]'


async def test():
    cookies = _load_linkedin_cookies()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=['--start-maximized'])
        ctx = await browser.new_context(viewport=None)
        await ctx.add_cookies(cookies)
        page = await ctx.new_page()
        print("Navigating...")
        await page.goto('https://www.linkedin.com/feed/', wait_until='domcontentloaded', timeout=45000)
        await page.wait_for_selector('button[aria-label="Start a post"]', timeout=15000)
        await page.wait_for_timeout(2000)
        print("Page ready - trying dispatch_event")

        btn = page.locator('button[aria-label="Start a post"]').first

        # dispatch_event bypasses Playwright's actionability checks AND shadow DOM restrictions
        await btn.dispatch_event('click')
        await page.wait_for_timeout(3000)

        ed_count = await page.locator(EDITOR_SEL).count()
        print(f"dispatch_event('click') — editor count: {ed_count}")

        if ed_count == 0:
            # Try full pointer sequence
            print("Trying mousedown+mouseup+click dispatch...")
            for evt in ['mousedown', 'mouseup', 'click']:
                await btn.dispatch_event(evt, {'bubbles': True, 'cancelable': True})
            await page.wait_for_timeout(3000)
            ed_count = await page.locator(EDITOR_SEL).count()
            print(f"After full sequence: {ed_count}")

        if ed_count == 0:
            # Try tap (touch event - some LinkedIn versions respond to this)
            print("Trying tap event...")
            await btn.tap()
            await page.wait_for_timeout(3000)
            ed_count = await page.locator(EDITOR_SEL).count()
            print(f"After tap: {ed_count}")

        if ed_count > 0:
            ed = page.locator(EDITOR_SEL).first
            await ed.click(force=True)
            await page.wait_for_timeout(300)
            await page.keyboard.type('BilalAgent test - DO NOT POST', delay=0)
            print("Typed!")
            await page.wait_for_timeout(5000)

        await page.wait_for_timeout(3000)
        await browser.close()


asyncio.run(test())
