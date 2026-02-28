"""
dashboard.py — BilalAgent v2.0 Tkinter Dashboard
5-tab interface: Overview, Jobs, Posts, Gigs, Settings
Features: Intelligence Mode selector, RAM monitor, stats grid
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext
import threading
import json
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import psutil
import yaml


# ─── Settings Helper ──────────────────────────────

SETTINGS_PATH = os.path.join(PROJECT_ROOT, "config", "settings.yaml")


def load_settings() -> dict:
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {"intelligence_mode": "local"}


def save_settings(data: dict):
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def save_setting(key: str, value):
    settings = load_settings()
    settings[key] = value
    save_settings(settings)


# ─── Dark Theme Colors ───────────────────────────

BG = "#0f172a"
BG_CARD = "#1e293b"
BG_INPUT = "#334155"
FG = "#e2e8f0"
FG_DIM = "#94a3b8"
ACCENT = "#3b82f6"
GREEN = "#10b981"
YELLOW = "#f59e0b"
RED = "#ef4444"
PURPLE = "#8b5cf6"


# ─── Dashboard App ───────────────────────────────

class DashboardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BilalAgent v2.0 — Dashboard")
        self.root.geometry("960x700")
        self.root.configure(bg=BG)
        self.root.minsize(800, 600)

        # Configure ttk style
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self._configure_styles()

        # Main container
        main = ttk.Frame(root, style="Main.TFrame")
        main.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Header
        header = tk.Frame(main, bg=ACCENT, height=48)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="⚡ BilalAgent v2.0", font=("Segoe UI", 14, "bold"),
                 bg=ACCENT, fg="white").pack(side=tk.LEFT, padx=16)

        self.mode_label = tk.Label(header, text="Mode: Local", font=("Segoe UI", 10),
                                   bg=ACCENT, fg="#bfdbfe")
        self.mode_label.pack(side=tk.RIGHT, padx=16)

        # Tabs
        self.notebook = ttk.Notebook(main, style="Dark.TNotebook")
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self._build_overview_tab()
        self._build_jobs_tab()
        self._build_posts_tab()
        self._build_gigs_tab()
        self._build_settings_tab()

        # Start RAM monitor
        self._update_ram()

    def _configure_styles(self):
        s = self.style
        s.configure("Main.TFrame", background=BG)
        s.configure("Card.TFrame", background=BG_CARD)
        s.configure("Dark.TNotebook", background=BG, borderwidth=0)
        s.configure("Dark.TNotebook.Tab", background=BG_CARD, foreground=FG,
                     padding=[16, 8], font=("Segoe UI", 10))
        s.map("Dark.TNotebook.Tab",
              background=[("selected", ACCENT)],
              foreground=[("selected", "white")])
        s.configure("Card.TLabel", background=BG_CARD, foreground=FG, font=("Segoe UI", 10))
        s.configure("CardTitle.TLabel", background=BG_CARD, foreground=FG,
                     font=("Segoe UI", 12, "bold"))
        s.configure("Stat.TLabel", background=BG_CARD, foreground=ACCENT,
                     font=("Segoe UI", 24, "bold"))
        s.configure("StatSub.TLabel", background=BG_CARD, foreground=FG_DIM,
                     font=("Segoe UI", 9))
        s.configure("Dark.Horizontal.TProgressbar", troughcolor=BG_INPUT,
                     background=GREEN, thickness=18)

    # ─── Tab 1: Overview ─────────────────────────

    def _build_overview_tab(self):
        tab = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(tab, text="  Overview  ")

        # Mode selector card
        mode_frame = tk.LabelFrame(tab, text="  Intelligence Mode  ", bg=BG_CARD, fg=ACCENT,
                                    font=("Segoe UI", 11, "bold"), padx=16, pady=12,
                                    bd=1, relief="groove", highlightbackground=BG_INPUT)
        mode_frame.pack(fill=tk.X, padx=12, pady=(12, 6))

        settings = load_settings()
        self.mode_var = tk.StringVar(value=settings.get("intelligence_mode", "local"))

        modes = [
            ("🔒  Pure Local (Ollama only — private, offline, unlimited)", "local"),
            ("🌐  Web Copilot (Claude/ChatGPT in browser — needs you at desk)", "web_copilot"),
            ("✨  Hybrid Refiner (local draft + Claude polish — best quality)", "hybrid"),
        ]

        for text, val in modes:
            rb = tk.Radiobutton(mode_frame, text=text, variable=self.mode_var, value=val,
                                bg=BG_CARD, fg=FG, selectcolor=BG_INPUT,
                                activebackground=BG_CARD, activeforeground=ACCENT,
                                font=("Segoe UI", 10), anchor="w", indicatoron=True,
                                highlightthickness=0)
            rb.pack(anchor="w", pady=2)

        self.mode_var.trace_add("write", self._on_mode_change)

        # RAM Monitor card
        ram_frame = tk.LabelFrame(tab, text="  RAM Monitor  ", bg=BG_CARD, fg=GREEN,
                                   font=("Segoe UI", 11, "bold"), padx=16, pady=10,
                                   bd=1, relief="groove", highlightbackground=BG_INPUT)
        ram_frame.pack(fill=tk.X, padx=12, pady=6)

        self.ram_bar = ttk.Progressbar(ram_frame, style="Dark.Horizontal.TProgressbar",
                                        length=400, mode="determinate")
        self.ram_bar.pack(fill=tk.X, pady=(0, 4))

        self.ram_label = tk.Label(ram_frame, text="Loading...", bg=BG_CARD, fg=FG_DIM,
                                   font=("Consolas", 10))
        self.ram_label.pack(anchor="w")

        # Stats + Actions row
        row = tk.Frame(tab, bg=BG)
        row.pack(fill=tk.X, padx=12, pady=6)

        # Stats grid
        stats_frame = tk.LabelFrame(row, text="  Stats  ", bg=BG_CARD, fg=PURPLE,
                                     font=("Segoe UI", 11, "bold"), padx=12, pady=8,
                                     bd=1, relief="groove", highlightbackground=BG_INPUT)
        stats_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))

        self.stat_labels = {}
        stats = self._get_stats()
        col = 0
        for name, value in stats.items():
            f = tk.Frame(stats_frame, bg=BG_CARD)
            f.grid(row=0, column=col, padx=12, pady=4)
            v_lbl = tk.Label(f, text=str(value), bg=BG_CARD, fg=ACCENT,
                             font=("Segoe UI", 22, "bold"))
            v_lbl.pack()
            tk.Label(f, text=name, bg=BG_CARD, fg=FG_DIM,
                     font=("Segoe UI", 9)).pack()
            self.stat_labels[name] = v_lbl
            col += 1

        # Pending approvals
        pending_frame = tk.LabelFrame(row, text="  Approvals  ", bg=BG_CARD, fg=YELLOW,
                                       font=("Segoe UI", 11, "bold"), padx=12, pady=8,
                                       bd=1, relief="groove", highlightbackground=BG_INPUT)
        pending_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(4, 0))

        self.pending_label = tk.Label(pending_frame, text="0", bg=BG_CARD, fg=YELLOW,
                                       font=("Segoe UI", 22, "bold"))
        self.pending_label.pack()
        tk.Label(pending_frame, text="Pending", bg=BG_CARD, fg=FG_DIM,
                 font=("Segoe UI", 9)).pack()
        tk.Button(pending_frame, text="Review Now", bg=ACCENT, fg="white",
                  font=("Segoe UI", 9, "bold"), bd=0, padx=10, pady=4,
                  command=self._review_pending).pack(pady=(6, 0))

        # Recent Actions log
        log_frame = tk.LabelFrame(tab, text="  Recent Actions  ", bg=BG_CARD, fg=FG,
                                   font=("Segoe UI", 11, "bold"), padx=12, pady=8,
                                   bd=1, relief="groove", highlightbackground=BG_INPUT)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(6, 12))

        self.log_text = tk.Text(log_frame, bg=BG_INPUT, fg=FG, font=("Consolas", 9),
                                 height=8, bd=0, wrap=tk.WORD, state=tk.DISABLED,
                                 insertbackground=FG)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self._refresh_overview()

    def _on_mode_change(self, *args):
        mode = self.mode_var.get()
        save_setting("intelligence_mode", mode)
        labels = {"local": "🔒 Local", "web_copilot": "🌐 Web Copilot", "hybrid": "✨ Hybrid"}
        self.mode_label.config(text=f"Mode: {labels.get(mode, mode)}")

        # Update scheduler mode too
        settings = load_settings()
        if "scheduler" in settings:
            settings["scheduler"]["mode"] = mode
            save_settings(settings)

    def _get_stats(self) -> dict:
        stats = {"Jobs Applied": 0, "Posts Made": 0, "Gigs Active": 0, "GitHub Activity": 0}
        try:
            from memory.excel_logger import get_applications, get_posts, get_gigs
            stats["Jobs Applied"] = len(get_applications())
            stats["Posts Made"] = len(get_posts())
            stats["Gigs Active"] = len(get_gigs())
        except Exception:
            pass
        try:
            import sqlite3
            db = os.path.join(PROJECT_ROOT, "memory", "agent_memory.db")
            conn = sqlite3.connect(db)
            row = conn.execute("SELECT COUNT(*) FROM github_state").fetchone()
            stats["GitHub Activity"] = row[0] if row else 0
            conn.close()
        except Exception:
            pass
        return stats

    def _refresh_overview(self):
        # Update stats
        stats = self._get_stats()
        for name, lbl in self.stat_labels.items():
            lbl.config(text=str(stats.get(name, 0)))

        # Update pending approvals
        try:
            import sqlite3
            db = os.path.join(PROJECT_ROOT, "memory", "agent_memory.db")
            conn = sqlite3.connect(db)
            row = conn.execute(
                "SELECT COUNT(*) FROM pending_tasks WHERE status = 'pending'"
            ).fetchone()
            self.pending_label.config(text=str(row[0] if row else 0))
            conn.close()
        except Exception:
            pass

        # Update recent actions
        try:
            import sqlite3
            db = os.path.join(PROJECT_ROOT, "memory", "agent_memory.db")
            conn = sqlite3.connect(db)
            rows = conn.execute(
                "SELECT action_type, details, created_at FROM action_log ORDER BY id DESC LIMIT 15"
            ).fetchall()
            conn.close()

            self.log_text.config(state=tk.NORMAL)
            self.log_text.delete("1.0", tk.END)
            for r in rows:
                ts = r[2][:16] if r[2] else ""
                detail = (r[1] or "")[:80]
                self.log_text.insert(tk.END, f"  {ts}  [{r[0]}]  {detail}\n")
            self.log_text.config(state=tk.DISABLED)
        except Exception:
            pass

        # Schedule next refresh (30s)
        self.root.after(30000, self._refresh_overview)

    def _review_pending(self):
        messagebox.showinfo("Pending Approvals",
                            "Open the Chrome Extension to review pending approvals.\n"
                            "Or use CLI: python agent.py \"show approvals\"")

    # ─── RAM Monitor ─────────────────────────────

    def _update_ram(self):
        try:
            mem = psutil.virtual_memory()
            used_gb = mem.used / (1024 ** 3)
            free_gb = mem.available / (1024 ** 3)
            total_gb = mem.total / (1024 ** 3)
            pct = mem.percent

            self.ram_bar["value"] = pct

            # Check active Ollama model
            model_name = "none"
            try:
                import requests
                r = requests.get("http://localhost:11434/api/ps", timeout=2)
                if r.status_code == 200:
                    models = r.json().get("models", [])
                    if models:
                        model_name = models[0].get("name", "unknown")
            except Exception:
                pass

            color = GREEN if pct < 70 else YELLOW if pct < 85 else RED
            self.ram_label.config(
                text=f"  {used_gb:.1f}GB used  |  {free_gb:.1f}GB free  |  "
                     f"{total_gb:.1f}GB total  |  Model: {model_name}",
                fg=color
            )

            # Update progressbar color
            self.style.configure("Dark.Horizontal.TProgressbar", background=color)

        except Exception:
            self.ram_label.config(text="  RAM: unavailable", fg=RED)

        self.root.after(3000, self._update_ram)

    # ─── Tab 2: Jobs ─────────────────────────────

    def _build_jobs_tab(self):
        tab = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(tab, text="  Jobs  ")

        # Toolbar
        toolbar = tk.Frame(tab, bg=BG_CARD)
        toolbar.pack(fill=tk.X, padx=12, pady=(12, 6))

        tk.Button(toolbar, text="🔍 Search Jobs", bg=ACCENT, fg="white",
                  font=("Segoe UI", 10, "bold"), bd=0, padx=14, pady=6,
                  command=self._search_jobs).pack(side=tk.LEFT, padx=4)

        self.job_filter_var = tk.StringVar(value="all")
        for text, val in [("All", "all"), ("Applied", "applied"), ("Saved", "saved"),
                          ("Interview", "interview")]:
            tk.Radiobutton(toolbar, text=text, variable=self.job_filter_var, value=val,
                           bg=BG_CARD, fg=FG, selectcolor=BG_INPUT,
                           font=("Segoe UI", 9), command=self._refresh_jobs).pack(side=tk.LEFT, padx=4)

        # Table
        cols = ("Date", "Title", "Company", "Score", "Status")
        self.job_tree = ttk.Treeview(tab, columns=cols, show="headings", height=18)
        for c in cols:
            self.job_tree.heading(c, text=c)
        self.job_tree.column("Date", width=90)
        self.job_tree.column("Title", width=250)
        self.job_tree.column("Company", width=180)
        self.job_tree.column("Score", width=70)
        self.job_tree.column("Status", width=100)
        self.job_tree.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        self._refresh_jobs()

    def _search_jobs(self):
        query = simpledialog.askstring("Search Jobs", "Enter job search query:",
                                        parent=self.root)
        if query:
            threading.Thread(target=self._run_job_search, args=(query,), daemon=True).start()

    def _run_job_search(self, query):
        try:
            from tools.apply_workflow import run_job_search
            run_job_search(query)
            self.root.after(0, self._refresh_jobs)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))

    def _refresh_jobs(self):
        for item in self.job_tree.get_children():
            self.job_tree.delete(item)
        try:
            from memory.excel_logger import get_applications
            apps = get_applications()
            status_filter = self.job_filter_var.get()
            for app in apps:
                if status_filter != "all" and app.get("Status", "").lower() != status_filter:
                    continue
                self.job_tree.insert("", "end", values=(
                    app.get("Date", ""),
                    app.get("Title", "")[:40],
                    app.get("Company", "")[:25],
                    app.get("Score", ""),
                    app.get("Status", ""),
                ))
        except Exception:
            pass

    # ─── Tab 3: Posts ────────────────────────────

    def _build_posts_tab(self):
        tab = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(tab, text="  Posts  ")

        toolbar = tk.Frame(tab, bg=BG_CARD)
        toolbar.pack(fill=tk.X, padx=12, pady=(12, 6))

        tk.Button(toolbar, text="📝 Generate Weekly Posts", bg=GREEN, fg="white",
                  font=("Segoe UI", 10, "bold"), bd=0, padx=14, pady=6,
                  command=self._generate_posts).pack(side=tk.LEFT, padx=4)

        tk.Button(toolbar, text="📂 Open Drafts", bg=BG_INPUT, fg=FG,
                  font=("Segoe UI", 10), bd=0, padx=14, pady=6,
                  command=lambda: os.startfile(os.path.join(PROJECT_ROOT, "memory", "post_drafts"))
                  ).pack(side=tk.LEFT, padx=4)

        cols = ("Date", "Type", "Preview", "Status", "Mode")
        self.post_tree = ttk.Treeview(tab, columns=cols, show="headings", height=18)
        for c in cols:
            self.post_tree.heading(c, text=c)
        self.post_tree.column("Date", width=90)
        self.post_tree.column("Type", width=130)
        self.post_tree.column("Preview", width=350)
        self.post_tree.column("Status", width=120)
        self.post_tree.column("Mode", width=80)
        self.post_tree.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        self._refresh_posts()

    def _generate_posts(self):
        mode = self.mode_var.get()
        threading.Thread(target=self._run_generate_posts, args=(mode,), daemon=True).start()

    def _run_generate_posts(self, mode):
        try:
            from tools.post_scheduler import generate_weekly_posts
            posts = generate_weekly_posts(mode=mode)
            self.root.after(0, self._refresh_posts)
            self.root.after(0, lambda: messagebox.showinfo(
                "Posts Generated", f"Generated {len(posts)} posts (mode: {mode})"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))

    def _refresh_posts(self):
        for item in self.post_tree.get_children():
            self.post_tree.delete(item)
        try:
            from memory.excel_logger import get_posts
            posts = get_posts()
            for p in posts:
                self.post_tree.insert("", "end", values=(
                    p.get("Date", ""),
                    p.get("Type", ""),
                    (p.get("Preview", "") or "")[:60],
                    p.get("Status", ""),
                    p.get("Mode", ""),
                ))
        except Exception:
            pass

    # ─── Tab 4: Gigs ─────────────────────────────

    def _build_gigs_tab(self):
        tab = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(tab, text="  Gigs  ")

        toolbar = tk.Frame(tab, bg=BG_CARD)
        toolbar.pack(fill=tk.X, padx=12, pady=(12, 6))

        tk.Button(toolbar, text="🛠️ Create Gig", bg=PURPLE, fg="white",
                  font=("Segoe UI", 10, "bold"), bd=0, padx=14, pady=6,
                  command=self._create_gig).pack(side=tk.LEFT, padx=4)

        tk.Button(toolbar, text="📊 Open Excel", bg=BG_INPUT, fg=FG,
                  font=("Segoe UI", 10), bd=0, padx=14, pady=6,
                  command=lambda: os.startfile(
                      os.path.join(PROJECT_ROOT, "memory", "gigs_created.xlsx"))
                  ).pack(side=tk.LEFT, padx=4)

        cols = ("Date", "Platform", "Service", "Title", "Status")
        self.gig_tree = ttk.Treeview(tab, columns=cols, show="headings", height=18)
        for c in cols:
            self.gig_tree.heading(c, text=c)
        self.gig_tree.column("Date", width=90)
        self.gig_tree.column("Platform", width=100)
        self.gig_tree.column("Service", width=120)
        self.gig_tree.column("Title", width=300)
        self.gig_tree.column("Status", width=100)
        self.gig_tree.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        self._refresh_gigs()

    def _create_gig(self):
        service = simpledialog.askstring("Create Gig",
            "Service type (mlops / chatbot / blockchain / data_science / backend):",
            parent=self.root)
        if service:
            threading.Thread(target=self._run_create_gig, args=(service,), daemon=True).start()

    def _run_create_gig(self, service):
        try:
            from tools.content_tools import generate_gig_description
            result = generate_gig_description(service)
            self.root.after(0, self._refresh_gigs)
            self.root.after(0, lambda: messagebox.showinfo("Gig Created",
                f"Gig for '{service}' created:\n{json.dumps(result, indent=2)[:500]}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))

    def _refresh_gigs(self):
        for item in self.gig_tree.get_children():
            self.gig_tree.delete(item)
        try:
            from memory.excel_logger import get_gigs
            gigs = get_gigs()
            for g in gigs:
                self.gig_tree.insert("", "end", values=(
                    g.get("Date", ""),
                    g.get("Platform", ""),
                    g.get("Service Type", ""),
                    (g.get("Title", "") or "")[:50],
                    g.get("Status", ""),
                ))
        except Exception:
            pass

    # ─── Tab 5: Settings ─────────────────────────

    def _build_settings_tab(self):
        tab = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(tab, text="  Settings  ")

        toolbar = tk.Frame(tab, bg=BG_CARD)
        toolbar.pack(fill=tk.X, padx=12, pady=(12, 6))

        tk.Button(toolbar, text="💾 Save Settings", bg=GREEN, fg="white",
                  font=("Segoe UI", 10, "bold"), bd=0, padx=14, pady=6,
                  command=self._save_settings_text).pack(side=tk.LEFT, padx=4)

        tk.Button(toolbar, text="🔄 Reload", bg=BG_INPUT, fg=FG,
                  font=("Segoe UI", 10), bd=0, padx=14, pady=6,
                  command=self._load_settings_text).pack(side=tk.LEFT, padx=4)

        self.settings_text = scrolledtext.ScrolledText(tab, bg=BG_INPUT, fg=FG,
                                                        font=("Consolas", 11),
                                                        insertbackground=FG,
                                                        bd=0, wrap=tk.WORD)
        self.settings_text.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        self._load_settings_text()

    def _load_settings_text(self):
        self.settings_text.delete("1.0", tk.END)
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                self.settings_text.insert("1.0", f.read())
        except FileNotFoundError:
            self.settings_text.insert("1.0", "# Settings file not found")

    def _save_settings_text(self):
        text = self.settings_text.get("1.0", tk.END)
        try:
            yaml.safe_load(text)  # Validate YAML
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                f.write(text)
            messagebox.showinfo("Saved", "Settings saved successfully!")
        except yaml.YAMLError as e:
            messagebox.showerror("YAML Error", f"Invalid YAML:\n{e}")


def launch_dashboard():
    """Launch the dashboard window."""
    root = tk.Tk()
    app = DashboardApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch_dashboard()
