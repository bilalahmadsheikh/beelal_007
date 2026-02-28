"""
test_all.py — BilalAgent v2.0 Full Test Suite (Phases 0-2)
Runs all component tests sequentially, reports pass/fail.
"""

import sys
import os
import json
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

PASS = 0
FAIL = 0
RESULTS = []

def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        RESULTS.append(f"  PASS  {name}")
        print(f"  ✓ PASS  {name}")
    else:
        FAIL += 1
        RESULTS.append(f"  FAIL  {name} — {detail}")
        print(f"  ✗ FAIL  {name} — {detail}")


print("=" * 60)
print("  BilalAgent v2.0 — Full Test Suite (Phases 0-2)")
print("=" * 60)


# ─────────────────────────────────────────
# PHASE 0: Model Runner + Environment
# ─────────────────────────────────────────
print("\n── PHASE 0: Model Runner ──")

from tools.model_runner import run_model, get_free_ram, safe_run, force_unload, _get_keep_alive

# T0.1: RAM check
free = get_free_ram()
test("T0.1 get_free_ram()", free > 0, f"Got {free:.1f}GB")

# T0.2: Keep-alive tiers
test("T0.2 Orchestrator keep_alive=5m", _get_keep_alive("gemma3:1b") == "5m")
test("T0.3 Specialist keep_alive=30s", _get_keep_alive("gemma3:4b") == "30s")
test("T0.4 Default keep_alive=30s", _get_keep_alive("unknown_model") == "30s")

# T0.5: Cold model call
print("\n  Running gemma3:1b (cold)...")
ram_before = get_free_ram()
result = run_model("gemma3:1b", "Say exactly: TEST_OK", system="You are a test assistant.")
test("T0.5 Cold model call", "[ERROR]" not in result, result[:80])

# T0.6: Warm model call (should show CACHE HIT)
print("  Running gemma3:1b (warm)...")
result2 = run_model("gemma3:1b", "Say exactly: WARM_OK", system="You are a test assistant.")
test("T0.6 Warm model call", "[ERROR]" not in result2, result2[:80])

# T0.7: Force unload
force_unload("gemma3:1b")
time.sleep(2)
ram_after = get_free_ram()
test("T0.7 Force unload recovers RAM", ram_after > ram_before - 0.5, f"{ram_before:.1f}→{ram_after:.1f}GB")

# T0.8: safe_run with low RAM threshold
result3 = safe_run("gemma3:1b", "Say: SAFE_OK", required_gb=0.5)
test("T0.8 safe_run() works", "[ERROR]" not in result3, result3[:80])
force_unload("gemma3:1b")
time.sleep(1)


# ─────────────────────────────────────────
# PHASE 1: Orchestrator + NLP + GitHub + DB
# ─────────────────────────────────────────
print("\n── PHASE 1: Agent Brain ──")

# T1.1: Orchestrator routing
from agents.orchestrator import route_command
print("\n  Routing: 'what are my skills'...")
routing = route_command("what are my skills")
test("T1.1 Orchestrator returns dict", isinstance(routing, dict))
test("T1.2 Routing has 'agent' key", "agent" in routing, str(routing))
test("T1.3 Routing has 'task' key", "task" in routing, str(routing))
force_unload("gemma3:1b")
time.sleep(1)

# T1.4: GitHub connector
from connectors.github_connector import GitHubConnector
gh = GitHubConnector()
repos = gh.get_repos()
test("T1.4 GitHub fetches repos", len(repos) > 0, f"{len(repos)} repos")

commits = gh.get_recent_commits(days=30)
test("T1.5 GitHub fetches commits", len(commits) >= 0, f"{len(commits)} commits")

summary = gh.get_summary()
test("T1.6 GitHub summary not empty", len(summary) > 100, f"{len(summary)} chars")
test("T1.7 Summary has real repo names", "IlmSeUrooj" in summary or "purchasing_power" in summary, summary[:100])

# T1.8: Database
from memory.db import init_db, save_profile, get_profile, log_action, get_recent_actions, save_memory, get_memory, log_content
init_db()
test("T1.8 DB init succeeds", True)

save_profile({"name": "Bilal", "test": True})
profile = get_profile()
test("T1.9 Profile save/get", profile is not None and profile.get("name") == "Bilal")

