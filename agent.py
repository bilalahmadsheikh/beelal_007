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
    
    # Step 0: Check Mode 2 (Browser Copilot) triggers
    mode_2_triggers = [
        "apply to this", "help with this page", "summarise this", "summarize this",
        "write proposal for this", "use claude for", "use chatgpt for",
        "copilot", "browser mode"
    ]

    settings = {}
    try:
        settings_path = os.path.join(PROJECT_ROOT, "config", "settings.yaml")
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f) or {}
    except Exception:
        pass

    intelligence_mode = settings.get("intelligence_mode", "local")

    if any(trigger in user_input.lower() for trigger in mode_2_triggers):
        if intelligence_mode in ["web_copilot", "hybrid"]:
            print("\n[MODE 2] Browser Copilot activated")
            try:
                from tools.browser_copilot import BrowserCopilot
                copilot = BrowserCopilot()

                # Detect target LLM
                target = "claude"
                if "chatgpt" in user_input.lower():
                    target = "chatgpt"

                result = copilot.full_flow(user_input, target_llm=target)
                print(f"[MODE 2] Result: {result.get('status', 'unknown')}")
                if result.get("status") == "ok":
                    print(result["response"][:500])
                return result
            except Exception as e:
                print(f"[MODE 2] Error: {e}")
                # Fall through to normal routing

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
        # Check Phase 6 brand/scheduling commands first
        brand_result = _try_brand(user_input)
        if brand_result is not None:
            result = brand_result
        # Then check Phase 5 freelance commands
        elif (freelance_result := _try_freelance(user_input)) is not None:
            result = freelance_result
        else:
            result = _handle_content(user_input, task)
    
    elif agent_name == "nlp":
        # Check if brand/freelance command was misrouted to NLP
        brand_result = _try_brand(user_input)
        if brand_result is not None:
            result = brand_result
        elif (freelance_result := _try_freelance(user_input)) is not None:
            result = freelance_result
        else:
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
        result = f"[NAVIGATION] Task '{task}' noted. Use browser tools for automation."
    
    elif agent_name == "jobs":
        result = _handle_jobs(user_input, task)
    
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


def _handle_jobs(user_input: str, task: str) -> str:
    """Handle job search and application commands."""
    from tools.apply_workflow import run_job_search, show_my_applications
    
    lower = user_input.lower()
    
    # Show applications
    if any(kw in lower for kw in ["show my application", "my applications", "applied jobs", "application log"]):
        status_filter = None
        for s in ["saved", "applied", "rejected", "interview", "offer"]:
            if s in lower:
                status_filter = s
                break
        return show_my_applications(status_filter)
    
    # Parse job search: "find X jobs Y" or "search for X in Y"
    query, location = _parse_job_query(user_input)
    print(f"  → Job search: '{query}' in '{location}'")
    
    return run_job_search(query, location)


