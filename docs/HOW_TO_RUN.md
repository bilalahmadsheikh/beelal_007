# How to Run BilalAgent v3.0 — Complete Feature Guide

Everything runs locally. No paid APIs. No cloud dependencies.

---

## Prerequisites

```bash
# Python 3.12+ with these packages
pip install ollama psutil pyyaml requests fastapi uvicorn openpyxl mss pyautogui playwright playwright-stealth pystray Pillow schedule python-jobspy beautifulsoup4 feedparser

# Playwright browsers
playwright install chromium

# Ollama models (once)
ollama pull gemma3:1b    # Router — 1GB RAM
ollama pull gemma3:4b    # Content — 3.3GB RAM
```

---

## 1. Start the Bridge Server

The bridge connects Chrome Extension ↔ Python agent. **Start this first.**

```bash
cd D:\beelal_007
uvicorn bridge.server:app --port 8000
```

**Expected output:**
```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Verify it's running:**
```bash
python -c "import requests; print(requests.get('http://localhost:8000/').status_code)"
# Should print: 200
```

---

## 2. Brand Check (GitHub Activity Summary)

Shows your GitHub repos, recent commits, and generates LinkedIn content ideas.

```bash
python agent.py "brand check"
```

**What happens:**
1. Orchestrator (gemma3:1b) routes to brand engine
2. GitHub API fetches your 20 repos + recent commits
3. Activity monitor finds new repos/commits/stars
4. Generates 3 content ideas for LinkedIn posts

**Expected output:**
```
[STEP 1] Routing via Orchestrator (gemma3:1b)...
  gemma3:1b: TTFT=0.2s | 40 tokens | 21.3 tok/s

📊 GitHub Activity Report:
  20 changes detected

💡 Content Ideas (3):
  1. [project_showcase] my-portfolio-website
  2. [project_showcase] Image_Classifier_CNN
  3. [project_showcase] Car-Rental-system

RAM: 2.2GB → 1.7GB (delta: -0.5GB)
```

---

## 3. NLP Analysis (Skill Analysis from GitHub)

Ask questions that analyze your profile and GitHub data.

```bash
python agent.py "what are my strongest skills based on my github"
```

**What happens:**
1. Orchestrator routes to NLP agent
2. GitHub connector pulls repo data
3. gemma3:1b analyzes your repos and identifies skill patterns

**Expected output:**
```
Routing: {"agent": "nlp", "task": "analyze_skills", "model": "gemma3:1b"}
RESULT: Based on your GitHub repositories, your strongest skills are
  Python (dominant), JavaScript/TypeScript, FastAPI, ML/MLOps...
Words: 109 | RAM: 1.8GB → 1.7GB
```

---

## 4. Content Generation

Generate LinkedIn posts, cover letters, gig descriptions.

```bash
# LinkedIn post about a project
python agent.py "write a linkedin post about basepy-sdk"

# Cover letter
python agent.py "write a cover letter for a Python backend developer role at Stripe"

# Generate all 5 gig descriptions
python agent.py "generate all gigs"

# Weekly posts (3 posts from GitHub activity)
python agent.py "generate weekly posts"
```

**What happens:**
1. Orchestrator routes to content agent
2. gemma3:1b unloads, gemma3:4b loads (3.3GB)
3. Deep repo context fetched (README, docs, commits)
4. Profile injected from `config/profile.yaml`
5. gemma3:4b generates content → force unload after

**Expected output (LinkedIn post):**
```
[STEP 2] Executing via content agent (model: gemma3:4b)...
  [safe_run] gemma3:4b loaded in 4.2s
  TTFT=1.1s | 487 tokens | 12.8 tok/s

RESULT: 🚀 Just shipped basepy-sdk — a Python SDK for Base L2...
Words: 287 | RAM: 5.1GB → 1.7GB (unloaded)
```

---

## 5. Job Search

Multi-site job search with profile-based scoring.

```bash
python agent.py "search python developer jobs in remote"
python agent.py "find ML engineer jobs"
```

**What happens:**
1. JobSpy scrapes Indeed, Glassdoor, LinkedIn (12h cache)
2. Each job scored against your profile via gemma3:1b
3. Results displayed with match scores
4. Logged to `memory/applied_jobs.xlsx`

---

## 6. Freelance Monitor

```bash
# Check for new Upwork projects matching your skills
python agent.py "check freelance projects"

# Generate a proposal
python agent.py "write proposal for Python API development project"

# Generate Upwork bio
python agent.py "generate upwork bio"
```

---

## 7. Permission Gate System

Every browser/vision action requires your permission. Test it independently:

```bash
python -c "
from tools.permission_gate import PermissionGate
gate = PermissionGate()

