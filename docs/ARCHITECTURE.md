# Architecture — BilalAgent v2.0

## Overview

BilalAgent is a personal AI desktop agent that runs 100% locally with no paid APIs. It uses multiple Ollama models with **tiered keep_alive caching** and dynamic RAM management to operate on a resource-constrained machine (8.5GB RAM). **Phases 0-6 complete.**

## System Diagram

```
┌─────────────────────────────────────────────────┐
│                 Chrome Extension                 │
│              (Manifest V3 / Overlay)             │
│   Context Snap • Approval • MutationObserver     │
│   Cookie Sync • AI Response Capture (Hybrid)     │
└────────────────────┬────────────────────────────┘
                     │ HTTP (localhost:8000)
┌────────────────────▼────────────────────────────┐
│               FastAPI Bridge                     │
│  /command /approve /status /ai_response          │
│  /context_snap /cookies /register_task           │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│          agent.py — Main Entry Point             │
│   Startup: DB init → Profile → GitHub Sync       │
│   CLI: python agent.py "command"                 │
│   Routing: brand → freelance → content → jobs    │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│              Orchestrator Agent                  │
│            Gemma 3 1B (always warm, 5m)          │
│   Input: raw command → Output: JSON routing      │
│   {"agent", "task", "model"}                     │
└──┬──────┬──────┬──────┬──────┬──────┬───────────┘
   │      │      │      │      │      │
   ▼      ▼      ▼      ▼      ▼      ▼
┌──────┐┌──────┐┌─────┐┌─────┐┌─────┐┌───────────┐
│ NLP  ││Cont- ││Navi-││Memo-││Jobs ││  Brand    │
│Agent ││ent   ││gate ││ry   ││Agent││  Engine   │
│gemma/││Agent ││     ││     ││     ││           │
│phi4  ││4B    ││     ││     ││     ││           │
└──┬───┘└──┬───┘└─────┘└─────┘└──┬──┘└──┬────────┘
   │       │                      │      │
   │       ├─ LinkedIn posts      │      ├─ GitHub Activity Monitor
   │       ├─ Cover letters       │      ├─ Weekly Post Generator
   │       ├─ Gig descriptions    │      ├─ Hybrid Refiner (Claude)
   │       └─ Opinion pieces      │      └─ Background Scheduler
   │                              │
   │       ┌──────────────────────▼─────────────────┐
   │       │  Job Search Pipeline                    │
   │       │ CDP → JobSpy → Score → Display → Excel  │
   │       └────────────────────────────────────────┘
   │
   │       ┌────────────────────────────────────────┐
   │       │  Freelance Pipeline (Phase 5)           │
   │       │ Upwork RSS → Monitor → Gig Gen → Fiverr │
   │       └────────────────────────────────────────┘
   ▼
┌────────────────────────────────────────┐
│       Connectors & Memory              │
│  GitHub REST API (24h cache)           │
│  GitHub Activity Monitor (SQLite)      │
│  JobSpy multi-site scraper (12h cache) │
│  CDP LinkedIn interceptor (stealth)    │
│  Upwork RSS freelance monitor          │
│  SQLite (profiles, actions, memory,    │
│    content, cookies, tasks, github)    │
│  Excel (jobs, gigs, posts)             │
│  Profile YAML config                   │
└────────────────────────────────────────┘
```

## Model Stack

| Tier | Model | Ollama Name | RAM | Role | keep_alive |
|---|---|---|---|---|---|
| Router | Gemma 3 1B | `gemma3:1b` | ~1 GB | Routes commands to agents | `5m` (always warm) |
| Content | Gemma 3 4B | `gemma3:4b` | ~3.3 GB | LinkedIn posts, cover letters, gigs, weekly posts | `30s` + explicit unload |
| NLP | Phi-4 Mini | `phi4-mini` | ~3 GB | Scoring, analysis | `30s` |
| Fallback | Gemma 2 9B | `gemma2:9b` | ~6 GB | Reliable alternative | `30s` |

## RAM Management Strategy

**Tiered keep_alive** — not `keep_alive:0` (which wastes time reloading):
- **Orchestrator**: `keep_alive=5m` — always warm for fast routing (1s TTFT on cache hit)
- **Specialists**: `keep_alive=30s` — short window for follow-up calls
- **After generation**: explicit `force_unload()` to reclaim RAM immediately

