"""
test_full_v3.py — BilalAgent v3.0 Full Verification
Runs all phase tests (0-10) in sequence.
Run: python tests/test_full_v3.py
"""

import os
import sys
import time
import importlib

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

passed = 0
failed = 0
results = []
phase_scores = {}


def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        results.append(f"  PASS  {name}")
    else:
        failed += 1
        results.append(f"  FAIL  {name} -- {detail}")


def header(phase, title):
    print(f"\n{'═' * 60}")
    print(f"  Phase {phase}: {title}")
    print(f"{'═' * 60}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PHASE 0-2: Core Foundation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
header("0-2", "Core Foundation (Model Runner, NLP, Orchestrator)")
p0_start = passed

# Model Runner
try:
    from agents.model_runner import safe_run, get_free_ram
    test("P0 model_runner imports", True)
    ram = get_free_ram()
    test("P0 get_free_ram returns float", isinstance(ram, float) and ram > 0, str(ram))
except Exception as e:
    test("P0 model_runner", False, str(e))

# NLP Agent
try:
    from agents.nlp_agent import analyze
    test("P1 nlp_agent imports", True)
except Exception as e:
    test("P1 nlp_agent", False, str(e))

# Orchestrator
try:
    from agents.orchestrator import route_command
    test("P2 orchestrator imports", True)
except Exception as e:
    test("P2 orchestrator", False, str(e))

# Database
try:
    from memory.db import init_db, save_profile, get_profile, log_action, log_content
    test("P0 memory.db imports", True)
    init_db()
    test("P0 init_db() success", True)
except Exception as e:
    test("P0 memory.db", False, str(e))

# Profile
try:
    import yaml
    with open(os.path.join(PROJECT_ROOT, "config", "profile.yaml"), "r") as f:
        profile = yaml.safe_load(f)
    test("P0 profile.yaml loads", profile is not None and "name" in profile)
except Exception as e:
    test("P0 profile.yaml", False, str(e))

# Settings
try:
    with open(os.path.join(PROJECT_ROOT, "config", "settings.yaml"), "r") as f:
        settings = yaml.safe_load(f)
    test("P0 settings.yaml loads", settings is not None)
except Exception as e:
    test("P0 settings.yaml", False, str(e))

# Ollama models
try:
    import subprocess
    result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
    models = result.stdout.lower()
    test("P0 gemma3:1b available", "gemma3:1b" in models)
    test("P0 gemma3:4b available", "gemma3:4b" in models or "gemma3:4b" in models)
except Exception as e:
    test("P0 ollama models", False, str(e))

phase_scores["0-2"] = passed - p0_start


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PHASE 3: Chrome Extension + Bridge
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
header("3", "Chrome Extension + Bridge Server")
p3_start = passed

# Extension files
ext_dir = os.path.join(PROJECT_ROOT, "chrome_extension")
test("P3 manifest.json exists", os.path.exists(os.path.join(ext_dir, "manifest.json")))
test("P3 content_script.js exists", os.path.exists(os.path.join(ext_dir, "content_script.js")))
test("P3 background.js exists", os.path.exists(os.path.join(ext_dir, "background.js")))

# Bridge
try:
    from bridge.server import app
    test("P3 bridge server imports", True)
except Exception as e:
    test("P3 bridge server", False, str(e))

# Browser tools
try:
    from tools.browser_tools import _create_stealth_context
    test("P3 browser_tools imports", True)
except Exception as e:
    test("P3 browser_tools", False, str(e))

phase_scores["3"] = passed - p3_start


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PHASE 4: Job Engine
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
header("4", "Job Engine + Excel Logger")
p4_start = passed

try:
    from tools.job_tools import search_jobs
    test("P4 job_tools imports", True)
except Exception as e:
    test("P4 job_tools", False, str(e))

try:
    from memory.excel_logger import get_applications, get_posts, get_gigs
    test("P4 excel_logger imports", True)
except Exception as e:
    test("P4 excel_logger", False, str(e))

try:
    from tools.content_tools import generate_gig_description
    test("P4 content_tools imports", True)
except Exception as e:
    test("P4 content_tools", False, str(e))

phase_scores["4"] = passed - p4_start


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PHASE 5: Freelance Monitor
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
header("5", "Freelance Monitor")
p5_start = passed

try:
    from connectors.freelance_monitor import FreelanceMonitor
    fm = FreelanceMonitor()
    test("P5 FreelanceMonitor imports", True)
    test("P5 Has check method", hasattr(fm, "check_new_projects") or hasattr(fm, "check"))
except Exception as e:
    test("P5 freelance_monitor", False, str(e))

# Gig tools
try:
    from tools.gig_tools import generate_gig
    test("P5 gig_tools imports", True)
except Exception as e:
    test("P5 gig_tools", False, str(e))

phase_scores["5"] = passed - p5_start


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PHASE 6: LinkedIn Brand + Hybrid Refiner
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
header("6", "LinkedIn Brand + Hybrid Refiner")
p6_start = passed

try:
    from connectors.github_monitor import GitHubActivityMonitor
    gam = GitHubActivityMonitor()
    test("P6 GitHubActivityMonitor imports", True)
    test("P6 Has content ideas", hasattr(gam, "get_content_ideas"))
except Exception as e:
    test("P6 github_monitor", False, str(e))

try:
    from tools.post_scheduler import generate_weekly_posts
    test("P6 post_scheduler imports", True)
except Exception as e:
    test("P6 post_scheduler", False, str(e))

try:
    from agents.content_agent import generate
    test("P6 content_agent imports", True)
except Exception as e:
    test("P6 content_agent", False, str(e))

phase_scores["6"] = passed - p6_start


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PHASE 7: Dashboard + System Tray
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
header("7", "Dashboard + System Tray + Startup")
p7_start = passed

try:
    from ui.dashboard import DashboardApp, launch_dashboard
    test("P7 dashboard imports", True)
except Exception as e:
    test("P7 dashboard", False, str(e))

try:
    from ui.tray_app import build_menu
    test("P7 tray_app imports", True)
except Exception as e:
    test("P7 tray_app", False, str(e))

test("P7 startup.py exists", os.path.exists(os.path.join(PROJECT_ROOT, "startup.py")))
test("P7 scheduler.py exists", os.path.exists(os.path.join(PROJECT_ROOT, "scheduler.py")))

phase_scores["7"] = passed - p7_start


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PHASE 8: UI-TARS Server + Screen Loop
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
header("8", "UI-TARS Server + Screen Loop")
p8_start = passed

# Server
try:
    from tools.uitars_server import UITARSServer, get_server
    test("P8 uitars_server imports", True)
    server = UITARSServer()
    test("P8 UITARSServer init", True)
except Exception as e:
    test("P8 uitars_server", False, str(e))

# Runner
try:
    from tools.uitars_runner import capture_screen, ask_uitars, execute_action
    test("P8 uitars_runner imports", True)
except Exception as e:
    test("P8 uitars_runner", False, str(e))

# Screen monitor
try:
    from tools.screen_monitor import ScreenMonitor
    test("P8 screen_monitor imports", True)
except Exception as e:
    test("P8 screen_monitor", False, str(e))

# llama-server.exe
test("P8 llama-server.exe exists",
     os.path.exists(r"D:\local_models\llama.cpp\llama-server.exe"))

# GGUF files
test("P8 2B GGUF exists",
     os.path.isdir(r"D:\local_models\bartowski\UI-TARS-2B-SFT-GGUF"))
test("P8 7B GGUF exists",
     os.path.isdir(r"D:\local_models\bartowski\UI-TARS-7B-SFT-GGUF"))

# Screenshot capture
try:
    screen = capture_screen()
    test("P8 Screenshot captured", len(screen) > 10000, f"Only {len(screen)} chars")
except Exception as e:
    test("P8 Screenshot capture", False, str(e))

phase_scores["8"] = passed - p8_start


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PHASE 9: Permission Gate
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
header("9", "Permission Gate")
p9_start = passed

try:
    from tools.permission_gate import PermissionGate, get_gate
    gate = PermissionGate()
    test("P9 PermissionGate imports", True)

    gate.set_allow_all(1)
    test("P9 Allow All activates", gate.is_allow_all_active())
    test("P9 Time remaining valid", gate.time_remaining() != "inactive")

    gate.revoke_allow_all()
    test("P9 Revoke works", not gate.is_allow_all_active())

    gate.add_skip_type("scroll")
    test("P9 Skip type added", "scroll" in gate.skip_types)
    gate.remove_skip_type("scroll")
except Exception as e:
    test("P9 PermissionGate", False, str(e))

# Bridge endpoints
with open(os.path.join(PROJECT_ROOT, "bridge", "server.py"), "r", encoding="utf-8") as f:
    bridge_code = f.read()
test("P9 /permission/request endpoint", "/permission/request" in bridge_code)
test("P9 /permission/pending endpoint", "/permission/pending" in bridge_code)
test("P9 /permission/result endpoint", "/permission/result" in bridge_code)
test("P9 /permission/set_allow_all endpoint", "/permission/set_allow_all" in bridge_code)
test("P9 /permission/allow_all_status endpoint", "/permission/allow_all_status" in bridge_code)

# Extension overlay
with open(os.path.join(PROJECT_ROOT, "chrome_extension", "content_script.js"), "r", encoding="utf-8") as f:
    ext_code = f.read()
test("P9 createPermissionOverlay in extension", "createPermissionOverlay" in ext_code)
test("P9 Allow All badge in extension", "allow-all-badge" in ext_code)

# Dashboard sections
with open(os.path.join(PROJECT_ROOT, "ui", "dashboard.py"), "r", encoding="utf-8") as f:
    dash_code = f.read()
test("P9 UI-TARS section in dashboard", "UI-TARS Vision Agent" in dash_code)
test("P9 Permission Controls in dashboard", "Permission Controls" in dash_code)

phase_scores["9"] = passed - p9_start


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PHASE 10: Browser Copilot
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
header("10", "Browser Copilot")
p10_start = passed

try:
    from tools.browser_copilot import BrowserCopilot
    copilot = BrowserCopilot()
    test("P10 BrowserCopilot imports", True)
    test("P10 Has permission gate", copilot.gate is not None)
except Exception as e:
    test("P10 BrowserCopilot", False, str(e))

# Prompt drafting
try:
    ctx = {
        "title": "Python Dev", "company": "Corp", "description": "Build APIs",
        "skills": ["Python"], "budget": "$50/hr"
    }
    p1 = copilot.draft_llm_prompt("write cover letter", ctx)
    test("P10 Cover letter prompt", len(p1) > 100)
    p2 = copilot.draft_llm_prompt("write proposal", ctx)
    test("P10 Proposal prompt", len(p2) > 100)
    p3 = copilot.draft_llm_prompt("write linkedin post", ctx)
    test("P10 LinkedIn prompt", len(p3) > 100)
except Exception as e:
    test("P10 Prompt drafting", False, str(e))

# Mode 2 routing
with open(os.path.join(PROJECT_ROOT, "agent.py"), "r", encoding="utf-8") as f:
    agent_code = f.read()
test("P10 Mode 2 triggers in agent", "mode_2_triggers" in agent_code)
test("P10 BrowserCopilot import in agent", "BrowserCopilot" in agent_code)
test("P10 full_flow call in agent", "copilot.full_flow" in agent_code)

# Code structure
with open(os.path.join(PROJECT_ROOT, "tools", "browser_copilot.py"), "r", encoding="utf-8") as f:
    cop_code = f.read()
test("P10 Has CDP strategy", "_extract_via_cdp" in cop_code)
test("P10 Has UI-TARS strategy", "_extract_via_uitars" in cop_code)
test("P10 Has Playwright strategy", "_extract_via_playwright" in cop_code)
test("P10 Permission gate checks >= 3", cop_code.count("self.gate.request") >= 3)
test("P10 Content output dir", os.path.isdir(os.path.join(PROJECT_ROOT, "memory", "content_output")))

phase_scores["10"] = passed - p10_start


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FILE COUNT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
header("FILES", "Project File Count")
py_count = 0
for root, dirs, files in os.walk(PROJECT_ROOT):
    dirs[:] = [d for d in dirs if d not in [".git", "__pycache__", "node_modules", ".venv"]]
    py_count += sum(1 for f in files if f.endswith((".py", ".js", ".yaml", ".md", ".json")))
test(f"Project has 50+ files ({py_count})", py_count >= 50, f"Only {py_count}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FINAL SUMMARY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("\n" + "━" * 60)
print("  BilalAgent v3.0 — FULL VERIFICATION RESULTS")
print("━" * 60)

for phase, score in phase_scores.items():
    print(f"  Phase {phase:>5}: {score} checks passed")

print(f"\n  {'─' * 40}")
print(f"  TOTAL: {passed}/{passed + failed} checks passed")
print(f"  {'─' * 40}")

if failed > 0:
    print(f"\n  FAILURES ({failed}):")
    for r in results:
        if "FAIL" in r:
            print(f"    {r}")

print("━" * 60)
