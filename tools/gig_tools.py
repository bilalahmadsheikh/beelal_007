"""
gig_tools.py — BilalAgent v2.0 Freelance Gig Generation Tools
Generates Fiverr/Upwork gigs, Upwork bios, and proposals using profile data.
All model calls through content_agent.generate() → gemma3:4b.
"""

import os
import sys
import json
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GIG_DRAFTS_DIR = os.path.join(PROJECT_ROOT, "memory", "gig_drafts")

# Service type definitions with pricing
SERVICE_CONFIG = {
    "mlops": {
        "label": "MLOps & ML Pipeline Development",
        "basic": {"price_usd": 20, "delivery_days": 3, "revisions": 1},
        "standard": {"price_usd": 65, "delivery_days": 7, "revisions": 2},
        "premium": {"price_usd": 130, "delivery_days": 14, "revisions": 3},
    },
    "chatbot": {
        "label": "AI Chatbot Development",
        "basic": {"price_usd": 25, "delivery_days": 3, "revisions": 1},
        "standard": {"price_usd": 75, "delivery_days": 7, "revisions": 2},
        "premium": {"price_usd": 150, "delivery_days": 14, "revisions": 3},
    },
    "blockchain": {
        "label": "Blockchain & Web3 Development",
        "basic": {"price_usd": 25, "delivery_days": 3, "revisions": 1},
        "standard": {"price_usd": 70, "delivery_days": 7, "revisions": 2},
        "premium": {"price_usd": 140, "delivery_days": 14, "revisions": 3},
    },
    "data_science": {
        "label": "Data Science & Analytics",
        "basic": {"price_usd": 15, "delivery_days": 2, "revisions": 1},
        "standard": {"price_usd": 50, "delivery_days": 5, "revisions": 2},
        "premium": {"price_usd": 100, "delivery_days": 10, "revisions": 3},
    },
    "backend": {
        "label": "Backend API Development",
        "basic": {"price_usd": 20, "delivery_days": 3, "revisions": 1},
        "standard": {"price_usd": 60, "delivery_days": 7, "revisions": 2},
        "premium": {"price_usd": 120, "delivery_days": 14, "revisions": 3},
    },
}

ALL_SERVICES = list(SERVICE_CONFIG.keys())


def _load_profile() -> dict:
    """Load profile from config/profile.yaml."""
    path = os.path.join(PROJECT_ROOT, "config", "profile.yaml")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _get_profile_context() -> str:
    """Build context string from profile for prompts."""
    profile = _load_profile()
    personal = profile.get("personal", {})
    projects = profile.get("projects", [])
    
    lines = [
        f"Name: {personal.get('name', '')}",
        f"Degree: {personal.get('degree', '')}",
        f"Skills: {', '.join(personal.get('skills', []))}",
        "\nProjects:",
    ]
    for p in projects:
        lines.append(f"- {p.get('name', '')}: {p.get('description', '')}")
        lines.append(f"  Tech: {', '.join(p.get('tech_stack', []))}")
        lines.append(f"  Highlight: {p.get('highlight', '')}")
    
    return "\n".join(lines)