**Load/Unload flow:**
```
1. Orchestrator routes command          (gemma3:1b stays loaded)
2. Content agent unloads orchestrator   (force_unload gemma3:1b)
3. Gemma 3 4B loads + generates         (safe_run with RAM check)
4. Content agent unloads specialist     (force_unload gemma3:4b)
5. Orchestrator reloads naturally on next command
```

## Dynamic Profile System

All prompts read from `config/profile.yaml` at runtime:
- **content_agent.py** → `_build_system_prompt()` injects name, degree, GitHub, location
- **content_tools.py** → `_load_profile()` injects name for authorship and GitHub URLs
- No hardcoded profile data in any prompt template

## Content Generation Pipeline

```
User Input: "write a linkedin post about IlmSeUrooj covering chrome extension"
  │
  ├─ Regex extracts project_name: "ilmseurooj" (first word after about/for/on)
  ├─ Full user input passed as user_request to all generators
  │
  ├─ _find_repo_name("ilmseurooj") → fuzzy match → "IlmSeUrooj"
  ├─ _get_deep_repo_context("IlmSeUrooj")
  │   ├─ README.md (full)
  │   ├─ docs/ folder (all .md files)
  │   ├─ CHANGELOG.md
  │   ├─ package.json (tech stack)
  │   └─ Recent commits (30)
  │
  ├─ _compress_context() → 39KB → 5KB
  │
  ├─ Prompt = repo_context + type_instructions + USER'S REQUEST
  └─ → content_agent.generate() → Gemma 3 4B → post
```

## LinkedIn Brand Engine (Phase 6)

```
"generate weekly posts"
  │
  ├─ GitHubActivityMonitor.get_content_ideas()
  │   ├─ check_new_activity() — repos, commits, stars, READMEs
  │   └─ Generate 3 ideas: project_showcase, learning_update, opinion
  │
  ├─ For each idea (3 posts):
  │   ├─ Mode "local": content_agent.generate() → gemma3:4b
  │   ├─ Mode "hybrid": local draft → Claude web UI polish
  │   │   ├─ Playwright opens claude.ai with extension loaded
  │   │   ├─ Types: "Refine this LinkedIn post..."
  │   │   ├─ MutationObserver captures Claude's response
  │   │   └─ ai_response → bridge → returned as polished text
  │   └─ Mode "web_copilot": full generation via Claude
  │
  ├─ Save to memory/post_drafts/{date}_{type}.txt
  ├─ Log to SQLite content_log (status="pending_approval")
  └─ Log to linkedin_posts.xlsx
```

## Command Pipeline

```
User Input → Orchestrator (gemma3:1b, 5m cache)
          → JSON: {"agent": "content", "task": "write_post", "model": "gemma3:4b"}
          → _try_brand() → _try_freelance() → _handle_content() / _handle_jobs()
          → Content Agent: unload router → load specialist → generate → unload specialist
          → Post-processing: clean, add repo link, add hashtags
          → Response displayed + RAM delta shown
          → Action logged to SQLite
```

## Directory Structure

