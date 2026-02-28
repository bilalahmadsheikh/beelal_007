"""
jobspy_connector.py — BilalAgent v2.0 Job Search Connector
Multi-site job scraping via python-jobspy with 12h caching.
Sites: LinkedIn, Indeed, Glassdoor
"""

import os
import json
import time
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_FILE = os.path.join(PROJECT_ROOT, "memory", "job_cache.json")
CACHE_HOURS = 12


def _load_cache() -> dict:
    """Load job cache from disk."""
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_cache(cache: dict) -> None:
    """Save job cache to disk."""
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, default=str)


def _cache_key(role: str, location: str, num: int) -> str:
    """Generate a cache key from search params."""
    return f"{role.lower().strip()}|{location.lower().strip()}|{num}"


def _is_cache_valid(cache_entry: dict) -> bool:
    """Check if a cache entry is still fresh (within CACHE_HOURS)."""
    try:
        cached_at = datetime.fromisoformat(cache_entry.get("cached_at", ""))
        age_hours = (datetime.now() - cached_at).total_seconds() / 3600
        return age_hours < CACHE_HOURS
    except (ValueError, TypeError):
        return False


def search_jobs(role: str, location: str = "remote", num: int = 20) -> list:
    """
    Search for jobs across LinkedIn, Indeed, and Glassdoor.
    Results are cached for 12 hours.
    
    Args:
        role: Job title to search for (e.g. "AI Engineer", "Python Developer")
        location: Location filter (e.g. "remote", "Pakistan", "USA")
        num: Number of results to fetch per site
        
    Returns:
        List of job dicts with keys: title, company, location, url, 
        description, salary, site_name, date_posted
    """
    # Check cache first
    cache = _load_cache()
    key = _cache_key(role, location, num)
    
    if key in cache and _is_cache_valid(cache[key]):
        jobs = cache[key]["jobs"]
        print(f"[JOBSPY] Using cached results ({len(jobs)} jobs, {key})")
        return jobs
    
    # Fresh search
    print(f"[JOBSPY] Searching: '{role}' in '{location}' (max {num} per site)...")
    
    try:
        from jobspy import scrape_jobs
        
        results = scrape_jobs(
            site_name=["indeed", "glassdoor", "linkedin"],
            search_term=role,
            location=location,
            results_wanted=num,
            hours_old=72,  # Jobs from last 3 days
            country_indeed="USA" if location.lower() == "remote" else location,
        )
        
        # Convert DataFrame to list of dicts
        jobs = []
        for _, row in results.iterrows():
            job = {
                "title": _clean_val(row.get("title", "")),
                "company": _clean_val(row.get("company_name", row.get("company", ""))),
                "location": _clean_val(row.get("location", location), location),
                "url": _clean_val(row.get("job_url", row.get("link", ""))),
                "description": _clean_val(row.get("description", ""))[:2000],
                "salary": _extract_salary(row),
                "site_name": _clean_val(row.get("site", "unknown")),
                "date_posted": _clean_val(row.get("date_posted", "")),
            }
            if job["title"] and job["company"]:
                jobs.append(job)
        
        print(f"[JOBSPY] Found {len(jobs)} jobs across all sites")
        
        # Cache results
        cache[key] = {
            "cached_at": datetime.now().isoformat(),
            "jobs": jobs,
        }
        _save_cache(cache)
        
        return jobs
        
    except ImportError:
        print("[JOBSPY] python-jobspy not installed. Run: pip install python-jobspy")
        return []
    except Exception as e:
        print(f"[JOBSPY] Search error: {e}")
        return []


def _clean_val(val, default: str = "") -> str:
    """Clean a value from pandas DataFrame — handle NaN, None, nan strings."""
    import math
    if val is None:
        return default
    s = str(val).strip()
    if s.lower() in ("nan", "none", "nat", ""):
        return default
    try:
        if isinstance(val, float) and math.isnan(val):
            return default
    except (TypeError, ValueError):
        pass
    return s


def _extract_salary(row) -> str:
    """Extract salary info from a jobspy result row."""
    import math
    
    min_sal = row.get("min_amount", None)
    max_sal = row.get("max_amount", None)
    currency = row.get("currency", "USD")
    interval = row.get("interval", "yearly")
    
    # Handle NaN
    try:
        if min_sal is not None and isinstance(min_sal, float) and math.isnan(min_sal):
            min_sal = None
        if max_sal is not None and isinstance(max_sal, float) and math.isnan(max_sal):
            max_sal = None
    except (TypeError, ValueError):
        pass
    
    currency = _clean_val(currency, "USD")
    interval = _clean_val(interval, "yearly")
    
    if min_sal and max_sal:
        return f"{currency} {min_sal:,.0f}-{max_sal:,.0f}/{interval}"
    elif min_sal:
        return f"{currency} {min_sal:,.0f}+/{interval}"
    elif max_sal:
        return f"Up to {currency} {max_sal:,.0f}/{interval}"
    return "Not listed"


def clear_cache() -> None:
    """Clear the job cache."""
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
        print("[JOBSPY] Cache cleared")


if __name__ == "__main__":
    print("=" * 50)
    print("JobSpy Connector Test")
    print("=" * 50)
    jobs = search_jobs("AI Engineer", "remote", num=5)
    for i, j in enumerate(jobs[:5], 1):
        print(f"\n{i}. {j['title']} @ {j['company']}")
        print(f"   {j['location']} | {j['salary']} | {j['site_name']}")
        print(f"   {j['url'][:80]}")
