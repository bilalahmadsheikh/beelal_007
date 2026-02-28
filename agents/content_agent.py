"""
content_agent.py — BilalAgent v2.0 Content Generation Agent
Professional Content Strategist for AI/ML Developers.
Primary: Gemma 3 4B (best 4B content model, same family as orchestrator, 3.3GB)
Fallback: Gemma 2 9B (reliable, well-tested)
"""

import sys
import os
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.model_runner import safe_run, get_free_ram, force_unload


def _load_profile_for_prompt() -> dict:
    """Load profile.yaml for dynamic prompt injection."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "profile.yaml")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _build_system_prompt() -> str:
    """Build system prompt with dynamic profile data from profile.yaml."""
    p = _load_profile_for_prompt()
    personal = p.get("personal", {})
    name = personal.get("name", "the developer")
    degree = personal.get("degree", "")
    github = personal.get("github", "")
    location = personal.get("location", "")
    
    return f"""You are a content writer for a developer who shares project stories on LinkedIn. You blend human storytelling with technical depth.

About the developer:
- Name: {name}
- {degree}{f', {location}' if location else ''}
- GitHub: github.com/{github}

Your writing style has TWO layers:

1. HUMAN LAYER (the story):
- Start with the real-world problem you OBSERVED — what frustrated you or someone around you?
- Show the journey: "I noticed students around me were...", "Coming from {location}, I saw that..."
- Make the reader feel WHY this project matters, what gap it fills
- Be personal, conversational, passionate — share the motivation

2. TECHNICAL LAYER (the craft):
- Name specific frameworks, libraries, architecture: Next.js, Supabase, RLS, Chrome Extension APIs
- Explain HOW you solved the problem technically — what design decisions you made and why
- Mention standout features with enough detail that another developer could appreciate them

Combine both: Tell the story THEN show the craft.

Rules:
- ONLY use facts from the provided GitHub data
- NEVER invent metrics or user counts not in the data
- Always include the GitHub repo link
- Write in first person as {name}"""


def generate(prompt: str, content_type: str = "general") -> str:
    """
    Generate content using the best available model.
    Primary: Gemma 3 4B | Fallback: Gemma 2 9B | Last resort: Gemma3 1B
    
    Args:
        prompt: Full generation prompt
        content_type: Type of content for logging
        
    Returns:
        Generated content string
    """
    free = get_free_ram()
    system_prompt = _build_system_prompt()
    
    # Try Gemma 3 4B first (best quality, same family as orchestrator)
    if free >= 3.0:
        # Unload orchestrator to free RAM for specialist
        force_unload("gemma3:1b")
        import time; time.sleep(1)
        free = get_free_ram()
        
        print(f"[CONTENT] Using Gemma 3 4B (primary) — {free:.1f}GB free")
        result = safe_run("gemma3:4b", prompt, required_gb=3.0, system=system_prompt)
        
        if not result.startswith("[ERROR]") and len(result) > 100:
            force_unload("gemma3:4b")  # Free RAM after generation
            return result
        
        # Log the error so user knows WHY it failed
        if result.startswith("[ERROR]"):
            print(f"[CONTENT] Gemma 3 4B failed: {result}")
        
        # Quality check failed — retry once
        if not result.startswith("[ERROR]") and len(result) < 150:
            print("[CONTENT] Output too short, retrying with Gemma 3 4B...")
            result = safe_run("gemma3:4b", prompt + "\n\nIMPORTANT: Write a complete, detailed response of at least 250 words.", required_gb=3.0, system=system_prompt)
            if not result.startswith("[ERROR]"):
                force_unload("gemma3:4b")
                return result
    
    # Fallback: Gemma 2 9B
    free = get_free_ram()
    if free >= 6.0:
        print(f"[CONTENT] Using Gemma 2 9B (fallback) — {free:.1f}GB free")
        result = safe_run("gemma2:9b", prompt, required_gb=6.0, system=system_prompt)
        if not result.startswith("[ERROR]"):
            force_unload("gemma2:9b")
            return result
    
    # Last resort: Gemma3 1B
    free = get_free_ram()
    print(f"[CONTENT] Using Gemma3 1B (last resort) — {free:.1f}GB free")
    result = safe_run("gemma3:1b", prompt, required_gb=0.5, system=system_prompt)
    return result


if __name__ == "__main__":
    print("=" * 50)
    print("Content Agent Test")
    print(f"Free RAM: {get_free_ram():.1f}GB")
    print("=" * 50)
    
    result = generate("Write a short LinkedIn post about starting an AI engineering project.")
    print(f"\nGenerated ({len(result)} chars):\n{result}")
