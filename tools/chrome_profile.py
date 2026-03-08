"""
tools/chrome_profile.py — BilalAgent v3.1
Manages Chrome profile detection and launch for BilalAgent.

The LinkedIn-logged-in profile is:
  Folder: Default
  Email:  ba8516127@gmail.com
  Path:   %LOCALAPPDATA%\\Google\\Chrome\\User Data\\Default

All settings come from config/settings.yaml under the 'chrome' key.
"""

import os
import json
import yaml

PROJECT_ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_PATH = os.path.join(PROJECT_ROOT, "config", "settings.yaml")
EXTENSION_DIR = os.path.join(PROJECT_ROOT, "chrome_extension")


def _load_chrome_settings() -> dict:
    """Return the 'chrome' section of settings.yaml."""
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f) or {}
        return settings.get("chrome", {})
    except Exception:
        return {}


def get_profile_path() -> str:
    """
    Return the full path to the configured Chrome profile folder.
    Reads profile_folder and user_data_dir from config/settings.yaml.
    Raises FileNotFoundError if the folder does not exist.
    """
    cfg        = _load_chrome_settings()
    user_data  = os.path.expandvars(
        cfg.get("user_data_dir",
                r"%LOCALAPPDATA%\Google\Chrome\User Data")
    )
    folder     = cfg.get("profile_folder", "Default")
    path       = os.path.join(user_data, folder)

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Chrome profile folder not found: {path}\n"
            f"Check chrome.profile_folder in config/settings.yaml"
        )
    return path


def get_chrome_exe() -> str:
    """
    Return the Chrome executable path.
    Reads from config/settings.yaml first, then falls back to standard paths.
    Raises FileNotFoundError if Chrome cannot be located.
    """
    cfg = _load_chrome_settings()
    candidates = [
        cfg.get("executable", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    raise FileNotFoundError(
        "Chrome executable not found. "
        "Set chrome.executable in config/settings.yaml"
    )


def get_extension_path() -> str:
    """Return path to the BilalAgent Chrome extension."""
    if not os.path.exists(EXTENSION_DIR):
        raise FileNotFoundError(f"Extension not found: {EXTENSION_DIR}")
    return EXTENSION_DIR


def verify_profile() -> dict:
    """
    Verify the configured Chrome profile exists and check for LinkedIn cookies.

    Returns dict:
        profile_path   — full folder path
        profile_name   — name from Preferences file
        has_cookies    — whether Network/Cookies exists
        cookie_size_kb — size of cookie db in KB
        linkedin_count — number of LinkedIn cookies (0 if Chrome is running)
    """
    profile_path = get_profile_path()
    cfg          = _load_chrome_settings()
    expected_name = cfg.get("profile_name", "")

    # Read internal profile name from Preferences
    prefs_path   = os.path.join(profile_path, "Preferences")
    profile_name = "Unknown"
    try:
        with open(prefs_path, "r", encoding="utf-8") as f:
            prefs = json.load(f)
        profile_name = prefs.get("profile", {}).get("name", "Unknown")
    except Exception:
        pass

    # Check cookie file
    cookies_path = os.path.join(profile_path, "Network", "Cookies")
    has_cookies  = os.path.exists(cookies_path)
    size_kb      = os.path.getsize(cookies_path) // 1024 if has_cookies else 0

    # Try to count LinkedIn cookies (may fail if Chrome has the file locked)
    linkedin_count = -1  # -1 = locked / couldn't check
    if has_cookies:
        import sqlite3, shutil, tempfile
        tmp = os.path.join(tempfile.gettempdir(), "bilal_cookie_check.sqlite")
        try:
            shutil.copy2(cookies_path, tmp)
            conn = sqlite3.connect(tmp)
            row  = conn.execute(
                "SELECT COUNT(*) FROM cookies WHERE host_key LIKE '%linkedin%'"
            ).fetchone()
            conn.close()
            linkedin_count = row[0] if row else 0
        except Exception:
            linkedin_count = -1  # Chrome is running, file locked
        finally:
            try:
                os.unlink(tmp)
            except Exception:
                pass

    result = {
        "profile_path":   profile_path,
        "profile_name":   profile_name,
        "expected_name":  expected_name,
        "has_cookies":    has_cookies,
        "cookie_size_kb": size_kb,
        "linkedin_count": linkedin_count,
    }

    print(f"  [CHROME] Profile folder : {profile_path}")
    print(f"  [CHROME] Profile name   : {profile_name}")
    print(f"  [CHROME] Cookies        : {'YES' if has_cookies else 'NO'} ({size_kb}KB)")
    if linkedin_count == -1:
        print(f"  [CHROME] LinkedIn cookies: LOCKED (Chrome is running — expected)")
    else:
        print(f"  [CHROME] LinkedIn cookies: {linkedin_count}")

    return result


if __name__ == "__main__":
    print("=== Chrome Profile Verification ===\n")
    try:
        info = verify_profile()
        print(f"\nProfile path  : {info['profile_path']}")
        print(f"Profile name  : {info['profile_name']}")
        print(f"Has cookies   : {info['has_cookies']}")
        print(f"Cookie size   : {info['cookie_size_kb']}KB")
        li = info['linkedin_count']
        print(f"LinkedIn      : {li if li >= 0 else 'locked (Chrome running)'}")
        print(f"\nChrome exe    : {get_chrome_exe()}")
        print(f"Extension     : {get_extension_path()}")
        print("\nAll OK — ready to launch.")
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
