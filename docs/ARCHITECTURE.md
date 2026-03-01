# Architecture — BilalAgent v3.0

## Overview

BilalAgent is a personal AI desktop agent that runs 100% locally with no paid APIs. It uses multiple Ollama models with **tiered keep_alive caching**, a **UI-TARS vision model** via llama.cpp, and a **permission-gated browser copilot** for full automation. **Phases 0-10 complete.**

## System Diagram

```
┌─────────────────────────────────────────────────┐
│                 Chrome Extension                 │
│              (Manifest V3 / Overlay)             │
│   Context Snap • Approval • MutationObserver     │
│   Cookie Sync • AI Response Capture (Hybrid)     │
│   ★ Permission Overlay (5 buttons, crosshair)    │
│   ★ Allow All Badge (click to revoke)            │
└────────────────────┬────────────────────────────┘
                     │ HTTP (localhost:8000)
┌────────────────────▼────────────────────────────┐
│               FastAPI Bridge                     │
│  /command /approve /status /ai_response          │
│  /context_snap /cookies /register_task           │
│  ★ /permission/request /pending /result          │
│  ★ /permission/set_allow_all /allow_all_status   │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│          agent.py — Main Entry Point             │
│   Startup: DB init → Profile → GitHub Sync       │
│   CLI: python agent.py "command"                 │
│   ★ Mode 2 Check → Browser Copilot triggers      │
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
   │
   ▼
┌────────────────────────────────────────────────────┐
│  ★ UI-TARS Vision Layer (Phase 8-10)               │
│                                                    │
│  llama-server.exe (port 8081) ─── GGUF models      │
│    ├─ UI-TARS 2B (fast, ~3GB RAM)                  │
│    └─ UI-TARS 7B (accurate, ~5GB RAM)              │
│                                                    │
│  UITARSServer ─→ capture_screen() ─→ ask_uitars()  │
│       ↓              ↓                    ↓        │
│  ScreenMonitor    mss library      OpenAI API      │
│  (2s interval)    (base64 PNG)     (llama.cpp)     │
│       ↓                                  ↓        │
│  PermissionGate ←── Bridge Endpoint ←── Extension  │
│  (Allow/Skip/Stop/Edit/Allow All)       Overlay    │
│       ↓                                           │
│  execute_action() ─→ pyautogui (click/type/scroll) │
└────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────┐
│  ★ Browser Copilot (Phase 10)                      │
│                                                    │
│  Trigger: "apply to this" / "copilot" / "use       │
│           claude for" (Mode 2 in agent.py)         │
│                                                    │
│  extract_page_context()                            │
│    ├─ Strategy A: CDP (LinkedIn/Upwork/Fiverr)     │
│    ├─ Strategy B: UI-TARS vision (screen read)     │
│    └─ Strategy C: Playwright (page source)         │
│         ↓                                          │
│  draft_llm_prompt() ─→ Cover letter / Proposal /   │
│                        LinkedIn post / Summary      │
│         ↓                                          │
│  open_and_fill_llm(target="claude"|"chatgpt")      │
│    ├─ Permission: Open browser        [Allow Once] │
│    ├─ Permission: Autofill prompt     [Allow Once] │
│    ├─ Permission: Click Send          [Allow Once] │
│    ├─ Wait for response (MutationObserver/polling)  │
│    └─ Permission: Use response        [Allow Once] │
│         ↓                                          │
│  Save to memory/content_output/                    │
└────────────────────────────────────────────────────┘

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

| Tier | Model | Runtime | RAM | Role | keep_alive |
|---|---|---|---|---|---|
| Router | Gemma 3 1B | Ollama | ~1 GB | Routes commands to agents | `5m` (always warm) |
| Content | Gemma 3 4B | Ollama | ~3.3 GB | LinkedIn posts, cover letters, gigs | `30s` + unload |
| NLP | Phi-4 Mini | Ollama | ~3 GB | Scoring, analysis | `30s` |
| Fallback | Gemma 2 9B | Ollama | ~6 GB | Reliable alternative | `30s` |
| Vision 2B | UI-TARS 2B | llama.cpp | ~3 GB | Fast screen reading | On-demand |
| Vision 7B | UI-TARS 7B | llama.cpp | ~5 GB | Accurate screen reading | On-demand |

## RAM Management Strategy

**Tiered keep_alive** — not `keep_alive:0` (which wastes time reloading):
- **Orchestrator**: `keep_alive=5m` — always warm for fast routing
- **Specialists**: `keep_alive=30s` — short window for follow-up calls
- **After generation**: explicit `force_unload()` to reclaim RAM immediately
- **UI-TARS**: CPU-only (`--ngl 0`), started/stopped on demand to avoid RAM contention

## Permission Gate System (Phase 9)

```
Action → PermissionGate.request()
  │
  ├─ Allow All active? → auto-approve
  ├─ Action type in skip_types? → auto-skip
  │
  └─ POST /permission/request → Bridge queues request
       │
       Chrome Extension polls /permission/pending
       │
       Permission Overlay displayed:
       ┌─────────────────────────────────────────┐
       │ ● CLICK  Click the Apply button         │
       │ Confidence: ████████░░ 85%              │
       │ Target: (500, 300)                      │
       │                                         │
       │ [Allow Once] [Allow All 30min] [Skip]   │
       │ [Stop] [Edit]                           │
       └─────────────────────────────────────────┘
       │
       POST /permission/result → decision stored
       │
       PermissionGate polls /permission/result/{task_id}
       │
       Returns: "allow" | "skip" | "stop" | "edit"
