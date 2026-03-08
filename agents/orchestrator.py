"""
orchestrator.py — BilalAgent v3.1 Command Router
Uses Gemma 3 1B to classify user commands and route to the right agent.
Always-on, lightweight (~1GB RAM), JSON-only output.

Fixed in v3.1: robust JSON parsing, num_predict=150, regex fallback.
"""

import json
import re
import sys
import os
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.model_runner import safe_run, get_free_ram


def _get_routing_model() -> str:
    """Get routing model from settings.yaml."""
    try:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "settings.yaml")
        with open(path, "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f) or {}
        return settings.get("routing_model", "gemma3:1b")
    except Exception:
        return "gemma3:1b"


# Short, explicit prompt that forces clean JSON from a 1B model
ROUTER_SYSTEM_PROMPT = """You are a task router. Respond with ONLY a JSON object, nothing else.
No explanation. No markdown. No code fences. Just the raw JSON.

Respond with exactly this structure:
{"agent": "content", "task": "write_post", "model": "gemma3:4b", "mode": "local", "needs_screen": false}

agent options: content, nlp, jobs, navigation, memory, brand, github
task: a short task name
model options: gemma3:4b, gemma3:1b, phi4-mini, gemma2:9b
mode options: local, browser_copilot, hybrid, vision
needs_screen: true only if task requires seeing the screen

Rules:
- Writing content (posts, letters, proposals, gigs, bios) → agent: "content", model: "gemma3:4b"
- Questions about profile, skills, projects → agent: "nlp", model: "gemma3:1b"
- Finding/searching jobs → agent: "jobs", model: "gemma3:1b"
- Brand check, github activity, weekly posts → agent: "brand", model: "gemma3:1b"
- Complex analysis, scoring → agent: "nlp", model: "phi4-mini"
- Browsing websites → agent: "navigation", model: "gemma3:1b"

Output ONLY the JSON object."""

SUPPORTED_AGENTS = {"nlp", "content", "navigation", "memory", "jobs", "brand", "github"}
SUPPORTED_MODELS = {"gemma3:1b", "phi4-mini", "gemma3:4b", "gemma2:9b"}


def route_command(user_input: str) -> dict:
    """
    Route a user command to the appropriate agent via Gemma 3 1B.
    
    Returns:
        dict with keys: agent, task, model, mode, needs_screen
    """
    prompt = f'Classify this user command and output JSON:\n\n"{user_input}"'
    
    raw = safe_run(
        model=_get_routing_model(),
        prompt=prompt,
        required_gb=0.5,
        system=ROUTER_SYSTEM_PROMPT,
        num_predict=150  # Routing JSON never needs more than 150 tokens
    )
    
    if raw.startswith("[ERROR]"):
        print(f"[ORCHESTRATOR] Model error: {raw}")
        return _default_route(user_input)
    
    print(f"  [DEBUG RAW ORCHESTRATOR]: '{raw[:300]}'")
    
    result = _parse_routing(raw)
    print(f"  [DEBUG PARSED ROUTING]: {json.dumps(result)}")
    return result


def _parse_routing(raw: str) -> dict:
    """
    Robustly extract routing JSON from orchestrator response.
    Uses 3 fallback strategies: direct parse → regex extraction → key-value extraction.
    """
    fallback = {
        "agent": "content",
        "task": "general",
        "model": "gemma3:4b",
        "mode": "local",
        "needs_screen": False,
    }
    
    if not raw or not raw.strip():
        print("[ROUTING] Empty response from orchestrator — using fallback")
        return fallback
    
    # Strip markdown code fences if present
    cleaned = re.sub(r'```(?:json)?\s*', '', raw).strip()
    cleaned = re.sub(r'```\s*$', '', cleaned).strip()
    
    # Try 1: direct JSON parse
    try:
        result = json.loads(cleaned)
        return _validate_routing(result)
    except (json.JSONDecodeError, TypeError):
        pass
    
    # Try 2: find JSON object anywhere in the text
    match = re.search(r'\{[^{}]*\}', cleaned, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            return _validate_routing(result)
        except (json.JSONDecodeError, TypeError):
            pass
    
    # Try 3: extract key-value pairs manually with regex
    result = {}
    patterns = {
        "agent": r'"agent"\s*:\s*"([^"]+)"',
        "task": r'"task"\s*:\s*"([^"]+)"',
        "model": r'"model"\s*:\s*"([^"]+)"',
        "mode": r'"mode"\s*:\s*"([^"]+)"',
        "needs_screen": r'"needs_screen"\s*:\s*(true|false)',
    }
    for key, pattern in patterns.items():
        m = re.search(pattern, raw, re.IGNORECASE)
        if m:
            val = m.group(1)
            if val.lower() == "true":
                val = True
            elif val.lower() == "false":
                val = False
            result[key] = val
    
    if result.get("agent"):
        print(f"[ROUTING] Partial parse succeeded: {result}")
        merged = {**fallback, **result}
        return _validate_routing(merged)
    
    print(f"[ROUTING] All parsing failed. Raw was: '{raw[:200]}'. Using fallback.")
    return fallback


def _validate_routing(result: dict) -> dict:
    """Validate and correct routing dict fields."""
    # Ensure all keys exist
    result.setdefault("agent", "content")
    result.setdefault("task", "general")
    result.setdefault("model", "gemma3:4b")
    result.setdefault("mode", "local")
    result.setdefault("needs_screen", False)
    
    # Validate agent
    if result["agent"] not in SUPPORTED_AGENTS:
        result["agent"] = "content"
    
    # Validate model
    if result["model"] not in SUPPORTED_MODELS:
        result["model"] = "gemma3:4b"  # Default to content model, NOT router
    
    # Content agent should always use gemma3:4b
    if result["agent"] == "content" and result["model"] == "gemma3:1b":
        result["model"] = "gemma3:4b"
    
    return result


def _default_route(user_input: str = "") -> dict:
    """Fallback routing when parsing fails or orchestrator errors.
    Uses keyword matching to make a best-effort guess."""
    lower = user_input.lower() if user_input else ""
    
    # Content detection
    if any(kw in lower for kw in ["write", "post", "letter", "cover", "gig", "proposal", "bio", "generate"]):
        return {"agent": "content", "task": "general", "model": "gemma3:4b", "mode": "local", "needs_screen": False}
    
    # Job detection
    if any(kw in lower for kw in ["job", "search", "find", "apply", "application"]):
        return {"agent": "jobs", "task": "search", "model": "gemma3:1b", "mode": "local", "needs_screen": False}
    
    # Brand detection
    if any(kw in lower for kw in ["brand", "github", "activity", "weekly"]):
        return {"agent": "brand", "task": "check", "model": "gemma3:1b", "mode": "local", "needs_screen": False}
    
    # Default: NLP analysis with 1B
    return {"agent": "nlp", "task": "general", "model": "gemma3:1b", "mode": "local", "needs_screen": False}


if __name__ == "__main__":
    print("=" * 50)
    print("Orchestrator Test")
    print(f"Free RAM: {get_free_ram():.1f}GB")
    print("=" * 50)
    
    test_commands = [
        "what are my projects and tech stacks",
        "write a cover letter for a Python job",
        "write a linkedin post about basepy-sdk",
        "browse LinkedIn for AI jobs",
        "brand check",
    ]
    
    for cmd in test_commands:
        print(f"\nCommand: \"{cmd}\"")
        result = route_command(cmd)
        print(f"Route:   {json.dumps(result)}")