# Turn on auto-approve for 5 minutes
gate.set_allow_all(5)
print(f'Active: {gate.is_allow_all_active()}')   # True
print(f'Remaining: {gate.time_remaining()}')      # 4m 59s

# Skip certain action types
gate.add_skip_type('scroll')
print(f'Skip types: {gate.skip_types}')           # ['scroll']

# Revoke auto-approve
gate.revoke_allow_all()
print(f'Active: {gate.is_allow_all_active()}')    # False
"
```

**Bridge permission endpoints** (while bridge is running):
```bash
# Queue a permission request
python -c "
import requests
r = requests.post('http://localhost:8000/permission/request', json={
    'task_id': 'test-1', 'action_type': 'click',
    'description': 'Click Apply on LinkedIn', 'confidence': 0.92
})
print(r.json())  # {'status': 'queued', 'task_id': 'test-1'}
"

# Check pending requests
python -c "
import requests
print(requests.get('http://localhost:8000/permission/pending').json())
"

# Set Allow All for 30 minutes
python -c "
import requests
r = requests.post('http://localhost:8000/permission/set_allow_all', json={'duration_minutes': 30})
print(r.json())  # {'status': 'ok', 'expires_at': ..., 'duration_minutes': 30}
"
```

**Chrome Extension overlay** — When a permission request is queued:
- A dark overlay appears at the bottom of Chrome
- Shows action type (CLICK/TYPE/SCROLL), description, confidence bar
- 5 buttons: **Allow Once**, **Allow All 30min**, **Skip**, **Stop**, **Edit**
- A pulsing crosshair shows the target coordinates
- Allow All mode shows a green badge in top-right (click to revoke)

---

## 8. UI-TARS Vision Model

The agent can "see" your screen using a local vision model.

```bash
# Take a screenshot (no server needed)
python -c "
from tools.uitars_runner import capture_screen
screen = capture_screen()
print(f'Screenshot: {len(screen):,} chars ({len(screen)*3/4/1024:.0f} KB)')
"
# Output: Screenshot: 1,805,740 chars (1323 KB)

# Start the UI-TARS 2B server (7 seconds to start)
python -c "
from tools.uitars_server import get_server
server = get_server()
server.start('2b')
print(f'Running: {server.is_running()}')
print(f'Model: {server.model_info}')
server.stop()
"

# Or start 7B for more accuracy (20-30 seconds)
python -c "
from tools.uitars_server import get_server
server = get_server()
server.start('7b')
# ... use it ...
server.stop()
"
```

**From the dashboard:** Click **Start 2B** or **Start 7B** button.

---

## 9. Browser Copilot (Mode 2)

Full automation chain: read page → draft prompt → fill Claude/ChatGPT → capture response.

**Setup:**
1. Set `intelligence_mode: web_copilot` in `config/settings.yaml`
2. Start bridge: `uvicorn bridge.server:app --port 8000`
3. Load Chrome Extension (see section 12)

**Run:**
```bash
python agent.py "apply to this job"
python agent.py "use claude for this"
python agent.py "copilot"
python agent.py "help with this page"
python agent.py "write proposal for this"
```

**What happens (with permission at every step):**
1. Agent reads current page (CDP → UI-TARS → Playwright)
2. Drafts a tailored prompt using your profile
3. Opens Claude.ai or ChatGPT in stealth browser
4. **Permission overlay:** "Open claude.ai" → [Allow Once]
5. Types prompt into Claude's input box
6. **Permission overlay:** "Autofill prompt" → [Allow Once]
7. Clicks Send
8. **Permission overlay:** "Click Send" → [Allow Once]
9. Waits for Claude's response (MutationObserver polling)
10. **Permission overlay:** "Use response" → [Allow Once]
11. Saves response to `memory/content_output/`

**Test prompt drafting without browser:**
```bash
python -c "
from tools.browser_copilot import BrowserCopilot
copilot = BrowserCopilot()
ctx = {
    'title': 'Senior Python Developer',
    'company': 'Google DeepMind',
    'description': 'Build ML infrastructure and APIs',
    'skills': ['Python', 'FastAPI', 'MLOps']
}
prompt = copilot.draft_llm_prompt('write cover letter', ctx)
print(f'Prompt ({len(prompt)} chars):')
print(prompt)
"
# Output: 776-char cover letter prompt with your profile injected
```

---

## 10. Dashboard (GUI)

Full desktop dashboard with tabs, stats, and controls.

```bash
python ui/dashboard.py
```

**What you see (900×700 window):**
- **Overview Tab:** Intelligence Mode selector, RAM monitor (live), Stats grid
- **UI-TARS Section:** Status indicator, Start 2B / Start 7B / Stop buttons
- **Permission Controls:** Allow All 30min/2hr, Revoke, skip checkboxes
- **Activity Tab:** Recent actions from SQLite
- **Settings Tab:** Configuration editor

---

## 11. System Tray

Runs in the background with a tray icon.

```bash
python ui/tray_app.py
```

**Right-click menu:** Quick actions (brand check, find jobs, write post), mode selector, quit.

---

## 12. Chrome Extension

**Install:**
1. Open Chrome → `chrome://extensions/`
2. Enable "Developer mode" (top right)
3. Click "Load unpacked"
4. Select `D:\beelal_007\chrome_extension\`
5. Pin the extension to your toolbar

**Features:**
- **Context Snap:** Right-click any page → "Send to BilalAgent" → sends page data to bridge
- **Approval Overlay:** When agent wants to submit a form, overlay appears for your approval
- **Permission Overlay:** UI-TARS action approval with 5 buttons + crosshair
- **Cookie Sync:** Syncs your login cookies for Playwright sessions
- **AI Response Capture:** MutationObserver watches Claude/ChatGPT for responses

---

## 13. Background Scheduler

Runs automated tasks on a schedule.

```bash
python scheduler.py
```

**Schedule:**
- Monday 9:00 AM → Generate weekly LinkedIn posts
- Every hour → Check for approved posts to publish
- Configurable in `scheduler.py`

---

## 14. Run All Tests

```bash
# Individual phase tests
python tests/test_phase8.py     # UI-TARS: 18/18
python tests/test_phase9.py     # Permission Gate: 36/36
python tests/test_phase10.py    # Browser Copilot: 40/40

