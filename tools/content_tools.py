"""
content_tools.py — BilalAgent v2.0 Content Generation Tools
LinkedIn posts, cover letters, and gig descriptions.
All content is grounded in REAL GitHub data (README, docs/, commits).
"""

import sys
import os
import json
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.content_agent import generate
from tools.model_runner import get_free_ram
from connectors.github_connector import GitHubConnector


def _load_profile() -> dict:
    """Load profile for context."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "profile.yaml")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _get_github_context() -> str:
    """Get general GitHub summary for broad context."""
    try:
        gh = GitHubConnector()
        return gh.get_summary()
    except Exception:
        return ""


def _find_repo_name(project_name: str) -> str | None:
    """Fuzzy match a project name to an actual GitHub repo name."""
    try:
        gh = GitHubConnector()
        repos = gh.get_repos()
        search = project_name.lower().replace("-", "").replace("_", "").replace(" ", "")
        
        # Exact match first
        for r in repos:
            if r["name"].lower() == project_name.lower():
                return r["name"]
        
        # Fuzzy match
        for r in repos:
            normalized = r["name"].lower().replace("-", "").replace("_", "")
            if search in normalized or normalized in search:
                return r["name"]
        
        return None
    except Exception:
        return None


def _get_deep_repo_context(project_name: str) -> str:
    """
    Fetch DEEP context for a repo: README + docs/ folder + CHANGELOG + package.json + commits.
    This is the PRIMARY data source for all content generation.
    """
    gh = GitHubConnector()
    
    # Fuzzy match to actual repo name
    repo_name = _find_repo_name(project_name)
    if not repo_name:
        print(f"  [CONTENT] Repo '{project_name}' not found on GitHub, using general context")
        return _get_github_context()
    
    print(f"  [CONTENT] Matched repo: {repo_name}")
    print(f"  [CONTENT] Fetching deep context (README + docs/ + commits)...")
    
    raw = gh.get_deep_repo_context(repo_name)
    
    # Compress into structured summary for the model
    return _compress_context(raw)


def _compress_context(raw_context: str) -> str:
    """
    Compress raw deep context into a structured, model-friendly summary.
    UNIVERSAL — works for ANY repo (Python SDK, web app, CLI tool, etc.).
    Keeps: README (first 2000 chars), last 8 commits, docs snippet.
    """
    lines = raw_context.split("\n")
    
    metadata = []
    readme_lines = []
    commit_lines = []
    docs_lines = []
    
    current_section = None
    readme_chars = 0
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            # Keep blank lines in README for readability
            if current_section == "readme" and readme_chars < 2000:
                readme_lines.append("")
            continue
        
        # Section detection
        if stripped.startswith("=== PROJECT:"):
            current_section = "metadata"
            metadata.append(stripped)
            continue
        elif stripped.startswith("=== README"):
            current_section = "readme"
            continue
        elif "COMMITS" in stripped and stripped.startswith("==="):
            current_section = "commits"
            continue
        elif stripped.startswith("=== "):
            # Any other === section goes to docs
            current_section = "docs"
            docs_lines.append(stripped)
            continue
        
        # Metadata
        if current_section == "metadata":
            if any(stripped.startswith(k) for k in ["Language:", "Description:", "URL:", "Last updated:", "Stars:", "Forks:"]):
                metadata.append(stripped)
        
        # README — keep first 2000 chars (the most important content)
        elif current_section == "readme":
            if readme_chars < 2000:
                readme_lines.append(stripped)
                readme_chars += len(stripped) + 1
        
        # Commits
        elif current_section == "commits":
            if stripped.startswith("- "):
                commit_lines.append(stripped)
        
        # Docs (FEATURES.md, CHANGELOG, etc.)
        elif current_section == "docs":
            if len("\n".join(docs_lines)) < 500:
                docs_lines.append(stripped)
    
    # Build compressed output
    parts = []
    
    # Metadata first
    if metadata:
        parts.extend(metadata)
        parts.append("")
    
    # README — the most important section
    if readme_lines:
        parts.append("=== README ===")
        parts.extend(readme_lines)
        parts.append("")
    
    # Recent commits — last 8
    if commit_lines:
        parts.append("=== RECENT COMMITS ===")
        for c in commit_lines[-8:]:
            msg = c[:120]  # Trim long commit messages
            parts.append(msg)
        parts.append("")
    
    # Docs snippet
    if docs_lines:
        parts.append("=== DOCS SNIPPET ===")
        parts.extend(docs_lines[:20])
    
    result = "\n".join(parts)
    print(f"  [CONTENT] Context: {len(result)} chars (README+commits+docs)")
    return result


# ─────────────────────────────────────────────────────
# Hard facts for known repos (prevents hallucination)
# ─────────────────────────────────────────────────────

BASEPY_FACTS = """
basepy-sdk is a production-grade Python SDK for the Base L2 blockchain (Ethereum L2 by Coinbase).

