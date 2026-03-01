"""
test_phase8.py — BilalAgent v2.0 Phase 8 Tests
Tests UI-TARS server, screenshot capture, vision API, action execution.
Run: python tests/test_phase8.py
"""

import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

from tools.uitars_server import UITARSServer
from tools.uitars_runner import capture_screen, ask_uitars, execute_action

passed = 0
failed = 0
results = []
server = None


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
print("  Phase 8: UI-TARS Server + Screen Loop — Tests")
print("=" * 60)


# ─── TEST 1: llama-server.exe exists ────────────
print("\n[TEST 1] llama-server.exe exists")
server_exe = r"D:\local_models\llama.cpp\llama-server.exe"
test("T1 llama-server.exe found", os.path.exists(server_exe), f"Not at {server_exe}")


# ─── TEST 2: GGUF files found ───────────────────
print("\n[TEST 2] GGUF files found")
server = UITARSServer()

path_2b = server._find_gguf(server.MODEL_PATHS["2b"])
test("T2a 2B GGUF found", path_2b is not None and path_2b.endswith(".gguf"), f"Got: {path_2b}")

path_7b = server._find_gguf(server.MODEL_PATHS["7b"])
test("T2b 7B GGUF found", path_7b is not None and path_7b.endswith(".gguf"), f"Got: {path_7b}")

mmproj_2b = server._find_mmproj(server.MODEL_PATHS["2b"])
test("T2c 2B mmproj found", mmproj_2b is not None and "mmproj" in mmproj_2b, f"Got: {mmproj_2b}")

mmproj_7b = server._find_mmproj(server.MODEL_PATHS["7b"])
test("T2d 7B mmproj found", mmproj_7b is not None and "mmproj" in mmproj_7b, f"Got: {mmproj_7b}")

if path_2b:
    print(f"  2B GGUF: {os.path.basename(path_2b)}")
    print(f"  2B mmproj: {os.path.basename(mmproj_2b) if mmproj_2b else 'N/A'}")
if path_7b:
    print(f"  7B GGUF: {os.path.basename(path_7b)}")
    print(f"  7B mmproj: {os.path.basename(mmproj_7b) if mmproj_7b else 'N/A'}")


# ─── TEST 3: Server start (2B — 30-90 seconds) ──
print("\n[TEST 3] Server start (UI-TARS 2B) — this takes 30-90 seconds, please wait...")
start_time = time.time()
start_result = server.start("2b")
elapsed = time.time() - start_time
test("T3a Server started", start_result == True, f"start() returned {start_result} — check memory/uitars_server.log")

if start_result:
    test("T3b Server is_running", server.is_running() == True)
    print(f"  Started in {elapsed:.1f}s")

    info = server.get_model_info()
    test("T3c get_model_info correct", info["running"] and info["model_size"] == "2b" and info["port"] == 8081)
    print(f"  Model info: {info}")
else:
    print("  ❌ Server failed to start. Remaining tests will be skipped.")
    test("T3b Server is_running (skipped)", False, "Server didn't start")
    test("T3c get_model_info (skipped)", False, "Server didn't start")


# ─── TEST 4: Screenshot capture ─────────────────
print("\n[TEST 4] Screenshot capture")
try:
    screen_b64 = capture_screen()
    test("T4a Screenshot captured", len(screen_b64) > 10000, f"Only {len(screen_b64)} chars")
    test("T4b No whitespace in base64", screen_b64 == screen_b64.strip())
    print(f"  Base64 length: {len(screen_b64)} chars")
    print(f"  Saved to: {os.path.join(PROJECT_ROOT, 'memory', 'screenshots', 'screen_current.png')}")
except Exception as e:
    test("T4 Screenshot capture", False, str(e))


# ─── TEST 5: UI-TARS responds (LIVE) ────────────
if start_result:
    print("\n[TEST 5] UI-TARS responds (LIVE vision call — may take 30-60s on CPU)...")
    try:
        result = ask_uitars("What application is currently visible on this screen?")
        test("T5a Response is dict", isinstance(result, dict))
        test("T5b Has 'action' key", "action" in result, str(result.keys()))
        test("T5c Has 'description' key", "description" in result)
        test("T5d Has 'confidence' key", "confidence" in result)
        print(f"  Action: {result.get('action')}")
        print(f"  Description: {result.get('description')}")
        print(f"  Confidence: {result.get('confidence')}")
        print(f"  Task complete: {result.get('task_complete')}")
    except Exception as e:
        test("T5 UI-TARS response", False, str(e))
else:
    print("\n[TEST 5] SKIPPED — server not running")
    test("T5 UI-TARS response (skipped)", False, "Server didn't start")


# ─── TEST 6: execute_action dry run ─────────────
print("\n[TEST 6] execute_action dry run")
mock_action = {
    "action": "done",
    "description": "test complete",
    "confidence": 1.0,
    "task_complete": True,
}
result = execute_action(mock_action)
test("T6a execute_action returns success", result.get("success") == True, str(result))
test("T6b action is 'done'", result.get("action") == "done")

# Also test ask action
ask_action = {
    "action": "ask",
    "description": "What should I do?",
    "confidence": 0.5,
    "task_complete": False,
}
ask_result = execute_action(ask_action)
test("T6c ask action works", ask_result.get("success") == True and ask_result.get("action") == "ask")


# ─── TEST 7: Server stop ────────────────────────
if start_result:
    print("\n[TEST 7] Server stop")
    server.stop()
    time.sleep(3)
    test("T7 Server stopped", server.is_running() == False)
else:
    print("\n[TEST 7] SKIPPED — server was not started")
    test("T7 Server stop (skipped)", False, "Server didn't start")


# ─── SUMMARY ────────────────────────────────────
print("\n" + "=" * 60)
print("  Phase 8 Test Results")
print("=" * 60)
for r in results:
    print(r)
print(f"\n  Phase 8: {passed}/{passed + failed} tests passed")
print("=" * 60)
