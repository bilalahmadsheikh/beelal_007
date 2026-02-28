# Changelog — BilalAgent v2.0

All notable changes to this project, listed by date.

---

## 2026-02-28

### Audit — Phase 3+4 Quality Pass

**Fixed:**
- `job_tools.py` — Profile cached in memory (was 60x disk reads for 60 jobs)
- `apply_workflow.py` — Removed double-scoring when no jobs pass min_score
- `job_tools.py` — Removed unused `_load_profile_skills()` dead code
- `cdp_interceptor.py` — Now loads stored LinkedIn cookies from SQLite
- `content_tools.py` — Removed hardcoded `bilalahmadsheikh` GitHub fallback
- `browser_tools.py` — CLI fallback when bridge is offline (was silently skipping)
- All stealth files — Chrome user-agent updated from 131 to 137

### Phase 4 — Chrome Extension + FastAPI Bridge

**Added:**
- `bridge/server.py` — FastAPI bridge with 8 endpoints (context_snap, approval, get_task, register_task, cookies CRUD, ai_response, status)
- `chrome_extension/manifest.json` — Manifest V3 with cookie, scripting, storage, tabs permissions
- `chrome_extension/background.js` — Cookie sync on install, message relay, task polling (2s)
- `chrome_extension/content_script.js` — Context snap button, approval overlay, MutationObserver (Claude + ChatGPT)
- `chrome_extension/popup.html` + `popup.js` — Dark-themed status popup
- `chrome_extension/icons/` — 16/48/128px extension icons
- `tools/browser_tools.py` — Playwright + stealth + cookie reuse + overlay approval
- `memory/db.py` — Added `cookies` and `pending_tasks` tables

**Tested:**
- All 8 bridge endpoints verified working
- Extension ready for chrome://extensions → Load unpacked

### Phase 3 — Job Search + CDP + Stealth

**Added:**
- `connectors/jobspy_connector.py` — Multi-site scraper (Indeed, Glassdoor, LinkedIn) with 12h cache
- `tools/cdp_interceptor.py` — CDP LinkedIn Voyager API interception with playwright-stealth
- `tools/job_tools.py` — Profile-aware job scoring via gemma3:1b (0-100, with fallback keyword matching)
- `memory/excel_logger.py` — Excel logger (`applied_jobs.xlsx`) with color-coded scores
- `tools/apply_workflow.py` — Full pipeline: CDP → JobSpy → score → display → Excel
- `agents/orchestrator.py` — Added `jobs` agent routing
- `agent.py` — Added `_handle_jobs()`, `_parse_job_query()`, job examples

**Tested:**
- 60 jobs found across Indeed/Glassdoor/LinkedIn
- All 60 scored at 22-31 tok/s with KV cache hits
- Top 5 displayed (Snowflake 95, Zoom 92, Meta 92)
- `applied_jobs.xlsx` created with 5 entries

## 2026-02-28

### Phase 2 — Content Generation Engine

**Added:**
- `agents/content_agent.py` — 3-tier model fallback (Qwen3 8B → Gemma 2 9B → Gemma3 1B)
  - Qwen3 thinking tag stripping, quality check with auto-retry
- `tools/content_tools.py` — 3 content generators
  - `generate_linkedin_post()` — max 1300 chars, hashtags, quality check
  - `generate_cover_letter()` — 3-paragraph structure, 250-350 word target
  - `generate_gig_description()` — JSON with title, tags, 3 pricing tiers
- `ui/approval_cli.py` — CLI approval: [A]pprove / [E]dit / [C]ancel
- `memory/db.py` — added `content_log` table + `log_content()` + `get_recent_content()`
- `agent.py` — content command regex parsing for LinkedIn/cover letter/gig commands

**Tested:**
- LinkedIn post: 178 words, real GitHub data referenced
- Cover letter: 521 words, references purchasing_power_ml, YouTube-Converter
- Gig description: valid JSON, 3 tiers, 90k customer metric
- RAM: Recovered after each generation call

## 2026-02-28

### Phase 1 — Agent Brain + GitHub Memory

**Added:**
- `agents/orchestrator.py` — Command router using Gemma 3 1B with JSON-only output
  - Routes to: nlp, content, navigation, memory agents
  - Handles markdown fences and malformed model output gracefully
- `agents/nlp_agent.py` — Personal Intelligence Analyst
  - Profile-aware answering from `config/profile.yaml`
  - Model fallback: requested model → gemma3:1b if insufficient RAM
  - Integrates GitHub context for project-related queries
- `connectors/github_connector.py` — GitHub REST API connector
  - PAT authentication from `.env`
  - 24h JSON cache at `memory/github_cache.json`
  - `get_repos()`, `get_readme()`, `get_recent_commits()`, `get_summary()`
- `memory/db.py` — SQLite memory layer
  - Tables: profiles, action_log, memory_store
  - UPSERT support for memory entries
  - Action logging for audit trail
- `config/profile.yaml` — Bilal's profile data
  - 4 projects with full tech stacks
  - 13 skills, education, GitHub info
  - Agent model configuration
- `agent.py` — Main CLI entry point
  - Startup: DB init → profile load → GitHub sync
  - Command pipeline: orchestrator route → agent execute → display
- Package `__init__.py` files for agents, connectors, memory, tools

**Tested:**
- End-to-end: "what are my 4 projects and their tech stacks" → correct response
- Orchestrator routing: valid JSON output
- GitHub: 20 repos, 23 commits cached
- RAM: 2.6GB → 1.4GB (model loaded, generated, responded)

### Phase 0 — Environment + First File

**Added:**
- Project folder structure (agents, tools, connectors, memory/*, config, ui, chrome_extension, bridge, docs)
- `.env` — Environment config (Ollama URL, GitHub credentials, bridge port)
- `tools/model_runner.py` — Core model runner with `keep_alive:0` pattern
- `docs/` — Full project documentation suite

**Tested:**
- Python 3.12.3, Node v22.17.0, Ollama with gemma3:1b
- All pip packages: crewai, playwright, psutil, fastapi, uvicorn, playwright-stealth
- Model runner: gemma3:1b responded correctly, RAM recovered +1.2GB after unload
