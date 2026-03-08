"""
orchestrator.py — BilalAgent v3.1 Command Router
Uses Gemma 3 1B to classify user commands and route to the right agent.
Always-on, lightweight (~1GB RAM), JSON-only output.
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


SUPPORTED_AGENTS = {"nlp", "content", "navigation", "memory", "jobs", "brand", "github"}
SUPPORTED_MODELS = {"gemma3:1b", "phi4-mini", "gemma3:4b", "gemma2:9b"}


def route_command(user_input: str) -> dict:
    """
    Route a user command to the appropriate agent via Gemma 3 1B.
    
    Returns:
        dict with keys: agent, model, mode, needs_screen
    """
    # One-shot prompt — no \n\n so stop sequences don't fire mid-prompt
    routing_prompt = (
        'Return JSON only, no text:\n'
        '{"agent":"content","model":"gemma3:4b","mode":"local","needs_screen":false}\n'
        f'Task: {user_input}\n'
        'JSON:'
    )

    raw = safe_run(
        model=_get_routing_model(),
        prompt=routing_prompt,
        required_gb=0.5,
        system="",
        options={
            "temperature": 0.0,
            "num_predict": 80,
            "stop": ["\n\n", "```", "\n#"],
        },
    )
    
    if raw.startswith("[ERROR]"):
        print(f"[ORCHESTRATOR] Model error: {raw}")
        return _default_route(user_input)
    
    # The stop token "}" is consumed, so add it back
    raw_fixed = raw.strip()
    if raw_fixed.startswith("{") and not raw_fixed.endswith("}"):
        raw_fixed = raw_fixed + "}"

    print(f"  [RAW ROUTING]: '{raw_fixed}'")
    
    result = parse_routing_response(raw_fixed)
    print(f"  [PARSED ROUTING]: {json.dumps(result)}")
    return result


def parse_routing_response(raw: str) -> dict:
    """Robustly extract routing JSON from orchestrator response."""
    fallback = {
        "agent": "content",
        "model": "gemma3:4b",
        "mode": "local",
        "needs_screen": False,
    }
    if not raw or not raw.strip():
        return fallback
    
    # Clean markdown fences
    cleaned = re.sub(r'```(?:json)?', '', raw).strip()
    cleaned = re.sub(r'```', '', cleaned).strip()
    
    # Try 1: direct parse
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    
    # Try 2: complete truncated JSON by adding closing brace
    try:
        if cleaned.startswith('{') and not cleaned.endswith('}'):
            return json.loads(cleaned + '}')
    except Exception:
        pass
    
    # Try 3: find any JSON object in the text
    match = re.search(r'\{.*?\}', cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    
    # Try 4: extract individual fields manually
    result = dict(fallback)
    for key, pattern in [
        ("agent",        r'"agent"\s*:\s*"(\w+)"'),
        ("model",        r'"model"\s*:\s*"([\w.:]+)"'),
        ("mode",         r'"mode"\s*:\s*"(\w+)"'),
        ("needs_screen", r'"needs_screen"\s*:\s*(true|false)'),
    ]:
        m = re.search(pattern, raw, re.IGNORECASE)
        if m:
            v = m.group(1)
            result[key] = (v == "true") if key == "needs_screen" else v
    
    # Validate agent and model
    if result["agent"] not in SUPPORTED_AGENTS:
        result["agent"] = "content"
    if result["model"] not in SUPPORTED_MODELS:
        result["model"] = "gemma3:4b"
    if result["agent"] == "content" and result["model"] == "gemma3:1b":
        result["model"] = "gemma3:4b"
    
    print(f"[ROUTING FALLBACK] Using: {result}")
    return result


def _default_route(user_input: str = "") -> dict:
    """Keyword-based fallback when orchestrator fails entirely."""
    lower = user_input.lower() if user_input else ""
    
    if any(kw in lower for kw in ["write", "post", "letter", "cover", "gig", "proposal", "bio", "generate"]):
        return {"agent": "content", "model": "gemma3:4b", "mode": "local", "needs_screen": False}
    if any(kw in lower for kw in ["job", "search", "find", "apply", "application"]):
        return {"agent": "jobs", "model": "gemma3:1b", "mode": "local", "needs_screen": False}
    if any(kw in lower for kw in ["brand", "github", "activity", "weekly"]):
        return {"agent": "brand", "model": "gemma3:1b", "mode": "local", "needs_screen": False}
    
    return {"agent": "nlp", "model": "gemma3:1b", "mode": "local", "needs_screen": False}


if __name__ == "__main__":
    print("=" * 50)
    print("Orchestrator Test")
    print(f"Free RAM: {get_free_ram():.1f}GB")
    print("=" * 50)
    
    test_commands = [
        "what are my projects",
        "write a linkedin post about basepy-sdk",
        "find AI jobs remote",
        "brand check",
    ]
    
    for cmd in test_commands:
        print(f"\nCommand: \"{cmd}\"")
        result = route_command(cmd)
        print(f"Route:   {json.dumps(result)}")
