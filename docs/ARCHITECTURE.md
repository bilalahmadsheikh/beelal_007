# Architecture — BilalAgent v2.0

## Overview

BilalAgent is a personal AI desktop agent that runs 100% locally with no paid APIs. It uses multiple Ollama models with **tiered keep_alive caching** and dynamic RAM management to operate on a resource-constrained machine (8.5GB RAM).

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
│   Parses: project_name (regex) + user_request    │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│              Orchestrator Agent                  │
│            Gemma 3 1B (always warm, 5m)          │
│   Input: raw command → Output: JSON routing      │
│   {"agent", "task", "model"}                     │
└───┬──────────┬──────────┬───────────┬───────────┬───────────┘
    │          │          │           │           │
    ▼          ▼          ▼           ▼           ▼
┌────────┐┌────────┐┌─────────┐┌──────────┐┌──────────┐
│  NLP   ││Content ││Navigate ││ Memory   ││  Jobs    │
│ Agent  ││ Agent  ││ Agent   ││ Agent    ││ Agent    │
│gemma/  ││Gemma3 ││gemma3:1b││  SQLite  ││ JobSpy   │
│phi4    ││  4B   ││         ││          ││ + CDP    │
└───┬────┘└───┬────┘└─────────┘└──────────┘└────┬─────┘
    │         │                                  │
    │         ├─ Unload orchestrator → Load gemma3:4b
    │         ├─ Generate with system prompt (from profile.yaml)
    │         ├─ Unload specialist → Return result
    │         └─ Fallback: gemma2:9b → gemma3:1b
    │                                            │
    │                                 ┌──────────▼──────────┐
    │                                 │  Job Search Pipeline │
    │                                 │ CDP → JobSpy → Score │
    │                                 │ → Display → Excel    │
    │                                 └─────────────────────┘
    ▼
┌────────────────────────────────────────┐
│       Connectors & Memory              │
│  GitHub REST API (24h cache)           │
│  JobSpy multi-site scraper (12h cache) │
│  CDP LinkedIn interceptor (stealth)    │
│  SQLite (profiles, actions, memory)    │
│  Excel logger (applied_jobs.xlsx)      │
│  Profile YAML config                   │
└────────────────────────────────────────┘
```

## Model Stack

| Tier | Model | Ollama Name | RAM | Role | keep_alive |
|---|---|---|---|---|---|
| Router | Gemma 3 1B | `gemma3:1b` | ~1 GB | Routes commands to agents | `5m` (always warm) |
| Content | Gemma 3 4B | `gemma3:4b` | ~3.3 GB | LinkedIn posts, cover letters, gigs | `30s` + explicit unload |
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

## Command Pipeline

```
User Input → Orchestrator (gemma3:1b, 5m cache)
          → JSON: {"agent": "content", "task": "write_post", "model": "gemma3:4b"}
          → Content Agent: unload router → load specialist → generate → unload specialist
          → Post-processing: clean, add repo link, add hashtags
          → Response displayed + RAM delta shown
          → Action logged to SQLite
```

## Directory Structure

```
D:\beelal_007\
├── agent.py             # ★ Main CLI entry point + command parsing
├── agents/              # Agent definitions
│   ├── orchestrator.py  # ★ Gemma 3 1B command router
│   ├── content_agent.py # ★ Gemma 3 4B content generation (dynamic profile)
│   └── nlp_agent.py     # ★ Profile-aware NLP analyst
├── tools/               # Core utilities
│   ├── model_runner.py  # ★ Ollama wrapper with tiered keep_alive
│   └── content_tools.py # ★ LinkedIn, cover letter, gig generators
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
│   └── profile.yaml     # ★ Dynamic profile (name, GitHub, degree)
├── ui/                  # Web UI (future)
├── chrome_extension/    # Manifest V3 extension (future)
├── bridge/              # FastAPI bridge (future)
├── test_all.py          # ★ Full test suite (Phases 0-2)
└── docs/                # Documentation
```

★ = Implemented in Phases 0-2

## Key Design Decisions

1. **No paid APIs** — Everything runs locally or via free services
2. **No Tkinter** — Approval happens via Chrome Extension overlay
3. **Never submit without approval** — Hard rule, no exceptions
4. **RAM-first architecture** — Only one heavy model loaded at a time
5. **Two-tier routing** — Lightweight 1B routes, heavier 4B executes on-demand
6. **All model calls through safe_run()** — Never call Ollama directly
7. **Tiered keep_alive** — Router stays warm (5m), specialists auto-expire (30s) + explicit unload
8. **Dynamic profile** — All prompts read from profile.yaml, nothing hardcoded
9. **24h caching** — GitHub data cached to avoid rate limits and speed up responses
10. **SQLite audit trail** — Every action logged for transparency
11. **User prompt passthrough** — Full user input passed as `user_request` to all generators
