"""
test_phase9.py — BilalAgent v2.0 Phase 9 Tests
Tests Permission Gate, Bridge endpoints, Extension overlay, dashboard integration.
Run: python tests/test_phase9.py
"""

import os
import sys
import time
import threading

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
print("  Phase 9: Permission Gate — Tests")
print("=" * 60)


# ─── TEST 1: PermissionGate Allow All logic ─────
print("\n[TEST 1] PermissionGate Allow All logic")
from tools.permission_gate import PermissionGate

gate = PermissionGate()

gate.set_allow_all(1)  # 1 minute
test("T1a Allow All is active", gate.is_allow_all_active() == True)

remaining = gate.time_remaining()
test("T1b Time remaining valid", "0m" in remaining or "1m" in remaining, f"Got: {remaining}")
print(f"  Time remaining: {remaining}")

gate.revoke_allow_all()
test("T1c Revoked successfully", gate.is_allow_all_active() == False)
test("T1d Time remaining is inactive", gate.time_remaining() == "inactive")

# Test skip types
gate.add_skip_type("scroll")
gate.add_skip_type("extract")
test("T1e Skip types set", "scroll" in gate.skip_types and "extract" in gate.skip_types)
gate.remove_skip_type("scroll")
test("T1f Skip type removed", "scroll" not in gate.skip_types)


# ─── Start bridge server for remaining tests ────
print("\n[SETUP] Starting bridge server...")

import subprocess
bridge_process = None

