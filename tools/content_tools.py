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
    Extracts: metadata, tech stack, website features, chrome extension features,
    architecture notes, build phases, commits. Filters out noise.
    """
    lines = raw_context.split("\n")
    
    metadata = []
    website_features = []
    extension_features = []
    architecture = []
    phases = []
    commits = []
    tech_deps = []
    
    current_section = None
    in_extension_block = False
    
    # Noise patterns to skip
    noise = [
        "section: prerequisites", "section: 1.", "section: 2.", "section: 3.",
        "section: 4.", "section: 5.", "clone and install", "environment variable",
        "run the website", "load the extension", "feature: quick start",
        "feature: decision", "decision 1:", "decision 2:", "decision 3:",
        "decision 4:", "decision 5:", "decision 6:", "decision 7:",
        "decision 8:", "decision 9:", "decision 10:", "decision 11:",
        "decision 12:", "date:**", "choice:**", "rationale:**",
        "status:**", "education system aware:**", "connected to:**",
        "section: files created", "section: step-by-step", "section: what was built",
        "files created", "src/app/", "src/data/", "src/components/",
        "src/utils/", "`src/", "section: tier 1:", "section: tier 2:",
        "target fields**", "iteration filter:", "iteration field/",
        "iteration degree", "docs/", "feature: project timeline",
        "feature: automated scraper", "feature: iteration",
    ]
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        
        # Section detection
        if stripped.startswith("=== PROJECT:"):
            current_section = "metadata"
            metadata.append(stripped)
            continue
        elif stripped.startswith("=== README"):
            current_section = "features"
            in_extension_block = False
            continue
        elif stripped.startswith("=== package.json"):
            current_section = "tech_stack"
            continue
        elif "architecture" in stripped.lower() and stripped.startswith("==="):
            current_section = "architecture"
            continue
        elif "FEATURES" in stripped and stripped.startswith("==="):
            current_section = "features"
            in_extension_block = False
            continue
        elif "PROGRESS" in stripped and stripped.startswith("==="):
            current_section = "phases"
            continue
        elif "CHANGELOG" in stripped and stripped.startswith("==="):
            current_section = "phases"
            continue
        elif "SCHEMA" in stripped and stripped.startswith("==="):
            current_section = "architecture"
            continue
        elif "DECISION" in stripped.upper() and stripped.startswith("==="):
            current_section = "skip"
            continue
        elif "DATA-SOURCE" in stripped.upper() and stripped.startswith("==="):
            current_section = "skip"
            continue
        elif "DEVELOPMENT-HISTORY" in stripped.upper() and stripped.startswith("==="):
            current_section = "phases"
            continue
        elif "COMMITS" in stripped and stripped.startswith("==="):
            current_section = "commits"
            continue
        elif stripped.startswith("=== Other docs"):
            current_section = "skip"
            continue
        elif stripped.startswith("=== "):
            current_section = "features"
            continue
        
        if current_section == "skip":
            continue
        
        # Check noise
        lower = stripped.lower()
        if any(n in lower for n in noise):
            continue
        
        # Metadata
        if current_section == "metadata":
            if any(stripped.startswith(k) for k in ["Language:", "Description:", "URL:", "Last updated:"]):
                metadata.append(stripped)
        
        # Features — detect Chrome Extension block
        elif current_section == "features":
            if "chrome extension" in lower and ("section:" in lower or stripped.startswith("###")):
                in_extension_block = True
                continue
            elif ("section: website" in lower or "section: one profile" in lower):
                in_extension_block = False
                continue
            elif stripped.startswith("Section: ") and "supported" not in lower:
                continue
            
            # Skip how-it-works lines and non-feature content
            if lower.startswith("how it works:**") or lower.startswith("what it does:**"):
                continue
            
            # Extract actual features
            feature_line = None
            if stripped.startswith("- **") or (stripped.startswith("**") and "—" in stripped):
                feature_line = stripped
            elif stripped.startswith("Feature: ") and "decision" not in lower:
                name = stripped[9:]
                if name and len(name) > 5:
                    feature_line = name
            
            if feature_line:
                target = extension_features if in_extension_block else website_features
                target.append(feature_line)
        
        # Tech stack
        elif current_section == "tech_stack":
            if '"dependencies"' in stripped or '"devDependencies"' in stripped:
                continue
            if '"' in stripped and ':' in stripped:
                try:
                    key = stripped.split('"')[1]
                    if key not in ("name", "version", "private", "scripts", "dev", "build", "start", "lint",
                                   "test-scrapers", "test-file-updates", "dependencies", "devDependencies"):
                        tech_deps.append(key)
                except IndexError:
                    pass
        
        # Architecture
        elif current_section == "architecture":
            if any(kw in lower for kw in ["next.js", "supabase", "app router", "component", "rls",
                                           "ci/cd", "chrome", "autofill", "3-tier", "78 column", "profile"]):
                architecture.append(stripped)
            elif stripped.startswith("- [x]"):
                phases.append(stripped[6:])
        
        # Phases
        elif current_section == "phases":
            if stripped.startswith("- [x]"):
                phases.append(stripped[6:])
            elif stripped.startswith("| ") and "---" not in stripped:
                parts = [p.strip() for p in stripped.split("|") if p.strip()]
                if len(parts) >= 3 and parts[0][0].isdigit():
                    phases.append(f"Iteration {parts[0]}: {parts[2]} ({parts[1]})")
        
        # Commits
        elif current_section == "commits":
            if stripped.startswith("- "):
                commits.append(stripped)
    
    # Build compressed output
    out = []
    
    # Metadata
    out.extend(metadata)
    out.append("")
    
    # Tech stack
    if tech_deps:
        out.append(f"Tech stack: {', '.join(tech_deps[:10])}")
        out.append("")
    
    # Architecture
    if architecture:
        out.append("ARCHITECTURE:")
        seen = set()
        for a in architecture:
            clean = a.strip().strip("#").strip()
            if clean not in seen and len(clean) > 10:
                seen.add(clean)
                out.append(f"  • {clean}")
        out.append("")
    
    # Website features
    if website_features:
        out.append("WEBSITE FEATURES:")
        seen = set()
        for f in website_features:
            clean = f.strip("- *").strip()
            if clean and clean not in seen and len(clean) > 10:
                seen.add(clean)
                out.append(f"  • {clean}")
        out.append("")
    
    # Chrome Extension features
    if extension_features:
        out.append("CHROME EXTENSION FEATURES:")
        seen = set()
        for f in extension_features:
            clean = f.strip("- *").strip()
            if clean and clean not in seen and len(clean) > 10:
                seen.add(clean)
                out.append(f"  • {clean}")
        out.append("")
    
    # Build phases
    if phases:
        out.append("BUILD JOURNEY:")
        seen = set()
        for p in phases[:12]:
            if p not in seen:
                seen.add(p)
                out.append(f"  • {p}")
        out.append("")
    
    # Commits
    if commits:
        out.append("RECENT WORK:")
        for c in commits[:6]:
            out.append(f"  {c}")
    
    compressed = "\n".join(out)
    print(f"  [CONTENT] Context compressed: {len(raw_context)} → {len(compressed)} chars")
    return compressed


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
    # Fetch DEEP repo data (README + docs/ + commits + metadata)
    repo_ctx = _get_deep_repo_context(project_name)
    
    type_instructions = {
        "project_showcase": "Write a project showcase post. Lead with the problem this project solves, show the technical approach from the README, highlight actual results and features documented in the repo.",
        "learning_update": "Write a learning journey post. Based on the commits and docs, share what was learned building this, specific challenges, what the project does.",
        "achievement": "Write an achievement announcement. Use specific features from the README and docs to celebrate what was built.",
        "opinion": "Write a thought-leadership opinion post. Take a stance on a technical topic related to this project's domain.",
    }
    
    instruction = type_instructions.get(post_type, type_instructions["project_showcase"])
    
    prompt = f"""Write a detailed LinkedIn post about this project. Here is ALL the real data from the repo:

