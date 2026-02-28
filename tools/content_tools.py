"""
content_tools.py — BilalAgent v2.0 Content Generation Tools
LinkedIn posts, cover letters, and gig descriptions.
All generation goes through agents/content_agent.py → safe_run() → keep_alive:0.
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
    """Get real GitHub data for grounding content."""
    try:
        gh = GitHubConnector()
        return gh.get_summary()
    except Exception:
        return ""


# ─────────────────────────────────────────────────────
# LinkedIn Post Generator
# ─────────────────────────────────────────────────────

def generate_linkedin_post(project_name: str, post_type: str = "project_showcase") -> str:
    """
    Generate a LinkedIn post about a project.
    
    Args:
        project_name: Name of the project to write about
        post_type: One of 'project_showcase', 'learning_update', 'achievement', 'opinion'
        
    Returns:
        LinkedIn post text (max 1300 chars, with hashtags)
    """
    github_ctx = _get_github_context()
    
    type_instructions = {
        "project_showcase": "Write a project showcase post. Lead with the problem solved, show the technical approach, highlight metrics and results.",
        "learning_update": "Write a learning journey post. Share what you learned building this, what surprised you, what you'd do differently.",
        "achievement": "Write an achievement announcement. Celebrate a milestone, share the journey, thank the community.",
        "opinion": "Write a thought-leadership opinion post. Take a stance on a technical topic related to this project.",
    }
    
    instruction = type_instructions.get(post_type, type_instructions["project_showcase"])
    
    prompt = f"""Write a LinkedIn post about the project: "{project_name}"

Post type: {post_type}
{instruction}

Real GitHub data for reference:
{github_ctx}

Requirements:
- Strong opening hook (first line grabs attention, NO generic "Excited to share...")  
- Include specific metrics where relevant (87% accuracy, 40% improvement, 90k customers)
- Sound like a real developer sharing their work, NOT AI-generated
- Use line breaks between sections for readability
- End with 3-5 relevant hashtags
- MAXIMUM 1300 characters total
- Write in first person as Bilal Ahmad Sheikh
- Be conversational and authentic"""

    result = generate(prompt, content_type="linkedin_post")
    
    # Enforce character limit
    if len(result) > 1300:
        # Truncate at last complete sentence before limit
        truncated = result[:1300]
        last_period = truncated.rfind('.')
        if last_period > 800:
            result = truncated[:last_period + 1]
    
    return result


# ─────────────────────────────────────────────────────
# Cover Letter Generator
# ─────────────────────────────────────────────────────

def generate_cover_letter(job_title: str, company: str, job_description: str = "") -> str:
    """
    Generate a targeted cover letter.
    
    Args:
        job_title: Position title
        company: Company name
        job_description: Optional job description for tailoring
        
    Returns:
        Cover letter (250-350 words)
    """
    github_ctx = _get_github_context()
    
    prompt = f"""Write a cover letter for this position:

Job Title: {job_title}
Company: {company}
{f"Job Description: {job_description}" if job_description else ""}

My real GitHub activity and projects:
{github_ctx}

Structure (3 paragraphs ONLY):
1. Opening: Why THIS role at THIS company specifically excites me. Be specific about the company, not generic.
2. Evidence: My single most relevant project with concrete metrics. Pick the one that best matches this job. Reference real repo names and tech stacks from my GitHub data.
3. Closing: Enthusiastic next step, mention availability for interview.

Requirements:
- 250-350 words STRICTLY (not shorter, not longer)
- Sound professional but warm, like a real human wrote it
- Reference specific technologies from the job description
- Include at least 2 concrete metrics from my projects
- NO generic phrases like "I am writing to express my interest" or "I believe I would be a great fit"
- Write as Bilal Ahmad Sheikh, AI Engineering student (3rd year, 6th semester)
- Sign off: "Best regards, Bilal Ahmad Sheikh"
"""

    return generate(prompt, content_type="cover_letter")


# ─────────────────────────────────────────────────────
# Gig Description Generator
# ─────────────────────────────────────────────────────

def generate_gig_description(service_type: str, platform: str = "fiverr") -> dict:
    """
    Generate a freelance gig description with pricing tiers.
    
    Args:
        service_type: One of 'mlops', 'chatbot', 'blockchain', 'data_science', 'backend'
        platform: Target platform ('fiverr', 'upwork')
        
    Returns:
        dict with keys: title, description, tags, packages (basic/standard/premium)
    """
    github_ctx = _get_github_context()
    
    service_context = {
        "mlops": "MLOps pipelines, model deployment, automated retraining. Reference: 87% accuracy prediction system with XGBoost + MLflow + Docker.",
        "chatbot": "AI chatbot development with FastAPI + Supabase. Reference: WhatsApp bot serving 90k customers for Pakistani SMEs.",
        "blockchain": "Blockchain SDKs and Web3 development. Reference: basepy-sdk with 40% performance improvement over Web3.py on Base L2.",
        "data_science": "Data science, ML models, analytics dashboards. Reference: Purchasing power prediction (87%), Route optimization with Kepler.",
        "backend": "Backend development with FastAPI, PostgreSQL, Docker. Reference: Production-grade APIs and microservices.",
    }
    
    context = service_context.get(service_type, service_context["backend"])
    
    prompt = f"""Create a {platform} gig listing for: {service_type}

Service context: {context}

My real projects (from GitHub):
{github_ctx}

Return a JSON object with EXACTLY this structure:
{{
    "title": "catchy gig title (max 80 chars)",
    "description": "detailed gig description (200-300 words). Reference real metrics. Explain what the client gets. Sound professional.",
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

Output ONLY the JSON. No explanation, no markdown fences."""

    raw = generate(prompt, content_type="gig_description")
    
    # Parse JSON from response
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
        # Return raw text as description if JSON parse fails
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
    post = generate_linkedin_post("purchasing_power_ml", "project_showcase")
    print(post)
    print(f"\n({len(post)} chars)")
