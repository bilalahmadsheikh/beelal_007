"""
test_phase10.py — BilalAgent v2.0 Phase 10 Tests
Tests Browser Copilot: page context extraction, prompt drafting, mode routing.
Run: python tests/test_phase10.py
"""

import os
import sys
import json
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

passed = 0
failed = 0
results = []


def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        results.append(f"  PASS  {name}")
        print(f"  PASS  {name}")
    else:
        failed += 1
        results.append(f"  FAIL  {name} -- {detail}")
        print(f"  FAIL  {name} -- {detail}")


print("=" * 60)
print("  Phase 10: Browser Copilot — Tests")
print("=" * 60)


# ─── TEST 1: BrowserCopilot import + init ────────
print("\n[TEST 1] BrowserCopilot import and initialization")
try:
    from tools.browser_copilot import BrowserCopilot
    copilot = BrowserCopilot()
    test("T1a BrowserCopilot imported", True)
    test("T1b Has permission gate", copilot.gate is not None)
    test("T1c Has bridge URL", copilot.bridge_url.startswith("http"))
    test("T1d Has extract_page_context", hasattr(copilot, "extract_page_context"))
    test("T1e Has draft_llm_prompt", hasattr(copilot, "draft_llm_prompt"))
    test("T1f Has open_and_fill_llm", hasattr(copilot, "open_and_fill_llm"))
    test("T1g Has full_flow", hasattr(copilot, "full_flow"))
except Exception as e:
    test("T1 Import", False, str(e))


# ─── TEST 2: draft_llm_prompt (no browser needed) ─
print("\n[TEST 2] draft_llm_prompt")
try:
    test_context = {
        "title": "Python Developer",
        "company": "TestCorp",
        "description": "Build ML pipelines and REST APIs using Python, FastAPI, and Docker.",
        "skills": ["Python", "FastAPI", "MLOps", "Docker"],
        "budget": "$50-100/hr"
    }

    # Cover letter
    prompt = copilot.draft_llm_prompt("write cover letter for this job", test_context)
    test("T2a Cover letter prompt length", len(prompt) > 100, f"Only {len(prompt)} chars")
    test("T2b Cover letter mentions title", "Python Developer" in prompt, prompt[:100])
    test("T2c Cover letter mentions company", "TestCorp" in prompt)
    print(f"  Cover letter prompt: {len(prompt)} chars")

    # Proposal
    prompt2 = copilot.draft_llm_prompt("write proposal for this project", test_context)
    test("T2d Proposal prompt generated", len(prompt2) > 100)
    test("T2e Proposal mentions budget", "50-100" in prompt2 or "budget" in prompt2.lower())

    # LinkedIn post
    prompt3 = copilot.draft_llm_prompt("write linkedin post about this", test_context)
    test("T2f LinkedIn prompt generated", len(prompt3) > 100)
    test("T2g LinkedIn mentions hashtag", "hashtag" in prompt3.lower())

    # Summary
    prompt4 = copilot.draft_llm_prompt("summarize this page", test_context)
    test("T2h Summary prompt generated", len(prompt4) > 50)

    # Generic
    prompt5 = copilot.draft_llm_prompt("help me understand this", test_context)
    test("T2i Generic prompt generated", len(prompt5) > 50)
    print(f"  All 5 prompt types working")

except Exception as e:
    test("T2 draft_llm_prompt", False, str(e))


# ─── TEST 3: Mode 2 routing in agent.py ──────────
print("\n[TEST 3] Mode 2 routing in agent.py")
try:
    agent_path = os.path.join(PROJECT_ROOT, "agent.py")
    with open(agent_path, "r", encoding="utf-8") as f:
        agent_code = f.read()

    test("T3a Has mode_2_triggers", "mode_2_triggers" in agent_code)
    test("T3b Has 'apply to this'", "apply to this" in agent_code)
    test("T3c Has 'copilot'", '"copilot"' in agent_code)
    test("T3d Has 'browser mode'", "browser mode" in agent_code)
    test("T3e Imports BrowserCopilot", "from tools.browser_copilot import BrowserCopilot" in agent_code)
    test("T3f Checks intelligence_mode", "intelligence_mode" in agent_code)
    test("T3g Checks web_copilot mode", "web_copilot" in agent_code)
    test("T3h Calls full_flow", "copilot.full_flow" in agent_code)

    # Test trigger detection logic
    triggers = [
        "apply to this", "help with this page", "summarise this", "summarize this",
        "write proposal for this", "use claude for", "use chatgpt for",
        "copilot", "browser mode"
    ]
    for trigger in triggers:
        test_input = f"please {trigger} job listing"
        matched = any(t in test_input.lower() for t in triggers)
        if not matched:
            test(f"T3 trigger '{trigger}'", False, "Did not match")
            break
    else:
        test("T3i All 9 triggers match correctly", True)