{repo_ctx}

Post type: {post_type}
{instruction}

USER'S REQUEST: "{user_request}"
Honor the user's request above — if they asked to focus on specific features, architecture, or aspects, prioritize those in your post.

WRITE THE POST WITH THIS FLOW:

1. THE PROBLEM (3-4 sentences):
   Open with the real-world problem. Make it personal — "As a student in Pakistan, I watched my classmates..." or "Every admission season in Pakistan...". Paint the picture so readers FEEL the frustration. Who faces this problem? How bad is it?

2. THE SOLUTION — OUR APPROACH (3-4 sentences):
   Introduce the project and its core idea. Name the architecture: what framework (Next.js? React?), what database (Supabase?), what browser tech (Chrome Extension?). Explain the key design decisions — WHY these tech choices? Connect each choice back to solving the problem. If there's a CI/CD pipeline or scraper engine, mention it.

3. KEY FEATURES — BE COMPREHENSIVE (8-12 sentences):
   This is the BIGGEST section. Go through the README and FEATURES.md and list ALL the major features with detail. For EACH feature, explain what it does for the user in one sentence. Include features like:
   - The swipe/discovery system
   - The filter system (how many filters? what dimensions?)
   - The admission chance predictor (how does it work?)
   - The Chrome Extension autofill (3-tier system? how many universities?)
   - The profile system (how many sections? how many columns?)
   - The application dashboard (kanban board?)
   - Entry tests, scholarships, deadlines, comparison tools
   - Any AI features (SOP helper, field mapping?)
   DO NOT skip features — mention as many as the data supports.

4. BUILD JOURNEY (2-3 sentences):
   How many iterations/phases? What was the progression? Reference the CHANGELOG or PROGRESS docs.

5. WHAT'S NEXT + REPO LINK (1-2 sentences):
   End with what's coming next and the GitHub repo link.

6. HASHTAGS: 4-6 relevant hashtags

CRITICAL RULES:
- ONLY use facts from the data above — NEVER invent metrics or user counts
- TARGET 400-500 words — this should be a DETAILED post
- Write detailed paragraphs, NOT bullet points
- NO preamble like "Here's a draft" — output ONLY the post itself
- Include the actual GitHub repo URL
- Write as Bilal Ahmad Sheikh, first person"""

    result = generate(prompt, content_type="linkedin_post")
    
    # Post-processing: strip AI preamble
    result = _clean_post(result, project_name)
    
    # Enforce character limit (generous for detailed posts)
    if len(result) > 3500:
        truncated = result[:3500]
        last_period = truncated.rfind('.')
        if last_period > 2500:
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
