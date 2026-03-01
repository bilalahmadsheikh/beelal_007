# User Guide — BilalAgent v3.0

## Quick Start

```bash
# 1. Start the bridge server
uvicorn bridge.server:app --port 8000

# 2. Run a command
python agent.py "write a linkedin post about my latest project"

# 3. Optional: Start the dashboard
python ui/dashboard.py

# 4. Optional: Start system tray
python ui/tray_app.py
```

## Intelligence Modes

Set in `config/settings.yaml`:

| Mode | Behavior | When to Use |
|---|---|---|
| `local` | Ollama only — private, offline, unlimited | Default, everyday use |
| `web_copilot` | Uses Claude/ChatGPT in browser via copilot | When at desk, need quality |
| `hybrid` | Local draft + Claude polish | Best quality balance |

## Mode 2: Browser Copilot

**Activated when** `intelligence_mode` is `web_copilot` or `hybrid` and you say:
- "apply to this job"
- "help with this page"
- "summarize this"
- "write proposal for this"
- "use claude for..."
- "copilot"
- "browser mode"

**What happens:**
1. Agent reads the current page (CDP / UI-TARS vision / Playwright)
2. Drafts a tailored prompt based on your profile
3. Opens Claude or ChatGPT in a stealth browser
4. **Asks your permission** before every action:
   - Opening the browser → "Allow" / "Skip" / "Stop"
   - Typing the prompt → "Allow" / "Edit" / "Stop"
   - Clicking Send → "Allow" / "Stop"
   - Using the response → "Allow" / "Stop"
5. Saves the response to `memory/content_output/`

## Permission Gate System

Every browser and UI-TARS action requires your permission. You'll see a Chrome overlay:

### Overlay Buttons

| Button | Effect |
|---|---|
| **Allow Once** | Approve this single action |
| **Allow All 30min** | Auto-approve everything for 30 minutes |
| **Skip** | Skip this action, continue with the next |
| **Stop** | Cancel the entire task immediately |
| **Edit** | Modify the action before it executes |

### Allow All Mode

When "Allow All" is active:
- A green badge appears in the top-right of Chrome
- All actions auto-approve (no overlay shown)
- Click the badge to revoke at any time
- Expires automatically after the set duration

### Dashboard Controls

From the dashboard (`python ui/dashboard.py`):
- **Allow All 30min / 2hr** buttons to set auto-approve from the desktop
- **Revoke** button to immediately disable auto-approve
- **Skip scroll / extract** checkboxes to auto-skip common actions

## UI-TARS Vision Model

The agent can "see" your screen using UI-TARS:

### Starting UI-TARS
```bash
# From dashboard: click "Start 2B" or "Start 7B"
# Or programmatically:
from tools.uitars_server import get_server
server = get_server()
server.start("2b")  # Fast, ~3GB RAM
server.start("7b")  # Accurate, ~5GB RAM
```

### What UI-TARS Does
- Captures screenshots every 2 seconds
- Identifies UI elements, text, buttons
- Can read job listings, forms, and web pages
- Executes actions: click, type, scroll (with permission)

### Hardware Requirements
- Runs on **CPU only** (no GPU needed)
- 2B model: ~3GB RAM, 7-10 second startup
- 7B model: ~5GB RAM, 20-30 second startup
- First inference is slower (cold start), subsequent calls are fast

## Common Commands

| Command | What It Does |
|---|---|
| `python agent.py "brand check"` | GitHub activity summary |
| `python agent.py "generate weekly posts"` | Creates 3 LinkedIn posts from GitHub activity |
| `python agent.py "search python developer jobs"` | Multi-site job search with scoring |
| `python agent.py "write cover letter"` | Generates cover letter from profile |
| `python agent.py "generate all gigs"` | Creates 5 Fiverr gig drafts |
| `python agent.py "apply to this job"` | **Mode 2**: Opens Claude, generates cover letter |
| `python agent.py "copilot"` | **Mode 2**: Browser Copilot flow |

## File Outputs

| Output | Location |
|---|---|
| Cover letters | `memory/cover_letters/` |
| LinkedIn post drafts | `memory/post_drafts/` |
| Gig descriptions | `memory/gig_drafts/` |
| Browser Copilot responses | `memory/content_output/` |
| Job applications log | `memory/applied_jobs.xlsx` |
| Gigs created log | `memory/gigs_created.xlsx` |
| LinkedIn posts log | `memory/linkedin_posts.xlsx` |
| UI-TARS debug log | `memory/uitars_debug.log` |

## Configuration

### config/profile.yaml
Your personal profile — used in all prompts:
```yaml
name: "Bilal Ahmad Sheikh"
github: "bilalahmadsheikh"
degree: "AI Engineering, 3rd year"
skills: [Python, FastAPI, MLOps, ...]
projects:
  - name: "basepy-sdk"
    description: "Python SDK for Base blockchain"
```

### config/settings.yaml
```yaml
intelligence_mode: "local"  # local | web_copilot | hybrid
bridge_port: 8000
models:
  router: "gemma3:1b"
  content: "gemma3:4b"
```

## Troubleshooting

| Problem | Fix |
|---|---|
| Bridge not connecting | Run `uvicorn bridge.server:app --port 8000` |
| Ollama models missing | Run `ollama pull gemma3:1b` and `ollama pull gemma3:4b` |
| Permission overlay not showing | Check Chrome Extension is loaded and bridge is running |
| UI-TARS timeout | First call on CPU is slow (60-180s) — wait for warmup |
| RAM too high | Stop UI-TARS from dashboard or `server.stop()` |
| Allow All won't activate | Make sure bridge is running on port 8000 |
