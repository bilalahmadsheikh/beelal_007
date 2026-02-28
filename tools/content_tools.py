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
    
    return gh.get_deep_repo_context(repo_name)


def _get_multi_repo_context(repo_names: list) -> str:
    """
    Fetch deep context for MULTIPLE repos.
    Used by cover letters and gig descriptions that reference several projects.
    """
    gh = GitHubConnector()
    sections = []
    
    for name in repo_names[:3]:  # Max 3 repos to keep prompt manageable
        repo_name = _find_repo_name(name)
        if repo_name:
            print(f"  [CONTENT] Fetching deep context for: {repo_name}")
            ctx = gh.get_deep_repo_context(repo_name)
            sections.append(ctx)
    
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

def generate_linkedin_post(project_name: str, post_type: str = "project_showcase") -> str:
    """
    Generate a LinkedIn post about a project using DEEP GitHub data
    (README + docs/ + CHANGELOG + commits).
    
    Args:
        project_name: Name of the project to write about
        post_type: One of 'project_showcase', 'learning_update', 'achievement', 'opinion'
        
    Returns:
        LinkedIn post text (max 1300 chars, with hashtags)
    """
    # Fetch DEEP repo data (README + docs/ + commits + metadata)
    repo_ctx = _get_deep_repo_context(project_name)
    
    type_instructions = {
        "project_showcase": "Write a project showcase post. Lead with the problem this project solves, show the technical approach from the README, highlight actual results and features documented in the repo.",
        "learning_update": "Write a learning journey post. Based on the commits and docs, share what was learned building this, specific challenges, what the project does.",
        "achievement": "Write an achievement announcement. Use specific features from the README and docs to celebrate what was built.",
        "opinion": "Write a thought-leadership opinion post. Take a stance on a technical topic related to this project's domain.",
    }
    
    instruction = type_instructions.get(post_type, type_instructions["project_showcase"])
    
    prompt = f"""Write a LinkedIn post about this project. Here is ALL the real data from the repo:

{repo_ctx}

Post type: {post_type}
{instruction}

WRITE THE POST WITH THIS FLOW:

1. THE PROBLEM (3-4 sentences):
   Open with the real-world problem this project addresses. Make it personal — "As a student in Pakistan, I watched my friends..." or "Every admission season, students across Pakistan face...". Paint the picture so non-technical readers FEEL the frustration. Why does this matter? Who struggles with this?

2. THE SOLUTION — HOW WE BUILT IT (3-4 sentences):
   Now go technical. Name the exact architecture: what framework, what database, what APIs. Explain the key design decisions from the docs — WHY Next.js? WHY Supabase? WHY a Chrome Extension? Connect each tech choice back to solving the problem from section 1.

3. STANDOUT FEATURES (3-4 sentences):
   Pick 2-3 specific features from the FEATURES.md or README and describe them in detail. Don't just list them — explain what they DO and why they're useful. Example: "The swipe-based discovery lets students browse universities like Tinder — swipe right to save, left to skip. Behind the scenes, a smart filter considers grade level, program type, and hostel availability."

4. WHAT'S NEXT + REPO LINK (1-2 sentences):
   End with what you're working on next (from commits or PROGRESS.md if available), and link the repo.

CRITICAL RULES:
- ONLY use facts from the data above — NEVER invent metrics or user counts
- Be BOTH human (the story, the why) AND technical (the how, the architecture)
- Write detailed paragraphs, NOT bullet points — this should feel like a story
- TARGET 250-350 words (longer than typical, but more engaging)
- NO preamble like "Here's a draft" — output ONLY the post itself
- Include the actual GitHub repo URL from the data
- End with 3-5 relevant hashtags
- Write as Bilal Ahmad Sheikh, first person"""

    result = generate(prompt, content_type="linkedin_post")
    
    # Post-processing: strip AI preamble
    result = _clean_post(result, project_name)
    
    # Enforce character limit (generous for longer posts)
    if len(result) > 2200:
        truncated = result[:2200]
        last_period = truncated.rfind('.')
        if last_period > 1500:
            result = truncated[:last_period + 1]
    
    # Ensure repo link is present
    repo_name = _find_repo_name(project_name) or project_name
    repo_url = f"https://github.com/bilalahmadsheikh/{repo_name}"
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

def generate_cover_letter(job_title: str, company: str, job_description: str = "") -> str:
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
- Write as Bilal Ahmad Sheikh, AI Engineering student (3rd year, 6th semester)
- Sign off: "Best regards, Bilal Ahmad Sheikh"
"""

    return generate(prompt, content_type="cover_letter")


# ─────────────────────────────────────────────────────
# Gig Description Generator
# ─────────────────────────────────────────────────────

def generate_gig_description(service_type: str, platform: str = "fiverr") -> dict:
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
- Output ONLY the JSON. No explanation, no markdown fences."""

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
