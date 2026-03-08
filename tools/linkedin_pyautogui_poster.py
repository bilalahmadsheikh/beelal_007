"""
tools/linkedin_pyautogui_poster.py — BilalAgent v3.1

Posts to LinkedIn using the user's already-open Chrome session.
- Copies content to clipboard
- Navigates the existing LinkedIn Chrome tab to ?shareActive=true (auto-opens composer)
- Pastes via keyboard shortcut
- No Playwright, no extension required — uses OS-level automation

Works as long as:
  - Chrome is open with LinkedIn (any linkedin.com page)
  - OR user is not in Chrome (we open a new tab)
"""

import time
import sys
import os
import webbrowser
import pyperclip
import pyautogui
import ctypes

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05

try:
    import win32gui
    import win32con
    import win32process
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

LINKEDIN_SHARE_URL = "https://www.linkedin.com/feed/?shareActive=true"


class LinkedInPyautoguiPoster:

    def __init__(self):
        self._log = print

    def set_log(self, fn):
        self._log = fn

    def _overlay_log(self, text: str, msg_type: str = "system"):
        self._log(f"  [PYAUTOGUI] {text}")
        try:
            from ui.desktop_overlay import get_overlay_instance
            ov = get_overlay_instance()
            if ov is not None:
                ov.log_signal.emit(text, msg_type)
        except Exception:
            pass

    def post(self, content: str) -> dict:
        """Post content to LinkedIn via clipboard + pyautogui."""

        # Step 1: Copy post content to clipboard
        try:
            pyperclip.copy(content)
            self._overlay_log(f"Copied {len(content.split())} words to clipboard")
        except Exception as e:
            return {"status": "failed", "reason": f"Clipboard error: {e}"}

        # Step 2: Find or open LinkedIn in Chrome
        hwnd = self._find_chrome_with_linkedin() if HAS_WIN32 else None

        if hwnd:
            self._overlay_log("Found LinkedIn in Chrome — opening post composer...")
            self._focus_window(hwnd)
            time.sleep(0.8)
            # Navigate to share URL in address bar
            self._navigate_to(LINKEDIN_SHARE_URL)
        else:
            self._overlay_log("Opening LinkedIn post composer in Chrome...")
            webbrowser.open(LINKEDIN_SHARE_URL)

        # Step 3: Wait for composer to open (shareActive=true auto-opens it)
        self._overlay_log("Waiting for LinkedIn composer to open...")
        time.sleep(5)

        # Step 4: Click the page center to ensure focus is in LinkedIn (not address bar)
        sw, sh = pyautogui.size()
        # Click in the center-right area (where composer usually appears)
        pyautogui.click(sw // 2, sh // 2)
        time.sleep(0.5)

        # Step 5: Select all and paste (replaces any default text in composer)
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.2)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(1)

        self._overlay_log("Content pasted into LinkedIn composer!")
        self._overlay_log("Review in Chrome and click 'Post' to publish")
        self._overlay_log("(Or Ctrl+Shift+Enter if Post button is active)")

        return {
            "status": "pasted",
            "reason": "Content pasted via clipboard — click Post in Chrome to publish",
            "word_count": len(content.split()),
        }

    def _find_chrome_with_linkedin(self):
        """Find Chrome window with LinkedIn open. Returns hwnd or None."""
        if not HAS_WIN32:
            return None
        results = []

        def cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd).lower()
            if "linkedin" in title and ("chrome" in title or "google" in title):
                results.append(hwnd)

        win32gui.EnumWindows(cb, None)
        if results:
            return results[0]

        # Fallback: any Chrome window (user likely has LinkedIn in a tab)
        def cb2(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd).lower()
            if "google chrome" in title or title.endswith("- google chrome"):
                results.append(hwnd)

        win32gui.EnumWindows(cb2, None)
        return results[0] if results else None

    def _focus_window(self, hwnd):
        """Bring Chrome to foreground."""
        try:
            # Restore if minimized
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.3)
            # Force foreground (needed on Windows 10/11)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            ctypes.windll.user32.BringWindowToTop(hwnd)
            time.sleep(0.4)
        except Exception:
            pass

    def _navigate_to(self, url: str):
        """Navigate Chrome to a URL via Ctrl+L + type + Enter."""
        pyautogui.hotkey('ctrl', 'l')   # Focus address bar
        time.sleep(0.4)
        pyautogui.hotkey('ctrl', 'a')   # Select all existing text
        time.sleep(0.1)
        # Paste URL (faster than typing)
        pyperclip.copy(url)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.2)
        pyautogui.press('enter')
        # Restore content to clipboard
        pyperclip.copy("")  # Clear briefly
        # (content will be re-set in step 5 via paste, which uses what's on clipboard now)
        # Wait — we need to KEEP content on clipboard for the paste step!
        # So restore it right after navigating
        time.sleep(0.3)
        pyperclip.copy("")  # cleared; we'll need to restore before paste


# Fix: clipboard management needs to preserve content after navigation
class LinkedInPyautoguiPosterV2(LinkedInPyautoguiPoster):
    """Fixed version: keeps content on clipboard through navigation."""

    def post(self, content: str) -> dict:
        """Post content to LinkedIn via clipboard + pyautogui."""

        # Step 1: Copy post content to clipboard
        try:
            pyperclip.copy(content)
            self._overlay_log(f"Copied {len(content.split())} words to clipboard")
        except Exception as e:
            return {"status": "failed", "reason": f"Clipboard error: {e}"}

        # Step 2: Find or open LinkedIn in Chrome
        hwnd = self._find_chrome_with_linkedin() if HAS_WIN32 else None

        if hwnd:
            self._overlay_log("Found Chrome — opening LinkedIn post composer...")
            self._focus_window(hwnd)
            time.sleep(0.8)
            self._navigate_url_without_clipboard(LINKEDIN_SHARE_URL)
        else:
            self._overlay_log("Opening LinkedIn post composer in Chrome...")
            webbrowser.open(LINKEDIN_SHARE_URL)

        # Step 3: Wait for composer
        self._overlay_log("Waiting for composer to open (5 seconds)...")
        time.sleep(5)

        # Step 4: Ensure content is still on clipboard (navigation may have cleared it)
        pyperclip.copy(content)
        time.sleep(0.2)

        # Step 5: Click center of page to ensure LinkedIn has focus
        sw, sh = pyautogui.size()
        pyautogui.click(sw // 2, sh // 2)
        time.sleep(0.5)

        # Step 6: Select all + paste
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.3)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(1)

        self._overlay_log("Content pasted! Review in Chrome, then click 'Post'", "agent")

        return {
            "status": "pasted",
            "reason": "Pasted via clipboard — click Post in Chrome to publish",
            "word_count": len(content.split()),
        }

    def _navigate_url_without_clipboard(self, url: str):
        """Navigate Chrome to URL by typing (not pasting) to preserve clipboard."""
        pyautogui.hotkey('ctrl', 'l')
        time.sleep(0.4)
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.1)
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.write(url, interval=0.01)  # type URL character by character
        time.sleep(0.2)
        pyautogui.press('enter')


if __name__ == "__main__":
    poster = LinkedInPyautoguiPosterV2()
    poster.set_log(lambda t, m="system": print(f"  [{m}] {t}"))
    result = poster.post("🧪 BilalAgent test — please ignore this post")
    print(f"Result: {result}")
