"""
tools/linkedin_playwright_poster.py — BilalAgent v3.1

Posts to LinkedIn using Playwright + cookies imported from the agent DB.
- Opens a fresh Chromium window (no Chrome profile conflicts)
- Injects LinkedIn session cookies (li_at etc.) so no login needed
- Types the post, waits for user to review and click Post
- Reports back to the bridge/overlay

No Chrome extension required. Works as long as LinkedIn cookies are synced.
"""

import asyncio
import json
import os
import sqlite3
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "memory", "agent_memory.db")


# ── Cookie helpers ────────────────────────────────────

SAMESIDE_MAP = {
    "no_restriction": "None",
    "lax": "Lax",
    "strict": "Strict",
    "unspecified": "None",
    None: "None",
}


def _normalize_domain(domain: str) -> str:
    """Normalize cookie domain for Playwright compatibility.
    .www.linkedin.com → .linkedin.com (Playwright needs root domain for auth cookies)
    """
    if not domain:
        return ".linkedin.com"
    # Strip .www. prefix — keep just .linkedin.com
    domain = domain.replace(".www.linkedin.com", ".linkedin.com")
    domain = domain.replace(".pk.linkedin.com", ".linkedin.com")
    # Ensure leading dot for cross-subdomain cookies
    if not domain.startswith(".") and not domain.startswith("px."):
        domain = "." + domain
    return domain


