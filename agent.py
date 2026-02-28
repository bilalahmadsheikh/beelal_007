"""
agent.py — BilalAgent v2.0 Main Entry Point
On start: loads profile, initializes DB, syncs GitHub, routes commands via orchestrator.
Usage: python agent.py "your command here"
"""

import sys
import os
import json
import yaml
import time
import re

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from tools.model_runner import get_free_ram, safe_run
from agents.orchestrator import route_command
from agents.nlp_agent import analyze
from connectors.github_connector import GitHubConnector
from memory.db import init_db, save_profile, get_profile, log_action, log_content


def load_profile_yaml() -> dict:
    """Load profile from config/profile.yaml."""
    path = os.path.join(PROJECT_ROOT, "config", "profile.yaml")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        print("[AGENT] Warning: config/profile.yaml not found")
        return {}


def startup():
    """Initialize the agent: DB, profile, GitHub sync."""
    print("=" * 60)
    print("  BilalAgent v2.0 — Starting Up")
    print("=" * 60)
    
    # 1. Check RAM
    free = get_free_ram()
    print(f"\n[1/4] System RAM: {free:.1f}GB free")
    
    # 2. Initialize database
    print("\n[2/4] Initializing database...")
    init_db()
    
    # 3. Load and save profile
    print("\n[3/4] Loading profile...")
    profile = load_profile_yaml()
    if profile:
        save_profile(profile)
        name = profile.get("personal", {}).get("name", "Unknown")
        projects = profile.get("projects", [])
        print(f"       Profile: {name} ({len(projects)} projects)")
    else:
        print("       Warning: No profile loaded")
    
    # 4. GitHub sync
    print("\n[4/4] Syncing GitHub...")
    try:
        gh = GitHubConnector()
        repos = gh.get_repos()
        print(f"       Found {len(repos)} repos")
        log_action("github_sync", f"Synced {len(repos)} repos", "completed")
    except Exception as e:
        print(f"       GitHub sync failed: {e}")
        log_action("github_sync", str(e), "failed")
    
    print("\n" + "=" * 60)
    print("  Agent Ready")
    print("=" * 60)
    
    return profile


def _parse_content_command(user_input: str) -> dict | None:
    """
    Try to parse a content generation command directly from user input.
    Returns dict with content_type and params, or None.
    """
    lower = user_input.lower()
    
    # LinkedIn post detection
    linkedin_patterns = [
        r"(?:write|create|generate|make)\s+(?:a\s+)?linkedin\s+post\s+(?:about|for|on)\s+(\S+)",
        r"linkedin\s+post\s+(?:about|for|on)\s+(\S+)",
    ]
    for pat in linkedin_patterns:
        m = re.search(pat, lower)
        if m:
            subject = m.group(1).strip().rstrip('.')
            return {"content_type": "linkedin_post", "project_name": subject, "post_type": "project_showcase"}
    
    # Cover letter detection
    cover_patterns = [
        r"(?:write|create|generate|make)\s+(?:a\s+)?cover\s+letter\s+for\s+(?:a\s+)?(.+?)(?:\s+at\s+(.+))?$",
        r"cover\s+letter\s+for\s+(?:a\s+)?(.+?)(?:\s+at\s+(.+))?$",
    ]
    for pat in cover_patterns:
        m = re.search(pat, lower)
        if m:
            job = m.group(1).strip().rstrip('.')
            company = m.group(2).strip().rstrip('.') if m.group(2) else "a tech company"
            return {"content_type": "cover_letter", "job_title": job, "company": company}
    
    # Gig description detection
    gig_patterns = [
        r"(?:write|create|generate|make)\s+(?:a\s+)?(?:fiverr|upwork)\s+gig\s+(?:for|about)\s+(.+)",
        r"(?:fiverr|upwork)\s+gig\s+(?:for|about)\s+(.+)",
        r"gig\s+(?:description|listing)\s+for\s+(.+)",
    ]
    for pat in gig_patterns:
        m = re.search(pat, lower)
        if m:
            service = m.group(1).strip().rstrip('.')
            platform = "fiverr" if "fiverr" in lower else "upwork" if "upwork" in lower else "fiverr"
            # Map to known service types
            service_map = {
                "mlops": "mlops", "ml ops": "mlops", "machine learning": "mlops",
                "chatbot": "chatbot", "chat bot": "chatbot", "whatsapp": "chatbot",
                "blockchain": "blockchain", "web3": "blockchain", "crypto": "blockchain",
                "data science": "data_science", "data analysis": "data_science", "analytics": "data_science",
                "backend": "backend", "api": "backend", "fastapi": "backend",
            }
            service_type = "backend"
            for key, val in service_map.items():
                if key in service:
                    service_type = val
                    break
            return {"content_type": "gig_description", "service_type": service_type, "platform": platform}
    
    return None


