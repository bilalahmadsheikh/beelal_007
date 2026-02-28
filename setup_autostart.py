"""
setup_autostart.py — BilalAgent v2.0 Windows Autostart
Adds/removes BilalAgent from Windows startup via Registry.
"""

import os
import sys
import winreg

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
STARTUP_SCRIPT = os.path.join(PROJECT_ROOT, "startup.py")

# Use pythonw for windowless operation
PYTHONW = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
if not os.path.exists(PYTHONW):
    PYTHONW = sys.executable

REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_NAME = "BilalAgent"
REG_VALUE = f'"{PYTHONW}" "{STARTUP_SCRIPT}"'


def add_to_startup():
    """Add BilalAgent to Windows startup via Registry."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, REG_NAME, 0, winreg.REG_SZ, REG_VALUE)
        winreg.CloseKey(key)

        print(f"✅ Added to Windows startup!")
        print(f"   Name:    {REG_NAME}")
        print(f"   Command: {REG_VALUE}")
        print(f"\n   BilalAgent will start automatically at login.")
        print(f"   To remove: python setup_autostart.py remove")
    except PermissionError:
        print("❌ Permission denied. Try running as Administrator.")
    except Exception as e:
        print(f"❌ Error: {e}")


def remove_from_startup():
    """Remove BilalAgent from Windows startup."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, REG_NAME)
        winreg.CloseKey(key)
        print(f"✅ Removed '{REG_NAME}' from Windows startup.")
    except FileNotFoundError:
        print(f"ℹ️ '{REG_NAME}' not found in startup — nothing to remove.")
    except Exception as e:
        print(f"❌ Error: {e}")


def check_startup():
    """Check if BilalAgent is in Windows startup."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, REG_NAME)
        winreg.CloseKey(key)
        print(f"✅ '{REG_NAME}' is in Windows startup:")
        print(f"   Command: {value}")
    except FileNotFoundError:
        print(f"❌ '{REG_NAME}' is NOT in Windows startup.")
    except Exception as e:
        print(f"❌ Error checking: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="BilalAgent Windows Autostart Setup")
    parser.add_argument("action", nargs="?", default="add",
                        choices=["add", "remove", "check"],
                        help="Action to perform (default: add)")
    args = parser.parse_args()

    if args.action == "add":
        add_to_startup()
    elif args.action == "remove":
        remove_from_startup()
    elif args.action == "check":
        check_startup()