def _load_linkedin_cookies() -> list:
    """Load LinkedIn cookies from agent DB and convert to Playwright format."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    seen = set()  # deduplicate by (name, domain)
    cookies = []
    for site in ("linkedin.com", "www.linkedin.com"):
        row = conn.execute(
            "SELECT cookie_data FROM cookies WHERE site = ?", (site,)
        ).fetchone()
        if row:
            raw = json.loads(row["cookie_data"])
            for c in raw:
                domain = _normalize_domain(c.get("domain", ".linkedin.com"))
                key = (c.get("name", ""), domain)
                if key in seen:
                    continue
                seen.add(key)
                pw = {
                    "name":     c.get("name", ""),
                    "value":    c.get("value", ""),
                    "domain":   domain,
                    "path":     c.get("path", "/"),
                    "secure":   bool(c.get("secure", True)),
                    "httpOnly": bool(c.get("httpOnly", False)),
                    "sameSite": SAMESIDE_MAP.get(c.get("sameSite"), "None"),
                }
                exp = c.get("expirationDate")
                if exp:
                    pw["expires"] = int(exp)
                if pw["name"] and pw["value"]:
                    cookies.append(pw)
    conn.close()
    return cookies


# ── Main poster ───────────────────────────────────────

class LinkedInPlaywrightPoster:

    COMPOSER_SELECTORS = [
        # Ordered: most specific first; use force=True to bypass shadow-DOM intercept
        'button[aria-label="Start a post"]',
        'button.share-box-feed-entry__trigger',
        '.share-box-feed-entry__trigger',
        '[data-view-name="share-box-feed-entry"] button',
        'div[aria-label="Start a post"]',
    ]

    EDITOR_SELECTORS = [
        'div.ql-editor[contenteditable="true"]',
        'div[data-placeholder="What do you want to talk about?"][contenteditable="true"]',
        'div.share-creation-state__text-editor div[contenteditable="true"]',
    ]

    POST_BTN_SELECTORS = [
        'button.share-actions__primary-action',
        'button[data-control-name="share.post"]',
        'button:has-text("Post"):not([disabled])',
    ]

    def __init__(self):
        self._log = print

    def set_log(self, fn):
        self._log = fn

    def _overlay_log(self, text: str, msg_type: str = "system"):
        self._log(f"  [PW POSTER] {text}")
        try:
            from ui.desktop_overlay import get_overlay_instance
            ov = get_overlay_instance()
            if ov is not None:
                ov.log_signal.emit(text, msg_type)
        except Exception:
            pass

    def post(self, content: str) -> dict:
        """Synchronous wrapper — runs the async post in a new event loop."""
        try:
            return asyncio.run(self._post_async(content))
        except RuntimeError:
            # Already inside an event loop (e.g. in a QThread)
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self._post_async(content))
            finally:
                loop.close()

    async def _post_async(self, content: str) -> dict:
        from playwright.async_api import async_playwright

        cookies = _load_linkedin_cookies()
        if not cookies:
            return {"status": "failed", "reason": "No LinkedIn cookies in DB — open LinkedIn in Chrome first"}

        self._overlay_log("🚀 Launching Playwright Chromium with LinkedIn session...")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                args=["--start-maximized", "--disable-blink-features=AutomationControlled"],
            )
            ctx = await browser.new_context(
                viewport=None,
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            )

            # Inject cookies BEFORE navigating
            await ctx.add_cookies(cookies)

            page = await ctx.new_page()

            # ── Navigate to LinkedIn feed ─────────────────────
            self._overlay_log("Navigating to LinkedIn feed...")
            await page.goto(
                "https://www.linkedin.com/feed/",
                wait_until="domcontentloaded",
                timeout=45000,
            )
            await page.wait_for_timeout(3000)

            # Check if still logged in
            url = page.url
            if "authwall" in url or "/login" in url or "/uas/" in url:
                await browser.close()
                return {
                    "status": "failed",
                    "reason": (
                        "LinkedIn session expired — cookies invalid.\n"
                        "Fix: Open LinkedIn in Chrome and leave it open. "
                        "The extension will re-sync fresh cookies."
                    ),
                }

            self._overlay_log("✓ Logged in to LinkedIn")

            # ── Open composer ─────────────────────────────────
            # Wait for feed to render React components (LinkedIn is slow)
            self._overlay_log("Waiting for LinkedIn feed to render...")
            try:
                await page.wait_for_selector(
                    'button[aria-label="Start a post"], .share-box-feed-entry__trigger',
                    timeout=15000, state="attached"
                )
            except Exception:
                pass  # Proceed anyway and let _open_composer handle fallbacks
            await page.wait_for_timeout(2000)

            self._overlay_log("Clicking 'Start a post'...")
            opened = await self._open_composer(page)
            if not opened:
                await browser.close()
                return {"status": "failed", "reason": "Could not find 'Start a post' button on LinkedIn feed"}

            self._overlay_log("✓ Composer opened — typing post...")

            # ── Type content ──────────────────────────────────
            typed = await self._type_content(page, content)
            if not typed:
                await browser.close()
                return {"status": "failed", "reason": "Could not find post editor"}

            word_count = len(content.split())
            self._overlay_log(f"✓ {word_count} words typed — review in the Chromium window")
            self._overlay_log("👆 Click 'Post' in Chromium when ready (or close to cancel)")

            # ── Wait for user to click Post (up to 5 min) ────
            result = await self._wait_for_post_or_cancel(page, timeout_s=300)

            await browser.close()

            if result == "posted":
                posted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._overlay_log(f"✅ Posted to LinkedIn at {posted_at}", "agent")
                self._log_success(content, posted_at)
                return {
                    "status": "posted",
                    "reason": "Success",
                    "posted_at": posted_at,
                    "word_count": word_count,
                }
            elif result == "cancelled":
                return {"status": "cancelled", "reason": "Browser closed before posting"}
            else:
                return {"status": "timeout", "reason": "No action taken in 5 minutes"}

    @staticmethod
    async def _js_click(page, sel: str) -> bool:
        """Dispatch full mousedown+mouseup+click sequence — required for React apps."""
        return await page.evaluate(f"""
            (() => {{
                const el = document.querySelector({json.dumps(sel)});
                if (!el) return false;
                el.scrollIntoView({{block:'center'}});
                el.focus();
                ['mousedown','mouseup','click'].forEach(t =>
                    el.dispatchEvent(new MouseEvent(t, {{bubbles:true, cancelable:true, view:window}}))
                );
                return true;
            }})()
        """)

    async def _open_composer(self, page) -> bool:
        async def _editor_visible():
            for ed in self.EDITOR_SELECTORS:
                if await page.locator(ed).count() > 0:
                    return True
            return False

        # Try each selector with full React-compatible event sequence
        for sel in self.COMPOSER_SELECTORS:
            try:
                if await page.locator(sel).count() == 0:
                    continue
                hit = await self._js_click(page, sel)
                if hit:
                    await page.wait_for_timeout(2500)
                    if await _editor_visible():
                        print(f"  [PW] Composer opened via: {sel}")
                        return True
            except Exception as e:
                print(f"  [PW] Selector {sel}: {e}")

        # Last resort: find button by text via JS
        try:
            await page.evaluate("""
                const btns = [...document.querySelectorAll('button, div[role="button"]')];
                const btn = btns.find(b => b.textContent.trim().toLowerCase() === 'start a post');
                if (btn) {
                    btn.scrollIntoView({block:'center'});
                    btn.focus();
                    ['mousedown','mouseup','click'].forEach(t =>
                        btn.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true, view:window}))
                    );
                }
            """)
            await page.wait_for_timeout(2500)
            if await _editor_visible():
                print("  [PW] Composer opened via JS text match")
                return True
        except Exception:
            pass

        return False

    async def _type_content(self, page, content: str) -> bool:
        for sel in self.EDITOR_SELECTORS:
            try:
                count = await page.locator(sel).count()
                if count == 0:
                    continue
                # Focus with full event sequence so React registers the click
                await self._js_click(page, sel)
                await page.wait_for_timeout(300)
                # Select all and delete
                await page.keyboard.press("Control+a")
                await page.keyboard.press("Delete")
                await page.wait_for_timeout(200)
                # Type via keyboard (preserves line breaks)
                lines = content.split("\n")
                for i, line in enumerate(lines):
                    if line:
                        await page.keyboard.type(line, delay=0)
                    if i < len(lines) - 1:
                        await page.keyboard.press("Shift+Enter")
                await page.wait_for_timeout(500)
                print(f"  [PW] Content typed ({len(content)} chars)")
                return True
            except Exception as e:
                print(f"  [PW] Type error {sel}: {e}")
                continue
        return False

    async def _wait_for_post_or_cancel(self, page, timeout_s: int = 300) -> str:
        """
        Wait until:
        - The post-success state appears (feed reloads with no modal), OR
        - The browser/page is closed, OR
        - Timeout
        """
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                # Check if page is still open
                url = page.url
            except Exception:
                return "cancelled"  # page closed

            # Check if modal is gone (post submitted) and we're on feed
            modal_open = await page.locator('div.ql-editor, .share-creation-state').count()
            if modal_open == 0 and "feed" in url:
                # Modal dismissed — likely posted
                await page.wait_for_timeout(1500)
                # Double-check: success toast often appears
                return "posted"

            await asyncio.sleep(1)

        return "timeout"

    # ── Logging ───────────────────────────────────────

    def _log_success(self, content: str, posted_at: str):
        try:
            from memory.excel_logger import log_linkedin_post
            log_linkedin_post(
                content=content,
                platform="linkedin",
                word_count=len(content.split()),
                status="uploaded",
                posted_at=posted_at,
            )
            print("  [PW POSTER] ✓ Logged to linkedin_posts.xlsx")
        except Exception as e:
            print(f"  [PW POSTER] Excel log failed: {e}")

        try:
            from memory.db import log_action
            log_action("linkedin_posted", {
                "words": len(content.split()),
                "posted_at": posted_at,
                "method": "playwright_cookies",
            }, "completed")
        except Exception:
            pass


# ── Smoke test ────────────────────────────────────────

if __name__ == "__main__":
    poster = LinkedInPlaywrightPoster()
    cookies = _load_linkedin_cookies()
    print(f"Loaded {len(cookies)} LinkedIn cookies from DB")
    auth = [c for c in cookies if c["name"] in ("li_at", "JSESSIONID", "bscookie")]
    for c in auth:
        print(f"  {c['name']}: {c['value'][:30]}...")

    print("\nStarting test post...")
    result = poster.post(
        "🧪 Test post from BilalAgent Playwright poster — please ignore"
    )
    print(f"Result: {result}")
