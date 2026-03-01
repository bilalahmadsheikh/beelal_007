"""
uitars_runner.py — BilalAgent v2.0 Phase 8
Sends screenshots to UI-TARS vision model and gets back action JSON.
Handles screen capture, API calls, and action execution (click/type/scroll).
"""

import os
import sys
import time
import json
import base64
import random
import logging
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

try:
    import mss
    import mss.tools
except ImportError:
    print("Installing mss...")
    os.system(f"{sys.executable} -m pip install mss")
    import mss
    import mss.tools

try:
    import pyautogui
except ImportError:
    print("Installing pyautogui...")
    os.system(f"{sys.executable} -m pip install pyautogui")
    import pyautogui

import requests

log = logging.getLogger("uitars_runner")

# ─── Config ──────────────────────────────────────

UITARS_URL = "http://127.0.0.1:8081"
SCREENSHOT_DIR = os.path.join(PROJECT_ROOT, "memory", "screenshots")
SCREENSHOT_PATH = os.path.join(SCREENSHOT_DIR, "screen_current.png")

os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Safety: moving mouse to top-left corner aborts all pyautogui actions
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1  # Small pause between pyautogui calls


# ─── System Prompt ───────────────────────────────

UITARS_SYSTEM_PROMPT = """You are a GUI agent. Analyze the screenshot and output ONLY valid JSON with these exact keys:
- action (string: one of "click", "type", "scroll", "extract", "done", "ask")
- x (int or null): x-coordinate for click/type/scroll actions
- y (int or null): y-coordinate for click/type/scroll actions
- text (string or null): text to type for "type" action, or extracted text for "extract"
- direction (string or null): "up" or "down" for scroll action
- amount (int or null): scroll amount (number of clicks) for scroll action
- region (array or null): [x, y, width, height] bounding box for "extract" action
- description (string): what you will do in plain English
- confidence (float 0-1): how confident you are this is the right action
- task_complete (bool): whether the overall task is now complete

No explanation, no markdown, only the JSON object."""


# ─── Screenshot Capture ─────────────────────────

def capture_screen() -> str:
    """
    Capture the primary monitor at full resolution using mss.
    
    Returns:
        Base64-encoded PNG string
    """
    with mss.mss() as sct:
        # Monitor 1 = primary display (0 = all monitors combined)
        monitor = sct.monitors[1]
        screenshot = sct.grab(monitor)

        # Save to disk
        png_bytes = mss.tools.to_png(screenshot.rgb, screenshot.size)
        with open(SCREENSHOT_PATH, "wb") as f:
            f.write(png_bytes)

        # Encode to base64
        b64 = base64.b64encode(png_bytes).decode("utf-8")
        return b64


