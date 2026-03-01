"""
screen_monitor.py — BilalAgent v2.0 Phase 8
Background thread watching the screen at regular intervals.
Provides a cached latest screenshot for fast UI-TARS queries.
"""

import os
import sys
import time
import threading
import logging

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tools.uitars_runner import capture_screen

log = logging.getLogger("screen_monitor")


class ScreenMonitor:
    """
    Background thread that captures screenshots at regular intervals.
    Provides cached screenshots for fast UI-TARS queries without
    needing to capture fresh every time.
    
    Usage:
        monitor = ScreenMonitor()
        monitor.start_background_watch()
        
        # Get latest screenshot instantly
        b64 = monitor.get_current_screen()
        
        monitor.stop()
    """

    def __init__(self, interval: float = 2.0):
        """
        Args:
            interval: Seconds between screenshot captures (default 2.0)
        """
        self.screenshot_interval = interval
        self.last_screenshot_b64 = None
        self.last_screenshot_time = 0.0
        self.running = False
        self._thread = None
        self._lock = threading.Lock()

    def _capture_loop(self):
        """Internal capture loop running in background thread."""
        log.info(f"[ScreenMonitor] Background watch started (interval: {self.screenshot_interval}s)")

        while self.running:
            try:
                b64 = capture_screen()
                with self._lock:
                    self.last_screenshot_b64 = b64
                    self.last_screenshot_time = time.time()
            except Exception as e:
                log.error(f"[ScreenMonitor] Capture error: {e}")

            # Sleep in small increments to allow fast stop
            sleep_remaining = self.screenshot_interval
            while sleep_remaining > 0 and self.running:
                time.sleep(min(0.5, sleep_remaining))
                sleep_remaining -= 0.5

        log.info("[ScreenMonitor] Background watch stopped")

    def start_background_watch(self):
        """Start the background screenshot capture thread."""
        if self.running:
            log.warning("[ScreenMonitor] Already running")
            return

        self.running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True, name="ScreenMonitor")
        self._thread.start()

    def get_current_screen(self, max_age: float = 3.0) -> str:
        """
        Get the latest screenshot, capturing fresh if cached one is too old.
        
        Args:
            max_age: Maximum age in seconds before capturing a fresh screenshot
            
        Returns:
            Base64-encoded PNG string
        """
        with self._lock:
            age = time.time() - self.last_screenshot_time

            if self.last_screenshot_b64 is not None and age <= max_age:
                return self.last_screenshot_b64

        # Cache too old or empty — capture fresh
        b64 = capture_screen()
        with self._lock:
            self.last_screenshot_b64 = b64
            self.last_screenshot_time = time.time()
        return b64

    def stop(self):
        """Stop the background screenshot capture."""
        self.running = False
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        log.info("[ScreenMonitor] Stopped")

    @property
    def is_active(self) -> bool:
        """Check if the monitor is actively capturing."""
        return self.running and self._thread is not None and self._thread.is_alive()


# ─── Module-Level Convenience ────────────────────

_monitor_instance = None


def get_monitor() -> ScreenMonitor:
    """Get or create the singleton ScreenMonitor instance."""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = ScreenMonitor()
    return _monitor_instance


if __name__ == "__main__":
    print("=" * 50)
    print("Screen Monitor Test")
    print("=" * 50)

    monitor = ScreenMonitor(interval=2.0)
    monitor.start_background_watch()

    print("Monitoring for 6 seconds...")
    time.sleep(6)

    screen = monitor.get_current_screen()
    print(f"Latest screenshot: {len(screen)} base64 chars")
    print(f"Age: {time.time() - monitor.last_screenshot_time:.1f}s")

    monitor.stop()
    print("Stopped.")
