"""
github_connector.py — BilalAgent v2.0 GitHub Integration
REST API connector with PAT auth and 24h JSON caching.
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

GITHUB_PAT = os.getenv("GITHUB_PAT", "")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "bilalahmadsheikh")
CACHE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "memory", "github_cache.json"
)
CACHE_TTL_HOURS = 24


class GitHubConnector:
    """GitHub REST API connector with caching."""
    
    def __init__(self):
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "BilalAgent/2.0",
        }
        if GITHUB_PAT:
            self.headers["Authorization"] = f"token {GITHUB_PAT}"
        self.cache = self._load_cache()
    
    def _load_cache(self) -> dict:
        """Load cache from disk."""
        cache_file = os.path.normpath(CACHE_PATH)
        try:
            if os.path.exists(cache_file):
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
        return {}
    
    def _save_cache(self):
        """Persist cache to disk."""
        cache_file = os.path.normpath(CACHE_PATH)
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2, default=str)
        except IOError as e:
            print(f"[GITHUB] Cache write failed: {e}")
    
    def _is_cached(self, key: str) -> bool:
        """Check if a cache entry exists and is within TTL."""
        if key not in self.cache:
            return False
        entry = self.cache[key]
        cached_at = entry.get("cached_at", 0)
        age_hours = (time.time() - cached_at) / 3600
        return age_hours < CACHE_TTL_HOURS
    
    def _get_cached(self, key: str):
        """Get cached data if valid."""
        if self._is_cached(key):
            return self.cache[key].get("data")
        return None
    
    def _set_cached(self, key: str, data):
        """Set cache entry with timestamp."""
        self.cache[key] = {
            "data": data,
            "cached_at": time.time()
        }
        self._save_cache()
    
    def _api_get(self, endpoint: str, params: dict = None) -> dict | list | None:
        """Make a GET request to the GitHub API."""
        url = f"{self.base_url}{endpoint}"
        try:
            resp = requests.get(url, headers=self.headers, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            print(f"[GITHUB] API error: {e}")
            return None
    
    def get_repos(self) -> list:
        """
        Get all public repos for the configured user.
        
        Returns:
            List of dicts with keys: name, description, language, stars, url, updated_at
        """
        cache_key = f"repos_{GITHUB_USERNAME}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            print(f"[GITHUB] Using cached repos ({len(cached)} repos)")
            return cached
        
        print(f"[GITHUB] Fetching repos for {GITHUB_USERNAME}...")
        raw = self._api_get(f"/users/{GITHUB_USERNAME}/repos", {
            "sort": "updated",
            "per_page": 100
        })
        
        if raw is None:
            return []
        
        repos = []
        for r in raw:
            repos.append({
                "name": r.get("name", ""),
                "description": r.get("description", "") or "",
                "language": r.get("language", "") or "",
                "stars": r.get("stargazers_count", 0),
                "url": r.get("html_url", ""),
                "updated_at": r.get("updated_at", ""),
            })
        
        self._set_cached(cache_key, repos)
        return repos
    
    def get_readme(self, repo: str) -> str:
        """
        Get the README content for a specific repo.
        
        Args:
            repo: Repository name (not full path)
            
        Returns:
            README content as string, or empty string on failure
        """
        cache_key = f"readme_{GITHUB_USERNAME}_{repo}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        print(f"[GITHUB] Fetching README for {repo}...")
        url = f"{self.base_url}/repos/{GITHUB_USERNAME}/{repo}/readme"
        try:
            resp = requests.get(url, headers={
                **self.headers,
                "Accept": "application/vnd.github.v3.raw"
            }, timeout=30)
            resp.raise_for_status()
            content = resp.text
            self._set_cached(cache_key, content)
            return content
        except requests.exceptions.RequestException:
            return ""
    
    def get_recent_commits(self, days: int = 30) -> list:
        """
        Get recent commits across all repos.
        
        Args:
            days: Number of days to look back (default: 30)
            
        Returns:
            List of dicts with keys: repo, message, date, sha
        """
        cache_key = f"commits_{GITHUB_USERNAME}_{days}d"
        cached = self._get_cached(cache_key)
        if cached is not None:
            print(f"[GITHUB] Using cached commits ({len(cached)} commits)")
            return cached
        
        repos = self.get_repos()
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
        all_commits = []
        for repo in repos[:10]:  # Limit to top 10 repos to avoid rate limits
            raw = self._api_get(
                f"/repos/{GITHUB_USERNAME}/{repo['name']}/commits",
                {"since": since, "per_page": 10}
            )
            if raw:
                for c in raw:
                    commit = c.get("commit", {})
                    all_commits.append({
                        "repo": repo["name"],
                        "message": commit.get("message", "").split("\n")[0],
                        "date": commit.get("author", {}).get("date", ""),
                        "sha": c.get("sha", "")[:7],
                    })
        
        # Sort by date descending
        all_commits.sort(key=lambda x: x.get("date", ""), reverse=True)
        
        self._set_cached(cache_key, all_commits)
        return all_commits
    
    def get_repo_tree(self, repo: str) -> list:
        """
        Get the file/directory tree for a repo (top-level + docs/).
        
        Returns:
            List of file paths found in the repo
        """
        cache_key = f"tree_{GITHUB_USERNAME}_{repo}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        print(f"[GITHUB] Fetching file tree for {repo}...")
        raw = self._api_get(f"/repos/{GITHUB_USERNAME}/{repo}/git/trees/main", {"recursive": "1"})
        
        # Try 'master' branch if 'main' fails
        if raw is None:
            raw = self._api_get(f"/repos/{GITHUB_USERNAME}/{repo}/git/trees/master", {"recursive": "1"})
        
        if raw is None:
            return []
        
        tree = raw.get("tree", [])
        paths = [item["path"] for item in tree if item.get("type") in ("blob", "tree")]
        
        self._set_cached(cache_key, paths)
        return paths
    
    def get_file_content(self, repo: str, path: str) -> str:
        """
        Fetch the raw content of any file from a repo.
        
        Args:
            repo: Repository name
            path: File path within the repo (e.g. 'docs/FEATURES.md')
            
        Returns:
            File content as string, or empty string on failure
        """
        cache_key = f"file_{GITHUB_USERNAME}_{repo}_{path.replace('/', '_')}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        print(f"[GITHUB] Fetching {repo}/{path}...")
        url = f"{self.base_url}/repos/{GITHUB_USERNAME}/{repo}/contents/{path}"
        try:
            resp = requests.get(url, headers={
                **self.headers,
                "Accept": "application/vnd.github.v3.raw"
            }, timeout=30)
            resp.raise_for_status()
            content = resp.text
            self._set_cached(cache_key, content)
            return content
        except requests.exceptions.RequestException:
            return ""
    
    def get_deep_repo_context(self, repo: str) -> str:
        """
        Build a comprehensive context from a repo:
        README + docs/ folder files + CHANGELOG + FEATURES + package.json.
        
        This is the PRIMARY source for content generation about a specific project.
        
        Args:
            repo: Repository name
            
        Returns:
            Rich multi-section text with all available project info
        """
        lines = [f"=== PROJECT: {repo} ==="]
        
        # 1. Repo metadata
        repos = self.get_repos()
        for r in repos:
            if r["name"] == repo:
                lines.append(f"Language: {r['language'] or 'Not detected'}")
                lines.append(f"Description: {r['description'] or 'No description'}")
                lines.append(f"URL: {r['url']}")
                lines.append(f"Last updated: {r['updated_at'][:10]}")
                break
        
        # 2. README
        readme = self.get_readme(repo)
        if readme:
            readme_text = readme[:5000] if len(readme) > 5000 else readme
            lines.append(f"\n=== README.md ===\n{readme_text}")
        
        # 3. Scan file tree for docs and important files
        tree = self.get_repo_tree(repo)
        
        # Important files to look for (case-insensitive matching)
        important_files = []
        docs_files = []
        
        for path in tree:
            lower = path.lower()
            # Top-level important files
            if lower in ("changelog.md", "features.md", "contributing.md", "architecture.md"):
                important_files.append(path)
            elif lower == "package.json":
                important_files.append(path)
            # Docs folder files
            elif lower.startswith("docs/") and lower.endswith(".md"):
                docs_files.append(path)
            elif lower.startswith("doc/") and lower.endswith(".md"):
                docs_files.append(path)
        
        # 4. Fetch important top-level files
        for fpath in important_files:
            content = self.get_file_content(repo, fpath)
            if content:
                content_text = content[:4000] if len(content) > 4000 else content
                lines.append(f"\n=== {fpath} ===\n{content_text}")
        
        # 5. Fetch docs/ folder files (up to 5 most relevant)
        if docs_files:
            # Prioritize: FEATURES, CHANGELOG, ARCHITECTURE, SCHEMA, PROGRESS, then others
            priority = ["feature", "changelog", "architecture", "schema", "progress", "api", "setup", "decision"]
            sorted_docs = sorted(docs_files, key=lambda p: next(
                (i for i, kw in enumerate(priority) if kw in p.lower()), len(priority)
            ))
            
            fetched = 0
            for fpath in sorted_docs:
                if fetched >= 8:
                    break
                content = self.get_file_content(repo, fpath)
                if content:
                    content_text = content[:4000] if len(content) > 4000 else content
                    lines.append(f"\n=== {fpath} ===\n{content_text}")
                    fetched += 1
            
            # List remaining docs we didn't fetch
            remaining = sorted_docs[fetched:]
            if remaining:
                lines.append(f"\n=== Other docs available (not fetched) ===")
                for p in remaining[:10]:
                    lines.append(f"  - {p}")
        
        # 6. Recent commits for this repo
        commits = self.get_recent_commits(days=60)
        repo_commits = [c for c in commits if c["repo"] == repo]
        if repo_commits:
            lines.append(f"\n=== RECENT COMMITS ({len(repo_commits)}) ===")
            for c in repo_commits[:10]:
                lines.append(f"  - {c['message'][:120]} ({c['date'][:10]})")
        
        return "\n".join(lines)
    
    def get_summary(self) -> str:
        """Get a comprehensive human-readable summary of all GitHub data."""
        repos = self.get_repos()
        commits = self.get_recent_commits(days=30)
        
        lines = [f"GitHub User: {GITHUB_USERNAME}", f"Total public repos: {len(repos)}"]
        
        if repos:
            lines.append("\nAll repositories (sorted by most recent):")
            for r in repos:
                lang = f" [{r['language']}]" if r['language'] else " [no language detected]"
                desc = r['description'][:100] if r['description'] else "no description"
                lines.append(f"  - {r['name']}{lang}: {desc}")
        
        if commits:
            lines.append(f"\nRecent commits (last 30 days): {len(commits)} total")
            for c in commits[:15]:
                lines.append(f"  - [{c['repo']}] {c['message'][:80]} ({c['date'][:10]})")
        
        # Summarize languages
        lang_count = {}
        for r in repos:
            lang = r.get('language', '')
            if lang:
                lang_count[lang] = lang_count.get(lang, 0) + 1
        if lang_count:
            sorted_langs = sorted(lang_count.items(), key=lambda x: x[1], reverse=True)
            lines.append(f"\nLanguages used across repos:")
            for lang, count in sorted_langs:
                lines.append(f"  - {lang}: {count} repo(s)")
        
        return "\n".join(lines)


if __name__ == "__main__":
    print("=" * 50)
    print("GitHub Connector Test")
    print("=" * 50)
    
    gh = GitHubConnector()
    
    repos = gh.get_repos()
    print(f"\nFound {len(repos)} repos:")
    for r in repos[:5]:
        print(f"  - {r['name']} ({r['language']}): {r['description'][:60]}")
    
    if repos:
        readme = gh.get_readme(repos[0]["name"])
        print(f"\nREADME for {repos[0]['name']}: {len(readme)} chars")
    
    commits = gh.get_recent_commits(days=30)
    print(f"\nRecent commits: {len(commits)}")
    for c in commits[:3]:
        print(f"  - [{c['repo']}] {c['message'][:50]}")
