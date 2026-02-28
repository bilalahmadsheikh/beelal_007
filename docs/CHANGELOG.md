# Changelog — BilalAgent v2.0

All notable changes to this project, listed by date.

---

## 2026-03-01

### Phase 6 — LinkedIn Brand Engine + Hybrid Refiner

**Added:**
- `connectors/github_monitor.py` — GitHubActivityMonitor class (tracks repos, commits, stars, README updates)
- `tools/post_scheduler.py` — Weekly post generation + hybrid_refine (3 modes: local/hybrid/web_copilot)
- `scheduler.py` — Background scheduler (Monday 9am posts, hourly approved post checks)
- `setup_scheduler_windows.py` — Windows Task Scheduler setup via schtasks
- `memory/excel_logger.py` — Added `linkedin_posts.xlsx` tracking (log_post, get_posts)
- `memory/db.py` — Added `github_state` table for activity monitoring
- `agent.py` — Added `_try_brand()` routing for brand/schedule/hybrid commands
- `chrome_extension/content_script.js` — Updated MutationObserver with task_id passthrough for hybrid mode

**Tested:**
- 3 weekly posts generated: beelal_007 (510 words), IlmSeUrooj (513 words), purchasing_power_ml (493 words)
- GitHub Activity Monitor: 22 activities detected on first scan
- linkedin_posts.xlsx created with color-coded status tracking
- Agent routing: brand check, generate posts, hybrid commands all working

---

## 2026-02-28

### Phase 5 — Freelance Automation

**Added:**
- `connectors/freelance_monitor.py` — Upwork RSS feed monitor with keyword matching and seen-project dedup
- `tools/gig_tools.py` — Fiverr/Upwork gig generation + proposal writing pipeline
- `memory/excel_logger.py` — Added `gigs_created.xlsx` tracking (log_gig, get_gigs)
- `memory/db.py` — Added `seen_projects` table for dedup
- `agent.py` — Added `_try_freelance()` routing for gig/proposal/monitor commands

**Tested:**
- Gig generation: JSON output with title, description, tags, pricing tiers
- Upwork proposal generation working
- Freelance monitor polling Upwork RSS
- gigs_created.xlsx logging verified

---

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

### Phase 2 — Content Generation Engine

**Added:**
- `agents/content_agent.py` — 3-tier model fallback (Gemma 3 4B → Gemma 2 9B → Gemma3 1B)
- `tools/content_tools.py` — 3 content generators (LinkedIn, cover letter, gig)
- `ui/approval_cli.py` — CLI approval: [A]pprove / [E]dit / [C]ancel
- `memory/db.py` — Added `content_log` table
- `agent.py` — Content command regex parsing

**Tested:**
- LinkedIn post: 178 words, real GitHub data referenced
- Cover letter: 521 words, references purchasing_power_ml, YouTube-Converter
- Gig description: valid JSON, 3 tiers, 90k customer metric

### Phase 1 — Agent Brain + GitHub Memory

**Added:**
- `agents/orchestrator.py` — Command router using Gemma 3 1B
- `agents/nlp_agent.py` — Personal Intelligence Analyst
- `connectors/github_connector.py` — GitHub REST API + 24h cache
- `memory/db.py` — SQLite memory layer
- `config/profile.yaml` — Bilal's profile data
- `agent.py` — Main CLI entry point

**Tested:**
- End-to-end: "what are my 4 projects" → correct response
- GitHub: 20 repos, 23 commits cached
- RAM: 2.6GB → 1.4GB

### Phase 0 — Environment + First File

**Added:**
- Project folder structure (12 directories)
- `.env` — Environment config
- `tools/model_runner.py` — Core model runner
- `docs/` — Documentation suite

**Tested:**
- Python 3.12.3, Node v22.17.0, Ollama running
- Model runner: gemma3:1b responded correctly, RAM recovered