# Full v3 verification (all phases 0-10)
python tests/test_full_v3.py    # 55+ checks
```

---

## 15. Excel Trackers

All activities are logged to Excel files:

```bash
python -c "
from memory.excel_logger import get_applications, get_posts, get_gigs
print(f'Job applications: {len(get_applications())} entries')
print(f'LinkedIn posts:   {len(get_posts())} entries')
print(f'Gigs created:     {len(get_gigs())} entries')
"
```

| File | Location | Tracks |
|---|---|---|
| `applied_jobs.xlsx` | `memory/` | Jobs found, scores, application status |
| `linkedin_posts.xlsx` | `memory/` | Posts generated, approval status |
| `gigs_created.xlsx` | `memory/` | Fiverr/Upwork gigs drafted |

---

## 16. Configuration Files

### config/profile.yaml
Your identity — injected into every prompt:
```yaml
name: "Bilal Ahmad Sheikh"
github: "bilalahmadsheikh"
degree: "AI Engineering, 3rd year, 6th semester"
university: "Pakistan"
skills:
  - Python
  - FastAPI
  - MLOps
  - Web3.py
projects:
  - name: "basepy-sdk"
    description: "Python SDK for Base L2 blockchain"
```

### config/settings.yaml
```yaml
intelligence_mode: "local"    # local | web_copilot | hybrid
bridge_port: 8000
models:
  router: "gemma3:1b"
  content: "gemma3:4b"
```

---

## Quick Reference

| Action | Command |
|---|---|
| Start bridge | `uvicorn bridge.server:app --port 8000` |
| Brand check | `python agent.py "brand check"` |
| Write post | `python agent.py "write linkedin post about basepy"` |
| Weekly posts | `python agent.py "generate weekly posts"` |
| Search jobs | `python agent.py "search python jobs"` |
| Cover letter | `python agent.py "write cover letter for..."` |
| Generate gigs | `python agent.py "generate all gigs"` |
| Copilot mode | `python agent.py "copilot"` (needs web_copilot mode) |
| Dashboard | `python ui/dashboard.py` |
| System tray | `python ui/tray_app.py` |
| Run tests | `python tests/test_full_v3.py` |

---

## RAM Usage (8.5GB system)

| State | RAM Used | What's Loaded |
|---|---|---|
| Idle | ~1.5 GB | Nothing |
| Routing | ~2.5 GB | gemma3:1b (1GB) |
| Content gen | ~5 GB | gemma3:4b (3.3GB) |
| UI-TARS 2B | ~4 GB | UI-TARS 2B (3GB) |
| UI-TARS 7B | ~6 GB | UI-TARS 7B (5GB) |
| After task | ~1.7 GB | Models force-unloaded |

Only one heavy model loads at a time. The agent manages this automatically.
