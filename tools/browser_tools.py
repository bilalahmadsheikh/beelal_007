"""
browser_tools.py — BilalAgent v2.0 Browser Automation with Stealth
Uses Playwright + stealth + extension overlay for approval.
Cookie reuse from SQLite for session persistence.
"""

import os
import sys
import json
import time
import sqlite3
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "memory", "agent_memory.db")
BRIDGE_URL = "http://localhost:8000"
EXTENSION_PATH = os.path.join(PROJECT_ROOT, "chrome_extension")


def _get_stored_cookies(site: str) -> list:
    """Get stored cookies from SQLite for Playwright context."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT cookie_data FROM cookies WHERE site = ?", (site,)).fetchone()
        conn.close()
        if row:
            return json.loads(row["cookie_data"])
    except Exception:
        pass
    return []


def _wait_for_approval(task_id: str, timeout: int = 300) -> str:
    """Wait for extension overlay approval via bridge polling."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            task = conn.execute(
                "SELECT status, result FROM pending_tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            conn.close()
            
            if task and task["status"] in ("approve", "cancel", "edit"):
                return task["status"]
        except Exception:
            pass
        time.sleep(1)
    
    return "timeout"


def _register_task(task_type: str, content_preview: str, action_label: str = "Approve") -> str:
    """Register a task for the extension overlay to display."""
    try:
        resp = requests.post(f"{BRIDGE_URL}/extension/register_task", json={
            "task_type": task_type,
            "content_preview": content_preview,
            "action_label": action_label,
        })
        return resp.json().get("task_id", "")
    except requests.exceptions.ConnectionError:
        print("[BROWSER] Bridge not running — falling back to CLI approval")
        return ""


def _create_stealth_context(playwright, load_extension: bool = False, site: str = ""):
    """Create a Playwright browser context with stealth and optional cookies."""
    from playwright_stealth import Stealth
    
    launch_args = ["--disable-blink-features=AutomationControlled"]
    
    if load_extension and os.path.isdir(EXTENSION_PATH):
        launch_args.extend([
            f"--load-extension={EXTENSION_PATH}",
            f"--disable-extensions-except={EXTENSION_PATH}",
        ])
        # Can't use headless with extensions
        browser = playwright.chromium.launch(
            headless=False,
            args=launch_args,
        )
    else:
        browser = playwright.chromium.launch(headless=True, args=launch_args)
    
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
        locale="en-US",
    )
    
    # Apply stealth
    stealth = Stealth()
    page = context.new_page()
    stealth.apply_stealth(page)
    
    # Load stored cookies if available
    if site:
        cookies = _get_stored_cookies(site)
        if cookies:
            # Convert Chrome extension cookies to Playwright format
            pw_cookies = []
            for c in cookies:
                pw_cookie = {
                    "name": c.get("name", ""),
                    "value": c.get("value", ""),
                    "domain": c.get("domain", ""),
                    "path": c.get("path", "/"),
                }
                if c.get("expirationDate"):
                    pw_cookie["expires"] = c["expirationDate"]
                if c.get("secure"):
                    pw_cookie["secure"] = True
                if c.get("httpOnly"):
                    pw_cookie["httpOnly"] = True
                if c.get("sameSite"):
                    samesite_map = {"unspecified": "None", "lax": "Lax", "strict": "Strict", "no_restriction": "None"}
                    pw_cookie["sameSite"] = samesite_map.get(c["sameSite"].lower(), "None")
                pw_cookies.append(pw_cookie)
            
            try:
                context.add_cookies(pw_cookies)
                print(f"[BROWSER] Loaded {len(pw_cookies)} cookies for {site}")
            except Exception as e:
                print(f"[BROWSER] Cookie load warning: {e}")
    
    return browser, context, page