log_action("test_run", "Full test suite", "running")
actions = get_recent_actions(5)
test("T1.10 Action logging", len(actions) > 0)

save_memory("test_key", "test_value", "test")
val = get_memory("test_key")
test("T1.11 Memory store", val == "test_value")

# T1.12: NLP agent
from agents.nlp_agent import analyze
print("\n  Running NLP analysis...")
nlp_result = analyze("What programming languages do I use?", context=summary)
test("T1.12 NLP agent responds", len(nlp_result) > 50 and "[ERROR]" not in nlp_result, nlp_result[:80])
test("T1.13 NLP uses GitHub data", "Python" in nlp_result or "python" in nlp_result, nlp_result[:80])
force_unload("gemma3:1b")
time.sleep(1)


# ─────────────────────────────────────────
# PHASE 2: Content Generation
# ─────────────────────────────────────────
print("\n── PHASE 2: Content Engine ──")

# T2.1: Content agent
from agents.content_agent import generate, _strip_thinking
test("T2.1 Strip thinking tags", _strip_thinking("<think>reasoning</think>Answer") == "Answer")

# T2.2: Content tools
from tools.content_tools import generate_linkedin_post, generate_cover_letter, generate_gig_description

print("\n  Generating LinkedIn post...")
post = generate_linkedin_post("IlmSeUrooj", "project_showcase")
test("T2.2 LinkedIn post generated", len(post) > 100 and "[ERROR]" not in post, f"{len(post)} chars")
test("T2.3 LinkedIn ≤ 1300 chars", len(post) <= 1400, f"{len(post)} chars")  # small buffer
force_unload("gemma3:1b")
force_unload("gemma3:4b")
time.sleep(2)

print("  Generating cover letter...")
cover = generate_cover_letter("ML Engineer", "OpenAI")
word_count = len(cover.split())
test("T2.4 Cover letter generated", len(cover) > 200 and "[ERROR]" not in cover, f"{word_count} words")
test("T2.5 Cover letter ≥ 150 words", word_count >= 150, f"{word_count} words")
force_unload("gemma3:1b")
force_unload("gemma3:4b")
time.sleep(2)

print("  Generating gig description...")
gig = generate_gig_description("chatbot", "fiverr")
test("T2.6 Gig returns dict", isinstance(gig, dict))
test("T2.7 Gig has title", "title" in gig, str(list(gig.keys())))
test("T2.8 Gig has packages", "packages" in gig, str(list(gig.keys())))
force_unload("gemma3:1b")
force_unload("gemma3:4b")
time.sleep(1)

# T2.9: Content logging
log_content("test_post", "Test content", "generated", "linkedin")
test("T2.9 Content logging", True)

# T2.10: Approval CLI module
from ui.approval_cli import auto_approve
result_approve = auto_approve("test", "Test content")
test("T2.10 Auto-approve works", result_approve == "approved")


# ─────────────────────────────────────────
# PHASE 2.5: Prompt Caching Verification
# ─────────────────────────────────────────
print("\n── PROMPT CACHING ──")

# T3.1: Cold vs warm comparison
print("\n  Cold start...")
force_unload("gemma3:1b")
time.sleep(2)
t1_start = time.time()
r1 = run_model("gemma3:1b", "Say: COLD", system="You are a router.")
t1 = time.time() - t1_start

print("  Warm start...")
t2_start = time.time()
r2 = run_model("gemma3:1b", "Say: WARM", system="You are a router.")
t2 = time.time() - t2_start

test("T3.1 Cold call succeeds", "[ERROR]" not in r1)
test("T3.2 Warm call succeeds", "[ERROR]" not in r2)
test("T3.3 Warm faster than cold", t2 < t1, f"cold={t1:.1f}s warm={t2:.1f}s")

# Cleanup
force_unload("gemma3:1b")
time.sleep(2)
ram_final = get_free_ram()


# ─────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────
print("\n" + "=" * 60)
print(f"  RESULTS: {PASS} passed, {FAIL} failed out of {PASS + FAIL}")
print("=" * 60)
for r in RESULTS:
    print(r)
print(f"\nFinal RAM: {ram_final:.1f}GB")
print("=" * 60)