def _try_brand(user_input: str):
    """
    Check if user_input is a Phase 6 brand/scheduling command. Returns result or None.
    Handles: weekly post generation, brand check, github activity, hybrid refine.
    """
    lower = user_input.lower()
    
    # Generate weekly posts
    if any(kw in lower for kw in [
        "generate weekly posts", "schedule posts", "weekly posts",
        "generate posts", "brand posts", "linkedin posts",
    ]):
        from tools.post_scheduler import generate_weekly_posts
        
        mode = "local"
        if "hybrid" in lower:
            mode = "hybrid"
        elif "web_copilot" in lower or "copilot" in lower:
            mode = "web_copilot"
        
        posts = generate_weekly_posts(mode=mode)
        
        if posts:
            summary_lines = [f"\n📝 Generated {len(posts)} weekly posts (mode: {mode}):\n"]
            for i, p in enumerate(posts, 1):
                summary_lines.append(f"  {i}. [{p['type']}] {p['project']} — {p['words']} words")
                summary_lines.append(f"     Saved: {p['path']}")
                summary_lines.append(f"     Preview: {p['final'][:120]}...")
            return "\n".join(summary_lines)
        return "No posts generated — check GitHub activity."
    
    # Brand check / GitHub activity
    if any(kw in lower for kw in [
        "brand check", "github activity", "activity check",
        "content ideas", "post ideas", "what to post",
    ]):
        from connectors.github_monitor import GitHubActivityMonitor
        
        monitor = GitHubActivityMonitor()
        activities = monitor.check_new_activity()
        ideas = monitor.get_content_ideas()
        
        lines = [f"\n📊 GitHub Activity Report:\n  {len(activities)} changes detected\n"]
        
        for a in activities[:5]:
            lines.append(f"  • [{a['type']}] {a['description']}")
        
        lines.append(f"\n💡 Content Ideas ({len(ideas)}):\n")
        for i, idea in enumerate(ideas, 1):
            lines.append(f"  {i}. [{idea['type']}] {idea['project']}")
            lines.append(f"     Hook: {idea['hook'][:80]}")
        
        return "\n".join(lines)
    
    # Hybrid refine
    if "hybrid refine" in lower or "refine post" in lower:
        from tools.post_scheduler import hybrid_refine
        
        # Extract text after the command keyword
        text = user_input
        for pattern in ["hybrid refine", "refine post"]:
            idx = lower.find(pattern)
            if idx >= 0:
                text = user_input[idx + len(pattern):].strip()
                break
        
        if len(text) < 20:
            return "Please provide the post text to refine: 'hybrid refine <your post text>'"
        
        result = hybrid_refine(text)
        return f"\n📝 Hybrid Refined Post:\n{'─' * 50}\n{result}\n{'─' * 50}"
    
    return None


def _try_freelance(user_input: str):
    """
    Check if user_input is a freelance command. Returns result or None.
    Handles: gig generation, proposals, upwork bio, freelance monitoring.
    """
    lower = user_input.lower()
    
    # Generate all gigs
    if "generate all gigs" in lower or "create all gigs" in lower:
        return _handle_generate_all_gigs(user_input)
    
    # Generate single gig: "generate fiverr gig for mlops"
    gig_match = re.search(r'(?:generate|create)\s+(?:(fiverr|upwork)\s+)?gig\s+(?:for\s+)?(\w+)', lower)
    if gig_match:
        platform = gig_match.group(1) or "fiverr"
        service = gig_match.group(2)
        return _handle_generate_gig(service, platform)
    
    # Check new freelance projects
    if any(kw in lower for kw in ["check new freelance", "freelance projects", "new projects", "upwork projects"]):
        return _handle_freelance_monitor(user_input)
    
    # Write proposal: "write proposal for: [text]"
    if "write proposal" in lower or "generate proposal" in lower:
        return _handle_proposal(user_input)
    
    # Generate Upwork bio
    if "upwork bio" in lower or "upwork profile" in lower:
        return _handle_upwork_bio(user_input)
    
    return None


def _handle_generate_all_gigs(user_input: str) -> str:
    """Generate all 5 gig drafts."""
    from tools.gig_tools import generate_all_gigs
    from memory.excel_logger import log_gig
    
    # Detect platform
    platform = "fiverr"
    if "upwork" in user_input.lower():
        platform = "upwork"
    
    print(f"  → Generating all gigs for {platform}")
    gigs = generate_all_gigs(platform)
    
    # Log all gigs to Excel
    for gig in gigs:
        price_range = f"${gig.get('basic', {}).get('price_usd', '?')}-${gig.get('premium', {}).get('price_usd', '?')}"
        log_gig(platform, gig.get("service", ""), gig.get("title", ""), "draft", price=price_range)
    
    # Format summary
    lines = [f"\n✅ Generated {len(gigs)} gig drafts for {platform}\n{'═' * 50}"]
    for i, gig in enumerate(gigs, 1):
        lines.append(f"\n{i}. [{gig.get('service', '')}] {gig.get('title', '')}")
        lines.append(f"   💰 ${gig.get('basic', {}).get('price_usd', '?')}-${gig.get('premium', {}).get('price_usd', '?')}")
        lines.append(f"   🏷️ {', '.join(gig.get('tags', [])[:5])}")
    lines.append(f"\n📁 Drafts saved to: memory/gig_drafts/")
    
    log_content("gig_batch", f"{len(gigs)} gigs generated", "generated", platform)
    return "\n".join(lines)