def capture_region(x: int, y: int, width: int, height: int) -> str:
    """
    Capture a specific screen region.
    
    Returns:
        Path to saved screenshot
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(SCREENSHOT_DIR, f"extract_{timestamp}.png")

    with mss.mss() as sct:
        region = {"left": x, "top": y, "width": width, "height": height}
        screenshot = sct.grab(region)
        png_bytes = mss.tools.to_png(screenshot.rgb, screenshot.size)
        with open(save_path, "wb") as f:
            f.write(png_bytes)

    return save_path


# ─── UI-TARS API Call ────────────────────────────

def ask_uitars(task: str, screenshot_b64: str = None, context: str = "") -> dict:
    """
    Send a screenshot to UI-TARS and get back an action JSON.
    
    Args:
        task: What the user wants to accomplish on screen
        screenshot_b64: Base64 PNG of the current screen (captured if None)
        context: Additional context about previous actions or state
        
    Returns:
        dict with action, x, y, text, description, confidence, task_complete
    """
    if screenshot_b64 is None:
        screenshot_b64 = capture_screen()

    # Build user message with image + text
    user_content = [
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}
        },
        {
            "type": "text",
            "text": f"Task: {task}\nContext: {context}\nWhat single action should I take next?"
        }
    ]

    payload = {
        "model": "ui-tars",  # llama.cpp ignores this, uses loaded model
        "messages": [
            {"role": "system", "content": UITARS_SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ],
        "max_tokens": 300,
        "temperature": 0.1,
        "stream": False,
    }

    try:
        resp = requests.post(
            f"{UITARS_URL}/v1/chat/completions",
            json=payload,
            timeout=180  # Vision models can be slow on CPU (first call needs warmup)
        )
        resp.raise_for_status()

        data = resp.json()
        raw_text = data["choices"][0]["message"]["content"].strip()

        # Parse JSON from response
        return _parse_action_json(raw_text)

    except requests.ConnectionError:
        return {
            "action": "ask",
            "description": "UI-TARS server is not running. Start it with UITARSServer().start('2b')",
            "confidence": 0,
            "task_complete": False,
        }
    except requests.Timeout:
        return {
            "action": "ask",
            "description": "UI-TARS request timed out (>120s). The model may be overloaded.",
            "confidence": 0,
            "task_complete": False,
        }
    except Exception as e:
        return {
            "action": "ask",
            "description": f"UI-TARS error: {str(e)}",
            "confidence": 0,
            "task_complete": False,
        }


def _parse_action_json(raw_text: str) -> dict:
    """
    Parse JSON from UI-TARS response text, handling markdown fences and extra text.
    """
    text = raw_text.strip()

    # Strip markdown code fences
    if "```" in text:
        lines = text.split("\n")
        json_lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(json_lines).strip()

    # Find JSON object
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        text = text[start:end]

    try:
        parsed = json.loads(text)

        # Validate required keys exist with defaults
        return {
            "action": parsed.get("action", "ask"),
            "x": parsed.get("x"),
            "y": parsed.get("y"),
            "text": parsed.get("text"),
            "direction": parsed.get("direction"),
            "amount": parsed.get("amount"),
            "region": parsed.get("region"),
            "description": parsed.get("description", "No description"),
            "confidence": float(parsed.get("confidence", 0.5)),
            "task_complete": bool(parsed.get("task_complete", False)),
        }
    except (json.JSONDecodeError, TypeError, ValueError):
        return {
            "action": "ask",
            "description": f"UI-TARS returned invalid JSON: {raw_text[:200]}",
            "confidence": 0,
            "task_complete": False,
        }


# ─── Action Execution ───────────────────────────

def execute_action(action: dict) -> dict:
    """
    Execute a screen action returned by UI-TARS.
    
    SAFETY: pyautogui.FAILSAFE is True — moving mouse to top-left corner
    of the screen will abort any action immediately.
    
    Args:
        action: dict from ask_uitars() with action type and parameters
        
    Returns:
        dict with success, action type, and details
    """
    action_type = action.get("action", "ask")
    x = action.get("x")
    y = action.get("y")
    text = action.get("text")
    direction = action.get("direction", "down")
    amount = action.get("amount", 3)
    region = action.get("region")
    description = action.get("description", "")

    log.info(f"[EXECUTE] {action_type}: {description}")

    try:
        if action_type == "click":
            if x is None or y is None:
                return {"success": False, "error": "Click action requires x and y coordinates"}
            pyautogui.moveTo(x, y, duration=0.3)
            time.sleep(0.2)
            pyautogui.click(x, y)
            return {"success": True, "action": "click", "x": x, "y": y, "description": description}

        elif action_type == "type":
            if text is None:
                return {"success": False, "error": "Type action requires text"}
            # Click target field first if coordinates given
            if x is not None and y is not None:
                pyautogui.click(x, y)
                time.sleep(0.3)
            # Type with human-like random intervals
            pyautogui.write(text, interval=random.uniform(0.04, 0.12))
            return {"success": True, "action": "type", "chars_typed": len(text), "description": description}

        elif action_type == "scroll":
            scroll_amount = amount if direction == "up" else -amount
            pyautogui.scroll(scroll_amount, x=x, y=y)
            return {"success": True, "action": "scroll", "direction": direction, "amount": amount, "description": description}

        elif action_type == "extract":
            if region and len(region) == 4:
                save_path = capture_region(region[0], region[1], region[2], region[3])
            else:
                # Full screen capture
                capture_screen()
                save_path = SCREENSHOT_PATH
            return {"success": True, "action": "extract", "saved_path": save_path, "description": description}

        elif action_type == "done":
            return {"success": True, "action": "done", "message": "Task complete", "description": description}

        elif action_type == "ask":
            return {"success": True, "action": "ask", "question": description}

        else:
            return {"success": False, "error": f"Unknown action type: {action_type}"}

    except pyautogui.FailSafeException:
        log.warning("[EXECUTE] FAILSAFE triggered — mouse moved to corner, aborting!")
        return {"success": False, "error": "FAILSAFE: Mouse moved to top-left corner. All actions aborted."}
    except Exception as e:
        log.error(f"[EXECUTE] Action failed: {e}")
        return {"success": False, "error": str(e)}


# ─── High-Level API ──────────────────────────────

def run_vision_task(task: str, max_steps: int = 10, require_approval: bool = True) -> list:
    """
    Run a multi-step vision task: screenshot → ask UI-TARS → execute → repeat.
    
    Args:
        task: Natural language description of what to do
        max_steps: Maximum number of actions before stopping
        require_approval: If True, print each action and wait for Enter before executing
        
    Returns:
        List of action results
    """
    results = []
    context = ""

    for step in range(1, max_steps + 1):
        print(f"\n{'─'*50}")
        print(f"Step {step}/{max_steps}")

        # Capture and ask
        screenshot = capture_screen()
        action = ask_uitars(task, screenshot, context)

        print(f"  Action: {action['action']}")
        print(f"  Description: {action['description']}")
        print(f"  Confidence: {action['confidence']:.1%}")

        # Check if done
        if action.get("task_complete") or action["action"] == "done":
            print(f"\n✅ Task complete: {action['description']}")
            results.append({"step": step, "action": action, "result": {"success": True, "action": "done"}})
            break

        # Check if model is asking a question
        if action["action"] == "ask":
            print(f"\n❓ UI-TARS asks: {action['description']}")
            results.append({"step": step, "action": action, "result": {"success": True, "action": "ask"}})
            break

        # Approval gate
        if require_approval:
            print(f"\n  → Press Enter to execute, or 'n' to skip...")
            user_input = input("  ").strip().lower()
            if user_input == "n":
                print("  Skipped.")
                context += f"\nStep {step}: Skipped by user — {action['description']}"
                continue

        # Execute
        result = execute_action(action)
        results.append({"step": step, "action": action, "result": result})

        if result["success"]:
            print(f"  ✅ Executed: {result.get('action')}")
            context += f"\nStep {step}: Executed {action['action']} — {action['description']}"
        else:
            print(f"  ❌ Failed: {result.get('error')}")
            context += f"\nStep {step}: FAILED {action['action']} — {result.get('error')}"

        # Brief pause between steps
        time.sleep(0.5)

    return results


if __name__ == "__main__":
    print("=" * 50)
    print("UI-TARS Runner Test")
    print("=" * 50)

    # Test screenshot
    b64 = capture_screen()
    print(f"Screenshot captured: {len(b64)} base64 chars")
    print(f"Saved to: {SCREENSHOT_PATH}")