def generate_gig(service: str, platform: str = "fiverr") -> dict:
    """
    Generate a complete freelance gig listing.
    
    Args:
        service: One of 'mlops', 'chatbot', 'blockchain', 'data_science', 'backend'
        platform: Target platform ('fiverr', 'upwork')
        
    Returns:
        dict with title, description, tags, basic/standard/premium packages,
        requirements, faq
    """
    from agents.content_agent import generate
    
    if service not in SERVICE_CONFIG:
        return {"error": f"Unknown service: {service}. Choose from: {ALL_SERVICES}"}
    
    config = SERVICE_CONFIG[service]
    profile_ctx = _get_profile_context()
    
    prompt = f"""Create a {platform} gig listing for: {config['label']}

My real profile and portfolio:
{profile_ctx}

Return a JSON object with EXACTLY this structure:
{{
    "title": "catchy gig title (max 80 chars, start with 'I will')",
    "description": "detailed gig description (250-350 words). MUST reference real metrics: 87% accuracy (ML project), 40% performance improvement (blockchain SDK), 90k customers (chatbot). Explain what the client gets. Sound professional and specific.",
    "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
    "requirements": "What I need from the client to start (2-3 bullet points)",
    "faq": [
        {{"q": "common question 1", "a": "answer"}},
        {{"q": "common question 2", "a": "answer"}}
    ],
    "basic": {{
        "title": "Basic",
        "description": "what's included in basic package",
        "price_usd": {config['basic']['price_usd']},
        "delivery_days": {config['basic']['delivery_days']},
        "revisions": {config['basic']['revisions']}
    }},
    "standard": {{
        "title": "Standard",
        "description": "what's included in standard package",
        "price_usd": {config['standard']['price_usd']},
        "delivery_days": {config['standard']['delivery_days']},
        "revisions": {config['standard']['revisions']}
    }},
    "premium": {{
        "title": "Premium",
        "description": "what's included in premium package",
        "price_usd": {config['premium']['price_usd']},
        "delivery_days": {config['premium']['delivery_days']},
        "revisions": {config['premium']['revisions']}
    }}
}}

CRITICAL: Output ONLY valid JSON. No explanation, no markdown fences — just the JSON object."""

    raw = generate(prompt, content_type="gig_description")
    result = _parse_gig_json(raw, service, platform, config)
    
    # Save draft
    _save_gig_draft(result, service, platform)
    
    return result


def _parse_gig_json(raw: str, service: str, platform: str, config: dict) -> dict:
    """Parse gig JSON from model output, with fallback."""
    text = raw.strip()
    
    # Strip markdown fences
    if "```" in text:
        lines = text.split("\n")
        json_lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(json_lines).strip()
    
    # Find JSON
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        text = text[start:end]
    
    try:
        result = json.loads(text)
        result["service"] = service
        result["platform"] = platform
        # Ensure packages have correct pricing from config
        for tier in ["basic", "standard", "premium"]:
            if tier in result and isinstance(result[tier], dict):
                result[tier]["price_usd"] = config[tier]["price_usd"]
                result[tier]["delivery_days"] = config[tier]["delivery_days"]
                result[tier]["revisions"] = config[tier]["revisions"]
        return result
    except (json.JSONDecodeError, TypeError):
        # Fallback
        return _fallback_gig(service, platform, config)


def _fallback_gig(service: str, platform: str, config: dict) -> dict:
    """Generate a fallback gig if model output fails to parse."""
    profile = _load_profile()
    name = profile.get("personal", {}).get("name", "Developer")
    
    return {
        "service": service,
        "platform": platform,
        "title": f"I will build {config['label'].lower()} solutions for your business",
        "description": f"Professional {config['label'].lower()} services by {name}. Experienced with Python, FastAPI, Docker, and modern tooling. Portfolio includes projects with 87% accuracy ML pipelines, 40% performance improvements, and systems serving 90k customers.",
        "tags": [service, "python", "fastapi", "ai", platform],
        "requirements": "Project requirements, timeline, and any existing codebase.",
        "faq": [
            {"q": "What technologies do you use?", "a": "Python, FastAPI, Docker, PostgreSQL, and cloud services."},
            {"q": "How long does a typical project take?", "a": f"{config['standard']['delivery_days']} days for a standard project."},
        ],
        "basic": {"title": "Basic", "description": "Basic implementation", **config["basic"]},
        "standard": {"title": "Standard", "description": "Full implementation with testing", **config["standard"]},
        "premium": {"title": "Premium", "description": "Complete solution with docs and support", **config["premium"]},
    }


