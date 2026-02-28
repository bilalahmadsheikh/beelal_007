"""
startup.py — BilalAgent v2.0 Main Entry Point
Launches all services: bridge, scheduler, hotkey, tray icon.
Usage: python startup.py (or pythonw startup.py for windowless)
"""

import os
import sys
import time
import signal
import threading
import logging

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

import yaml

# ─── Logging ─────────────────────────────────────

LOG_PATH = os.path.join(PROJECT_ROOT, "memory", "startup.log")
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger("startup")


# ─── Settings ────────────────────────────────────

SETTINGS_PATH = os.path.join(PROJECT_ROOT, "config", "settings.yaml")


def load_settings() -> dict:
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


# ─── Service Launchers ───────────────────────────

def start_bridge(port: int = 8000):
    """Start the FastAPI bridge server in a background thread."""
    def _run():
        try:
            import uvicorn
            log.info(f"Starting bridge on port {port}...")
            uvicorn.run("bridge.server:app", host="127.0.0.1", port=port,
                        log_level="warning", access_log=False)
        except Exception as e:
            log.error(f"Bridge failed: {e}")

    t = threading.Thread(target=_run, daemon=True, name="bridge")
    t.start()
    log.info(f"Bridge thread started (port {port})")
    return t


def start_scheduler():
    """Start the background scheduler."""
    def _run():
        try:
            from scheduler import main as scheduler_main
            scheduler_main()
        except Exception as e:
            log.error(f"Scheduler failed: {e}")

    t = threading.Thread(target=_run, daemon=True, name="scheduler")
    t.start()
    log.info("Scheduler thread started")
    return t


def start_hotkey_listener(hotkey: str = "ctrl+shift+b"):
    """Start the global hotkey listener."""
    def _run():
        try:
            import keyboard  # pip install keyboard
        except ImportError:
            log.warning("keyboard module not installed (pip install keyboard), hotkey disabled")
            return

        def on_hotkey():
            log.info(f"Hotkey {hotkey} pressed — launching dashboard")
            try:
                from ui.dashboard import launch_dashboard
                threading.Thread(target=launch_dashboard, daemon=True).start()
            except Exception as e:
                log.error(f"Dashboard launch failed: {e}")

        keyboard.add_hotkey(hotkey, on_hotkey)
        log.info(f"Hotkey listener active: {hotkey}")
        keyboard.wait()  # Block forever

    t = threading.Thread(target=_run, daemon=True, name="hotkey")
    t.start()
    return t


def start_github_monitor(check_hours: int = 24):
    """Start periodic GitHub activity monitoring."""
    def _run():
        import time as _time
        while True:
            try:
                from connectors.github_monitor import GitHubActivityMonitor
                monitor = GitHubActivityMonitor()
                activities = monitor.check_new_activity()
                if activities:
                    log.info(f"GitHub: {len(activities)} new activities detected")
            except Exception as e:
                log.error(f"GitHub monitor error: {e}")
            _time.sleep(check_hours * 3600)

    t = threading.Thread(target=_run, daemon=True, name="github_monitor")
    t.start()
    log.info(f"GitHub monitor started (every {check_hours}h)")
    return t


# ─── Main ────────────────────────────────────────

def main():
    log.info("=" * 50)
    log.info("BilalAgent v2.0 Starting Up")
    log.info(f"PID: {os.getpid()}")
    log.info(f"Project: {PROJECT_ROOT}")
    log.info("=" * 50)

    settings = load_settings()
    mode = settings.get("intelligence_mode", "local")
    port = settings.get("bridge_port", 8000)
    hotkey = settings.get("hotkey", "ctrl+shift+b")
    github_hours = settings.get("github_check_hours", 24)
    enable_hotkey = settings.get("enable_hotkey", True)

    log.info(f"Mode: {mode}")

    # Initialize database
    try:
        from memory.db import init_db
        init_db()
    except Exception as e:
        log.error(f"DB init failed: {e}")

    # Start services
    threads = []

    # 1. Bridge server
    threads.append(start_bridge(port))
    time.sleep(1)  # Give bridge time to start

    # 2. Background scheduler
    threads.append(start_scheduler())

    # 3. GitHub monitor
    threads.append(start_github_monitor(github_hours))

    # 4. Hotkey listener (optional)
    if enable_hotkey:
        try:
            threads.append(start_hotkey_listener(hotkey))
        except Exception:
            log.warning("Hotkey listener failed to start")

    log.info(f"All services started ({len(threads)} threads)")

    # 5. Tray icon (runs on main thread — blocks)
    try:
        from ui.tray_app import launch_tray
        log.info("Launching system tray...")
        launch_tray()  # This blocks until quit
    except ImportError:
        log.warning("pystray not available, running without tray icon")
        log.info("Press Ctrl+C to stop")
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            pass
    except Exception as e:
        log.error(f"Tray failed: {e}")

    log.info("BilalAgent v2.0 shutdown complete")


if __name__ == "__main__":
    main()