def handle_command(user_input: str, profile: dict):
    """Process a user command through the full pipeline."""
    print(f"\n{'─' * 60}")
    print(f"Command: \"{user_input}\"")
    print(f"{'─' * 60}")
    
    # Step 1: Route via orchestrator
    print("\n[STEP 1] Routing via Orchestrator (gemma3:1b)...")
    ram_before = get_free_ram()
    
    routing = route_command(user_input)
    print(f"         Routing: {json.dumps(routing, indent=2)}")
    log_action("route", json.dumps(routing), "completed")
    
    # Step 2: Execute via appropriate agent
    agent_name = routing.get("agent", "nlp")
    task = routing.get("task", "general")
    model = routing.get("model", "gemma3:1b")
    
    print(f"\n[STEP 2] Executing via {agent_name} agent (model: {model})...")
    
    if agent_name == "content":
        result = _handle_content(user_input, task)
    
    elif agent_name == "nlp":
        # Always include GitHub data
        context = ""
        try:
            gh = GitHubConnector()
            context = gh.get_summary()
        except Exception:
            pass
        result = analyze(task=user_input, context=context, model=model)
    
    elif agent_name == "memory":
        result = f"[MEMORY] Task '{task}' noted. Memory operations coming in future phases."
    
    elif agent_name == "navigation":
        result = f"[NAVIGATION] Task '{task}' noted. Browser automation coming in Phase 3."
    
    else:
        result = f"[UNKNOWN] Agent '{agent_name}' not recognized."
    
    # Step 3: Display result
    ram_after = get_free_ram()
    
    print(f"\n{'─' * 60}")
    print(f"RESULT:")
    print(f"{'─' * 60}")
    if isinstance(result, dict):
        print(json.dumps(result, indent=2))
    else:
        print(result)
    
    word_count = len(result.split()) if isinstance(result, str) else 0
    print(f"\n{'─' * 60}")
    if isinstance(result, str):
        print(f"Words: {word_count} | Chars: {len(result)}")
    print(f"RAM: {ram_before:.1f}GB → {ram_after:.1f}GB (delta: {ram_after - ram_before:+.1f}GB)")
    print(f"{'─' * 60}")
    
    log_action("response", str(result)[:500], "completed")
    
    return result


def _handle_content(user_input: str, task: str) -> str | dict:
    """Handle content generation commands."""
    from tools.content_tools import generate_linkedin_post, generate_cover_letter, generate_gig_description
    
    # Try to parse content command
    parsed = _parse_content_command(user_input)
    
    if parsed and parsed["content_type"] == "linkedin_post":
        print(f"  → LinkedIn post about: {parsed['project_name']}")
        result = generate_linkedin_post(parsed["project_name"], parsed.get("post_type", "project_showcase"), user_request=user_input)
        log_content("linkedin_post", result, "generated", "linkedin")
        return result
    
    elif parsed and parsed["content_type"] == "cover_letter":
        print(f"  → Cover letter for: {parsed['job_title']} at {parsed['company']}")
        result = generate_cover_letter(parsed["job_title"], parsed["company"], user_request=user_input)
        log_content("cover_letter", result, "generated")
        return result
    
    elif parsed and parsed["content_type"] == "gig_description":
        print(f"  → Gig description for: {parsed['service_type']} on {parsed['platform']}")
        result = generate_gig_description(parsed["service_type"], parsed["platform"], user_request=user_input)
        log_content("gig_description", json.dumps(result), "generated", parsed["platform"])
        return result
    
    # Fallback: generic content generation via content agent
    from agents.content_agent import generate
    result = generate(user_input, content_type="general")
    log_content("general", result, "generated")
    return result


def main():
    """Main entry point."""
    profile = startup()
    
    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:])
        handle_command(user_input, profile)
    else:
        print("\nUsage: python agent.py \"your command here\"")
        print("\nExamples:")
        print('  python agent.py "what are my 4 projects and their tech stacks"')
        print('  python agent.py "write a linkedin post about purchasing_power_ml"')
        print('  python agent.py "write a cover letter for Python developer at Google"')
        print('  python agent.py "fiverr gig for chatbot"')


if __name__ == "__main__":
    main()
