"""
model_runner.py — BilalAgent v2.0 Model Runner
Handles all Ollama model calls with tiered keep_alive + prompt caching.

Caching Strategy:
- Orchestrator (gemma3:1b, ~1GB): keep_alive=5m — always warm, KV cache reused
- Specialists (gemma3:4b, gemma2:9b): keep_alive=30s — short window for follow-ups
- After specialist finishes: explicit unload to reclaim RAM for next model
- System prompts are hashed and reused consistently for KV cache hits
"""

import requests
import psutil
import os
import hashlib
import time
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# ─────────────────────────────────────────────────────
# Keep-alive tiers: model → keep_alive duration
# Ollama caches the KV state (context window) while model is loaded.
# Keeping the model loaded = prompt prefix stays cached = fast TTFT.
# ─────────────────────────────────────────────────────
KEEP_ALIVE_TIERS = {
    # Tier 1: Router — always warm (tiny, ~1GB)
    "gemma3:1b":   "5m",
    
    # Tier 2: Specialists — short window for back-to-back calls
    "gemma3:4b":       "30s",
    "gemma2:9b":   "30s",
    "phi4-mini":   "30s",
    
    # Default for unknown models
    "_default":    "30s",
}

# Track which model is currently loaded to avoid conflicts
_current_loaded_model = None
_last_system_hash = {}


def _get_keep_alive(model: str) -> str:
    """Get the keep_alive duration for a model based on its tier."""
    return KEEP_ALIVE_TIERS.get(model, KEEP_ALIVE_TIERS["_default"])


def _hash_system_prompt(system: str) -> str:
    """Hash a system prompt for cache consistency tracking."""
    return hashlib.md5(system.encode()).hexdigest()[:8] if system else ""


def run_model(model: str, prompt: str, system: str = "", keep_alive: str = None, num_predict: int = None) -> str:
    """
    Run an Ollama model with tiered keep_alive for KV caching.
    
    The same system prompt → same KV cache prefix → fast TTFT on repeat calls.
    
    Args:
        model: Model name (e.g. 'gemma3:1b', 'gemma3:4b')
        prompt: User prompt to send
        system: Optional system prompt (cached in KV when model stays loaded)
        keep_alive: Override keep_alive (uses tier default if None)
        
    Returns:
        Generated text response as string
    """
    global _current_loaded_model
    
    # If a different LARGE model is loaded, unload it first to free RAM
    if (_current_loaded_model 
        and _current_loaded_model != model 
        and _current_loaded_model != "gemma3:1b"):  # Never unload the router
        _unload_model(_current_loaded_model)
    
    url = f"{OLLAMA_BASE_URL}/api/generate"
    
    # Use tiered keep_alive unless explicitly overridden
    model_keep_alive = keep_alive if keep_alive is not None else _get_keep_alive(model)
    
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": model_keep_alive,
    }
    if system:
        payload["system"] = system
    if num_predict:
        payload["options"] = {"num_predict": num_predict}
    
    # Log cache status
    sys_hash = _hash_system_prompt(system)
    prev_hash = _last_system_hash.get(model)
    cache_hit = (prev_hash == sys_hash and _current_loaded_model == model and sys_hash != "")
    _last_system_hash[model] = sys_hash
    
    if cache_hit:
        print(f"  [CACHE HIT] {model} — system prompt cached, fast TTFT")
    
    start = time.time()
    
    # Guard against oversized prompts that would stall the model
    if len(prompt) > 12000:
        print(f"  [WARN] Prompt too large ({len(prompt)} chars), truncating to 12000")
        prompt = prompt[:12000]
        payload["prompt"] = prompt
    
    try:
        response = requests.post(url, json=payload, timeout=300)
        response.raise_for_status()
        
        elapsed = time.time() - start
        result_data = response.json()
        result_text = result_data.get("response", "").strip()
        
        # Track loaded model
        _current_loaded_model = model
        
        # Log timing
        eval_count = result_data.get("eval_count", 0)
        prompt_eval_duration = result_data.get("prompt_eval_duration", 0) / 1e9  # ns → seconds
        total_duration = result_data.get("total_duration", 0) / 1e9
        
        ttft = prompt_eval_duration if prompt_eval_duration > 0 else elapsed
        tps = eval_count / (total_duration - prompt_eval_duration) if (total_duration - prompt_eval_duration) > 0 else 0
        
        print(f"  [TIMING] {model}: TTFT={ttft:.1f}s | {eval_count} tokens | {tps:.1f} tok/s | keep_alive={model_keep_alive}")
        
        return result_text
        
    except requests.exceptions.ConnectionError:
        return "[ERROR] Cannot connect to Ollama. Is it running?"
    except requests.exceptions.Timeout:
        return "[ERROR] Ollama request timed out (300s)."
    except Exception as e:
        return f"[ERROR] {str(e)}"


