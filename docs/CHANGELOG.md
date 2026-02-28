# Changelog — BilalAgent v2.0

All notable changes to this project, listed by date.

---

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
