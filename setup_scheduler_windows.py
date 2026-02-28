"""
setup_scheduler_windows.py — BilalAgent v2.0 Windows Task Scheduler Setup
Creates a Windows Task Scheduler entry to run scheduler.py at login.
"""

import os
import sys
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SCHEDULER_PATH = os.path.join(PROJECT_ROOT, "scheduler.py")

# Use pythonw for windowless operation
PYTHONW = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
if not os.path.exists(PYTHONW):
    PYTHONW = sys.executable  # Fallback to python.exe


def create_task():
    """Create a Windows Task Scheduler entry for BilalAgent scheduler."""
    task_name = "BilalAgent_Scheduler"
    
    # Build schtasks command
    cmd = [
        "schtasks", "/create",
        "/tn", task_name,
        "/tr", f'"{PYTHONW}" "{SCHEDULER_PATH}"',
        "/sc", "ONLOGON",       # Run at login
        "/rl", "LIMITED",       # Run with limited privileges
        "/f",                   # Force overwrite if exists
    ]
    
    print(f"Creating scheduled task: {task_name}")
    print(f"  Script: {SCHEDULER_PATH}")
    print(f"  Python: {PYTHONW}")
    print(f"  Trigger: On login")
    print()
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Task '{task_name}' created successfully!")
            print(f"   The scheduler will run automatically at login.")
            print(f"\n   To run now: python scheduler.py")
            print(f"   To remove:  schtasks /delete /tn {task_name} /f")
        else:
            print(f"❌ Failed to create task:")
            print(f"   {result.stderr}")
            print(f"\n   Try running this script as Administrator.")
    except FileNotFoundError:
        print("❌ schtasks not found. Are you on Windows?")
    except Exception as e:
        print(f"❌ Error: {e}")


def remove_task():
    """Remove the BilalAgent scheduler task."""
    task_name = "BilalAgent_Scheduler"
    
    try:
        result = subprocess.run(
            ["schtasks", "/delete", "/tn", task_name, "/f"],
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            print(f"✅ Task '{task_name}' removed.")
        else:
            print(f"Task '{task_name}' not found or already removed.")
    except Exception as e:
        print(f"❌ Error: {e}")


def check_task():
    """Check if the scheduler task exists."""
    task_name = "BilalAgent_Scheduler"
    
    try:
        result = subprocess.run(
            ["schtasks", "/query", "/tn", task_name],
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            print(f"✅ Task '{task_name}' exists:")
            print(result.stdout)
        else:
            print(f"❌ Task '{task_name}' not found.")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="BilalAgent Windows Scheduler Setup")
    parser.add_argument("action", nargs="?", default="create", 
                        choices=["create", "remove", "check"],
                        help="Action to perform (default: create)")
    args = parser.parse_args()
    
    if args.action == "create":
        create_task()
    elif args.action == "remove":
        remove_task()
    elif args.action == "check":
        check_task()