def post_to_linkedin(post_text: str) -> bool:
    """
    Post content to LinkedIn using stealth browser.
    Uses stored cookies for login, extension overlay for approval.
    
    Args:
        post_text: The text content to post
        
    Returns:
        True if posted successfully
    """
    from playwright.sync_api import sync_playwright
    
    print(f"[BROWSER] Preparing LinkedIn post ({len(post_text)} chars)...")
    
    # Register task for overlay approval
    task_id = _register_task("linkedin_post", post_text[:200], "Post to LinkedIn")
    
    with sync_playwright() as p:
        browser, context, page = _create_stealth_context(p, load_extension=True, site="linkedin.com")
        
        try:
            # Navigate to LinkedIn
            page.goto("https://www.linkedin.com/feed/", wait_until="networkidle", timeout=30000)
            time.sleep(2)
            
            # Check if logged in
            if "login" in page.url.lower() or "checkpoint" in page.url.lower():
                print("[BROWSER] Not logged in to LinkedIn — need cookies from extension")
                browser.close()
                return False
            
            # Click "Start a post" button
            start_post = page.query_selector(
                'button.share-box-feed-entry__trigger, '
                'button[aria-label*="Start a post"], '
                '.share-box-feed-entry__trigger'
            )
            if start_post:
                start_post.click()
                time.sleep(1.5)
            
            # Type in the post editor
            editor = page.query_selector(
                '.ql-editor, '
                '[contenteditable="true"], '
                '.share-creation-state__text-editor .ql-editor'
            )
            if editor:
                editor.fill(post_text)
                print("[BROWSER] Post text filled")
            
            # Wait for overlay approval
            if task_id:
                print(f"[BROWSER] Waiting for overlay approval (task: {task_id})...")
                result = _wait_for_approval(task_id, timeout=300)
                
                if result == "approve":
                    # Click Post button
                    post_btn = page.query_selector(
                        'button.share-actions__primary-action, '
                        'button[aria-label*="Post"]'
                    )
                    if post_btn:
                        post_btn.click()
                        time.sleep(3)
                        print("[BROWSER] ✅ LinkedIn post submitted!")
                        browser.close()
                        return True
                else:
                    print(f"[BROWSER] Post cancelled: {result}")
            
            browser.close()
            return False
            
        except Exception as e:
            print(f"[BROWSER] LinkedIn error: {e}")
            browser.close()
            return False


def fill_fiverr_gig(gig_data: dict) -> bool:
    """
    Fill a Fiverr gig form using stealth browser.
    Uses stored cookies, extension overlay for approval.
    
    Args:
        gig_data: Dict with title, description, category, price, delivery_time
        
    Returns:
        True if form filled and approved
    """
    from playwright.sync_api import sync_playwright
    
    print(f"[BROWSER] Preparing Fiverr gig: {gig_data.get('title', '')}...")
    
    # Register for overlay approval
    task_id = _register_task("fiverr_gig", gig_data.get("title", "")[:200], "Create Gig")
    
    with sync_playwright() as p:
        browser, context, page = _create_stealth_context(p, load_extension=True, site="fiverr.com")
        
        try:
            page.goto("https://www.fiverr.com/seller_dashboard", wait_until="networkidle", timeout=30000)
            time.sleep(2)
            
            if "join" in page.url.lower() or "login" in page.url.lower():
                print("[BROWSER] Not logged in to Fiverr — need cookies from extension")
                browser.close()
                return False
            
            # Navigate to new gig page
            page.goto("https://www.fiverr.com/users/gigs/create", wait_until="networkidle", timeout=30000)
            time.sleep(2)
            
            # Fill gig title
            title_input = page.query_selector('input[name="title"], #gig-title, textarea[name="title"]')
            if title_input:
                title_input.fill(gig_data.get("title", ""))
            
            # Fill description
            desc_input = page.query_selector('.ql-editor, [contenteditable="true"], textarea[name="description"]')
            if desc_input:
                desc_input.fill(gig_data.get("description", ""))
            
            print("[BROWSER] Fiverr gig form filled")
            
            # Wait for overlay approval
            if task_id:
                print(f"[BROWSER] Waiting for overlay approval (task: {task_id})...")
                result = _wait_for_approval(task_id, timeout=300)
                
                if result == "approve":
                    print("[BROWSER] ✅ Gig form approved — ready for manual review")
                    time.sleep(5)  # Give user time to review
                    browser.close()
                    return True
                else:
                    print(f"[BROWSER] Gig cancelled: {result}")
            
            browser.close()
            return False
            
        except Exception as e:
            print(f"[BROWSER] Fiverr error: {e}")
            browser.close()
            return False


if __name__ == "__main__":
    print("=" * 50)
    print("Browser Tools Test")
    print("=" * 50)
    
    # Test stealth context creation
    from playwright.sync_api import sync_playwright
    
    with sync_playwright() as p:
        browser, context, page = _create_stealth_context(p, site="linkedin.com")
        page.goto("https://bot.sannysoft.com/", timeout=15000)
        time.sleep(2)
        title = page.title()
        print(f"Stealth test page: {title}")
        browser.close()
    
    print("✅ Stealth browser context works")