```

## Browser Copilot (Phase 10)

**Mode 2 Triggers** (detected in `agent.py` before orchestrator routing):
- "apply to this", "help with this page", "summarize this"
- "write proposal for this", "use claude for", "copilot", "browser mode"

**Requires**: `intelligence_mode: web_copilot` or `hybrid` in `config/settings.yaml`

**Flow**:
1. Extract page context (CDP → UI-TARS → Playwright fallback)
2. Draft LLM prompt (cover letter / proposal / LinkedIn / summary)
3. Open Claude/ChatGPT with stealth browser
4. Permission gate at every step (open, type, send, use response)
5. Capture response via MutationObserver + page polling
6. Save to `memory/content_output/`

## Directory Structure

```
D:\beelal_007\
├── agent.py                 # ★ Main CLI + Mode 2 routing + command parsing
├── scheduler.py             # ★ Background scheduler (Monday 9am, hourly)
├── startup.py               # ★ Windows autostart
├── CLAUDE.md                # ★ Project identity + rules (v3.0)
├── agents/                  # Agent definitions
│   ├── orchestrator.py      # ★ Gemma 3 1B command router
│   ├── content_agent.py     # ★ Gemma 3 4B content generation
│   ├── model_runner.py      # ★ safe_run() + RAM management
│   └── nlp_agent.py         # ★ Profile-aware NLP analyst
├── tools/                   # Core utilities
│   ├── browser_copilot.py   # ★ Phase 10: Full-chain browser automation
│   ├── permission_gate.py   # ★ Phase 9: Action approval system
│   ├── uitars_server.py     # ★ Phase 8: llama.cpp vision model manager
│   ├── uitars_runner.py     # ★ Phase 8: Screen → API → action pipeline
│   ├── screen_monitor.py    # ★ Phase 8: Background screenshot cache
│   ├── content_tools.py     # ★ LinkedIn, cover letter, gig generators
│   ├── post_scheduler.py    # ★ Weekly posts + hybrid_refine (3 modes)
│   ├── job_tools.py         # ★ Job scoring via gemma3:1b
│   ├── apply_workflow.py    # ★ Full job pipeline
│   ├── gig_tools.py         # ★ Fiverr/Upwork gig generation
│   ├── cdp_interceptor.py   # ★ LinkedIn Voyager API via CDP
│   └── browser_tools.py     # ★ Stealth browser: LinkedIn post, Fiverr gig
├── connectors/              # Platform connectors
│   ├── github_connector.py  # ★ REST API + 24h cache
│   ├── github_monitor.py    # ★ Activity monitor
│   ├── jobspy_connector.py  # ★ Multi-site scraper
│   └── freelance_monitor.py # ★ Upwork RSS monitor
├── memory/                  # Persistent storage
│   ├── db.py                # ★ SQLite (8+ tables)
│   ├── excel_logger.py      # ★ Excel: jobs, gigs, posts
│   ├── content_output/      # ★ Browser Copilot saved responses
│   ├── screenshots/         # Browser automation screenshots
│   ├── cover_letters/       # Generated cover letters
│   ├── gig_drafts/          # Generated gig descriptions
│   └── post_drafts/         # Generated weekly posts
├── bridge/                  # FastAPI bridge (localhost:8000)
│   └── server.py            # ★ 14+ endpoints including permission system
├── chrome_extension/        # Manifest V3 Chrome Extension
│   ├── manifest.json        # ★ Permissions: cookies, scripting, storage
│   ├── background.js        # ★ Cookie sync, message relay
│   ├── content_script.js    # ★ Context snap, overlay, permission overlay
│   ├── popup.html/js        # ★ Status popup
│   └── icons/               # ★ Extension icons
├── config/                  # Configuration
│   ├── profile.yaml         # ★ Dynamic profile
│   └── settings.yaml        # ★ Intelligence mode, bridge port
├── ui/                      # UI interfaces
│   ├── dashboard.py         # ★ Tkinter 900x700 (overview, UI-TARS, permissions)
│   └── tray_app.py          # ★ System tray (pystray)
├── tests/                   # Test suites
│   ├── test_phase8.py       # ★ UI-TARS: 18/18
│   ├── test_phase9.py       # ★ Permission Gate: 36/36
│   ├── test_phase10.py      # ★ Browser Copilot: 40/40
│   └── test_full_v3.py      # ★ Full verification: 55+ checks
└── docs/                    # Documentation
    ├── ARCHITECTURE.md       # ★ This file
    └── USER_GUIDE.md         # ★ Permission system + Mode 2 guide
```

★ = Implemented (Phases 0-10 complete, 55+ files)

## Key Design Decisions

1. **No paid APIs** — Everything runs locally or via free services
2. **No Tkinter for approval** — Approval via Chrome Extension overlay (CLI fallback)
3. **Never submit without approval** — Hard rule, no exceptions
4. **Never execute without PermissionGate** — Every UI-TARS/browser action gated
5. **RAM-first architecture** — Only one heavy model loaded at a time
6. **Two-tier routing** — 1B routes, 4B/vision executes on-demand
7. **All model calls through safe_run()** — Never call Ollama directly
8. **Tiered keep_alive** — Router=5m, specialists=30s + explicit unload
9. **Dynamic profile** — All prompts read from profile.yaml
10. **24h/12h caching** — GitHub/JobSpy cached to avoid rate limits
11. **SQLite audit trail** — Every action logged
12. **Cookie sync** — Extension → SQLite → Playwright
13. **Stealth everywhere** — playwright-stealth on all browser contexts
14. **Hybrid Refiner** — Local + Claude web UI for superior content
15. **GitHub-driven content** — Real commits/stars → post topics
16. **Three Excel trackers** — Jobs, gigs, LinkedIn posts
17. **Permission gate on everything** — Allow Once, Allow All, Skip, Stop, Edit
18. **3-strategy extraction** — CDP, UI-TARS vision, Playwright fallback
19. **CPU-only vision** — --ngl 0 for UI-TARS (no GPU required)