def _save_gig_draft(gig: dict, service: str, platform: str) -> str:
    """Save gig draft to memory/gig_drafts/."""
    os.makedirs(GIG_DRAFTS_DIR, exist_ok=True)
    filename = f"{platform}_{service}.json"
    filepath = os.path.join(GIG_DRAFTS_DIR, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(gig, f, indent=2, ensure_ascii=False)
    
    print(f"[GIG] Draft saved: {filepath}")
    return filepath


def generate_all_gigs(platform: str = "fiverr") -> list:
    """
    Generate gig drafts for all 5 service types.
    
    Args:
        platform: Target platform
        
    Returns:
        List of gig dicts
    """
    results = []
    for i, service in enumerate(ALL_SERVICES, 1):
        print(f"\n[GIG] Generating {i}/{len(ALL_SERVICES)}: {service}...")
        gig = generate_gig(service, platform)
        results.append(gig)
        print(f"[GIG] ✅ {service}: {gig.get('title', '?')[:60]}")
    
    print(f"\n[GIG] All {len(results)} gig drafts saved to {GIG_DRAFTS_DIR}")
    return results


def generate_upwork_bio(focus: str = "ml_engineer") -> str:
    """
    Generate an Upwork profile bio.
    
    Args:
        focus: One of 'ml_engineer', 'backend_dev', 'blockchain_dev'
        
    Returns:
        Bio string (max 5000 chars)
    """
    from agents.content_agent import generate
    
    profile_ctx = _get_profile_context()
    
    focus_labels = {
        "ml_engineer": "Machine Learning Engineer",
        "backend_dev": "Backend Developer",
        "blockchain_dev": "Blockchain Developer",
    }
    focus_label = focus_labels.get(focus, focus)
    
    prompt = f"""Write an Upwork profile bio for a {focus_label}.

My real profile:
{profile_ctx}

RULES:
- Max 5000 characters
- Professional but personable tone
- Start with a strong opening hook (not "I am a...")
- Reference REAL project metrics: 87% accuracy (Purchasing Power Prediction), 40% performance improvement (basepy-sdk), 90k customers (WhatsApp AI Chatbot)
- Mention actual tech stacks from the projects
- Include a call to action at the end
- Structure: Hook → Experience → Projects → Skills → CTA
- NO invented metrics or projects
- Sound like a real person, not a template"""

    result = generate(prompt, content_type="bio")
    
    # Enforce 5000 char limit
    if len(result) > 5000:
        result = result[:4950]
        last_sentence = result.rfind(".")
        if last_sentence > 4000:
            result = result[:last_sentence + 1]
    
    # Save draft
    os.makedirs(GIG_DRAFTS_DIR, exist_ok=True)
    filepath = os.path.join(GIG_DRAFTS_DIR, f"upwork_bio_{focus}.txt")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(result)
    print(f"[GIG] Bio saved: {filepath}")
    
    return result


def generate_proposal(job_text: str) -> str:
    """
    Generate a client proposal for a freelance job listing.
    
    Args:
        job_text: The job description text
        
    Returns:
        Proposal string (150-200 words)
    """
    from agents.content_agent import generate
    
    profile = _load_profile()
    personal = profile.get("personal", {})
    projects = profile.get("projects", [])
    
    # Find the most relevant project
    project_summaries = "\n".join([
        f"- {p['name']}: {p.get('description', '')} (Highlight: {p.get('highlight', '')})"
        for p in projects
    ])
    
    prompt = f"""Write a freelance proposal responding to this job posting:

JOB POSTING:
{job_text[:2000]}

MY PROJECTS:
{project_summaries}

My name: {personal.get('name', 'Developer')}

RULES:
- 150-200 words STRICTLY
- Reference ONE specific matching project by name with its real metric
- Show you read the job description (mention a specific requirement)
- End with a question to start a conversation
- No generic opener like "I am writing to express interest"
- Sound confident and specific, like someone who does this daily
- Sign off with your name"""

    result = generate(prompt, content_type="proposal")
    
    # Enforce word limit
    words = result.split()
    if len(words) > 220:
        result = " ".join(words[:200])
        last_period = result.rfind(".")
        if last_period > len(result) - 100:
            result = result[:last_period + 1]
    
    return result


if __name__ == "__main__":
    print("=" * 50)
    print("Gig Tools Test")
    print("=" * 50)
    
    # Test single gig generation
    gig = generate_gig("mlops", "fiverr")
    print(f"\nTitle: {gig.get('title', '?')}")
    print(f"Tags: {gig.get('tags', [])}")
    print(f"Basic: ${gig.get('basic', {}).get('price_usd', '?')}")
    print(f"Standard: ${gig.get('standard', {}).get('price_usd', '?')}")
    print(f"Premium: ${gig.get('premium', {}).get('price_usd', '?')}")
