"""
scheduler.py — BilalAgent v2.0 Background Scheduler
Runs post generation on schedule and checks for approved posts.
Usage: pythonw scheduler.py (windowless) or python scheduler.py
"""

import os
import sys
import time
import signal
import logging
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

try:
    import schedule
except ImportError:
    print("Installing schedule library...")
    os.system(f"{sys.executable} -m pip install schedule")
    import schedule

import yaml

# ─── Logging ─────────────────────────────────────
LOG_PATH = os.path.join(PROJECT_ROOT, "memory", "scheduler.log")
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger("scheduler")


# ─── Config ──────────────────────────────────────

def _load_settings() -> dict:
    """Load scheduler settings from settings.yaml."""
    path = os.path.join(PROJECT_ROOT, "config", "settings.yaml")
    try:
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        return config.get("scheduler", {})
    except Exception:
        return {}


# ─── Scheduled Tasks ────────────────────────────

def task_generate_weekly_posts():
    """Generate 3 weekly LinkedIn posts."""
    log.info("Starting weekly post generation...")
    
    settings = _load_settings()
    mode = settings.get("mode", "local")
    
    try:
        from tools.post_scheduler import generate_weekly_posts
        posts = generate_weekly_posts(mode=mode)
        log.info(f"Generated {len(posts)} posts (mode: {mode})")
        
        for p in posts:
            log.info(f"  [{p['type']}] {p['project']} — {p['words']} words → {p['path']}")
    except Exception as e:
        log.error(f"Post generation failed: {e}")


def task_check_approved_posts():
    """Check for approved posts and post them to LinkedIn."""
    try:
        import sqlite3
        db_path = os.path.join(PROJECT_ROOT, "memory", "agent_memory.db")
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        # Find approved posts that haven't been posted yet
        approved = conn.execute("""
            SELECT * FROM content_log 
            WHERE status = 'approved' AND platform = 'linkedin'
            ORDER BY created_at ASC LIMIT 1
        """).fetchone()
        
        conn.close()
        
        if approved:
            content = approved["content"]
            log.info(f"Found approved post ({len(content)} chars), posting to LinkedIn...")
            
            try:
                from tools.browser_tools import post_to_linkedin
                result = post_to_linkedin(content)
                
                # Update status
                conn = sqlite3.connect(db_path)
                conn.execute(
                    "UPDATE content_log SET status = 'posted' WHERE id = ?",
                    (approved["id"],)
                )
                conn.commit()
                conn.close()
                
                log.info(f"Posted to LinkedIn: {content[:80]}...")
            except Exception as e:
                log.error(f"LinkedIn posting failed: {e}")
        
    except Exception as e:
        log.error(f"Approved post check failed: {e}")


# ─── Main Loop ───────────────────────────────────

running = True

def signal_handler(sig, frame):
    global running
    log.info("Shutdown signal received, stopping scheduler...")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def main():
    log.info("=" * 50)
    log.info("BilalAgent Scheduler Starting")
    log.info(f"PID: {os.getpid()}")
    log.info("=" * 50)
    
    settings = _load_settings()
    post_day = settings.get("post_day", "monday")
    post_time = settings.get("post_time", "09:00")
    check_interval = settings.get("check_interval_hours", 1)
    
    # Schedule weekly post generation
    getattr(schedule.every(), post_day).at(post_time).do(task_generate_weekly_posts)
    log.info(f"Scheduled: Weekly posts on {post_day} at {post_time}")
    
    # Schedule approved post checking
    schedule.every(check_interval).hours.do(task_check_approved_posts)
    log.info(f"Scheduled: Check approved posts every {check_interval}h")
    
    log.info("Scheduler running. Press Ctrl+C to stop.")
    
    while running:
        schedule.run_pending()
        time.sleep(60)  # Check every minute
    
    log.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
