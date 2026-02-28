# Setup Guide — BilalAgent v2.0

## Prerequisites

| Tool | Required Version | Install |
|---|---|---|
| Python | 3.12+ | [python.org](https://python.org) |
| Node.js | 22+ | [nodejs.org](https://nodejs.org) |
| Ollama | Latest | [ollama.com](https://ollama.com) |
| Chrome | Latest | For extension loading |

## Python Packages

```bash
pip install crewai playwright psutil fastapi uvicorn playwright-stealth python-dotenv requests pyyaml openpyxl python-jobspy schedule
```

### Playwright Setup
```bash
playwright install chromium
```

## Ollama Models

```bash
# Required
ollama pull gemma3:1b       # Orchestrator (router)
ollama pull gemma3:4b       # Content generation

# Optional
ollama pull gemma2:9b       # Fallback
ollama pull phi4-mini       # Logic/scoring
```

## Environment Variables

Create `D:\beelal_007\.env`:

```env
GITHUB_PAT=your_github_token_here
GITHUB_USERNAME=bilalahmadsheikh
OLLAMA_BASE_URL=http://localhost:11434
BRIDGE_PORT=8000
```

## Chrome Extension

1. Open `chrome://extensions`
2. Enable **Developer Mode**
3. Click **Load unpacked** → select `D:\beelal_007\chrome_extension\`

## Verify Installation

```bash
# 1. Python
python --version  # → 3.12+

# 2. Packages
pip show fastapi uvicorn playwright-stealth pyyaml openpyxl python-jobspy schedule

# 3. Ollama
ollama list  # → gemma3:1b, gemma3:4b at minimum

# 4. Playwright
python -c "from playwright.sync_api import sync_playwright; print('Playwright OK')"

# 5. Model Runner
python -c "from tools.model_runner import get_free_ram; print(f'RAM: {get_free_ram():.1f}GB')"
```

## Running the Agent

```bash
cd D:\beelal_007

# Start the bridge server (background)
python -m uvicorn bridge.server:app --port 8000 &

# Basic usage
python agent.py "your command here"

# Examples — Content Generation
python agent.py "write a linkedin post about IlmSeUrooj"
python agent.py "write a cover letter for a Python developer role"

# Examples — Job Search
python agent.py "find AI Engineer jobs remote"
python agent.py "show my applications"

# Examples — Freelance
python agent.py "generate fiverr gig for mlops"
python agent.py "check upwork for python projects"

# Examples — LinkedIn Brand (Phase 6)
python agent.py "generate weekly posts"
python agent.py "generate weekly posts hybrid"
python agent.py "check github activity"
python agent.py "brand check"
```

## Background Scheduler

```bash
# Run scheduler manually
python scheduler.py

# Register with Windows Task Scheduler (runs at login)
python setup_scheduler_windows.py create

# Check if registered
python setup_scheduler_windows.py check

# Remove from scheduler
python setup_scheduler_windows.py remove
```

### What Happens on Startup
1. **RAM check** — displays available memory
2. **Database init** — creates SQLite tables (profiles, actions, memory, content, cookies, tasks, seen_projects, github_state)
3. **Profile load** — reads `config/profile.yaml` into memory
4. **GitHub sync** — fetches repos and caches for 24h
5. **Command routing** — orchestrator classifies → agent executes
