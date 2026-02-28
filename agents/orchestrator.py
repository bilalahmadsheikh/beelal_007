"""
orchestrator.py — BilalAgent v2.0 Command Router
Uses Gemma 3 1B to classify user commands and route to the right agent.
Always-on, lightweight (~1GB RAM), JSON-only output.
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.model_runner import safe_run, get_free_ram


ROUTER_SYSTEM_PROMPT = """You are a command router for a personal AI agent. Your ONLY job is to output valid JSON.

Given a user command, classify it and output JSON with these exact keys:
- "agent": one of "nlp", "content", "navigation", "memory"
- "task": a short task name like "profile_query", "project_info", "write_cover_letter", "browse_jobs", "save_data", "analyze_job"
- "model": the model to use, one of "gemma3:1b", "phi4-mini", "qwen3:8b"

Rules:
- Questions about the user's profile, projects, skills, experience → agent: "nlp", model: "gemma3:1b"
- Complex analysis, scoring, structured reasoning → agent: "nlp", model: "phi4-mini"
- Writing cover letters, posts, proposals → agent: "content", model: "qwen3:8b"
- Browsing websites, scraping jobs → agent: "navigation", model: "gemma3:1b"
- Storing/retrieving data, notes, memories → agent: "memory", model: "gemma3:1b"

Output ONLY the JSON object. No explanation, no markdown, no extra text. Just the raw JSON."""


SUPPORTED_AGENTS = {"nlp", "content", "navigation", "memory"}
SUPPORTED_MODELS = {"gemma3:1b", "phi4-mini", "qwen3:8b", "gemma2:9b"}


def route_command(user_input: str) -> dict:
    """
    Route a user command to the appropriate agent via Gemma 3 1B.
    
    Args:
        user_input: Raw user command string
        
    Returns:
        dict with keys: agent, task, model
        On failure: dict with agent="nlp", task="general", model="gemma3:1b"
    """
    prompt = f"Classify this user command and output JSON:\n\n\"{user_input}\""
    
    raw = safe_run(
        model="gemma3:1b",
        prompt=prompt,
        required_gb=0.5,
        system=ROUTER_SYSTEM_PROMPT
    )
    
    if raw.startswith("[ERROR]"):
        print(f"[ORCHESTRATOR] Model error: {raw}")
        return _default_route()
    
    return _parse_routing(raw)


def _parse_routing(raw: str) -> dict:
    """Extract JSON from model response, handling markdown fences and noise."""
    text = raw.strip()
    
    # Strip markdown code fences if present
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
    
    # Try to find JSON object in the response
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        text = text[start:end]
    
    try:
        result = json.loads(text)
        # Validate keys
        if "agent" not in result:
            result["agent"] = "nlp"
        if "task" not in result:
            result["task"] = "general"
        if "model" not in result:
            result["model"] = "gemma3:1b"
        
        # Validate values
        if result["agent"] not in SUPPORTED_AGENTS:
            result["agent"] = "nlp"
        if result["model"] not in SUPPORTED_MODELS:
            result["model"] = "gemma3:1b"
            
        return result
    except (json.JSONDecodeError, TypeError):
        print(f"[ORCHESTRATOR] Failed to parse JSON from: {raw[:200]}")
        return _default_route()


def _default_route() -> dict:
    """Fallback routing when parsing fails."""
    return {
        "agent": "nlp",
        "task": "general",
        "model": "gemma3:1b"
    }


if __name__ == "__main__":
    print("=" * 50)
    print("Orchestrator Test")
    print(f"Free RAM: {get_free_ram():.1f}GB")
    print("=" * 50)
    
    test_commands = [
        "what are my projects and tech stacks",
        "write a cover letter for a Python job",
        "browse LinkedIn for AI jobs",
        "save this note: meeting at 3pm",
    ]
    
    for cmd in test_commands:
        print(f"\nCommand: \"{cmd}\"")
        result = route_command(cmd)
        print(f"Route:   {json.dumps(result)}")
