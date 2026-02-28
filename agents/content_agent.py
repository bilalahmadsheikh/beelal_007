"""
content_agent.py — BilalAgent v2.0 Content Generation Agent
Professional Content Strategist for AI/ML Developers.
Primary: Qwen3 8B (best 2025 output, hybrid thinking mode)
Fallback: Gemma 2 9B (reliable, well-tested)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.model_runner import safe_run, get_free_ram


CONTENT_SYSTEM_PROMPT = """You are a content writer for a developer who shares project stories on LinkedIn. You blend human storytelling with technical depth.

About the developer:
- Name: Bilal Ahmad Sheikh
- AI Engineering student, 3rd year (6th semester), Pakistan
- GitHub: github.com/bilalahmadsheikh

Your writing style has TWO layers:

1. HUMAN LAYER (the story):
- Start with the real-world problem you OBSERVED — what frustrated you or someone around you?
- Show the journey: "I noticed students around me were...", "Coming from Pakistan, I saw that..."
- Make the reader feel WHY this project matters, what gap it fills
- Be personal, conversational, passionate — share the motivation

2. TECHNICAL LAYER (the craft):
- Name specific frameworks, libraries, architecture: Next.js, Supabase, RLS, Chrome Extension APIs
- Explain HOW you solved the problem technically — what design decisions you made and why
- Mention standout features with enough detail that another developer could appreciate them

Combine both: Tell the story THEN show the craft.

Example of GOOD:
"Every year, thousands of Pakistani students apply to 5-10 universities — manually filling the same form over and over. I built IlmSeUrooj to fix this: a Next.js app with Supabase backend + Chrome Extension that autofills university portals. The swipe-based discovery UI lets students browse universities like Tinder — swipe right to save, left to skip."

Example of BAD:
"Excited to share my new project! It uses modern technologies to help students. Check it out!"

Rules:
- ONLY use facts from the provided GitHub data
- NEVER invent metrics or user counts not in the data
- Always include the GitHub repo link
- Write in first person as Bilal"""


def generate(prompt: str, content_type: str = "general") -> str:
    """
    Generate content using the best available model.
    Primary: Qwen3 8B | Fallback: Gemma 2 9B | Last resort: Gemma3 1B
    
    Args:
        prompt: Full generation prompt
        content_type: Type of content for logging
        
    Returns:
        Generated content string
    """
    free = get_free_ram()
    
    # Try Qwen3 8B first (best quality)
    if free >= 5.0:
        print(f"[CONTENT] Using Qwen3 8B (primary) — {free:.1f}GB free")
        result = safe_run("qwen3:8b", prompt, required_gb=5.0, system=CONTENT_SYSTEM_PROMPT)
        
        # Strip thinking tags if present (Qwen3 hybrid mode)
        result = _strip_thinking(result)
        
        if not result.startswith("[ERROR]") and len(result) > 100:
            return result
        
        # Quality check failed — retry once
        if not result.startswith("[ERROR]") and len(result) < 150:
            print("[CONTENT] Output too short, retrying with Qwen3 8B...")
            result = safe_run("qwen3:8b", prompt + "\n\nIMPORTANT: Write a complete, detailed response of at least 250 words.", required_gb=5.0, system=CONTENT_SYSTEM_PROMPT)
            result = _strip_thinking(result)
            if not result.startswith("[ERROR]"):
                return result
    
    # Fallback: Gemma 2 9B
    free = get_free_ram()
    if free >= 6.0:
        print(f"[CONTENT] Using Gemma 2 9B (fallback) — {free:.1f}GB free")
        result = safe_run("gemma2:9b", prompt, required_gb=6.0, system=CONTENT_SYSTEM_PROMPT)
        if not result.startswith("[ERROR]"):
            return result
    
    # Last resort: Gemma3 1B
    free = get_free_ram()
    print(f"[CONTENT] Using Gemma3 1B (last resort) — {free:.1f}GB free")
    result = safe_run("gemma3:1b", prompt, required_gb=0.5, system=CONTENT_SYSTEM_PROMPT)
    return result


def _strip_thinking(text: str) -> str:
    """Strip Qwen3's <think>...</think> reasoning tags from output."""
    import re
    # Remove <think>...</think> blocks (Qwen3 hybrid thinking mode)
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    return cleaned.strip()


if __name__ == "__main__":
    print("=" * 50)
    print("Content Agent Test")
    print(f"Free RAM: {get_free_ram():.1f}GB")
    print("=" * 50)
    
    result = generate("Write a short LinkedIn post about starting an AI engineering project.")
    print(f"\nGenerated ({len(result)} chars):\n{result}")