def _unload_model(model: str) -> None:
    """Unload a specific model from RAM."""
    global _current_loaded_model
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {"model": model, "prompt": "", "stream": False, "keep_alive": 0}
    try:
        requests.post(url, json=payload, timeout=15)
        if _current_loaded_model == model:
            _current_loaded_model = None
        print(f"  [UNLOAD] {model} freed from RAM")
    except Exception:
        pass


def force_unload(model: str) -> None:
    """
    Force unload a model from RAM by sending keep_alive:0.
    Use this if a model is stuck in memory or before loading a bigger model.
    """
    _unload_model(model)


def unload_all_specialists() -> None:
    """Unload all specialist models, keeping only the router (gemma3:1b)."""
    for model in ["gemma3:4b", "gemma2:9b", "phi4-mini"]:
        _unload_model(model)


def get_free_ram() -> float:
    """
    Get available system RAM in GB.
    
    Returns:
        Free RAM in gigabytes (float)
    """
    mem = psutil.virtual_memory()
    return mem.available / (1024 ** 3)


def safe_run(model: str, prompt: str, required_gb: float = 2.0, system: str = "", num_predict: int = None) -> str:
    """
    Run a model only if enough RAM is available.
    Automatically unloads competing specialists before loading.
    
    Args:
        model: Model name
        prompt: User prompt
        required_gb: Minimum free RAM in GB required to run
        system: Optional system prompt (cached for fast TTFT)
        
    Returns:
        Generated text or error message if insufficient RAM
    """
    free = get_free_ram()
    
    # If not enough RAM, try unloading specialists first
    if free < required_gb:
        print(f"  [RAM] {free:.1f}GB free, need {required_gb:.1f}GB — unloading specialists...")
        unload_all_specialists()
        time.sleep(1)
        free = get_free_ram()
    
    if free < required_gb:
        return (
            f"[ERROR] Not enough RAM. "
            f"Need {required_gb:.1f}GB, only {free:.1f}GB free. "
            f"Close some apps and retry."
        )
    return run_model(model, prompt, system, num_predict=num_predict)


if __name__ == "__main__":
    print("=" * 50)
    print("BilalAgent v2.0 — Model Runner Test (with caching)")
    print("=" * 50)

    # Test 1: RAM check
    free_before = get_free_ram()
    print(f"\n[1] Free RAM before: {free_before:.1f}GB")

    # Test 2: Cold start (first call — no cache)
    print("\n[2] Running gemma3:1b (COLD start)...")
    system_prompt = "You are a router. Output only JSON. Never explain."
    result = run_model("gemma3:1b", "Say exactly: MODEL_RUNNER_OK", system=system_prompt)
    print(f"    Response: {result}")

    # Test 3: Warm start (same model + same system prompt — KV cached)
    print("\n[3] Running gemma3:1b (WARM start — same system prompt)...")
    result2 = run_model("gemma3:1b", "Say exactly: CACHE_TEST_OK", system=system_prompt)
    print(f"    Response: {result2}")

    # Test 4: RAM after
    time.sleep(1)
    free_after = get_free_ram()
    print(f"\n[4] Free RAM (model still warm): {free_after:.1f}GB")
    
    # Test 5: Explicit unload
    print("\n[5] Force unloading gemma3:1b...")
    force_unload("gemma3:1b")
    time.sleep(2)
    free_final = get_free_ram()
    print(f"    Free RAM after unload: {free_final:.1f}GB")

    # Verdict
    print("\n" + "=" * 50)
    if "[ERROR]" in result:
        print("RESULT: FAIL — Model call returned an error")
    else:
        print("RESULT: PASS")
    print(f"RAM: {free_before:.1f}GB → warm:{free_after:.1f}GB → unloaded:{free_final:.1f}GB")
    print("=" * 50)
