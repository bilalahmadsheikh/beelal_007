"""
tray_app.py — BilalAgent v2.0 System Tray Application
Status icon with right-click menu, toast notifications, mode switching.
"""

import os
import sys
import threading

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Installing pystray and Pillow...")
    os.system(f"{sys.executable} -m pip install pystray Pillow")
    import pystray
    from PIL import Image, ImageDraw, ImageFont

import yaml


# ─── Settings ────────────────────────────────────

SETTINGS_PATH = os.path.join(PROJECT_ROOT, "config", "settings.yaml")


def load_settings() -> dict:
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {"intelligence_mode": "local"}


def save_setting(key: str, value):
    settings = load_settings()
    settings[key] = value
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        yaml.dump(settings, f, default_flow_style=False, sort_keys=False)


# ─── Icon Generation ─────────────────────────────

def create_icon_image() -> Image.Image:
    """Create a 64x64 blue icon with 'BA' text."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Blue circle background
    draw.ellipse([2, 2, 62, 62], fill="#3b82f6", outline="#1d4ed8", width=2)

    # White "BA" text
    try:
        font = ImageFont.truetype("segoeui.ttf", 22)
    except Exception:
        try:
            font = ImageFont.truetype("arial.ttf", 22)
        except Exception:
            font = ImageFont.load_default()

    # Center text
    bbox = draw.textbbox((0, 0), "BA", font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (64 - tw) // 2
    y = (64 - th) // 2 - 2
    draw.text((x, y), "BA", fill="white", font=font)

    return img


# ─── Toast Notifications ─────────────────────────

def show_toast(title: str, message: str):
    """Show a Windows toast notification."""
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name="BilalAgent v2.0",
            timeout=5,
        )
    except ImportError:
        # Fallback: use win10toast or just print
        try:
            from win10toast import ToastNotifier
            ToastNotifier().show_toast(title, message, duration=5, threaded=True)
        except ImportError:
            print(f"[TOAST] {title}: {message}")


# ─── Menu Actions ────────────────────────────────

def open_dashboard(icon=None, item=None):
    """Launch the dashboard in a separate thread."""
    def _launch():
        from ui.dashboard import launch_dashboard
        launch_dashboard()
    threading.Thread(target=_launch, daemon=True).start()


def find_jobs(icon=None, item=None):
    """Run job search with keyword input."""
    def _run():
        import tkinter as tk
        from tkinter import simpledialog
        root = tk.Tk()
        root.withdraw()
        query = simpledialog.askstring("Find Jobs", "Enter search query:", parent=root)
        root.destroy()
        if query:
            try:
                from tools.apply_workflow import run_job_search
                result = run_job_search(query)
                show_toast("Jobs Found", f"Search complete for: {query}")
            except Exception as e:
                show_toast("Job Search Error", str(e)[:100])
    threading.Thread(target=_run, daemon=True).start()


def write_post(icon=None, item=None):
    """Generate a LinkedIn post."""
    def _run():
        try:
            settings = load_settings()
            mode = settings.get("intelligence_mode", "local")
            from tools.post_scheduler import generate_weekly_posts
            posts = generate_weekly_posts(mode=mode)
            show_toast("Posts Generated", f"{len(posts)} posts created (mode: {mode})")
        except Exception as e:
            show_toast("Post Error", str(e)[:100])
    threading.Thread(target=_run, daemon=True).start()


def create_gig(icon=None, item=None):
    """Create a Fiverr gig."""
    def _run():
        import tkinter as tk
        from tkinter import simpledialog
        root = tk.Tk()
        root.withdraw()
        service = simpledialog.askstring("Create Gig",
            "Service (mlops/chatbot/blockchain/data_science/backend):", parent=root)
        root.destroy()
        if service:
            try:
                from tools.content_tools import generate_gig_description
                generate_gig_description(service)
                show_toast("Gig Created", f"Gig for '{service}' created")
            except Exception as e:
                show_toast("Gig Error", str(e)[:100])
    threading.Thread(target=_run, daemon=True).start()


def check_projects(icon=None, item=None):
    """Check for new freelance projects."""
    def _run():
        try:
            from connectors.freelance_monitor import FreelanceMonitor
            monitor = FreelanceMonitor()
            projects = monitor.check_upwork()
            show_toast("Project Check", f"Found {len(projects)} new projects")
        except Exception as e:
            show_toast("Monitor Error", str(e)[:100])
    threading.Thread(target=_run, daemon=True).start()


def view_job_log(icon=None, item=None):
    path = os.path.join(PROJECT_ROOT, "memory", "applied_jobs.xlsx")
    if os.path.exists(path):
        os.startfile(path)
    else:
        show_toast("No Log", "No applied_jobs.xlsx found yet")


def view_post_log(icon=None, item=None):
    path = os.path.join(PROJECT_ROOT, "memory", "linkedin_posts.xlsx")
    if os.path.exists(path):
        os.startfile(path)
    else:
        show_toast("No Log", "No linkedin_posts.xlsx found yet")


def open_settings(icon=None, item=None):
    os.startfile(SETTINGS_PATH)


def set_mode(mode_name: str):
    """Change intelligence mode and show toast."""
    def _action(icon=None, item=None):
        save_setting("intelligence_mode", mode_name)
        labels = {"local": "Pure Local", "web_copilot": "Web Copilot", "hybrid": "Hybrid Refiner"}
        show_toast("Mode Changed", f"Intelligence Mode: {labels.get(mode_name, mode_name)}")
        # Update tray title
        if icon:
            icon.title = f"BilalAgent v2.0 — {labels.get(mode_name, mode_name)}"
    return _action


def quit_app(icon, item):
    """Quit the tray app."""
    icon.stop()


# ─── Build Menu ──────────────────────────────────

def build_menu():
    settings = load_settings()
    current_mode = settings.get("intelligence_mode", "local")
    labels = {"local": "Pure Local", "web_copilot": "Web Copilot", "hybrid": "Hybrid Refiner"}

    return pystray.Menu(
        pystray.MenuItem(f"BilalAgent v2.0 — {labels.get(current_mode, current_mode)}",
                         None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Open Dashboard", open_dashboard, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Find Jobs...", find_jobs),
        pystray.MenuItem("Write LinkedIn Post", write_post),
        pystray.MenuItem("Create Fiverr Gig", create_gig),
        pystray.MenuItem("Check New Projects", check_projects),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("View Job Log", view_job_log),
        pystray.MenuItem("View Post Log", view_post_log),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Intelligence Mode", pystray.Menu(
            pystray.MenuItem("🔒 Pure Local", set_mode("local"),
                             checked=lambda item: load_settings().get("intelligence_mode") == "local"),
            pystray.MenuItem("🌐 Web Copilot", set_mode("web_copilot"),
                             checked=lambda item: load_settings().get("intelligence_mode") == "web_copilot"),
            pystray.MenuItem("✨ Hybrid Refiner", set_mode("hybrid"),
                             checked=lambda item: load_settings().get("intelligence_mode") == "hybrid"),
        )),
        pystray.MenuItem("Settings", open_settings),
        pystray.MenuItem("Quit", quit_app),
    )


# ─── Launch ──────────────────────────────────────

def launch_tray():
    """Launch the system tray icon."""
    icon_image = create_icon_image()
    settings = load_settings()
    current_mode = settings.get("intelligence_mode", "local")
    labels = {"local": "Pure Local", "web_copilot": "Web Copilot", "hybrid": "Hybrid Refiner"}

    icon = pystray.Icon(
        "BilalAgent",
        icon_image,
        title=f"BilalAgent v2.0 — {labels.get(current_mode, current_mode)}",
        menu=build_menu(),
    )

    show_toast("BilalAgent v2.0", f"Running — Mode: {labels.get(current_mode, current_mode)}")
    icon.run()


if __name__ == "__main__":
    launch_tray()
