"""
tools/linkedin_extension_poster.py — BilalAgent v3.1

Posts to LinkedIn using the Chrome extension already running in the user's
existing Chrome tab — no new Chrome window, no profile locks, no Playwright.

Flow:
  1. Send open_composer action → extension clicks "Start a post" in YOUR tab
  2. Send type_content action → extension types the post, shows Upload/Edit/Cancel bar
  3. User clicks Upload → extension clicks Post → reports 'posted' back
  4. Log success

Requires:
  - Bridge running:   python agent.py --bridge  (or uvicorn bridge.server:app)
  - LinkedIn open in Chrome with BilalAgent extension loaded
"""

import time
import uuid
import requests
from datetime import datetime

BRIDGE = "http://localhost:8000"


class LinkedInExtensionPoster:

    def __init__(self):
        from tools.permission_gate import PermissionGate
        self.gate = PermissionGate()

    # ── Bridge helpers ────────────────────────────────

    def _bridge_post(self, endpoint: str, data: dict) -> dict:
        try:
            r = requests.post(f"{BRIDGE}{endpoint}", json=data, timeout=5)
            return r.json()
        except Exception as e:
            print(f"  [EXT POSTER] Bridge POST error {endpoint}: {e}")
            return {}

    def _bridge_get(self, endpoint: str) -> dict:
        try:
            r = requests.get(f"{BRIDGE}{endpoint}", timeout=5)
            return r.json()
        except Exception as e:
            print(f"  [EXT POSTER] Bridge GET error {endpoint}: {e}")
            return {}

    def _overlay_log(self, text: str, msg_type: str = "system"):
        print(f"  [EXT POSTER] {text}")
        try:
            from ui.desktop_overlay import get_overlay_instance
            overlay = get_overlay_instance()
            if overlay is not None:
                overlay.log_signal.emit(text, msg_type)
        except Exception:
            pass

    # ── Action helpers ────────────────────────────────

    def _send_action(self, action_type: str, content: str = None) -> str:
        """Queue a LinkedIn action to the bridge. Returns action_id."""
        action_id = str(uuid.uuid4())[:8]
        payload = {"action_id": action_id, "type": action_type}
        if content:
            payload["content"] = content
        self._bridge_post("/linkedin/action", payload)
        print(f"  [EXT POSTER] Queued: {action_type} ({action_id})")
        return action_id

    def _wait_for_action(self, action_id: str, timeout: int = 30) -> dict:
        """Poll bridge until extension reports action done or failed."""
        start = time.time()
        while time.time() - start < timeout:
            time.sleep(0.5)
            result = self._bridge_get(f"/linkedin/action/result/{action_id}")
            status = result.get("status", "not_found")
            if status in ("done", "failed"):
                return result
        return {"status": "timeout", "message": "Extension did not respond in time"}

    # ── Main entry point ──────────────────────────────

    def post(self, content: str, source_task: str = "") -> dict:
        """
        Post to LinkedIn via the browser extension.
        Flow: Push content to agent → popup shows preview → user clicks Post →
              extension opens LinkedIn → types content → shows Upload overlay.
        Returns: {status, reason, posted_at?, word_count?}
        """
        print(f"\n  [EXT POSTER] Starting LinkedIn post via extension")
        print(f"  [EXT POSTER] Words: {len(content.split())}")

        # Verify bridge is alive
        health = self._bridge_get("/status")
        if not health.get("status") == "ok":
            return {
                "status": "failed",
                "reason": "Bridge is not running. Start it with: python agent.py --bridge",
            }

        # ── STEP 0: Push content to agent/content/ready ──
        # This notifies the Chrome Extension popup via SSE.
        # The popup shows a content preview card with Post/Edit/Reject buttons.
        self._overlay_log("📝 Pushing generated content to extension popup…")
        self._notify_agent("Generated LinkedIn post — sending to browser for review…")

        push_result = self._bridge_post("/agent/content/ready", {
            "content": content,
            "content_type": "linkedin_post",
            "task_id": source_task or str(uuid.uuid4())[:8],
            "metadata": {"word_count": len(content.split())},
        })
        agent_task_id = push_result.get("task_id", "")

        if agent_task_id:
            self._overlay_log(f"✓ Content pushed to popup (task: {agent_task_id})")
            self._overlay_log("Waiting for user decision in extension popup…")

            # Wait for user decision (approved/rejected/editing) — up to 5 minutes
            decision = self._wait_for_content_decision(agent_task_id, timeout=300)

            if decision == "rejected":
                self._overlay_log("✕ User rejected the post from popup.")
                self._notify_agent("Post rejected by user.")
                return {"status": "cancelled", "reason": "User rejected from extension popup"}

            if decision == "editing":
                self._overlay_log("✏️ User chose to edit — posting handled by extension.")
                return {"status": "editing", "reason": "User editing via extension popup"}

            if decision == "approved":
                self._overlay_log("✓ User approved — extension is posting to LinkedIn…")
                self._notify_agent("✅ User approved! Posting to LinkedIn now…")
                # The popup already triggered AGENT_POST_LINKEDIN in background.js
                # Wait for the LinkedIn action results
                return self._wait_for_linkedin_post_result(agent_task_id)

        # Fallback: if agent content push failed, go direct extension route
        self._overlay_log("Direct extension posting (agent push unavailable)…")
        return self._post_via_extension(content, source_task)

    def _notify_agent(self, message: str):
        """Send a message to the extension popup via bridge."""
        try:
            self._bridge_post("/agent/message", {"message": message})
        except Exception:
            pass

    def _wait_for_content_decision(self, task_id: str, timeout: int = 300) -> str:
        """Poll bridge until user makes a decision on content."""
        start = time.time()
        while time.time() - start < timeout:
            time.sleep(1)
            result = self._bridge_get(f"/agent/content/status/{task_id}")
            status = result.get("status", "pending_review")
            if status in ("approved", "rejected", "editing"):
                return status
        return "timeout"

    def _wait_for_linkedin_post_result(self, task_id: str) -> dict:
        """Wait for the extension to complete the LinkedIn post."""
        start = time.time()
        while time.time() - start < 120:
            time.sleep(2)
            result = self._bridge_get(f"/agent/content/status/{task_id}")
            status = result.get("status", "")
            if status == "posted":
                posted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._log_success(result.get("content", ""), posted_at)
                return {
                    "status": "posted",
                    "reason": "Posted via extension popup flow",
                    "posted_at": posted_at,
                    "word_count": result.get("word_count", 0),
                }
            elif status in ("failed", "rejected"):
                return {"status": status, "reason": result.get("message", "Post failed")}
        return {"status": "timeout", "reason": "LinkedIn posting timed out"}

    def _post_via_extension(self, content: str, source_task: str = "") -> dict:
        """Original direct extension posting flow (fallback)."""
        # ── STEP 1: open composer
        self._overlay_log("Asking extension to open LinkedIn composer…")
        action_id = self._send_action("open_composer")

        result = self._wait_for_action(action_id, timeout=25)
        if result["status"] == "failed":
            self._overlay_log(f"⚠ Extension failed ({result.get('message','')}) — switching to Playwright fallback...")
            return self._playwright_fallback(content)
        if result["status"] == "timeout":
            self._overlay_log("⚠ Extension timed out — switching to Playwright fallback...")
            return self._playwright_fallback(content)

        self._overlay_log("✓ Composer opened — typing post…")
        time.sleep(0.8)

        # ── STEP 2: type content + show Upload/Edit/Cancel
        self._overlay_log(f"Typing {len(content.split())} words into composer…")
        action_id_type = self._send_action("type_content", content)

        self._overlay_log("Post typed — check LinkedIn tab: click Upload / Edit / Cancel")
        result = self._wait_for_action(action_id_type, timeout=300)

        if result["status"] == "timeout":
            self._overlay_log("⚠ type_content timed out — switching to Playwright fallback...")
            return self._playwright_fallback(content)

        message = result.get("result", result.get("message", ""))

        if message == "posted":
            posted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._overlay_log(f"✅ Posted to LinkedIn at {posted_at}", "agent")
            self._log_success(content, posted_at)
            return {
                "status": "posted",
                "reason": "Success",
                "posted_at": posted_at,
                "word_count": len(content.split()),
            }
        elif message == "user_editing":
            self._overlay_log("User is editing the post — post manually when ready")
            return {"status": "editing", "reason": "User editing the post manually in LinkedIn"}
        elif message == "cancelled":
            self._overlay_log("Post cancelled by user")
            return {"status": "cancelled", "reason": "User cancelled the post"}
        else:
            return {"status": "done", "reason": message or "Extension reported done"}

    # ── Playwright fallback ───────────────────────────

    def _playwright_fallback(self, content: str) -> dict:
        """Fallback 1: Playwright + LinkedIn cookies in fresh Chromium."""
        self._overlay_log("Fallback 1: Playwright with LinkedIn cookies...")
        try:
            from tools.linkedin_playwright_poster import LinkedInPlaywrightPoster
            pw = LinkedInPlaywrightPoster()
            pw.set_log(lambda text, t="system": self._overlay_log(text, t))
            result = pw.post(content)
            if result.get("status") not in ("failed",):
                return result
            self._overlay_log(f"Playwright failed: {result.get('reason','')} — trying pyautogui...")
        except Exception as e:
            self._overlay_log(f"Playwright error: {e} — trying pyautogui...")
        return self._pyautogui_fallback(content)

    def _pyautogui_fallback(self, content: str) -> dict:
        """Fallback 2: pyautogui — navigate existing Chrome and paste via clipboard."""
        self._overlay_log("Fallback 2: pyautogui clipboard poster (using your Chrome)...")
        try:
            from tools.linkedin_pyautogui_poster import LinkedInPyautoguiPosterV2
            pg = LinkedInPyautoguiPosterV2()
            pg.set_log(lambda text, t="system": self._overlay_log(text, t))
            return pg.post(content)
        except Exception as e:
            self._overlay_log(f"pyautogui fallback failed: {e}")
            return {"status": "failed", "reason": f"All posting methods failed: {e}"}

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
            print("  [EXT POSTER] ✓ Logged to linkedin_posts.xlsx")
        except Exception as e:
            print(f"  [EXT POSTER] Excel log failed: {e}")

        try:
            from memory.db import log_action
            log_action("linkedin_posted", {
                "words": len(content.split()),
                "posted_at": posted_at,
                "method": "extension",
            }, "completed")
        except Exception:
            pass


if __name__ == "__main__":
    print("LinkedInExtensionPoster — smoke test")
    print("Bridge check...")
    try:
        r = requests.get(f"{BRIDGE}/status", timeout=3)
        print(f"Bridge: {r.json()}")
    except Exception as e:
        print(f"Bridge offline: {e}")