KEY FEATURES:
- Circuit breaker pattern: auto-pauses requests when RPC errors spike
- Rate limiting: token bucket algorithm, prevents API throttling
- Intelligent caching: reduces redundant RPC calls, saves ~$80 per million requests
- L1 + L2 fee calculation: accurate gas estimation for Base transactions
- Async-first design: built on web3.py with asyncio support
- Comprehensive benchmarks: documented performance metrics
- Production-ready: 2-5x faster operations vs naive web3.py usage

TECHNICAL STACK: Python, web3.py, asyncio, Base L2, Ethereum
AUTHOR: Bilal Ahmad Sheikh, AI Engineering student at GIKI Pakistan
REPO: https://github.com/bilalahmadsheikh/basepy
"""


def _get_repo_facts(project_name: str, user_request: str = "") -> str:
    """Inject hard facts for known repos to prevent hallucination."""
    lower_name = project_name.lower()
    lower_req = user_request.lower() if user_request else ""
    
    if "basepy" in lower_name or "basepy" in lower_req or "base l2" in lower_req or "blockchain sdk" in lower_req:
        return f"ABOUT THIS PROJECT (verified facts — use these):\n{BASEPY_FACTS}"
    
    return ""


def _check_post_quality(post: str, repo_name: str, task: str) -> dict:
    """Catch obvious hallucinations before showing to user."""
    issues = []
    
    # Check if post mentions completely unrelated topics
    unrelated_keywords = [
        "university admission", "entry test", "kanban",
        "sop helper", "autofill university", "admission chance",
        "swipe/discovery", "chrome extension autofill",
    ]
    for kw in unrelated_keywords:
        if kw.lower() in post.lower():
            issues.append(f"Contains unrelated topic: '{kw}'")
    
    # Check minimum length
    words = len(post.split())
    if words < 80:
        issues.append(f"Too short: {words} words")
    if words > 600:
        issues.append(f"Too long: {words} words")
    
    # Check repo name is mentioned (loosely)
    repo_lower = repo_name.lower().replace("-", "").replace("_", "")
    post_lower = post.lower().replace("-", "").replace("_", "")
    if repo_lower not in post_lower and repo_name.lower() not in post.lower():
        issues.append(f"Does not mention repo name: {repo_name}")
    
    if issues:
        print(f"  [QUALITY CHECK] Issues found:")
        for issue in issues:
            print(f"    - {issue}")
        return {"pass": False, "issues": issues}
    
    print(f"  [QUALITY CHECK] Post looks relevant ({words} words)")
    return {"pass": True, "issues": []}


def _get_multi_repo_context(repo_names: list) -> str:
    """
    Fetch deep context for MULTIPLE repos.
    Used by cover letters and gig descriptions that reference several projects.
    Each repo gets full _compress_context() treatment (same as LinkedIn posts).
    """
    gh = GitHubConnector()
    sections = []
    
    for name in repo_names[:3]:  # Max 3 repos to keep prompt manageable
        repo_name = _find_repo_name(name)
        if repo_name:
            print(f"  [CONTENT] Fetching deep context for: {repo_name}")
            raw = gh.get_deep_repo_context(repo_name)
            compressed = _compress_context(raw)
            sections.append(compressed)
    
    if not sections:
        return _get_github_context()
    
    return "\n\n" + ("\n\n---\n\n".join(sections))


def _find_relevant_repos(job_title: str, service_type: str = "") -> list:
    """
    Find repos most relevant to a job title or service type by matching
    languages, descriptions, and repo names.
    """
    gh = GitHubConnector()
    repos = gh.get_repos()
    
    search_terms = (job_title + " " + service_type).lower().split()
    
    scored = []
    for r in repos:
        score = 0
        text = f"{r['name']} {r['description']} {r['language']}".lower()
        for term in search_terms:
            if term in text:
                score += 1
        if r['language']:
            score += 0.5  # Bonus for having a detected language
        if r['description']:
            score += 0.5  # Bonus for having a description
        scored.append((r['name'], score))
    
    scored.sort(key=lambda x: x[1], reverse=True)
    return [name for name, _ in scored[:3] if _ > 0]


# ─────────────────────────────────────────────────────
# LinkedIn Post Generator
# ─────────────────────────────────────────────────────

def generate_linkedin_post(project_name: str, post_type: str = "project_showcase", user_request: str = "") -> str:
    """
    Generate a LinkedIn post about a project using DEEP GitHub data
    (README + docs/ + CHANGELOG + commits).
    
    Args:
        project_name: Name of the project to write about
        post_type: One of 'project_showcase', 'learning_update', 'achievement', 'opinion'
        user_request: The user's original request text — included in prompt for custom instructions
        
    Returns:
        LinkedIn post text (with hashtags)"""
    # Load profile for dynamic name injection
    profile = _load_profile()
    profile_name = profile.get("personal", {}).get("name", "the developer")
    
    # Fetch DEEP repo data (README + docs/ + commits + metadata)
    repo_ctx = _get_deep_repo_context(project_name)
    
    type_instructions = {
        "project_showcase": "Write a project showcase post. Lead with the problem this project solves, show the technical approach from the README, highlight actual results and features documented in the repo.",
        "learning_update": "Write a learning journey post. Based on the commits and docs, share what was learned building this, specific challenges, what the project does.",
        "achievement": "Write an achievement announcement. Use specific features from the README and docs to celebrate what was built.",
        "opinion": "Write a thought-leadership opinion post. Take a stance on a technical topic related to this project's domain.",
    }
    
    instruction = type_instructions.get(post_type, type_instructions["project_showcase"])
    
    # Inject hard facts for known repos
    fact_block = _get_repo_facts(project_name, user_request)
    
    prompt = f"""You are writing a LinkedIn post for {profile_name}.

