# BilalAgent v2.0 — Complete Project Documentation

> A fully local, privacy-first AI Desktop Agent that automates job applications, LinkedIn content, freelance gigs, and personal branding — all running on your machine with no paid APIs.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture & System Design](#2-architecture--system-design)
3. [Layer-by-Layer Breakdown](#3-layer-by-layer-breakdown)
4. [Feature Guide — What Each Feature Does & How](#4-feature-guide)
5. [Intelligence Modes](#5-intelligence-modes)
6. [Model Stack & RAM Management](#6-model-stack--ram-management)
7. [Database & Storage](#7-database--storage)
8. [Chrome Extension](#8-chrome-extension)
9. [User Interaction Guide](#9-user-interaction-guide)
10. [Configuration](#10-configuration)
11. [File Map](#11-file-map)
12. [Phase History](#12-phase-history)
13. [Test Results](#13-test-results)

---

## 1. Project Overview

**BilalAgent** is a personal AI desktop agent built by Bilal Ahmad Sheikh, a 3rd-year AI Engineering student. It runs entirely on a local machine using Ollama models — no OpenAI API keys, no cloud calls, no subscription fees. Everything stays on your hardware.

### What It Does

| Capability | What Happens |
|---|---|
| **Job Applications** | Searches Indeed/Glassdoor/LinkedIn → scores each job against your profile → generates a tailored cover letter → saves to Excel |
| **LinkedIn Posts** | Fetches your GitHub activity → generates 3 weekly thought-leadership posts → optional Claude polish via Hybrid mode |
| **Freelance Gigs** | Generates Fiverr/Upwork gig listings with 3-tier pricing → monitors Upwork RSS for matching projects → writes proposals |
| **Content Generation** | Cover letters, LinkedIn posts, gig descriptions — all from your profile data, all using your actual projects |
| **Dashboard** | Tkinter 5-tab UI showing stats, RAM usage, mode selector, data tables, settings editor |
| **System Tray** | Always-on icon in Windows taskbar with quick-action menu and toast notifications |
| **Voice Input** | Optional Whisper-based voice commands |

### Design Philosophy

1. **Local-First**: Everything runs on your machine. Your data never leaves your disk.
2. **RAM-Aware**: Only one heavy model loaded at a time. Models auto-unload after use.
3. **No Paid APIs**: Uses Ollama (free, local) for all AI. Claude.ai web UI (free tier) for optional polishing.
4. **Profile-Driven**: All content is generated from `config/profile.yaml` — your actual skills, projects, and experience.
5. **Approval-Required**: Nothing is submitted without your explicit approval.

---

## 2. Architecture & System Design

### System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER LAYER                              │
│                                                                 │
│   CLI (agent.py)    Dashboard (ui/dashboard.py)    Voice Input  │
│         │                    │                         │        │
│   System Tray (ui/tray_app.py)  ←→  Hotkey (ctrl+shift+b)     │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                      ROUTING LAYER                              │
│                                                                 │
│   Orchestrator (agents/orchestrator.py)                         │
│   Uses: Gemma 3 1B (~1GB) — always warm, routes all commands   │
│                                                                 │
│   Input: "write a cover letter for Google"                      │
│   Output: { agent: "content", task: "write_cover_letter",       │
│             model: "gemma3:4b" }                                │
└────────────┬──────────┬──────────┬──────────┬───────────────────┘
             │          │          │          │
┌────────────▼──┐ ┌─────▼────┐ ┌──▼──────┐ ┌─▼──────────────────┐
│ Content Agent │ │ NLP Agent│ │Jobs Agent│ │ Brand Engine       │
│ gemma3:4b     │ │ gemma3:1b│ │ JobSpy  │ │ GitHub Monitor     │
│ (3.3GB)       │ │ (~1GB)   │ │ Scoring │ │ Post Scheduler     │
│               │ │          │ │         │ │ Hybrid Refiner     │
│ Cover letters │ │ Profile  │ │ Search  │ │ LinkedIn posts     │
│ LinkedIn posts│ │ queries  │ │ Score   │ │ GitHub activity    │
│ Gig listings  │ │ Analysis │ │ Apply   │ │ Weekly automation  │
└───────────────┘ └──────────┘ └─────────┘ └────────────────────┘
                                                     │
┌────────────────────────────────────────────────────▼────────────┐
│                      BROWSER LAYER                              │
│                                                                 │
│   Playwright + Stealth → LinkedIn/Claude.ai/job sites           │
│   Chrome Extension ←→ FastAPI Bridge (localhost:8000)           │
│   CDP Interceptor → LinkedIn API enrichment                     │
│   Cookie Reuse → Session persistence via SQLite                 │
└─────────────────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                      STORAGE LAYER                              │
│                                                                 │
│   SQLite (agent_memory.db)     Excel Trackers (.xlsx)           │
│   ├─ action_log               ├─ applied_jobs.xlsx              │
│   ├─ content_log              ├─ linkedin_posts.xlsx            │
│   ├─ pending_tasks            └─ gigs_created.xlsx              │
│   ├─ cookies                                                    │
│   ├─ seen_projects            YAML Config                       │
│   ├─ profiles                 ├─ config/profile.yaml            │
│   ├─ memory_store             └─ config/settings.yaml           │
│   └─ github_state                                               │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow Example: "write a cover letter for Python Developer at Google"

1. **User types** the command in CLI or Dashboard
2. **Orchestrator** (gemma3:1b) classifies → `{agent: "content", model: "gemma3:4b"}`
3. **agent.py** routes to `_handle_content()` → detects "cover letter" keywords
4. **content_tools.py** extracts job title ("Python Developer"), company ("Google")
5. **github_connector.py** fetches the user's actual GitHub repos, finds most relevant ones
6. **content_agent.py** unloads gemma3:1b, loads gemma3:4b (3.3GB)
7. **System prompt** is built dynamically from `profile.yaml` — real name, degree, projects
8. **gemma3:4b generates** a ~400 word cover letter using the user's actual projects
9. **gemma3:4b unloads** immediately after generation (RAM freed)
10. **Result displayed** to user, logged to `content_log` in SQLite

---

## 3. Layer-by-Layer Breakdown

### Layer 1: User Interface Layer

**Purpose**: How the user interacts with BilalAgent.

#### CLI Entry Point — `agent.py`

The primary way to use BilalAgent. Takes a natural language command, routes it through the orchestrator, and executes the appropriate workflow.

```bash
python agent.py "write a linkedin post about IlmSeUrooj"
python agent.py "find AI Engineer jobs remote"
python agent.py "generate weekly posts hybrid"
```

**How it works**: `handle_command(user_input)` → orchestrator routes → agent executes → result displayed.

Special command patterns are caught first (before the orchestrator) via keyword matching:
- "find jobs" / "search jobs" → `_try_jobs()`
- "cover letter" / "linkedin post" / "gig" → `_handle_content()`
- "weekly posts" / "brand check" / "github activity" → `_try_brand()`
- "check upwork" / "new projects" → `_try_freelance()`

#### Dashboard — `ui/dashboard.py`

A Tkinter GUI (960×700, dark theme) with 5 tabs:

| Tab | What It Shows |
|---|---|
| **Overview** | Intelligence Mode radio buttons, live RAM monitor (3s refresh), stats grid (jobs/posts/gigs/GitHub), pending approvals, recent actions log |
| **Jobs** | Table of all job applications from `applied_jobs.xlsx`, search button, status filter (all/applied/saved/interview) |
| **Posts** | Table of LinkedIn posts from `linkedin_posts.xlsx`, "Generate Weekly Posts" button, "Open Drafts" button |
| **Gigs** | Table of freelance gigs from `gigs_created.xlsx`, "Create Gig" button, "Open Excel" button |
| **Settings** | Editable YAML text view of `config/settings.yaml`, Save/Reload buttons |

The dashboard refreshes stats every 30 seconds and RAM every 3 seconds.

#### System Tray — `ui/tray_app.py`

Always-on tray icon (64×64 blue circle with "BA" text) in the Windows taskbar. Right-click gives you:
- Open Dashboard (double-click also works)
- Find Jobs / Write Post / Create Gig / Check Projects
- View Job Log / Post Log (opens Excel directly)
- Intelligence Mode submenu (switch modes)
- Settings / Quit

Shows Windows toast notifications when actions complete.

#### Voice Input — `tools/voice_tools.py`

Optional. Uses OpenAI's Whisper tiny model (39MB) + sounddevice to:
1. Record 5 seconds of audio
2. Transcribe locally via Whisper
3. Pass the text to `agent.py` as a command

---

### Layer 2: Routing Layer

**Purpose**: Classify what the user wants and decide which agent handles it.

#### Orchestrator — `agents/orchestrator.py`

Uses the **Gemma 3 1B** model (~1GB RAM) to classify user commands into JSON:

```json
{"agent": "content", "task": "write_cover_letter", "model": "gemma3:4b"}
```

The routing model reads from `settings.yaml` (`routing_model` key) so you can swap it without code changes.

**Why a 1B model for routing?** It's lightweight (~1GB), loads in <1 second, stays warm with a 5-minute keep_alive window, and has near-zero latency for simple classification tasks. The KV cache is reused across calls when the system prompt matches.

Supported agents: `nlp`, `content`, `navigation`, `memory`, `jobs`.

---

### Layer 3: Agent Layer

**Purpose**: Execute specialized tasks using the appropriate model.

#### Content Agent — `agents/content_agent.py`

The workhorse. Generates all text content using a tiered model strategy:

1. **Primary**: Model from `settings.yaml` → `content_model_primary` (default: gemma3:4b, 3.3GB)
2. **Fallback**: Model from `settings.yaml` → `content_model_fallback` (default: gemma2:9b, 6GB)
3. **Last resort**: Router model (gemma3:1b) — for when RAM is very tight

Before generating, it:
- Unloads the router model to free RAM
- Builds a system prompt from `profile.yaml` (developer name, degree, GitHub, projects)
- Enforces minimum output length (retries if <150 chars)
- Unloads the specialist model after generation

**Typical output**: 300-800 words of content that references the user's actual projects, technologies, and GitHub repos.

#### Content Tools — `tools/content_tools.py`

High-level functions that wrap the content agent with specific workflows:

| Function | What It Does |
|---|---|
| `generate_cover_letter(title, company, description)` | Fetches relevant GitHub repos → builds job-specific prompt → generates cover letter |
| `generate_linkedin_post(project, post_type)` | Fetches deep repo context (README, docs, commits) → generates thought-leadership post |
| `generate_gig_description(service)` | Generates Fiverr/Upwork gig with 3-tier pricing → logs to Excel |

**Deep repo context** means: the system fetches the project's README, file tree, recent commits, and docs — then compresses it into a concise context string for the model.

#### NLP Agent — `agents/nlp_agent.py`

Handles profile queries, analysis, and general NLP tasks using gemma3:1b. Falls back gracefully if RAM is low.

---

### Layer 4: Connectors

**Purpose**: Interface with external services and data sources.

#### GitHub Connector — `connectors/github_connector.py`

Fetches real data from your GitHub account:
- `get_repos()` — all public repos with descriptions, languages, stars, forks
- `get_commits(repo)` — recent commits with messages and dates
- `get_file_tree(repo)` — file/directory structure
- `get_readme(repo)` — full README content

Caching: Results are cached in memory with timestamps. Cache expires after 1 hour.

#### GitHub Activity Monitor — `connectors/github_monitor.py`

Tracks changes in your GitHub account since the last check:
- New repositories created
- Recent commits (last 7 days)
- Star count changes
- README updates

Stores state in SQLite (`github_state` table). Used by the post scheduler to generate LinkedIn content ideas based on actual activity.

**Example output**: `[{type: "project_showcase", project: "IlmSeUrooj", hook: "Updated IlmSeUrooj with 5 new commits"}]`

#### JobSpy Connector — `connectors/jobspy_connector.py`

Wraps the `python-jobspy` library to scrape jobs from Indeed, Glassdoor, LinkedIn, and ZipRecruiter. Returns standardized job dicts with title, company, location, salary, description, URL.

#### Freelance Monitor — `connectors/freelance_monitor.py`

Monitors Upwork RSS feeds for new projects matching your skills. Features:
- Keywords loaded from `profile.yaml` skills
- Deduplication via SQLite (`seen_projects` table)
- Multiple RSS URL format attempts (Upwork changes these periodically)
- HTML cleaning for job descriptions

---

### Layer 5: Tools

**Purpose**: Specialized utilities for specific workflows.

#### Model Runner — `tools/model_runner.py`

The foundation of everything. Manages Ollama model lifecycle:

| Function | What It Does |
|---|---|
| `run_model(model, prompt, system)` | Call Ollama API, handle streaming, return text |
| `safe_run(model, prompt, required_gb)` | Check RAM → unload if needed → run model |
| `force_unload(model)` | Set keep_alive=0 to immediately free RAM |
| `get_free_ram()` | psutil query → available GB as float |
| `unload_specialists()` | Unload all models except the router |

**RAM management strategy**:
- Router (gemma3:1b): `keep_alive=5m` — stays warm for fast routing
- Specialists (gemma3:4b, gemma2:9b): `keep_alive=30s` — short window, then auto-free

**Before loading a specialist**: The model runner checks available RAM. If a different specialist is already loaded, it force-unloads it first. Only one heavy model is ever in RAM at a time.

#### Job Tools — `tools/job_tools.py`

Scores jobs against your profile using gemma3:1b (or whatever `routing_model` is configured):

```python
score = score_job({"title": "AI Engineer", "company": "OpenAI", "description": "..."})
# Returns: {"score": 85, "matching_skills": ["Python", "ML"], "missing": ["Go"], "reason": "..."}
```

Score breakdown:
- 90-100: Perfect match
- 70-89: Strong match
- 50-69: Partial match
- 30-49: Weak match
- 0-29: Poor match

Falls back to keyword-matching when the model fails.

#### Apply Workflow — `tools/apply_workflow.py`

Full job application pipeline:
1. `run_job_search(query)` → Search across sites → CDP enrichment → Score all jobs → Display top matches → Log to Excel
2. `run_apply_flow(job)` → Generate cover letter → Show for approval → Save file → Log to Excel

#### Post Scheduler — `tools/post_scheduler.py`

Generates 3 weekly LinkedIn posts:
1. Fetches content ideas from `GitHubActivityMonitor`
2. For each idea, generates a post via the content pipeline
3. If mode is "hybrid", sends to Claude.ai for polishing
4. Saves drafts to `memory/post_drafts/`
5. Logs to SQLite and Excel

**Hybrid Refinement Flow**:
1. Local model generates a rough draft
2. Playwright opens claude.ai with stealth
3. Chrome Extension injects the refinement prompt
4. MutationObserver captures Claude's response
5. Response sent to bridge → scheduler receives polished text

#### Gig Tools — `tools/gig_tools.py`

Generates freelance gig listings with 5 service types and 3-tier pricing:

| Service | Basic | Standard | Premium |
|---|---|---|---|
| MLOps & ML Pipeline | $20 / 3 days | $65 / 7 days | $150 / 14 days |
| AI Chatbot | $15 / 3 days | $50 / 7 days | $100 / 14 days |
| Blockchain Web3 | $25 / 3 days | $80 / 7 days | $200 / 14 days |
| Data Science | $15 / 3 days | $50 / 7 days | $100 / 14 days |
| Backend API | $20 / 3 days | $60 / 7 days | $120 / 14 days |

Also generates Upwork profile bios and client proposals.

#### Browser Tools — `tools/browser_tools.py`

Playwright + stealth for browser automation:
- Login to LinkedIn with cookie reuse
- Post content to LinkedIn
- Navigate to job pages
- CDP interception for LinkedIn API responses

Uses `playwright-stealth` to avoid bot detection.

---

### Layer 6: Bridge & Extension

**Purpose**: Connect the Chrome Extension to the Python backend.

#### FastAPI Bridge — `bridge/server.py`

Runs on `localhost:8000` (configurable via `settings.yaml`). Endpoints:

| Endpoint | What It Does |
|---|---|
| `GET /status` | Health check, returns queue size |
| `POST /extension/context` | Receives page context snapped by extension |
| `POST /extension/approve` | Receives approval/rejection from overlay |
| `POST /extension/ai_response` | Receives AI responses captured by MutationObserver |
| `GET /extension/pending` | Returns pending tasks for the extension |
| `POST /extension/register_task` | Registers a new task (e.g., hybrid refinement wait) |

#### Chrome Extension — `chrome_extension/`

Manifest V3 extension that:
1. **Context Snap**: Extracts page content (job descriptions, project listings) and sends to bridge
2. **Approval Overlay**: Shows content for review with approve/edit/reject buttons
3. **AI Response Capture**: MutationObserver watches claude.ai/ChatGPT for generated responses, sends them to bridge with task_id matching

---

### Layer 7: Storage

**Purpose**: Persist all data locally.

#### SQLite — `memory/db.py`

Single database at `memory/agent_memory.db` with 8 tables:

| Table | Purpose |
|---|---|
| `action_log` | Every action the agent takes (timestamped) |
| `content_log` | All generated content (type, text, platform, model, status) |
| `pending_tasks` | Tasks waiting for approval (content preview, status) |
| `cookies` | Browser cookies for session persistence |
| `seen_projects` | Freelance projects already processed (dedup) |
| `profiles` | Stored user profiles |
| `memory_store` | General key-value memory |
| `github_state` | GitHub activity monitor state (last checked repos/stars) |

#### Excel Trackers — `memory/excel_logger.py`

3 Excel files for human-readable tracking:

| File | Columns | Purpose |
|---|---|---|
| `applied_jobs.xlsx` | Date, Title, Company, Score, Status, URL | Track all job applications |
| `linkedin_posts.xlsx` | Date, Type, Preview, Status, Mode | Track LinkedIn posts |
| `gigs_created.xlsx` | Date, Platform, Service, Title, Status | Track freelance gigs |

All have color-coded status cells (green=applied/approved, yellow=pending, red=rejected).

---

## 4. Feature Guide

### Feature 1: Cover Letter Generation

**What it does**: Generates a personalized cover letter for a specific job, referencing your actual GitHub projects.

**Command**: `python agent.py "write a cover letter for Python Developer at Google"`

**How it works**:
1. Extracts job title ("Python Developer") and company ("Google") from the command
2. Fetches your GitHub repos, finds the most relevant ones to the job
3. For each relevant repo: fetches README, file tree, commits
4. Compresses the context into a concise summary
5. Builds a specialized prompt: "Write a cover letter for {name}, {degree}, applying for {title} at {company}. Reference these projects: {repo_data}"
6. gemma3:4b generates 300-500 words
7. Output format: Full cover letter with greeting, body paragraphs referencing projects, closing

**Expected output**: A ~400 word cover letter that mentions 2-3 of your actual projects by name, references specific technologies you used, and explains why they're relevant to the job.

### Feature 2: LinkedIn Post Generation

**What it does**: Generates a thought-leadership LinkedIn post about one of your projects.

**Command**: `python agent.py "write a linkedin post about IlmSeUrooj"`

**How it works**:
1. Matches "IlmSeUrooj" to your actual GitHub repo
2. Fetches deep context: README, full file tree, recent commits, languages used
3. Compresses to ~2000 chars of context
4. Uses a specialized system prompt with two layers:
   - **Human Layer**: Personal story, motivation, real-world problem
   - **Technical Layer**: Frameworks, architecture, design decisions
5. Output: 300-600 words with hashtags

**Expected output**: A LinkedIn post written in first person as you, telling the story of why you built the project, what technical decisions you made, and including the GitHub link.

### Feature 3: Job Search & Scoring

**What it does**: Searches multiple job sites, scores each job against your profile, and displays the best matches.

**Command**: `python agent.py "find AI Engineer jobs remote"`

**How it works**:
1. Tries CDP interception on LinkedIn first (enriched data with apply links)
2. Falls back to JobSpy for Indeed + Glassdoor
3. Each job scored 0-100 by gemma3:1b against your profile.yaml skills and projects
4. Top matches displayed with score, matching skills, missing skills, and reason
5. Top 5 saved to `applied_jobs.xlsx` as "saved"

### Feature 4: Weekly LinkedIn Posts (Automated)

**What it does**: Generates 3 LinkedIn posts per week based on your GitHub activity.

**Command**: `python agent.py "generate weekly posts"` or via Dashboard button

**How it works**:
1. GitHubActivityMonitor checks for new repos, commits, star changes
2. Generates content ideas: project showcases, learning updates, opinions
3. For each idea, runs the full content pipeline
4. Saves drafts to `memory/post_drafts/` with metadata
5. Logs to SQLite and `linkedin_posts.xlsx`
6. Status: "pending_approval" — nothing posts without your approval

### Feature 5: Freelance Gig Generation

**What it does**: Generates complete Fiverr/Upwork gig listings with pricing.

**Command**: `python agent.py "generate fiverr gig for mlops"`

**How it works**:
1. Loads SERVICE_CONFIG for the selected service type
2. Builds profile context from profile.yaml
3. Generates title, description, tags, FAQ, requirements
4. Includes 3-tier pricing (basic/standard/premium)
5. Saves draft and logs to `gigs_created.xlsx`

### Feature 6: Freelance Project Monitoring

**What it does**: Monitors Upwork RSS feeds for new projects matching your skills.

**Command**: `python agent.py "check upwork for python projects"`

**How it works**:
1. Loads keywords from profile.yaml skills or user query
2. Fetches Upwork RSS/Atom feeds for each keyword
3. Deduplicates against `seen_projects` table
4. Returns only new, unseen projects with title, description, budget, URL

---

## 5. Intelligence Modes

BilalAgent supports 3 intelligence modes, switchable from the Dashboard, Tray, or `settings.yaml`:

### 🔒 Pure Local (Default)

- **How**: Ollama only — all processing on your machine
- **Models**: gemma3:1b (routing) + gemma3:4b (content)
- **Pros**: Completely private, works offline, unlimited usage, no rate limits
- **Cons**: Quality limited by local model capability
- **Best for**: Daily use, privacy-sensitive content, offline operation

### 🌐 Web Copilot

- **How**: Opens Claude.ai or ChatGPT in a browser, types your prompt, captures the output
- **Models**: Claude/ChatGPT via browser (free tiers)
- **Pros**: Highest quality output from state-of-the-art models
- **Cons**: Requires you to be logged in, needs you at desk for CAPTCHAs
- **Best for**: Complex analysis, important cover letters, high-stakes content

### ✨ Hybrid Refiner

- **How**: Local model writes a rough draft → Claude.ai polishes it
- **Models**: gemma3:4b (draft) + Claude web UI (polish)
- **Pros**: Best quality LinkedIn posts, natural-sounding language, fast drafts
- **Cons**: Requires Claude.ai login once, slightly slower
- **Best for**: LinkedIn posts, content that needs to sound human

---

## 6. Model Stack & RAM Management

### Models Used

| Model | Size | RAM | Role | Keep Alive |
|---|---|---|---|---|
| **Gemma 3 1B** | ~0.7GB | ~1GB | Router, NLP, scoring | 5 minutes |
| **Gemma 3 4B** | ~2.5GB | ~3.3GB | Content generation (primary) | 30 seconds |
| **Gemma 2 9B** | ~5GB | ~6GB | Content generation (fallback) | 30 seconds |

### RAM Management Rules

1. **Only one heavy model at a time**: Before loading gemma3:4b, the system force-unloads gemma3:1b
2. **Auto-unload after use**: Content models unload immediately after generating
3. **RAM check before load**: `get_free_ram()` checked before every model call
4. **Graceful degradation**: If not enough RAM for 4B, tries 9B (if more RAM somehow), then falls back to 1B

### Typical RAM Flow

```
Idle:        gemma3:1b loaded (1GB used)
User types:  Orchestrator runs (gemma3:1b, warm, instant)
Routing:     Classification complete in <0.5s
Content:     gemma3:1b unloaded → gemma3:4b loaded (3.3GB)
Generating:  ~10s at ~10 tokens/sec
Done:        gemma3:4b unloaded → RAM back to baseline
```

---

## 7. Database & Storage

### SQLite Schema

```sql
-- Every action the agent takes
action_log(id, action_type, details, result, created_at)

-- All generated content
content_log(id, content_type, content, status, platform, model_used, created_at)

-- Tasks waiting for user approval
pending_tasks(id, task_id, task_type, content_preview, status, result, metadata, created_at, updated_at)

-- Browser cookies for session persistence
cookies(id, site, cookie_data, updated_at)

-- Freelance projects already seen (dedup)
seen_projects(id, project_id, title, url, keyword, seen_at)

-- GitHub monitor state
github_state(id, key, value, updated_at)
```

### File Storage

```
memory/
├── agent_memory.db           # SQLite database
├── applied_jobs.xlsx         # Job application tracker
├── linkedin_posts.xlsx       # Post tracker
├── gigs_created.xlsx         # Gig tracker
├── cover_letters/            # Generated cover letters (.txt)
├── post_drafts/              # LinkedIn post drafts (.txt)
├── gig_drafts/               # Gig listing drafts (.json)
├── content_output/           # Raw content output files
├── scheduler.log             # Background scheduler logs
└── startup.log               # Startup orchestrator logs
```

---

## 8. Chrome Extension

### Architecture

```
popup.html → Quick actions (context snap, open dashboard)
    │
background.js → Service worker, manages extension state
    │
content_script.js → Injected into all pages
    ├─ Context extraction (job pages, project pages)
    ├─ Approval overlay (approve/edit/reject)
    └─ MutationObserver → Captures AI responses from Claude/ChatGPT
    │
    └──→ POST to localhost:8000/extension/* (bridge)
```

### How the Approval Overlay Works

1. Bridge sends a pending_task to the extension
2. Content script creates a floating overlay panel
3. Shows content preview with Approve / Edit / Reject buttons
4. User decision sent back to bridge → Python code continues

### How Hybrid Refinement Uses the Extension

1. Python opens claude.ai via Playwright
2. Sets `window.__bilalAgentTaskId` for tracking
3. Types the refinement prompt
4. MutationObserver detects generation complete
5. Sends `{response, task_id}` to `/extension/ai_response`
6. Python polls bridge for the response

---

## 9. User Interaction Guide

### Getting Started

```bash
# 1. Install Python deps
pip install pyyaml openpyxl psutil fastapi uvicorn requests pystray Pillow schedule keyboard playwright-stealth python-jobspy

# 2. Install Playwright
playwright install chromium

# 3. Download Ollama models
ollama pull gemma3:1b
ollama pull gemma3:4b

# 4. Configure your profile
# Edit config/profile.yaml with your details

# 5. Set your GitHub PAT
# Edit .env: GITHUB_PAT=your_token

# 6. Launch
python startup.py
```

### Daily Workflow

1. **Morning**: BilalAgent starts automatically (if autostart configured)
2. **Job Search**: Right-click tray → "Find Jobs" → enter query → review scored results
3. **Apply**: From the Jobs tab, select a job → generate cover letter → approve → logged
4. **LinkedIn**: Dashboard → Posts tab → "Generate Weekly Posts" → review drafts → approve
5. **Freelance**: Right-click tray → "Check New Projects" → review matches → generate proposal

### Mode Switching

**Dashboard**: Overview tab → Radio buttons at the top
**Tray**: Right-click → Intelligence Mode → select mode
**YAML**: Edit `config/settings.yaml` → `intelligence_mode: hybrid`

---

## 10. Configuration

### config/profile.yaml

Your identity. Everything generated references this:

```yaml
personal:
  name: "Bilal Ahmad Sheikh"
  degree: "BE AI Engineering — 3rd Year"
  github: "bilalahmadsheikh"
  linkedin: "bilalahmadsheikh"
  location: "Pakistan"
  skills: [Python, FastAPI, PyTorch, MLOps, ...]

projects:
  - name: IlmSeUrooj
    description: "University admission portal"
    tech_stack: [Next.js, Supabase, Chrome Extension]
  # ... more projects
```

### config/settings.yaml

Runtime behavior. All dynamic values read from here:

```yaml
intelligence_mode: local     # local / web_copilot / hybrid
content_model_primary: "gemma3:4b"
content_model_fallback: "gemma2:9b"
routing_model: "gemma3:1b"
bridge_port: 8000
enable_job_search: true
enable_linkedin: true
enable_fiverr: true
enable_upwork: true
job_keywords: [AI engineer, data scientist, ...]
post_days: [Monday, Wednesday, Friday]
```

---

## 11. File Map

```
beelal_007/
├── agent.py                  # CLI entry point, command routing
├── startup.py                # Service orchestrator (bridge+tray+scheduler)
├── scheduler.py              # Background job (weekly posts, approved check)
├── setup_autostart.py        # Windows Registry autostart
├── setup_scheduler_windows.py # Task Scheduler setup
│
├── agents/
│   ├── orchestrator.py       # Command router (gemma3:1b)
│   ├── content_agent.py      # Content generation (gemma3:4b)
│   └── nlp_agent.py          # NLP/analysis (gemma3:1b)
│
├── tools/
│   ├── model_runner.py       # Ollama API + RAM management
│   ├── content_tools.py      # Cover letters, posts, gigs
│   ├── job_tools.py          # Job scoring + display
│   ├── apply_workflow.py     # Full application pipeline
│   ├── browser_tools.py      # Playwright automation
│   ├── cdp_interceptor.py    # LinkedIn CDP enrichment
│   ├── post_scheduler.py     # Weekly post generation
│   ├── gig_tools.py          # Freelance gig generation
│   └── voice_tools.py        # Whisper voice input
│
├── connectors/
│   ├── github_connector.py   # GitHub API (repos, commits, README)
│   ├── github_monitor.py     # GitHub activity tracking
│   ├── jobspy_connector.py   # Indeed/Glassdoor/LinkedIn scraping
│   └── freelance_monitor.py  # Upwork RSS monitoring
│
├── memory/
│   ├── db.py                 # SQLite schema + helpers
│   └── excel_logger.py       # Excel tracking (jobs, posts, gigs)
│
├── bridge/
│   └── server.py             # FastAPI bridge (8 endpoints)
│
├── ui/
│   ├── dashboard.py          # Tkinter 5-tab dashboard
│   ├── tray_app.py           # System tray (pystray)
│   └── approval_cli.py       # CLI approval prompts
│
├── chrome_extension/
│   ├── manifest.json         # Manifest V3
│   ├── content_script.js     # Page injection + observer
│   ├── background.js         # Service worker
│   └── popup.html            # Popup UI
│
├── config/
│   ├── profile.yaml          # User identity + projects
│   └── settings.yaml         # Runtime configuration
│
├── docs/                     # 9 documentation files
├── CLAUDE.md                 # AI assistant context file
└── README.md                 # Usage guide
```

---

## 12. Phase History

| Phase | Name | What Was Built | When |
|---|---|---|---|
| **0** | Foundation | Model runner, RAM management, Ollama integration | Night 1 |
| **1** | Routing | Orchestrator, command classification, agent routing | Night 1 |
| **2** | Content | Content agent, cover letters, LinkedIn posts, prompts | Night 2 |
| **3** | Jobs | JobSpy, CDP interception, scoring, apply workflow, Excel | Night 3 |
| **4** | Browser | Playwright, stealth, bridge server, Chrome Extension | Night 4 |
| **5** | Freelance | Upwork RSS monitor, gig tools, proposals, 5 templates | Night 5 |
| **6** | Brand | GitHub monitor, post scheduler, hybrid refiner, weekly posts | Night 6 |
| **7** | Final Shell | Dashboard, system tray, voice, startup, autostart, settings | Night 7 |

---

## 13. Test Results

Full test run across all phases, verified 2026-03-01:

```
Phase 0 — Model Runner:     9/9 passed (run_model, safe_run, keep_alive, force_unload)
Phase 1 — Orchestrator:     5/5 passed (routing to content agent confirmed)
Phase 2 — Content Agent:    4/4 passed (gemma3:4b generated 302, 393, 837 tokens)
Phase 2b — Content Tools:   3/3 passed (cover letter, LinkedIn post, gig)
Phase 3 — Job Tools:        9/9 passed (scoring returned 0-100 with matching skills)
Phase 4 — Bridge/Browser:   7/7 passed (FastAPI, dynamic URL, extension files)
Phase 5 — Freelance:        14/14 passed (5 services, 3-tier pricing, RSS monitor)
Phase 6 — GitHub/Posts:     7/7 passed (monitor, ideas, scheduler, Excel)
Phase 7 — Dashboard/Tray:   18/18 passed (mode persistence, icon, menu, RAM)
Database:                   8/8 passed (all tables exist)
Files:                      39/39 passed (all required files exist)

Total: 123 checks — 121 passed, 2 non-critical (doc mismatches)
```

---

*Built over 7 nights by Bilal Ahmad Sheikh — BilalAgent v2.0 (Phases 0-7 complete)*
