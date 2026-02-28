"""
freelance_monitor.py — BilalAgent v2.0 Freelance Project Monitor
Monitors Upwork RSS feeds for new projects matching user skills.
Tracks seen projects in SQLite to avoid duplicates.
"""

import os
import sys
import json
import sqlite3
import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "memory", "agent_memory.db")

# Default keywords from profile skills
DEFAULT_KEYWORDS = ["python fastapi", "mlops", "blockchain web3", "ai chatbot", "data science"]


def _get_default_keywords() -> list:
    """Load default keywords from profile.yaml skills."""
    import yaml
    path = os.path.join(PROJECT_ROOT, "config", "profile.yaml")
    try:
        with open(path, "r", encoding="utf-8") as f:
            profile = yaml.safe_load(f) or {}
        skills = profile.get("personal", {}).get("skills", [])
        # Group into meaningful search queries
        if skills:
            return [
                "python fastapi",
                "mlops machine learning",
                "blockchain web3",
                "ai chatbot",
                "data science python",
            ]
    except Exception:
        pass
    return DEFAULT_KEYWORDS


def _ensure_seen_table():
    """Create seen_projects table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seen_projects (
            project_id TEXT PRIMARY KEY,
            title TEXT,
            url TEXT,
            keyword TEXT,
            first_seen TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def _is_seen(project_id: str) -> bool:
    """Check if a project has been seen before."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT 1 FROM seen_projects WHERE project_id = ?", (project_id,)).fetchone()
    conn.close()
    return row is not None


def _mark_seen(project_id: str, title: str, url: str, keyword: str):
    """Mark a project as seen."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO seen_projects (project_id, title, url, keyword) VALUES (?, ?, ?, ?)",
        (project_id, title, url, keyword)
    )
    conn.commit()
    conn.close()


def _fetch_rss(keyword: str) -> list:
    """Fetch Upwork RSS/Atom feed for a keyword. Tries multiple URL formats."""
    import requests
    
    encoded = keyword.replace(" ", "+")
    
    # Try multiple Upwork feed URL formats (they change periodically)
    urls_to_try = [
        f"https://www.upwork.com/ab/feed/jobs/rss?q={encoded}&sort=recency",
        f"https://www.upwork.com/ab/feed/jobs/atom?q={encoded}&sort=recency",
        f"https://www.upwork.com/ab/feed/jobs/rss?q={encoded}",
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
    }
    
    for url in urls_to_try:
        try:
            resp = requests.get(url, timeout=15, headers=headers)
            if resp.status_code == 410:
                continue  # Try next URL format
            resp.raise_for_status()
            
            root = ET.fromstring(resp.content)
            items = []
            
            # Try RSS format
            for item in root.findall(".//item"):
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                description = item.findtext("description", "")
                pub_date = item.findtext("pubDate", "")
                
                project_id = hashlib.md5(link.encode()).hexdigest()[:12] if link else ""
                
                budget = ""
                import re
                budget_match = re.search(r'\$[\d,]+(?:\s*-\s*\$[\d,]+)?', description)
                if budget_match:
                    budget = budget_match.group(0)
                
                if title and link:
                    items.append({
                        "project_id": project_id,
                        "title": title,
                        "url": link,
                        "description": _clean_html(description)[:500],
                        "budget": budget,
                        "posted": pub_date,
                        "keyword": keyword,
                    })
            
            # Try Atom format if no RSS items found
            if not items:
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                for entry in root.findall(".//atom:entry", ns):
                    title = entry.findtext("atom:title", "", ns)
                    link_elem = entry.find("atom:link", ns)
                    link = link_elem.get("href", "") if link_elem is not None else ""
                    summary = entry.findtext("atom:summary", "", ns)
                    published = entry.findtext("atom:published", "", ns)
                    
                    project_id = hashlib.md5(link.encode()).hexdigest()[:12] if link else ""
                    
                    if title and link:
                        items.append({
                            "project_id": project_id,
                            "title": title,
                            "url": link,
                            "description": _clean_html(summary)[:500],
                            "budget": "",
                            "posted": published,
                            "keyword": keyword,
                        })
            
            if items:
                return items
                
        except ET.ParseError:
            continue
        except Exception as e:
            print(f"[MONITOR] Feed error for '{keyword}' ({url[:50]}): {e}")
            continue
    
    # All URLs failed — Upwork may have deprecated RSS feeds
    print(f"[MONITOR] No RSS feed available for '{keyword}' (Upwork may have disabled feeds)")
    return []


def _clean_html(text: str) -> str:
    """Strip HTML tags from text."""
    import re
    clean = re.sub(r'<[^>]+>', ' ', text)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


def check_new_projects(keywords: list = None) -> list:
    """
    Check for new freelance projects on Upwork RSS.
    
    Args:
        keywords: List of search keywords. Uses defaults from profile if None.
        
    Returns:
        List of new (unseen) project dicts
    """
    _ensure_seen_table()
    
    if keywords is None:
        keywords = _get_default_keywords()
    
    print(f"[MONITOR] Checking {len(keywords)} keywords for new projects...")
    
    all_new = []
    
    for keyword in keywords:
        print(f"[MONITOR] Searching: '{keyword}'...")
        items = _fetch_rss(keyword)
        
        new_items = []
        for item in items:
            if not _is_seen(item["project_id"]):
                _mark_seen(item["project_id"], item["title"], item["url"], keyword)
                new_items.append(item)
        
        if new_items:
            print(f"[MONITOR]   → {len(new_items)} new projects for '{keyword}'")
            all_new.extend(new_items)
        else:
            print(f"[MONITOR]   → No new projects for '{keyword}'")
    
    print(f"\n[MONITOR] Total new projects: {len(all_new)}")
    return all_new


def display_projects(projects: list) -> str:
    """Format projects for display."""
    if not projects:
        return "No new freelance projects found."
    
    lines = [f"\n🔍 New Freelance Projects ({len(projects)} found)\n{'═' * 50}"]
    
    for i, p in enumerate(projects[:15], 1):
        lines.append(f"\n{'─' * 50}")
        lines.append(f"  #{i} | {p['title'][:70]}")
        if p.get('budget'):
            lines.append(f"  💰 {p['budget']}")
        lines.append(f"  🔑 Keyword: {p['keyword']}")
        lines.append(f"  🔗 {p['url'][:80]}")
        if p.get('description'):
            lines.append(f"  📝 {p['description'][:120]}...")
    
    lines.append(f"\n{'═' * 50}")
    return "\n".join(lines)


if __name__ == "__main__":
    print("=" * 50)
    print("Freelance Monitor Test")
    print("=" * 50)
    
    projects = check_new_projects(["python fastapi"])
    print(display_projects(projects))