{fact_block}

ACTUAL REPO CONTEXT:
{repo_ctx}

Post type: {post_type}
{instruction}

USER'S REQUEST: "{user_request}"
Honor the user's request — if they asked to focus on specific features, prioritize those.

WRITE A LINKEDIN POST THAT:
- Opens with a specific technical problem developers face (not generic)
- Mentions at least 2 specific features from the context above with real numbers if available
- Shows {profile_name}'s perspective as a builder creating production-grade tools
- Is 200-280 words (not longer)
- Ends with: repo link, 4-6 relevant hashtags
- NO image placeholders
- NO mention of topics NOT in the repo context (no university admissions, no unrelated projects)
- Write in first person as {profile_name}
- NO preamble like "Here's a draft" — output ONLY the post itself

Post:"""

    result = generate(prompt, content_type="linkedin_post")
    
    # Post-processing: strip AI preamble
    result = _clean_post(result, project_name)
    
    # Hallucination guard — catch unrelated content
    quality = _check_post_quality(result, project_name, user_request)
    if not quality["pass"]:
        print("  [QUALITY] Regenerating with stricter prompt (temperature=0.3)...")
        strict_prompt = prompt + "\n\nCRITICAL: Only mention facts from the repo context above. Do NOT invent features."
        from agents.content_agent import generate as _gen
        result = _gen(strict_prompt, content_type="linkedin_post")
        result = _clean_post(result, project_name)
    
    # Enforce character limit (generous for detailed posts)
    if len(result) > 3500:
        truncated = result[:3500]
        last_period = truncated.rfind('.')
        if last_period > 2500:
            result = truncated[:last_period + 1]
    
    # Ensure repo link is present (dynamic from profile)
    profile = _load_profile()
    github_user = profile.get("personal", {}).get("github", "")
    if not github_user:
        # Skip repo link if GitHub username not in profile
        pass
    else:
        repo_name = _find_repo_name(project_name) or project_name
        repo_url = f"https://github.com/{github_user}/{repo_name}"
        if repo_url not in result and "github.com" not in result:
            result += f"\n\n🔗 {repo_url}"
    
    # Ensure hashtags are present
    if "#" not in result:
        result += f"\n\n#OpenSource #GitHub #WebDev #BuildInPublic"
    
    return result


def _clean_post(text: str, project_name: str) -> str:
    """Strip AI preamble and meta-commentary from generated posts."""
    lines = text.strip().split("\n")
    clean_lines = []
    skip_preamble = True
    
    for line in lines:
        lower = line.strip().lower()
        
        # Skip known preamble patterns
        if skip_preamble:
            if any(p in lower for p in [
                "here's a", "here is a", "here's the", "okay,", "sure,",
                "here's a linkedin", "draft for", "crafted in the style",
                "aiming for", "approximately"
            ]):
                continue
            if lower == "---":
                continue
            if lower == "":
                continue
            skip_preamble = False
        
        # Skip trailing meta-commentary
        if any(p in lower for p in [
            "important notes", "considerations:", "to help me refine",
            "could you share", "here are some"
        ]):
            break
        if lower == "---" and len(clean_lines) > 5:
            break
        
        clean_lines.append(line)
    
    return "\n".join(clean_lines).strip()


# ─────────────────────────────────────────────────────
# Cover Letter Generator
# ─────────────────────────────────────────────────────

def generate_cover_letter(job_title: str, company: str, job_description: str = "", user_request: str = "") -> str:
    """
    Generate a targeted cover letter using REAL GitHub project data.
    Automatically finds the most relevant repos for the job.
    
    Args:
        job_title: Position title
        company: Company name
        job_description: Optional job description for tailoring
        
    Returns:
        Cover letter (250-350 words)
    """
    # Find which repos are most relevant to this job
    relevant_repos = _find_relevant_repos(job_title)
    
    if relevant_repos:
        print(f"  [CONTENT] Most relevant repos for '{job_title}': {relevant_repos}")
        project_ctx = _get_multi_repo_context(relevant_repos)
    else:
        project_ctx = _get_github_context()
    
    # Load profile for dynamic name injection
    profile = _load_profile()
    profile_name = profile.get("personal", {}).get("name", "the developer")
    profile_degree = profile.get("personal", {}).get("degree", "")
    
    prompt = f"""Write a cover letter for this position:

