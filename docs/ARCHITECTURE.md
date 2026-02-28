# Architecture — BilalAgent v2.0

## Overview

BilalAgent is a personal AI desktop agent that runs 100% locally with no paid APIs. It uses multiple Ollama models with aggressive RAM management (`keep_alive:0`) to operate on a resource-constrained machine.

## System Diagram

```
┌─────────────────────────────────────────────────┐
│                 Chrome Extension                 │
│              (Manifest V3 / Overlay)             │
│         Approval UI • Job Scraping • Forms       │
└────────────────────┬────────────────────────────┘
                     │ HTTP (localhost:8000)
┌────────────────────▼────────────────────────────┐
│               FastAPI Bridge                     │
│        /command  /approve  /status               │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│          agent.py — Main Entry Point             │
│   Startup: DB init → Profile → GitHub Sync       │
│   CLI: python agent.py "command"                 │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│              Orchestrator Agent                  │
│            Gemma 3 1B (always-on)                │
│   Input: raw command → Output: JSON routing      │
│   {"agent", "task", "model"}                     │
└───┬──────────┬──────────┬───────────┬───────────┘
    │          │          │           │
    ▼          ▼          ▼           ▼
┌────────┐┌────────┐┌─────────┐┌──────────┐
│  NLP   ││Content ││Navigate ││ Memory   │
│ Agent  ││ Agent  ││ Agent   ││ Agent    │
│gemma/  ││Qwen3  ││gemma3:1b││  SQLite  │
│phi4    ││ 8B    ││         ││          │
└───┬────┘└────────┘└─────────┘└──────────┘
    │
    ▼
┌────────────────────────────────────────┐
│       Connectors & Memory              │
│  GitHub REST API (24h cache)           │
│  SQLite (profiles, actions, memory)    │
│  Profile YAML config                   │
└────────────────────────────────────────┘
```

## Two-Tier Model System

| Tier | Model | RAM | Role | Load Strategy |
|---|---|---|---|---|
| Tier 1: Router | Gemma 3 1B | ~1 GB | Routes every command to the right agent | First to load, lightweight |
| Tier 2: NLP | Phi-4 Mini | ~3 GB | Complex analysis, scoring, structured tasks | On-demand |
| Tier 2: Content | Qwen3 8B | ~5 GB | Writing, cover letters, proposals | On-demand |
| Tier 2: Fallback | Gemma 2 9B | ~6 GB | Reliable alternative content generation | On-demand |

> **Critical rule:** All model calls use `keep_alive:0` and go through `safe_run()` — load → generate → unload immediately.

## Command Pipeline

```
User Input → Orchestrator (gemma3:1b)
          → JSON: {"agent": "nlp", "task": "profile_query", "model": "gemma3:1b"}
          → NLP Agent loads profile + GitHub context
          → safe_run(model, prompt) with keep_alive:0
          → Response displayed + RAM delta shown
          → Action logged to SQLite
```

## Intelligence Modes

| Mode | Description |
|---|---|
| `local` | Fully offline, Ollama models only |
| `web_copilot` | Chrome extension scrapes, models process locally |
| `hybrid` | Best of both — web data + local intelligence |

## Directory Structure

```
D:\beelal_007\
├── agent.py             # ★ Main CLI entry point
├── agents/              # Agent definitions
│   ├── orchestrator.py  # ★ Gemma 3 1B command router
│   └── nlp_agent.py     # ★ Profile-aware NLP analyst
├── tools/               # Core utilities
│   └── model_runner.py  # ★ Ollama wrapper with keep_alive:0
├── connectors/          # Platform connectors
│   └── github_connector.py  # ★ REST API + 24h cache
├── memory/              # Persistent storage
│   ├── db.py            # ★ SQLite memory layer
│   ├── agent_memory.db  # SQLite database
│   ├── github_cache.json # GitHub API cache
│   ├── screenshots/
│   ├── cover_letters/
│   ├── gig_drafts/
│   └── post_drafts/
├── config/              # Configuration
│   └── profile.yaml     # ★ Bilal's profile data
├── ui/                  # Web UI (future)
├── chrome_extension/    # Manifest V3 extension (future)
├── bridge/              # FastAPI bridge (future)
└── docs/                # Documentation
```

★ = Implemented in Phase 0-1

## Key Design Decisions

1. **No paid APIs** — Everything runs locally or via free services
2. **No Tkinter** — Approval happens via Chrome Extension overlay
3. **Never submit without approval** — Hard rule, no exceptions
4. **RAM-first architecture** — Only one heavy model loaded at a time
5. **Two-tier routing** — Lightweight 1B routes, heavier models execute on-demand
6. **All model calls through safe_run()** — Never call Ollama directly
7. **24h caching** — GitHub data cached to avoid rate limits and speed up responses
8. **SQLite audit trail** — Every action logged for transparency