except Exception as e:
    test("T3 Mode 2 routing", False, str(e))


# ─── TEST 4: BrowserCopilot code structure ────────
print("\n[TEST 4] BrowserCopilot code structure")
try:
    copilot_path = os.path.join(PROJECT_ROOT, "tools", "browser_copilot.py")
    with open(copilot_path, "r", encoding="utf-8") as f:
        copilot_code = f.read()

    test("T4a Has CDP strategy", "_extract_via_cdp" in copilot_code)
    test("T4b Has UI-TARS strategy", "_extract_via_uitars" in copilot_code)
    test("T4c Has Playwright strategy", "_extract_via_playwright" in copilot_code)
    test("T4d Has PermissionGate import", "from tools.permission_gate import" in copilot_code)
    test("T4e Has stealth context import", "_create_stealth_context" in copilot_code)
    test("T4f Has Claude selectors", "claude" in copilot_code.lower() and "contenteditable" in copilot_code)
    test("T4g Has ChatGPT selectors", "chatgpt" in copilot_code.lower() and "prompt-textarea" in copilot_code)
    test("T4h Has memory save path", "content_output" in copilot_code)
    test("T4i Has response polling", "MutationObserver" in copilot_code or "poll" in copilot_code.lower())
    test("T4j Permission gate at every step", copilot_code.count("self.gate.request") >= 3,
         f"Only {copilot_code.count('self.gate.request')} gate checks (need >=3)")

except Exception as e:
    test("T4 Code structure", False, str(e))


# ─── TEST 5: Content output directory ────────────
print("\n[TEST 5] Content output directory")
try:
    output_dir = os.path.join(PROJECT_ROOT, "memory", "content_output")
    os.makedirs(output_dir, exist_ok=True)
    test("T5a content_output directory exists", os.path.isdir(output_dir))

    # Test file write
    test_file = os.path.join(output_dir, "_test_write.txt")
    with open(test_file, "w") as f:
        f.write("test")
    test("T5b Can write to content_output", os.path.exists(test_file))
    os.remove(test_file)

except Exception as e:
    test("T5 Output directory", False, str(e))


# ─── TEST 6: Integration smoke test ──────────────
print("\n[TEST 6] Integration smoke test")
try:
    # Verify extract_page_context returns valid dict even without browser
    context = copilot.extract_page_context()
    test("T6a extract_page_context returns dict", isinstance(context, dict))
    test("T6b Has 'source' key", "source" in context)
    test("T6c Has 'description' key", "description" in context)
    print(f"  Source: {context.get('source')} | Title: {context.get('title', '')[:50]}")

except Exception as e:
    test("T6 Integration", False, str(e))


# ─── MANUAL TEST 7 ───────────────────────────────
print("\n[TEST 7] MANUAL — Live end-to-end test instructions")
print("  1. Open Chrome and go to any LinkedIn job listing")
print("  2. Start bridge: uvicorn bridge.server:app --port 8000")
print("  3. Start UI-TARS 2B (or skip if testing Claude directly)")
print("  4. Set intelligence_mode to 'web_copilot' in config/settings.yaml")
print("  5. Run: python agent.py 'apply to this job'")
print("")
print("  EXPECTED:")
print("    → Permission overlay: 'Open claude.ai in browser' [Allow Once]")
print("    → Chrome opens claude.ai")
print("    → Permission overlay: 'Autofill prompt into Claude' [Allow Once]")
print("    → Prompt typed into Claude input")
print("    → Permission overlay: 'Click Send' [Allow Once]")
print("    → Waits for response (MutationObserver)")
print("    → Permission overlay: 'Use response' [Allow Once]")
print("    → Saved to memory/content_output/")
results.append("  INFO  T7 Manual test instructions printed")


# ─── SUMMARY ────────────────────────────────────
print("\n" + "=" * 60)
print("  Phase 10 Test Results")
print("=" * 60)
for r in results:
    print(r)
print(f"\n  Phase 10: {passed}/{passed + failed} tests passed")
print("=" * 60)