try:
    # Check if bridge already running
    import requests
    try:
        r = requests.get("http://localhost:8000/", timeout=2)
        bridge_already_running = r.status_code == 200
    except Exception:
        bridge_already_running = False

    if not bridge_already_running:
        bridge_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "bridge.server:app", "--port", "8000",
             "--log-level", "warning"],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        # Wait for bridge to be ready
        for _ in range(20):
            try:
                r = requests.get("http://localhost:8000/", timeout=1)
                if r.status_code == 200:
                    print("  Bridge started successfully")
                    break
            except Exception:
                time.sleep(0.5)
        else:
            print("  WARNING: Bridge may not have started")
    else:
        print("  Bridge already running")


    # ─── TEST 2: Bridge permission endpoints ────────
    print("\n[TEST 2] Bridge permission endpoints")

    # Queue a permission request
    r = requests.post("http://localhost:8000/permission/request", json={
        "task_id": "test-123",
        "action_type": "click",
        "description": "Click the Apply button",
        "x": 500, "y": 300, "confidence": 0.9
    })
    test("T2a /permission/request accepted", r.status_code == 200)

    data = r.json()
    test("T2b Status is queued", data.get("status") == "queued", str(data))
    print(f"  Response: {data}")

    # Check pending list
    r = requests.get("http://localhost:8000/permission/pending")
    test("T2c /permission/pending returns list", r.status_code == 200)
    pending = r.json()
    test("T2d Pending has our task", any(p["task_id"] == "test-123" for p in pending),
         f"Pending: {[p['task_id'] for p in pending]}")

    # Check result before decision (should be pending)
    r = requests.get("http://localhost:8000/permission/result/test-123")
    test("T2e Result before decision is pending", r.json().get("decision") == "pending")

    # Resolve it
    r = requests.post("http://localhost:8000/permission/result", json={
        "task_id": "test-123",
        "decision": "allow"
    })
    test("T2f /permission/result POST accepted", r.status_code == 200)

    # Verify resolution
    r = requests.get("http://localhost:8000/permission/result/test-123")
    test("T2g Decision stored as 'allow'", r.json().get("decision") == "allow")
    print(f"  Decision: {r.json()}")

    # Non-existent task
    r = requests.get("http://localhost:8000/permission/result/nonexistent-999")
    test("T2h Non-existent returns not_found", r.json().get("decision") == "not_found")


    # ─── TEST 3: Allow All endpoint ─────────────────
    print("\n[TEST 3] Allow All endpoint")

    r = requests.post("http://localhost:8000/permission/set_allow_all",
                       json={"duration_minutes": 30})
    test("T3a set_allow_all returns ok", r.json().get("status") == "ok")
    print(f"  Set: {r.json()}")

    r = requests.get("http://localhost:8000/permission/allow_all_status")
    status_data = r.json()
    test("T3b allow_all_status shows active", status_data.get("active") == True)
    test("T3c time_remaining > 0", status_data.get("time_remaining_seconds", 0) > 0)
    print(f"  Status: {status_data}")

    # Auto-approve test: new request should auto-approve
    r = requests.post("http://localhost:8000/permission/request", json={
        "task_id": "test-auto-456",
        "action_type": "scroll",
        "description": "Auto-scroll test",
        "confidence": 1.0
    })
    test("T3d Auto-approve returns auto_allowed",
         r.json().get("status") == "auto_allowed", str(r.json()))

    # Revoke
    r = requests.post("http://localhost:8000/permission/set_allow_all",
                       json={"duration_minutes": 0})
    test("T3e Revoke accepted", r.status_code == 200)

    r = requests.get("http://localhost:8000/permission/allow_all_status")
    test("T3f After revoke, active is False", r.json().get("active") == False)


    # ─── TEST 4: Extension overlay HTML validation ──
    print("\n[TEST 4] Extension overlay code validation")

    ext_path = os.path.join(PROJECT_ROOT, "chrome_extension", "content_script.js")
    with open(ext_path, "r", encoding="utf-8") as f:
        content = f.read()

    test("T4a Has createPermissionOverlay function", "createPermissionOverlay" in content)
    test("T4b Has allow_all decision", "allow_all" in content)
    test("T4c Has permission/result endpoint", "permission/result" in content)
    test("T4d Has permission/pending endpoint", "permission/pending" in content)
    test("T4e Has ACTION_COLORS", "ACTION_COLORS" in content)
    test("T4f Has crosshair indicator", "crosshair" in content.lower() or "permPulse" in content)
    test("T4g Has Allow All badge", "allow-all-badge" in content)
    test("T4h Has 5 buttons", content.count("perm-btn") >= 5)


    # ─── TEST 5: Dashboard code validation ──────────
    print("\n[TEST 5] Dashboard integration validation")

    dash_path = os.path.join(PROJECT_ROOT, "ui", "dashboard.py")
    with open(dash_path, "r", encoding="utf-8") as f:
        dash_content = f.read()

    test("T5a Has UI-TARS Vision Agent section", "UI-TARS Vision Agent" in dash_content)
    test("T5b Has Permission Controls section", "Permission Controls" in dash_content)
    test("T5c Has _uitars_action method", "_uitars_action" in dash_content)
    test("T5d Has _set_allow_all method", "_set_allow_all" in dash_content)
    test("T5e Has Start 2B button", "Start 2B" in dash_content)
    test("T5f Has Allow All 30min button", "Allow All 30min" in dash_content)
    test("T5g Has Revoke button", "Revoke" in dash_content)
    test("T5h Has skip checkboxes", "skip_scroll_var" in dash_content and "skip_extract_var" in dash_content)


except Exception as e:
    print(f"\n  EXCEPTION during tests: {e}")
    import traceback
    traceback.print_exc()

finally:
    # Clean up bridge if we started it
    if bridge_process:
        print("\n[CLEANUP] Stopping bridge server...")
        bridge_process.terminate()
        try:
            bridge_process.wait(timeout=5)
        except Exception:
            bridge_process.kill()
        print("  Bridge stopped")


# ─── SUMMARY ────────────────────────────────────
print("\n" + "=" * 60)
print("  Phase 9 Test Results")
print("=" * 60)
for r in results:
    print(r)
print(f"\n  Phase 9: {passed}/{passed + failed} tests passed")
print("=" * 60)
