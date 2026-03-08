"""
tools/linkedin_poster.py — BilalAgent v3.0 Phase 4
LinkedIn post uploader via Playwright browser automation.

Flow:
  Permission: open LinkedIn →
  Open LinkedIn feed →
  Extension confirms composer_open →
  Permission: type post →
  Type into composer →
  Permission: click Post →
  Click Post button →
  Extension confirms post_confirmed →
  Log to Excel + SQLite
"""

import os
import sys
import time
import uuid
import requests
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

BRIDGE = "http://localhost:8000"
LINKEDIN_FEED = "https://www.linkedin.com/feed/"
EXTENSION_DIR = os.path.join(PROJECT_ROOT, "chrome_extension")


# ─── Chrome profile helpers (module-level) ────────────

def _get_chrome_profile_path() -> str:
    """Return the default Chrome User Data directory on Windows, or None."""
    candidates = [
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome Beta\User Data"),
        os.path.expandvars(r"%LOCALAPPDATA%\Chromium\User Data"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _get_chrome_executable() -> str:
    """Return the Chrome executable path on Windows, or 'chrome' as fallback."""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return "chrome"


class LinkedInPoster:

    def __init__(self):
        from tools.permission_gate import PermissionGate
        self.gate = PermissionGate()
        self.task_id = str(uuid.uuid4())[:8]
        self.page = None
        self.context = None
        self._pw = None

    # ── Chrome profile launch ─────────────────────────

    def _progress(self, stage: str, percent: int):
        """Send progress update to desktop overlay if running."""
        print(f"  [PROGRESS] {percent}% — {stage}")
        try:
            from ui.desktop_overlay import get_overlay_instance
            overlay = get_overlay_instance()
            if overlay is not None:
                overlay.progress_signal.emit(stage, percent)
        except Exception:
            pass

    def _close_chrome_with_permission(self) -> bool:
        """Ask permission before killing Chrome (needed to unlock the profile)."""
        decision = self.gate.request({
            "action": "open_browser",
            "description": (
                "Chrome needs to close briefly so the agent can use your "
                "LinkedIn session. Chrome will reopen with your full profile. "
                "Save any open work, then click Allow."
            ),
            "confidence": 1.0,
            "task_id": f"chrome_close_{self.task_id}",
        })
        if decision not in ("allow", "allow_all"):
            return False
        print("  [CHROME] Closing Chrome to free profile lock...")
        os.system("taskkill /F /IM chrome.exe /T >nul 2>&1")
        time.sleep(2.5)
        return True

    def _launch_with_existing_profile(self) -> bool:
        """
        Launch Chrome using the configured profile (Default / ba8516127@gmail.com).
        LinkedIn session is already active in that profile — no login needed.
        Chrome must be fully closed before this runs (profile lock).
        """
        from playwright.sync_api import sync_playwright
        from tools.chrome_profile import get_profile_path, get_chrome_exe, get_extension_path

        profile_path = get_profile_path()
        chrome_exe   = get_chrome_exe()
        ext_path     = get_extension_path()

        print(f"  [CHROME] Profile : {profile_path}")
        print(f"  [CHROME] Exe     : {chrome_exe}")

        self._pw = sync_playwright().__enter__()

        # launch_persistent_context uses the real profile —
        # all cookies, localStorage, and LinkedIn session are preserved
        self.context = self._pw.chromium.launch_persistent_context(
            user_data_dir   = profile_path,
            executable_path = chrome_exe,
            headless        = False,
            args            = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                f"--disable-extensions-except={ext_path}",
                f"--load-extension={ext_path}",
                "--start-maximized",
            ],
            ignore_default_args = ["--enable-automation"],
            slow_mo             = 40,
        )

        pages     = self.context.pages
        self.page = pages[0] if pages else self.context.new_page()
        print("  [CHROME] ✓ Launched with Default profile (ba8516127@gmail.com)")
        print("  [CHROME] ✓ LinkedIn session should be active")
        return True

    # ── Bridge helpers ────────────────────────────────

    def _bridge_post(self, endpoint: str, data: dict):
        try:
            requests.post(f"{BRIDGE}{endpoint}", json=data, timeout=3)
        except Exception:
            pass

    def _bridge_get(self, endpoint: str) -> dict:
        try:
            r = requests.get(f"{BRIDGE}{endpoint}", timeout=3)
            return r.json()
        except Exception:
            return {}

    def _wait_for_extension_state(self, expected_state: str,
                                   timeout: int = 25) -> bool:
        """Poll bridge until extension reports expected_state."""
        for _ in range(timeout):
            time.sleep(1)
            data = self._bridge_get(f"/extension/page_state/{self.task_id}")
            if data.get("state") == expected_state:
                print(f"  [EXT] Confirmed: {expected_state}")
                return True
        print(f"  [EXT] Timeout waiting for: {expected_state} (continuing anyway)")
        return False

    # ── Main flow ─────────────────────────────────────

    def post(self, content: str, source_task: str = "") -> dict:
        """
        Full LinkedIn post flow with permission gates at every step.
        Returns: {status, reason, posted_at, word_count, extension_confirmed}
        """
        print(f"\n  [LINKEDIN] Post upload starting (task {self.task_id})")
        print(f"  [LINKEDIN] Words: {len(content.split())}")

        # Register task so Chrome extension starts watching
        self._bridge_post("/tasks/register", {
            "task_id": self.task_id,
            "type": "linkedin_post",
            "content_preview": content[:80],
            "status": "active",
        })

        # ── PERMISSION 1: Close Chrome + reopen with profile ─
        # This single gate covers closing Chrome and reopening it.
        if not self._close_chrome_with_permission():
            return {"status": "cancelled",
                    "reason": "Permission denied: Chrome profile launch"}

        # ── OPEN BROWSER WITH REAL PROFILE ────────────
        self._progress("🌐 Opening Chrome with your profile", 52)
        try:
            self._launch_with_existing_profile()
            self.page.goto(LINKEDIN_FEED,
                           wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
        except Exception as e:
            return {"status": "failed", "reason": f"Chrome launch failed: {e}"}

        # ── CHECK LOGIN ───────────────────────────────
        if "login" in self.page.url or "checkpoint" in self.page.url:
            self._progress("🔑 Waiting for LinkedIn login...", 54)
            print("  [LINKEDIN] Not logged in — waiting up to 60s for manual login")
            for _ in range(60):
                time.sleep(1)
                if "feed" in self.page.url:
                    print("  [LINKEDIN] Logged in")
                    break
            else:
                self.page.close()
                return {"status": "failed", "reason": "Not logged in to LinkedIn"}

        self._progress("🔗 LinkedIn feed loaded", 58)
        print("  [LINKEDIN] Feed loaded")

        # ── CLICK START A POST ────────────────────────
        start_selectors = [
            "button.share-box-feed-entry__trigger",
            "div.share-box-feed-entry__closed-share-box button",
            "xpath=//button[contains(normalize-space(),'Start a post')]",
            "xpath=//span[contains(normalize-space(),'Start a post')]/..",
        ]
        clicked = False
        for sel in start_selectors:
            try:
                self.page.locator(sel).first.click(timeout=6000)
                clicked = True
                print("  [LINKEDIN] Clicked 'Start a post'")
                break
            except Exception:
                continue
        if not clicked:
            self.page.close()
            return {"status": "failed", "reason": "Could not find 'Start a post' button"}

        time.sleep(1.5)
        self._wait_for_extension_state("composer_open", timeout=10)
        self._progress("📝 Composer open", 63)

        # ── PERMISSION 2: Type post ───────────────────
        preview = content[:100].replace("\n", " ")
        decision = self.gate.request({
            "action": "type",
            "description": f'Type your post into LinkedIn composer: "{preview}..."',
            "text": content,
            "confidence": 1.0,
            "task_id": f"li_type_{self.task_id}",
        })
        if decision not in ("allow", "allow_all"):
            self.page.close()
            return {"status": "cancelled",
                    "reason": f"Permission denied: type post ({decision})"}

        # ── TYPE THE POST ─────────────────────────────
        editor_selectors = [
            "div.ql-editor",
            "div[data-placeholder='What do you want to talk about?']",
            "div.share-creation-state__text-editor div[contenteditable='true']",
            "div[contenteditable='true']",
        ]
        typed = False
        for sel in editor_selectors:
            try:
                editor = self.page.locator(sel).first
                editor.click(timeout=5000)
                time.sleep(0.4)
                self.page.keyboard.type(content, delay=15)
                typed = True
                print("  [LINKEDIN] Post typed into composer")
                break
            except Exception:
                continue
        if not typed:
            self.page.close()
            return {"status": "failed", "reason": "Could not find post editor"}

        self._progress("✍ Post typed into composer", 72)
        time.sleep(0.8)

        # ── TERMINAL PREVIEW ──────────────────────────
        print(f"\n  {'─'*52}")
        print(f"  POST PREVIEW ({len(content.split())} words):")
        print(f"  {'─'*52}")
        for line in content.split("\n")[:12]:
            print(f"  {line}")
        if content.count("\n") > 12:
            print(f"  ...")
        print(f"  {'─'*52}\n")

        # ── PERMISSION 3: Click Post ──────────────────
        decision = self.gate.request({
            "action": "click",
            "description": "CLICK POST — this will publish LIVE on LinkedIn",
            "confidence": 1.0,
            "task_id": f"li_post_{self.task_id}",
        })
        if decision not in ("allow", "allow_all"):
            self.page.close()
            return {
                "status": "cancelled",
                "reason": "User chose not to publish — post typed but not sent",
            }

        self._progress("📤 Submitting post to LinkedIn", 85)
        # ── CLICK POST BUTTON ─────────────────────────
        post_selectors = [
            "button.share-actions__primary-action",
            "button[data-control-name='share.post']",
            "xpath=//button[normalize-space()='Post']",
            "button.share-creation-state__post-btn",
        ]
        posted = False
        for sel in post_selectors:
            try:
                self.page.locator(sel).first.click(timeout=6000)
                posted = True
                print("  [LINKEDIN] Post button clicked")
                break
            except Exception:
                continue

        if not posted:
            print("  [LINKEDIN] Could not auto-click Post — please click within 20s")
            time.sleep(20)

        time.sleep(3)

        # ── WAIT FOR EXTENSION CONFIRMATION ──────────
        confirmed = self._wait_for_extension_state("post_confirmed", timeout=15)
        posted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._progress("✅ Post published on LinkedIn", 100)

        # ── LOG SUCCESS ───────────────────────────────
        try:
            from memory.excel_logger import log_linkedin_post
            log_linkedin_post(
                content=content,
                platform="linkedin",
                word_count=len(content.split()),
                status="uploaded",
                posted_at=posted_at,
            )
            print("  [LINKEDIN] Logged to linkedin_posts.xlsx")
        except Exception as e:
            print(f"  [LINKEDIN] Excel log failed: {e}")

        try:
            from memory.db import log_action
            log_action("linkedin_posted", {
                "task_id": self.task_id,
                "words": len(content.split()),
                "posted_at": posted_at,
                "extension_confirmed": confirmed,
            }, "completed")
        except Exception:
            pass

        self._bridge_post("/tasks/complete", {
            "task_id": self.task_id,
            "status": "posted",
            "posted_at": posted_at,
        })

        # Leave Chrome open so user can continue browsing after posting.
        # Only close the page we used; keep the context (Chrome window) running.
        try:
            self.page.close()
        except Exception:
            pass
        # Clear progress bar
        self._progress("", 0)

        print(f"  [LINKEDIN] Posted at {posted_at}")
        return {
            "status": "posted",
            "reason": "Success",
            "posted_at": posted_at,
            "word_count": len(content.split()),
            "extension_confirmed": confirmed,
        }


if __name__ == "__main__":
    # Quick smoke test — prints a test post without uploading
    print("LinkedInPoster loaded OK")
    print("Usage: LinkedInPoster().post(content='your post here')")
