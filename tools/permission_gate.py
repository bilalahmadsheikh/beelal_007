"""
permission_gate.py — BilalAgent v2.0 Phase 9
Permission gate for UI-TARS actions. Every screen action must be approved
through the Chrome Extension overlay before execution.

Supports three modes:
- Manual: Each action requires explicit approval
- Allow All: Auto-approve for N minutes (set via dashboard or extension)
- Skip: Certain action types (scroll, extract) can be auto-skipped
"""

import os
import sys
import time
import uuid
import logging

import requests

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

log = logging.getLogger("permission_gate")


class PermissionGate:
    """
    Gate between UI-TARS action decisions and execution.
    Routes approval requests through the bridge → Chrome Extension overlay.
    
    Usage:
        gate = PermissionGate()
        decision = gate.request(action_dict)  # "allow" | "skip" | "stop" | "edit"
        if decision == "allow":
            execute_action(action_dict)
    """

    def __init__(self, bridge_url: str = None):
        """
        Args:
            bridge_url: Bridge server URL. Reads from settings.yaml if not provided.
        """
        if bridge_url:
            self.bridge_url = bridge_url.rstrip("/")
        else:
            self.bridge_url = self._get_bridge_url()

        self.allow_all = False
        self.allow_all_expires = 0.0
        self.skip_types = []  # e.g. ["scroll", "extract"]

    def _get_bridge_url(self) -> str:
        """Read bridge port from settings.yaml."""
        try:
            import yaml
            settings_path = os.path.join(PROJECT_ROOT, "config", "settings.yaml")
            with open(settings_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            port = config.get("bridge_port", 8000)
            return f"http://localhost:{port}"
        except Exception:
            return "http://localhost:8000"

    def request(self, action: dict, task_id: str = None) -> str:
        """
        Request permission for an action.

        Emits to BOTH:
          1. Desktop overlay (via singleton — immediate, no polling delay)
          2. Bridge (so Chrome extension overlay also picks it up)

        Polls both sources every 0.4s until a decision is received.

        Returns:
            "allow" | "skip" | "stop" | "edit"
        """
        if task_id is None:
            task_id = f"perm-{uuid.uuid4().hex[:8]}"

        action_type = action.get("action", "unknown")
        description = action.get("description", "No description")
        confidence  = action.get("confidence", 0)

        # Stamp the action with the task_id so popup can report back
        action["task_id"] = task_id

        # 1. Check Allow All mode
        if self.is_allow_all_active():
            self._log_auto_allowed(action)
            return "allow"

        # 2. Check skip types
        if action_type in self.skip_types:
            log.info(f"[PermissionGate] '{action_type}' in skip list — auto-skip")
            return "skip"

        # 3. Emit to desktop overlay immediately (no HTTP delay)
        self._emit_to_overlay(action)

        # 4. Also post to bridge (Chrome extension overlay)
        try:
            payload = {
                "task_id":     task_id,
                "action_type": action_type,
                "description": description,
                "x":           action.get("x"),
                "y":           action.get("y"),
                "text":        action.get("text"),
                "confidence":  confidence,
            }
            requests.post(
                f"{self.bridge_url}/permission/request",
                json=payload, timeout=5,
            )
        except requests.ConnectionError:
            log.warning("[PermissionGate] Bridge not reachable — overlay-only mode")
        except Exception as e:
            log.warning(f"[PermissionGate] Bridge post failed: {e}")

        # 5. Poll for decision — check overlay cache first (fast), then bridge
        poll_url   = f"{self.bridge_url}/permission/result/{task_id}"
        timeout    = 300  # 5 minutes
        interval   = 0.4
        start_time = time.time()

        print(f"  [GATE] Waiting: {action_type} — {description[:60]}")

        while time.time() - start_time < timeout:
            # Fast path: overlay already recorded a decision
            decision = self._check_overlay_decision(task_id)
            if decision:
                log.info(f"[PermissionGate] Overlay decision: {decision}")
                if decision == "allow_all":
                    self.set_allow_all(30)
                    return "allow"
                return decision

            # Slow path: poll bridge (Chrome extension may have answered)
            try:
                resp = requests.get(poll_url, timeout=2)
                if resp.status_code == 200:
                    data = resp.json()
                    bridge_decision = data.get("decision", "pending")
                    if bridge_decision not in ("pending", "not_found"):
                        log.info(f"[PermissionGate] Bridge decision: {bridge_decision}")
                        if bridge_decision == "allow_all":
                            self.set_allow_all(30)
                            return "allow"
                        return bridge_decision
            except Exception:
                pass

            time.sleep(interval)

        log.warning(f"[PermissionGate] Timeout after {timeout}s — stopping task")
        return "stop"

    # ─── Overlay helpers ──────────────────────────────

    def _emit_to_overlay(self, action: dict):
        """Emit permission request to desktop overlay singleton (thread-safe)."""
        try:
            from ui.desktop_overlay import get_overlay_instance
            overlay = get_overlay_instance()
            if overlay is not None:
                overlay.show_permission_request(action)
        except Exception:
            pass

    def _check_overlay_decision(self, task_id: str):
        """Check if overlay has recorded a decision for task_id. Returns None if pending."""
        try:
            from ui.desktop_overlay import get_overlay_instance
            overlay = get_overlay_instance()
            if overlay is not None:
                return overlay.get_permission_decision(task_id)
        except Exception:
            pass
        return None

    def _log_auto_allowed(self, action: dict):
        remaining = self.time_remaining()
        desc = action.get("description", "")[:60]
        log.info(f"[PermissionGate] Auto-allowed ({remaining}): {desc}")
        print(f"  [GATE] Auto-allowed ({remaining}): {desc}")

    def set_allow_all(self, minutes: int = 30):
        """Enable auto-approve for N minutes."""
        self.allow_all = True
        self.allow_all_expires = time.time() + (minutes * 60)
        log.info(f"[PermissionGate] Allow All active for {minutes} minutes")

    def revoke_allow_all(self):
        """Disable auto-approve immediately."""
        self.allow_all = False
        self.allow_all_expires = 0.0
        log.info("[PermissionGate] Allow All revoked")

    def is_allow_all_active(self) -> bool:
        """Check if Allow All mode is currently active (and not expired)."""
        if self.allow_all and time.time() < self.allow_all_expires:
            return True
        if self.allow_all:
            # Expired
            self.revoke_allow_all()
        return False

    def time_remaining(self) -> str:
        """Get human-readable time remaining for Allow All mode."""
        if not self.is_allow_all_active():
            return "inactive"
        remaining = int(self.allow_all_expires - time.time())
        return f"{remaining // 60}m {remaining % 60}s"

    def add_skip_type(self, action_type: str):
        """Add an action type to auto-skip list."""
        if action_type not in self.skip_types:
            self.skip_types.append(action_type)
            log.info(f"[PermissionGate] Added '{action_type}' to skip list")

    def remove_skip_type(self, action_type: str):
        """Remove an action type from auto-skip list."""
        if action_type in self.skip_types:
            self.skip_types.remove(action_type)
            log.info(f"[PermissionGate] Removed '{action_type}' from skip list")


# ─── Module-Level Convenience ────────────────────

_gate_instance = None


def get_gate() -> PermissionGate:
    """Get or create the singleton PermissionGate instance."""
    global _gate_instance
    if _gate_instance is None:
        _gate_instance = PermissionGate()
    return _gate_instance


if __name__ == "__main__":
    print("=" * 50)
    print("Permission Gate Test")
    print("=" * 50)

    gate = PermissionGate()

    # Test Allow All logic
    gate.set_allow_all(1)
    print(f"Allow All active: {gate.is_allow_all_active()}")
    print(f"Time remaining: {gate.time_remaining()}")

    gate.revoke_allow_all()
    print(f"After revoke: {gate.is_allow_all_active()}")
    print(f"Time remaining: {gate.time_remaining()}")
