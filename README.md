# BilalAgent v2.0

**Personal AI Desktop Agent** — runs 100% locally with no paid APIs. Built by [Bilal Ahmad Sheikh](https://github.com/bilalahmadsheikh), AI Engineering, 3rd year.

## Features

| Feature | Description |
|---|---|
| 🤖 **AI Content** | LinkedIn posts, cover letters, gig descriptions via Gemma 3 4B |
| 💼 **Job Search** | Multi-site scraping (Indeed, Glassdoor, LinkedIn) + profile scoring |
| 📊 **Dashboard** | Tkinter 5-tab UI: stats, RAM monitor, mode selector, data tables |
| 🔒 **3 Intelligence Modes** | Pure Local / Web Copilot / Hybrid Refiner |
| 🌐 **Chrome Extension** | Context snap, approval overlay, AI response capture |
| 📅 **Scheduler** | Weekly LinkedIn posts, automated GitHub monitoring |
| 🎤 **Voice Input** | Whisper-based hands-free commands (optional) |
| 💻 **System Tray** | Always-on icon with quick actions and mode switching |

## Quick Start

```bash
cd D:\beelal_007

# 1. Install dependencies
pip install pyyaml openpyxl psutil fastapi uvicorn requests
pip install pystray Pillow schedule keyboard
pip install playwright-stealth python-jobspy python-dotenv

# 2. Set up Playwright
playwright install chromium

# 3. Download models
ollama pull gemma3:1b    # Required — router
ollama pull gemma3:4b    # Required — content

# 4. Configure
copy .env.example .env   # Add your GITHUB_PAT

# 5. Launch everything
python startup.py
```

## Usage

### Command Line

```bash
# Content generation
python agent.py "write a linkedin post about IlmSeUrooj"
python agent.py "write a cover letter for Python Developer at Google"
python agent.py "generate fiverr gig for mlops"

# Job search
python agent.py "find AI Engineer jobs remote"
python agent.py "show my applications"

# LinkedIn Brand
python agent.py "generate weekly posts"
python agent.py "generate weekly posts hybrid"
python agent.py "check github activity"
python agent.py "brand check"

# Freelance
python agent.py "check upwork for python projects"
```

### Dashboard

```bash
python ui/dashboard.py
```

5-tab interface:
- **Overview** — Intelligence Mode selector, live RAM monitor, stats, recent actions
- **Jobs** — Job applications table, search, filter by status
- **Posts** — LinkedIn posts, generate weekly, open drafts
- **Gigs** — Freelance gigs, create new, open Excel
- **Settings** — Edit settings.yaml directly

### System Tray

```bash
python startup.py
```

Right-click the tray icon for:
- Open Dashboard
- Find Jobs / Write Post / Create Gig / Check Projects
- View job and post logs
- Switch Intelligence Mode
- Settings / Quit

### Intelligence Modes

| Mode | How It Works | Best For |
|---|---|---|
| **🔒 Pure Local** | Ollama only — private, offline | Daily use, privacy |
| **🌐 Web Copilot** | Claude/ChatGPT in browser | Complex analysis |
| **✨ Hybrid Refiner** | Local draft → Claude polish | LinkedIn posts |

Switch modes via:
- Dashboard → Overview tab → Radio buttons
- System Tray → Right-click → Intelligence Mode
- Edit `config/settings.yaml` → `intelligence_mode:`

### Voice Input (Optional)

```bash
pip install openai-whisper sounddevice numpy
python tools/voice_tools.py
```

### Windows Autostart

```bash
python setup_autostart.py add      # Enable autostart
python setup_autostart.py check    # Verify status
python setup_autostart.py remove   # Disable
```

## Architecture

```
User → Chrome Extension ←→ FastAPI Bridge (localhost:8000)
                                ↓
                         agent.py (main entry)
                                ↓
                    Gemma 3 1B (router, always warm)
                   ╱           │           ╲
              Content      Jobs Agent    Brand Engine
            (Gemma 3 4B)   (JobSpy)    (GitHub Monitor)
                                        (Post Scheduler)
                                        (Hybrid Refiner)
```

## Model Stack

| Model | Role | RAM |
|---|---|---|
| Gemma 3 1B | Router + NLP + Scoring | ~1 GB |
| Gemma 3 4B | Content generation | ~3.3 GB |
| Gemma 2 9B | Fallback (optional) | ~6 GB |

## File Structure

```
├── agent.py              # CLI entry point
├── startup.py            # Full service launcher
├── scheduler.py          # Background post scheduler
├── setup_autostart.py    # Windows Registry autostart
├── setup_scheduler_windows.py  # Task Scheduler setup
├── agents/               # Orchestrator, Content, NLP agents
├── tools/                # Model runner, content tools, jobs, voice
├── connectors/           # GitHub, JobSpy, Freelance, GitHub Monitor
├── memory/               # SQLite, Excel loggers, caches
├── bridge/               # FastAPI server (8 endpoints)
├── chrome_extension/     # Manifest V3 extension
├── ui/                   # Dashboard (tkinter), Tray (pystray), CLI approval
├── config/               # profile.yaml, settings.yaml
└── docs/                 # 9 documentation files
```

## License

Personal project — see [GitHub](https://github.com/bilalahmadsheikh/beelal_007).