Job Title: {job_title}
Company: {company}
{f"Job Description: {job_description}" if job_description else ""}

My REAL project data (from GitHub repos — README, docs, commits):
{project_ctx}

General GitHub profile:
{_get_github_context()}

Structure (3 paragraphs ONLY):
1. Opening: Why THIS role at THIS company specifically excites me. Be specific about the company.
2. Evidence: My most relevant project(s) with REAL details from the README/docs above. Reference actual features, architecture, and tech stacks. Do NOT invent metrics.
3. Closing: Enthusiastic next step, mention availability for interview.

CRITICAL RULES:
- ONLY reference project details that appear in the README/docs data above
- NEVER invent performance numbers, user counts, or metrics not in the data
- Reference actual repo names, actual tech stacks, actual features from the docs
- 250-350 words STRICTLY
- Sound professional but warm, like a real human wrote it
- NO generic phrases like "I am writing to express my interest"
- Write as {profile_name}, {profile_degree}
- Sign off: "Best regards, {profile_name}"

USER'S REQUEST: "{user_request}"
Honor the user's specific instructions above if any.
"""

    return generate(prompt, content_type="cover_letter")


# ─────────────────────────────────────────────────────
# Gig Description Generator
# ─────────────────────────────────────────────────────

def generate_gig_description(service_type: str, platform: str = "fiverr", user_request: str = "") -> dict:
    """
    Generate a freelance gig description using REAL GitHub project data.
    Automatically finds relevant repos as portfolio evidence.
    
    Args:
        service_type: One of 'mlops', 'chatbot', 'blockchain', 'data_science', 'backend'
        platform: Target platform ('fiverr', 'upwork')
        
    Returns:
        dict with keys: title, description, tags, packages (basic/standard/premium)
    """
    # Find repos relevant to this service type
    relevant_repos = _find_relevant_repos(service_type)
    
    if relevant_repos:
        print(f"  [CONTENT] Portfolio repos for '{service_type}': {relevant_repos}")
        project_ctx = _get_multi_repo_context(relevant_repos)
    else:
        project_ctx = _get_github_context()
    
    prompt = f"""Create a {platform} gig listing for: {service_type}

