"""
github_monitor.py — BilalAgent v2.0 GitHub Activity Monitor
Detects new repos, commits, stars, README updates since last check.
Generates post ideas based on activity.
"""

import os
import sys
import json
import sqlite3
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from connectors.github_connector import GitHubConnector

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "memory", "agent_memory.db")


class GitHubActivityMonitor:
    """Monitors GitHub for new activity and generates post ideas."""
    
    def __init__(self):
        self.gh = GitHubConnector()
        self._ensure_table()
    
    def _ensure_table(self):
        """Ensure github_state table exists."""
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS github_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
        conn.close()
    
    def _get_state(self, key: str) -> str:
        """Get a state value from SQLite."""
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT value FROM github_state WHERE key = ?", (key,)).fetchone()
        conn.close()
        return row[0] if row else ""
    
    def _set_state(self, key: str, value: str):
        """Set a state value in SQLite (upsert)."""
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT INTO github_state (key, value, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')
        """, (key, value))
        conn.commit()
        conn.close()
    
    def check_new_activity(self) -> list:
        """
        Check for new GitHub activity since last check.
        
        Returns:
            List of activity dicts: {type, description, repo, data}
        """
        activities = []
        
        # 1. Check for new repos
        current_repos = self.gh.get_repos()
        current_repo_names = {r["name"] for r in current_repos}
        
        prev_repos_str = self._get_state("known_repos")
        prev_repo_names = set(json.loads(prev_repos_str)) if prev_repos_str else set()
        
        new_repos = current_repo_names - prev_repo_names
        for repo_name in new_repos:
            repo_data = next((r for r in current_repos if r["name"] == repo_name), {})
            activities.append({
                "type": "new_repo",
                "description": f"New repository created: {repo_name}",
                "repo": repo_name,
                "data": repo_data,
            })
            print(f"  [MONITOR] New repo: {repo_name}")
        
        # Update known repos
        self._set_state("known_repos", json.dumps(list(current_repo_names)))
        
        # 2. Check recent commits (7 days)
        recent_commits = self.gh.get_recent_commits(days=7)
        
        prev_commits_str = self._get_state("last_commit_shas")
        prev_shas = set(json.loads(prev_commits_str)) if prev_commits_str else set()
        
        new_commits = [c for c in recent_commits if c["sha"] not in prev_shas]
        
        # Group by repo
        commits_by_repo = {}
        for c in new_commits:
            commits_by_repo.setdefault(c["repo"], []).append(c)
        
        for repo_name, commits in commits_by_repo.items():
            activities.append({
                "type": "new_commits",
                "description": f"{len(commits)} new commits in {repo_name}",
                "repo": repo_name,
                "data": {"count": len(commits), "messages": [c["message"] for c in commits[:5]]},
            })
            print(f"  [MONITOR] {len(commits)} new commits in {repo_name}")
        
        # Update commit tracking (keep last 200 SHAs)
        all_shas = list(prev_shas | {c["sha"] for c in recent_commits})
        self._set_state("last_commit_shas", json.dumps(all_shas[-200:]))
        
        # 3. Check star counts
        prev_stars_str = self._get_state("star_counts")
        prev_stars = json.loads(prev_stars_str) if prev_stars_str else {}
        
        for repo in current_repos:
            name = repo["name"]
            current_stars = repo.get("stars", 0)
            prev_count = prev_stars.get(name, 0)
            
            if current_stars > prev_count and prev_count > 0:
                gained = current_stars - prev_count
                activities.append({
                    "type": "stars_gained",
                    "description": f"{name} gained {gained} star{'s' if gained > 1 else ''}! ({prev_count} → {current_stars})",
                    "repo": name,
                    "data": {"gained": gained, "total": current_stars},
                })
                print(f"  [MONITOR] {name} gained {gained} star(s)")
        
        # Update star counts
        star_map = {r["name"]: r.get("stars", 0) for r in current_repos}
        self._set_state("star_counts", json.dumps(star_map))
        
        # 4. Check for README updates (compare lengths)
        prev_readmes_str = self._get_state("readme_lengths")
        prev_readmes = json.loads(prev_readmes_str) if prev_readmes_str else {}
        
        readme_lengths = {}
        for repo in current_repos[:10]:  # Check top 10 repos only
            name = repo["name"]
            readme = self.gh.get_readme(name)
            readme_lengths[name] = len(readme)
            
            prev_len = prev_readmes.get(name, 0)
            if prev_len > 0 and len(readme) > prev_len + 100:  # Significant update
                activities.append({
                    "type": "readme_updated",
                    "description": f"{name} README updated ({prev_len} → {len(readme)} chars)",
                    "repo": name,
                    "data": {"prev_length": prev_len, "new_length": len(readme)},
                })
                print(f"  [MONITOR] {name} README updated")
        
        self._set_state("readme_lengths", json.dumps(readme_lengths))
        self._set_state("last_check", datetime.now().isoformat())
        
        print(f"[MONITOR] Activity check complete: {len(activities)} changes found")
        return activities
    
    def get_content_ideas(self) -> list:
        """
        Generate post ideas based on recent GitHub activity.
        
        Returns:
            List of idea dicts: {type, project, hook, data}
        """
        activities = self.check_new_activity()
        ideas = []
        
        # If no activity, use top repos for general content
        if not activities:
            repos = self.gh.get_repos()
            # Pick top 3 by update recency
            sorted_repos = sorted(repos, key=lambda r: r.get("updated_at", ""), reverse=True)
            
            for repo in sorted_repos[:3]:
                ideas.append({
                    "type": "project_showcase",
                    "project": repo["name"],
                    "hook": f"Deep dive into {repo['name']} — {repo.get('description', 'a project')}",
                    "data": repo,
                })
            
            print(f"[MONITOR] No new activity — generated {len(ideas)} ideas from top repos")
            return ideas
        
        # Generate ideas from activity
        for act in activities:
            if act["type"] == "new_repo":
                ideas.append({
                    "type": "project_showcase",
                    "project": act["repo"],
                    "hook": f"Just created a new repo: {act['repo']}! Here's what it does and why I built it.",
                    "data": act["data"],
                })
            
            elif act["type"] == "new_commits":
                count = act["data"]["count"]
                messages = act["data"]["messages"]
                
                if count >= 5:
                    ideas.append({
                        "type": "learning_update",
                        "project": act["repo"],
                        "hook": f"Shipped {count} commits to {act['repo']} this week. Here's what I learned building it.",
                        "data": act["data"],
                    })
                else:
                    ideas.append({
                        "type": "project_showcase",
                        "project": act["repo"],
                        "hook": f"Latest updates to {act['repo']}: {messages[0][:60]}...",
                        "data": act["data"],
                    })
            
            elif act["type"] == "stars_gained":
                ideas.append({
                    "type": "achievement",
                    "project": act["repo"],
                    "hook": f"{act['repo']} just hit {act['data']['total']} stars! Here's the story behind this project.",
                    "data": act["data"],
                })
            
            elif act["type"] == "readme_updated":
                ideas.append({
                    "type": "learning_update",
                    "project": act["repo"],
                    "hook": f"Major documentation update for {act['repo']} — why good docs matter.",
                    "data": act["data"],
                })
        
        # Ensure we have at least 3 ideas (pad with opinion posts)
        if len(ideas) < 3:
            repos = self.gh.get_repos()
            topics = [
                "Why I build everything with Python — my tech stack philosophy",
                "What I've learned as a 3rd-year AI Engineering student building real projects",
                "Open source is the best portfolio — here's my proof",
            ]
            for i in range(3 - len(ideas)):
                ideas.append({
                    "type": "opinion",
                    "project": repos[i]["name"] if i < len(repos) else "",
                    "hook": topics[i % len(topics)],
                    "data": {},
                })
        
        # Ensure variety: 1 showcase, 1 learning, 1 opinion
        idea_types = {i["type"] for i in ideas}
        final = []
        for target_type in ["project_showcase", "learning_update", "opinion"]:
            match = next((i for i in ideas if i["type"] == target_type), None)
            if match:
                final.append(match)
                ideas.remove(match)
        
        # Fill remaining with whatever's left
        while len(final) < 3 and ideas:
            final.append(ideas.pop(0))
        
        print(f"[MONITOR] Generated {len(final)} content ideas")
        return final[:3]


if __name__ == "__main__":
    print("=" * 50)
    print("GitHub Activity Monitor Test")
    print("=" * 50)
    
    monitor = GitHubActivityMonitor()
    
    activities = monitor.check_new_activity()
    print(f"\nActivities: {len(activities)}")
    for a in activities:
        print(f"  [{a['type']}] {a['description']}")
    
    ideas = monitor.get_content_ideas()
    print(f"\nContent Ideas: {len(ideas)}")
    for i in ideas:
        print(f"  [{i['type']}] {i['project']}: {i['hook'][:80]}")
