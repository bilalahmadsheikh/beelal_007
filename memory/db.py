"""
db.py — BilalAgent v2.0 SQLite Memory Layer
Persistent storage for profiles, action logs, and agent memory.
"""

import sqlite3
import json
import os
from datetime import datetime


DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "agent_memory.db"
)


def _get_conn() -> sqlite3.Connection:
    """Get a connection to the SQLite database."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database with required tables."""
    conn = _get_conn()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS action_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_type TEXT NOT NULL,
            details TEXT,
            status TEXT DEFAULT 'completed',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_store (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT,
            category TEXT DEFAULT 'general',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS content_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_type TEXT NOT NULL,
            content TEXT NOT NULL,
            status TEXT DEFAULT 'generated',
            platform TEXT DEFAULT '',
            model_used TEXT DEFAULT '',
            word_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    
    conn.commit()
    conn.close()
    print("[DB] Database initialized at", DB_PATH)


def save_profile(data: dict):
    """
    Save or update the user profile.
    
    Args:
        data: Profile data dict (will be JSON serialized)
    """
    conn = _get_conn()
    cursor = conn.cursor()
    
    # Check if profile exists
    cursor.execute("SELECT id FROM profiles LIMIT 1")
    existing = cursor.fetchone()
    
    json_data = json.dumps(data, indent=2)
    
    if existing:
        cursor.execute(
            "UPDATE profiles SET data = ?, updated_at = datetime('now') WHERE id = ?",
            (json_data, existing["id"])
        )
    else:
        cursor.execute(
            "INSERT INTO profiles (data) VALUES (?)",
            (json_data,)
        )
    
    conn.commit()
    conn.close()


def get_profile() -> dict | None:
    """
    Get the stored user profile.
    
    Returns:
        Profile data as dict, or None if not found
    """
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT data FROM profiles ORDER BY updated_at DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    
    if row:
        try:
            return json.loads(row["data"])
        except json.JSONDecodeError:
            return None
    return None


def log_action(action_type: str, details: str = "", status: str = "completed"):
    """
    Log an agent action for audit trail.
    
    Args:
        action_type: Type of action (e.g. 'route', 'query', 'github_sync')
        details: JSON or text description of what happened
        status: 'completed', 'failed', 'pending'
    """
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO action_log (action_type, details, status) VALUES (?, ?, ?)",
        (action_type, details, status)
    )
    conn.commit()
    conn.close()


def get_recent_actions(limit: int = 20) -> list:
    """Get recent actions from the log."""
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM action_log ORDER BY created_at DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_memory(key: str, value: str, category: str = "general"):
    """Save a key-value pair to memory store."""
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO memory_store (key, value, category, updated_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            category = excluded.category,
            updated_at = datetime('now')
    """, (key, value, category))
    conn.commit()
    conn.close()


def get_memory(key: str) -> str | None:
    """Retrieve a value from memory store."""
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM memory_store WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else None


def log_content(content_type: str, content: str, status: str = "generated",
                platform: str = "", model_used: str = ""):
    """
    Log generated content for tracking.
    
    Args:
        content_type: 'linkedin_post', 'cover_letter', 'gig_description'
        content: The generated content text
        status: 'generated', 'approved', 'posted', 'cancelled'
        platform: Target platform (e.g. 'linkedin', 'fiverr', 'upwork')
        model_used: Which model generated it
    """
    word_count = len(content.split()) if isinstance(content, str) else 0
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO content_log (content_type, content, status, platform, model_used, word_count)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (content_type, content[:2000], status, platform, model_used, word_count)
    )
    conn.commit()
    conn.close()


def get_recent_content(content_type: str = "", limit: int = 10) -> list:
    """Get recent generated content from the log."""
    conn = _get_conn()
    cursor = conn.cursor()
    if content_type:
        cursor.execute(
            "SELECT * FROM content_log WHERE content_type = ? ORDER BY created_at DESC LIMIT ?",
            (content_type, limit)
        )
    else:
        cursor.execute(
            "SELECT * FROM content_log ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    print("=" * 50)
    print("Database Test")
    print("=" * 50)
    
    init_db()
    
    # Test profile
    save_profile({"name": "Bilal Ahmad Sheikh", "test": True})
    profile = get_profile()
    print(f"\nProfile: {profile}")
    
    # Test action log
    log_action("test", "Testing database", "completed")
    actions = get_recent_actions(5)
    print(f"\nRecent actions: {len(actions)}")
    for a in actions:
        print(f"  - [{a['status']}] {a['action_type']}: {a['details']}")
    
    # Test memory
    save_memory("test_key", "test_value", "test")
    val = get_memory("test_key")
    print(f"\nMemory test: {val}")
    
    print("\nAll tests passed!")
