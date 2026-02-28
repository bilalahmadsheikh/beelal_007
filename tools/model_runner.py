"""
model_runner.py — BilalAgent v2.0 Model Runner
Handles all Ollama model calls with keep_alive:0 pattern.
Every model is loaded -> generates -> unloaded immediately to save RAM.
"""

import requests
import psutil
import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def run_model(model: str, prompt: str, system: str = "") -> str:
    """
    Run an Ollama model with keep_alive:0 (auto-unload after generation).
    
    Args:
        model: Model name (e.g. 'gemma3:1b', 'qwen3:8b')
        prompt: User prompt to send
        system: Optional system prompt
        
    Returns:
        Generated text response as string
    """
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": 0,  # Unload model immediately after generation
    }
    if system:
        payload["system"] = system

    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except requests.exceptions.ConnectionError:
        return "[ERROR] Cannot connect to Ollama. Is it running?"
    except requests.exceptions.Timeout:
        return "[ERROR] Ollama request timed out (120s)."
    except Exception as e:
        return f"[ERROR] {str(e)}"


def force_unload(model: str) -> None:
    """
    Force unload a model from RAM by sending keep_alive:0 with empty prompt.
    Use this if a model is stuck in memory.
    """
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": model,
        "prompt": "",
        "stream": False,
        "keep_alive": 0,
    }
    try:
        requests.post(url, json=payload, timeout=30)
    except Exception:
        pass  # Best effort — if it fails, model may already be unloaded


def get_free_ram() -> float:
    """
    Get available system RAM in GB.
    
    Returns:
        Free RAM in gigabytes (float)
    """
    mem = psutil.virtual_memory()
    return mem.available / (1024 ** 3)


def safe_run(model: str, prompt: str, required_gb: float = 2.0, system: str = "") -> str:
    """
    Run a model only if enough RAM is available.
    
    Args:
        model: Model name
        prompt: User prompt
        required_gb: Minimum free RAM in GB required to run
        system: Optional system prompt
        
    Returns:
        Generated text or error message if insufficient RAM
    """
    free = get_free_ram()
    if free < required_gb:
        return (
            f"[ERROR] Not enough RAM. "
            f"Need {required_gb:.1f}GB, only {free:.1f}GB free. "
            f"Close some apps and retry."
        )
    return run_model(model, prompt, system)


if __name__ == "__main__":
    print("=" * 50)
    print("BilalAgent v2.0 — Model Runner Test")
    print("=" * 50)

    # Test 1: RAM check
    free_before = get_free_ram()
    print(f"\n[1] Free RAM before: {free_before:.1f}GB")

    # Test 2: Run model
    print("\n[2] Running gemma3:1b with keep_alive:0...")
    result = run_model("gemma3:1b", "Say exactly: MODEL_RUNNER_OK")
    print(f"    Response: {result}")

    # Test 3: RAM after (model should be unloaded)
    import time
    time.sleep(2)  # Give Ollama a moment to unload
    free_after = get_free_ram()
    print(f"\n[3] Free RAM after unload: {free_after:.1f}GB")

    # Verdict
    print("\n" + "=" * 50)
    if "[ERROR]" in result:
        print("RESULT: FAIL — Model call returned an error")
    elif "MODEL_RUNNER_OK" in result.upper():
        print("RESULT: PASS — Model responded correctly")
    else:
        print(f"RESULT: PARTIAL — Model responded but without exact phrase")
    print(f"RAM recovery: {free_after - free_before:+.1f}GB")
    print("=" * 50)
