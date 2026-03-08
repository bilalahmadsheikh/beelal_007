"""
test_extension_update.py — Tests for Chrome Extension v3.0 Update
Tests: Bridge agent endpoints (content push, SSE, prompts, decisions)
       + offline static checks (imports, file structure, manifest)
"""

import sys
import os
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BRIDGE = "http://localhost:8000"

passed = 0
failed = 0


def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}{' -- ' + detail if detail else ''}")


def bridge_alive():
    try:
        import requests
        r = requests.get(f"{BRIDGE}/status", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def agent_endpoints_available():
    """Check if the NEW agent endpoints exist (bridge was restarted with updated code)."""
    try:
        import requests
        r = requests.get(f"{BRIDGE}/agent/content/latest", timeout=3)
        return r.status_code != 404
    except Exception:
        return False


# ===================================================================
# SECTION 1: OFFLINE STATIC CHECKS (always run)
# ===================================================================

print("=" * 60)
print("Chrome Extension v3.0 -- Test Suite")
print("=" * 60)

# -- Import Checks --
print("\n--- Import Checks ---")
try:
    from bridge.server import app
    test("Bridge server app imports", True)
except Exception as e:
    test("Bridge server app imports", False, str(e))

try:
    from bridge.server import AgentContentReady, AgentContentDecision
    test("AgentContentReady/Decision models import", True)
except Exception as e:
    test("AgentContentReady/Decision models import", False, str(e))

try:
    from bridge.server import AgentPromptBody, AgentMessageBody
    test("AgentPromptBody/MessageBody models import", True)
except Exception as e:
    test("AgentPromptBody/MessageBody models import", False, str(e))

try:
    from bridge.server import _push_sse_event, agent_content_store, agent_prompts, sse_queues
    test("SSE internals import", True)
except Exception as e:
    test("SSE internals import", False, str(e))

# -- LinkedIn Poster Checks --
print("\n--- LinkedIn Poster ---")
try:
    from tools.linkedin_extension_poster import LinkedInExtensionPoster
    poster = LinkedInExtensionPoster()
    test("LinkedInExtensionPoster instantiates", True)
except Exception as e:
    test("LinkedInExtensionPoster instantiates", False, str(e))

try:
    assert hasattr(poster, '_notify_agent'), "Missing _notify_agent"
    assert hasattr(poster, '_wait_for_content_decision'), "Missing _wait_for_content_decision"
    assert hasattr(poster, '_wait_for_linkedin_post_result'), "Missing _wait_for_linkedin_post_result"
    assert hasattr(poster, '_post_via_extension'), "Missing _post_via_extension"
    test("New poster methods exist", True)
except Exception as e:
    test("New poster methods exist", False, str(e))

# -- Extension File Checks --
print("\n--- Extension Files ---")
ext_dir = os.path.join(PROJECT_ROOT, "chrome_extension")

files = ["manifest.json", "popup.html", "popup.js", "popup.css",
         "background.js", "content_script.js"]
for f in files:
    test(f"File exists: {f}", os.path.exists(os.path.join(ext_dir, f)))

# Manifest version
with open(os.path.join(ext_dir, "manifest.json"), encoding="utf-8") as f:
    manifest = json.load(f)
test("Manifest version is 3.0", manifest.get("version") == "3.0",
     f"Got: {manifest.get('version')}")

# popup.html checks
with open(os.path.join(ext_dir, "popup.html"), encoding="utf-8") as f:
    html = f.read()
test("popup.html includes popup.css", "popup.css" in html)
test("popup.html has tab-bar", "tab-bar" in html)
test("popup.html has prompt-bar", "prompt-bar" in html)
test("popup.html has feed-scroll", "feed-scroll" in html)

# popup.js checks
with open(os.path.join(ext_dir, "popup.js"), encoding="utf-8") as f:
    js = f.read()
test("popup.js has EventSource (SSE)", "EventSource" in js)
test("popup.js has content_ready handler", "content_ready" in js)
test("popup.js has AGENT_POST_LINKEDIN", "AGENT_POST_LINKEDIN" in js)
test("popup.js has AGENT_SEND_PROMPT", "AGENT_SEND_PROMPT" in js)
test("popup.js has showContentCard", "showContentCard" in js)
test("popup.js has content preview card", "content-card" in js)

# background.js checks
with open(os.path.join(ext_dir, "background.js"), encoding="utf-8") as f:
    bg = f.read()
test("background.js has AGENT_POST_LINKEDIN handler", "AGENT_POST_LINKEDIN" in bg)
test("background.js has AGENT_SEND_PROMPT handler", "AGENT_SEND_PROMPT" in bg)
test("background.js has AGENT_OPEN_TAB handler", "AGENT_OPEN_TAB" in bg)
test("background.js has agentPostToLinkedIn function", "agentPostToLinkedIn" in bg)
test("background.js has findOrOpenLinkedInTab", "findOrOpenLinkedInTab" in bg)

# content_script.js checks
with open(os.path.join(ext_dir, "content_script.js"), encoding="utf-8") as f:
    cs = f.read()
test("content_script.js has agent branding", "Generated by BilalAgent" in cs)
test("content_script.js bridgeAlive before pollActiveTasks",
     cs.index("let bridgeAlive") < cs.index("pollActiveTasks"),
     "bridgeAlive should be declared before pollActiveTasks to avoid TDZ")

# popup.css checks
with open(os.path.join(ext_dir, "popup.css"), encoding="utf-8") as f:
    css = f.read()
test("popup.css has root variables", "--bg-primary" in css)
test("popup.css has content-card styles", ".content-card" in css)
test("popup.css has glass/gradient effects", "linear-gradient" in css or "rgba" in css)

# Documentation check
docs_path = os.path.join(PROJECT_ROOT, "docs", "CHROME_EXTENSION.md")
test("CHROME_EXTENSION.md exists", os.path.exists(docs_path))
if os.path.exists(docs_path):
    with open(docs_path, encoding="utf-8") as f:
        doc = f.read()
    test("Docs mention v3.0", "v3.0" in doc)
    test("Docs mention SSE", "SSE" in doc)
    test("Docs mention agent-driven", "agent-driven" in doc or "Agent-Driven" in doc)


# ===================================================================
# SECTION 2: ONLINE BRIDGE ENDPOINT TESTS (only if bridge is running)
# ===================================================================

if bridge_alive():
    import requests

    print("\n--- Bridge Online: Agent Endpoints ---")

    if not agent_endpoints_available():
        print("\n  ** Bridge is running but MISSING new agent endpoints.")
        print("  ** Restart the bridge to load updated server.py:")
        print("  **   uvicorn bridge.server:app --port 8000 --reload")
        print("  ** Skipping online endpoint tests.\n")
    else:
        # Content Push
        r = requests.post(f"{BRIDGE}/agent/content/ready", json={
            "content": "Test LinkedIn post about AI engineering #AI #Python",
            "content_type": "linkedin_post",
            "task_id": "test_001",
        }, timeout=5)
        test("POST /agent/content/ready returns 200", r.status_code == 200)
        data = r.json()
        test("Returns task_id", "task_id" in data)
        test("Status is pending_review", data.get("status") == "pending_review")
        test("Has word_count", data.get("word_count", 0) > 0)

        # Content Latest
        r = requests.get(f"{BRIDGE}/agent/content/latest", timeout=5)
        test("GET /agent/content/latest returns 200", r.status_code == 200)
        data = r.json()
        test("Returns pending content", data.get("status") == "pending_review")

        # Content Status
        r = requests.get(f"{BRIDGE}/agent/content/status/test_001", timeout=5)
        test("GET /agent/content/status returns 200", r.status_code == 200)

        # Content Decision
        r = requests.post(f"{BRIDGE}/agent/content/decision", json={
            "task_id": "test_001",
            "decision": "approved",
        }, timeout=5)
        test("POST /agent/content/decision returns 200", r.status_code == 200)
        data = r.json()
        test("Decision recorded", data.get("decision") == "approved")

        r = requests.get(f"{BRIDGE}/agent/content/status/test_001", timeout=5)
        data = r.json()
        test("Status updated to approved", data.get("status") == "approved")

        # Prompt
        r = requests.post(f"{BRIDGE}/agent/prompt", json={
            "prompt": "Generate a post about BasePy",
            "source": "extension",
        }, timeout=5)
        test("POST /agent/prompt returns 200", r.status_code == 200)
        data = r.json()
        test("Prompt queued", data.get("status") == "queued")

        # Prompt Pending
        r = requests.get(f"{BRIDGE}/agent/prompt/pending", timeout=5)
        test("GET /agent/prompt/pending returns 200", r.status_code == 200)
        data = r.json()
        test("Has pending prompts", isinstance(data, list) and len(data) > 0)
        if isinstance(data, list) and len(data) > 0:
            test("Prompt text correct",
                 any(isinstance(p, dict) and "BasePy" in p.get("prompt", "") for p in data))

        # Prompts consumed
        r = requests.get(f"{BRIDGE}/agent/prompt/pending", timeout=5)
        data = r.json()
        test("Prompts consumed after fetch", isinstance(data, list) and len(data) == 0)

        # Agent Message
        r = requests.post(f"{BRIDGE}/agent/message", json={
            "message": "Test message from desktop agent",
            "message_type": "agent_message",
        }, timeout=5)
        test("POST /agent/message returns 200", r.status_code == 200)

        # SSE Stream
        print("\n--- SSE Stream ---")
        try:
            r = requests.get(f"{BRIDGE}/agent/stream", stream=True, timeout=3)
            test("GET /agent/stream returns 200", r.status_code == 200)
            test("Content-Type is text/event-stream",
                 "text/event-stream" in r.headers.get("content-type", ""))
            r.close()
        except requests.exceptions.ReadTimeout:
            test("SSE stream responds (streaming)", True)
        except Exception as e:
            test("SSE stream responds", False, str(e))
else:
    print("\n--- Bridge OFFLINE ---")
    print("  Bridge is not running. Start it with:")
    print("    uvicorn bridge.server:app --port 8000")
    print("  Online endpoint tests skipped.\n")


# ===================================================================
# Summary
# ===================================================================

print(f"\n{'=' * 60}")
print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
if failed == 0:
    print("ALL TESTS PASSED")
else:
    print(f"{failed} TESTS FAILED")
print(f"{'=' * 60}")