def _handle_generate_gig(service: str, platform: str) -> str:
    """Generate a single gig draft."""
    from tools.gig_tools import generate_gig
    from memory.excel_logger import log_gig
    
    print(f"  → Generating {platform} gig for: {service}")
    gig = generate_gig(service, platform)
    
    if "error" in gig:
        return gig["error"]
    
    # Log to Excel
    price_range = f"${gig.get('basic', {}).get('price_usd', '?')}-${gig.get('premium', {}).get('price_usd', '?')}"
    log_gig(platform, service, gig.get("title", ""), "draft", price=price_range)
    
    log_content("gig_description", json.dumps(gig), "generated", platform)
    return gig


def _handle_freelance_monitor(user_input: str) -> str:
    """Check for new freelance projects."""
    from connectors.freelance_monitor import check_new_projects, display_projects
    
    # Extract custom keywords if provided
    lower = user_input.lower()
    keywords = None
    if "for " in lower:
        after = lower.split("for ", 1)[1].strip()
        keywords = [k.strip() for k in after.split(",") if k.strip()]
    
    print(f"  → Checking freelance projects" + (f" for: {keywords}" if keywords else ""))
    projects = check_new_projects(keywords)
    
    result = display_projects(projects)
    log_action("freelance_monitor", f"{len(projects)} new projects found", "completed")
    return result


def _handle_proposal(user_input: str) -> str:
    """Generate a freelance proposal."""
    from tools.gig_tools import generate_proposal
    
    # Extract job text after "for:" or "for "
    job_text = user_input
    for sep in ["for:", "for "]:
        if sep in user_input.lower():
            idx = user_input.lower().index(sep) + len(sep)
            job_text = user_input[idx:].strip()
            break
    
    print(f"  → Generating proposal for: {job_text[:60]}...")
    result = generate_proposal(job_text)
    log_content("proposal", result, "generated")
    return result


def _handle_upwork_bio(user_input: str) -> str:
    """Generate an Upwork profile bio."""
    from tools.gig_tools import generate_upwork_bio
    
    # Detect focus
    lower = user_input.lower()
    focus = "ml_engineer"  # default
    if "backend" in lower:
        focus = "backend_dev"
    elif "blockchain" in lower or "web3" in lower:
        focus = "blockchain_dev"
    
    print(f"  → Generating Upwork bio (focus: {focus})")
    result = generate_upwork_bio(focus)
    log_content("upwork_bio", result, "generated", "upwork")
    return result


def _parse_job_query(user_input: str) -> tuple:
    """Parse a job search command into (query, location)."""
    lower = user_input.lower()
    
    # Remove command prefixes
    for prefix in ["find ", "search for ", "search ", "look for ", "get "]:
        if lower.startswith(prefix):
            lower = lower[len(prefix):]
            break
    
    # Extract location
    location = "remote"  # default
    location_keywords = [
        "in pakistan", "in usa", "in uk", "in europe", "in india",
        "in lahore", "in karachi", "in islamabad",
        "remote", "on-site", "hybrid",
    ]
    for loc in location_keywords:
        if loc in lower:
            location = loc.replace("in ", "").strip()
            lower = lower.replace(loc, "").strip()
            break
    
    # Clean up the query
    for noise in ["jobs", "job", "internships", "internship", "positions", "openings"]:
        lower = lower.replace(noise, "").strip()
    
    query = lower.strip() or "AI Engineer"
    return query, location


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
        print('  python agent.py "find AI jobs remote"')
        print('  python agent.py "find Python internships Pakistan"')
        print('  python agent.py "show my applications"')


if __name__ == "__main__":
    main()