```
D:\beelal_007\
├── agent.py                 # ★ Main CLI entry + command parsing + routing
├── scheduler.py             # ★ Background scheduler (Monday 9am posts, hourly checks)
├── setup_scheduler_windows.py # ★ Windows Task Scheduler setup (schtasks)
├── CLAUDE.md                # ★ Project identity + rules for AI assistants
├── agents/                  # Agent definitions
│   ├── orchestrator.py      # ★ Gemma 3 1B command router
│   ├── content_agent.py     # ★ Gemma 3 4B content generation (dynamic profile)
│   └── nlp_agent.py         # ★ Profile-aware NLP analyst
├── tools/                   # Core utilities
│   ├── model_runner.py      # ★ Ollama wrapper with tiered keep_alive
│   ├── content_tools.py     # ★ LinkedIn, cover letter, gig generators
│   ├── post_scheduler.py    # ★ Weekly posts + hybrid_refine (3 modes)
│   ├── job_tools.py         # ★ Job scoring via gemma3:1b (profile-matched, cached)
│   ├── apply_workflow.py    # ★ Full job pipeline: search → score → approve → log
│   ├── gig_tools.py         # ★ Fiverr/Upwork gig + proposal generation
│   ├── cdp_interceptor.py   # ★ LinkedIn Voyager API via CDP + stealth
│   └── browser_tools.py     # ★ Stealth browser: LinkedIn post, Fiverr gig + overlay
├── connectors/              # Platform connectors
│   ├── github_connector.py  # ★ REST API + 24h cache
│   ├── github_monitor.py    # ★ Activity monitor (repos, commits, stars, READMEs)
│   ├── jobspy_connector.py  # ★ Multi-site scraper (Indeed, Glassdoor, LinkedIn)
│   └── freelance_monitor.py # ★ Upwork RSS monitor with keyword matching
├── memory/                  # Persistent storage
│   ├── db.py                # ★ SQLite (7 tables: profiles, actions, memory, content,
│   │                        #          cookies, tasks, seen_projects, github_state)
│   ├── excel_logger.py      # ★ Excel: applied_jobs.xlsx, gigs_created.xlsx, linkedin_posts.xlsx
│   ├── agent_memory.db      # SQLite database
│   ├── github_cache.json    # GitHub API cache (24h)
│   ├── job_cache.json       # JobSpy search cache (12h)
│   ├── applied_jobs.xlsx    # Job application tracker
│   ├── gigs_created.xlsx    # Freelance gig tracker
│   ├── linkedin_posts.xlsx  # LinkedIn post tracker (Phase 6)
│   ├── screenshots/         # Browser automation screenshots
│   ├── cover_letters/       # Generated cover letters
│   ├── gig_drafts/          # Generated gig descriptions
│   └── post_drafts/         # Generated weekly posts (Phase 6)
├── bridge/                  # FastAPI bridge (localhost:8000)
│   └── server.py            # ★ 8 endpoints: context_snap, approval, cookies, tasks, ai_response
├── chrome_extension/        # Manifest V3 Chrome Extension
│   ├── manifest.json        # ★ Permissions: cookies, scripting, storage, tabs
│   ├── background.js        # ★ Cookie sync, message relay, task polling
│   ├── content_script.js    # ★ Context snap, overlay, MutationObserver + task_id
│   ├── popup.html           # ★ Status popup with bridge connection indicator
│   ├── popup.js             # ★ Popup logic
│   └── icons/               # ★ Extension icons (16/48/128px)
├── config/                  # Configuration
│   └── profile.yaml         # ★ Dynamic profile (name, GitHub, degree, skills)
├── ui/                      # Approval interfaces
│   └── approval_cli.py      # ★ CLI fallback: [A]pprove / [E]dit / [C]ancel
├── test_all.py              # ★ Full test suite
└── docs/                    # Documentation (10 files)
```

★ = Implemented (Phases 0-6 complete)

## Key Design Decisions

1. **No paid APIs** — Everything runs locally or via free services
2. **No Tkinter** — Approval happens via Chrome Extension overlay (CLI fallback)
3. **Never submit without approval** — Hard rule, no exceptions
4. **RAM-first architecture** — Only one heavy model loaded at a time
5. **Two-tier routing** — Lightweight 1B routes, heavier 4B executes on-demand
6. **All model calls through safe_run()** — Never call Ollama directly
7. **Tiered keep_alive** — Router stays warm (5m), specialists auto-expire (30s) + explicit unload
8. **Dynamic profile** — All prompts read from profile.yaml, nothing hardcoded
9. **24h caching** — GitHub data cached to avoid rate limits and speed up responses
10. **12h job cache** — JobSpy results cached to avoid repeated scraping
11. **SQLite audit trail** — Every action logged for transparency
12. **User prompt passthrough** — Full user input passed as `user_request` to all generators
13. **Profile caching** — job_tools loads profile once, not per-job (in-memory cache)
14. **Cookie sync** — Chrome Extension syncs cookies → SQLite → Playwright reuses them
15. **Stealth everywhere** — playwright-stealth on all browser contexts, modern user-agents
16. **Hybrid Refiner** — Local + Claude web UI for superior LinkedIn content
17. **GitHub-driven content** — Activity monitor turns real commits/stars into post topics
18. **Three Excel trackers** — Jobs, gigs, LinkedIn posts with color-coded status