My REAL portfolio projects (from GitHub — README, docs, commits):
{project_ctx}

General GitHub profile:
{_get_github_context()}

Return a JSON object with EXACTLY this structure:
{{
    "title": "catchy gig title (max 80 chars)",
    "description": "detailed gig description (200-300 words). Reference REAL features and tech stacks from the repos above. Explain what the client gets. Sound professional.",
    "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
    "packages": {{
        "basic": {{
            "name": "Basic",
            "price": "$XX",
            "delivery": "X days",
            "description": "what's included",
            "revisions": 1
        }},
        "standard": {{
            "name": "Standard",
            "price": "$XX",
            "delivery": "X days",
            "description": "what's included",
            "revisions": 2
        }},
        "premium": {{
            "name": "Premium",
            "price": "$XX",
            "delivery": "X days",
            "description": "what's included",
            "revisions": 3
        }}
    }}
}}

CRITICAL RULES:
- ONLY reference tech stacks, features, and capabilities demonstrated in the repos above
- NEVER invent metrics or portfolio items not in the data
- Price based on actual demonstrated skill level
-CRITICAL: Output ONLY valid JSON. No explanation, no markdown — just the JSON object.

USER'S REQUEST: "{user_request}"
Honor the user's specific instructions above if any.
"""

    raw = generate(prompt, content_type="gig_description")
    return _parse_gig_json(raw, service_type, platform)


def _parse_gig_json(raw: str, service_type: str, platform: str) -> dict:
    """Parse gig JSON from model output, with fallback."""
    text = raw.strip()
    
    # Strip markdown fences
    if "```" in text:
        lines = text.split("\n")
        json_lines = []
        inside = False
        for line in lines:
            if line.strip().startswith("```"):
                inside = not inside
                continue
            if inside:
                json_lines.append(line)
        text = "\n".join(json_lines).strip()
    
    # Find JSON object
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        text = text[start:end]
    
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {
            "title": f"{service_type.replace('_', ' ').title()} Services on {platform.title()}",
            "description": raw,
            "tags": [service_type, "python", "ai", "ml", "developer"],
            "packages": {
                "basic": {"name": "Basic", "price": "$50", "delivery": "3 days", "description": "Basic implementation", "revisions": 1},
                "standard": {"name": "Standard", "price": "$100", "delivery": "5 days", "description": "Full implementation", "revisions": 2},
                "premium": {"name": "Premium", "price": "$200", "delivery": "7 days", "description": "Full implementation + support", "revisions": 3},
            }
        }


if __name__ == "__main__":
    print("=" * 60)
    print("Content Tools Test")
    print(f"Free RAM: {get_free_ram():.1f}GB")
    print("=" * 60)
    
    # Test LinkedIn post
    print("\n[TEST 1] LinkedIn Post:")
    post = generate_linkedin_post("IlmSeUrooj", "project_showcase")
    print(post)
    print(f"\n({len(post)} chars)")
