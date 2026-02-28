"""
nlp_agent.py — BilalAgent v2.0 Personal Intelligence Analyst
Handles profile queries, project info, analysis, and structured reasoning.
Uses REAL GitHub data as primary source, profile.yaml as supplement.
"""

import sys
import os
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.model_runner import safe_run, get_free_ram


# Load profile data
PROFILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "profile.yaml"
)


def _load_profile() -> dict:
    """Load the user profile from config/profile.yaml."""
    try:
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        print("[NLP_AGENT] Warning: profile.yaml not found")
        return {}
    except Exception as e:
        print(f"[NLP_AGENT] Error loading profile: {e}")
        return {}


def _profile_context(profile: dict) -> str:
    """Convert profile dict to a MINIMAL context string (just personal info, not projects)."""
    if not profile:
        return ""
    
    lines = []
    info = profile.get("personal", {})
    if info:
        lines.append(f"Name: {info.get('name', 'Unknown')}")
        lines.append(f"GitHub: {info.get('github', 'N/A')}")
        lines.append(f"Education: {info.get('degree', 'N/A')}")
        lines.append(f"Location: {info.get('location', 'N/A')}")
        skills = info.get("skills", [])
        if skills:
            lines.append(f"Skills: {', '.join(skills)}")
    
    return "\n".join(lines)


NLP_SYSTEM_PROMPT = """You are a Personal Intelligence Analyst for {name}. 
You answer questions based PRIMARILY on real GitHub data (repos, commits, languages).
The GitHub data is the ground truth — it shows what {name} has actually built.
Profile info (name, education, skills) is supplementary context.
Be specific: reference actual repo names, languages, and commit messages from the GitHub data.
Do NOT make up information. Only use what's in the provided data."""


def analyze(task: str, context: str = "", model: str = "gemma3:1b") -> str:
    """
    Run NLP analysis on a task.
    
    Args:
        task: The user's question or analysis task
        context: GitHub data or other real data (PRIMARY source)
        model: Model to use (default: gemma3:1b, can be phi4-mini)
        
    Returns:
        Analysis result as string
    """
    profile = _load_profile()
    profile_ctx = _profile_context(profile)  # Only personal info, NOT projects
    name = profile.get("personal", {}).get("name", "the user")
    
    system = NLP_SYSTEM_PROMPT.format(name=name)
    
    # Build prompt: GitHub data is PRIMARY, profile is supplementary
    prompt_parts = []
    
    if context:
        prompt_parts.append(f"=== GITHUB DATA (PRIMARY SOURCE — this is real) ===\n{context}")
    
    if profile_ctx:
        prompt_parts.append(f"=== PERSONAL INFO (supplementary) ===\n{profile_ctx}")
    
    prompt_parts.append(f"=== USER QUESTION ===\n{task}")
    prompt_parts.append("Answer using the GITHUB DATA above as your primary source. Reference actual repo names, languages, and commit activity.")
    
    prompt = "\n\n".join(prompt_parts)
    
    # Determine RAM requirement based on model
    ram_needed = 1.0 if model == "gemma3:1b" else 3.0
    
    # Try requested model, fall back to gemma3:1b
    if model != "gemma3:1b":
        free = get_free_ram()
        if free < ram_needed:
            print(f"[NLP_AGENT] Not enough RAM for {model} ({free:.1f}GB free), falling back to gemma3:1b")
            model = "gemma3:1b"
            ram_needed = 1.0
    
    result = safe_run(
        model=model,
        prompt=prompt,
        required_gb=ram_needed,
        system=system
    )
    
    return result


if __name__ == "__main__":
    print("=" * 50)
    print("NLP Agent Test")
    print(f"Free RAM: {get_free_ram():.1f}GB")
    print("=" * 50)
    
    # Test with GitHub context
    from connectors.github_connector import GitHubConnector
    gh = GitHubConnector()
    context = gh.get_summary()
    
    answer = analyze("What are my projects and their tech stacks?", context=context)
    print(f"\nAnswer:\n{answer}")
