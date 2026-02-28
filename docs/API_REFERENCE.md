# API Reference — BilalAgent v2.0

## tools/model_runner.py

### `run_model(model, prompt, system="", keep_alive=None) → str`
Run an Ollama model with tiered `keep_alive` for KV caching. Router uses `5m`, specialists use `30s`.

| Param | Type | Description |
|---|---|---|
| `model` | `str` | Model name (e.g. `gemma3:1b`, `gemma3:4b`) |
| `prompt` | `str` | User prompt |
| `system` | `str` | Optional system prompt |
| **Returns** | `str` | Generated text or `[ERROR] ...` message |

### `force_unload(model) → None`
Force unload a model from RAM. Use if a model is stuck in memory.

### `get_free_ram() → float`
Returns available system RAM in GB.

### `safe_run(model, prompt, required_gb=2.0, system="") → str`
Run a model only if enough free RAM is available. **All agent code must use this function.**

---

## agents/orchestrator.py

### `route_command(user_input: str) → dict`
Route a user command to the appropriate agent via Gemma 3 1B.

**Supported agents:** `nlp`, `content`, `navigation`, `memory`, `jobs`
**Supported models:** `gemma3:1b`, `phi4-mini`, `gemma3:4b`, `gemma2:9b`

---

## agents/content_agent.py

### `generate(prompt, content_type="general") → str`
Generate content using best available model (Gemma 3 4B → Gemma 2 9B → Gemma3 1B). System prompt built dynamically from `config/profile.yaml`.

---

## tools/content_tools.py

### `generate_linkedin_post(project_name, post_type="project_showcase", user_request="") → str`
Max ~3500 chars. Types: `project_showcase`, `learning_update`, `achievement`, `opinion`.

### `generate_cover_letter(job_title, company, job_description="", user_request="") → str`
3-paragraph cover letter, 250-350 word target.

### `generate_gig_description(service_type, platform="fiverr", user_request="") → dict`
JSON with title, description, tags, packages. Services: `mlops`, `chatbot`, `blockchain`, `data_science`, `backend`.

All generators accept `user_request` — the full user input is injected into the prompt.

---

## tools/post_scheduler.py (Phase 6)

### `generate_weekly_posts(mode="local") → list`
Generate 3 weekly LinkedIn posts based on GitHub activity. Modes: `local`, `hybrid`, `web_copilot`.

Returns list of dicts: `{type, draft, final, path, words, status, mode}`

### `hybrid_refine(draft, task_id="") → str`
Send a draft to Claude web UI for polishing via Playwright + extension MutationObserver. Timeout: 120s, falls back to original draft.

---

## tools/gig_tools.py (Phase 5)

### `generate_gig_listing(service_type, platform="fiverr") → dict`
Generate Fiverr/Upwork gig listing with title, description, tags, pricing tiers.

### `generate_proposal(project_data, user_profile) → str`
Generate a proposal matched to a specific freelance posting.

---

## tools/job_tools.py

### `score_job(job: dict) → dict`
Score a job against user profile via gemma3:1b. Returns `{score, matching_skills, missing, reason}`. Profile cached in memory.

### `get_top_jobs(jobs: list, min_score=65) → list`
Score all jobs and return `(job, score)` tuples above min_score, sorted descending.

---

## tools/apply_workflow.py

### `run_job_search(query, location="remote", num=20, min_score=65) → str`
Full pipeline: CDP → JobSpy → score → display. Returns formatted results.

### `run_apply_flow(job, score_result) → str`
Generate cover letter, show for approval, save to file, log to Excel.

---

## tools/cdp_interceptor.py

### `intercept_linkedin_jobs(search_query, max_jobs=20) → list`
CDP intercept LinkedIn's Voyager API. Loads stored cookies from SQLite for authenticated access. Falls back to empty list on failure.

---

## tools/browser_tools.py

### `post_to_linkedin(post_text: str) → bool`
Post to LinkedIn via stealth browser + cookie reuse. Overlay approval with CLI fallback.

### `fill_fiverr_gig(gig_data: dict) → bool`
Fill Fiverr gig form via stealth browser. Overlay approval with CLI fallback.

---

## connectors/github_connector.py

| Method | Returns | Description |
|---|---|---|
| `get_repos()` | `list[dict]` | All public repos (cached 24h) |
| `get_readme(repo)` | `str` | README content for a repo |
| `get_recent_commits(days=30)` | `list[dict]` | Recent commits across repos |
| `get_summary()` | `str` | Human-readable GitHub summary |
| `get_deep_repo_context(repo)` | `dict` | Full context: README + docs + commits + tree |

---

## connectors/github_monitor.py (Phase 6)

### `GitHubActivityMonitor`

| Method | Returns | Description |
|---|---|---|
| `check_new_activity()` | `list[dict]` | Activities since last check (new repos, commits, stars, README updates) |
| `get_content_ideas()` | `list[dict]` | 3 post ideas based on activity |

---

## connectors/jobspy_connector.py

### `search_jobs(role, location="remote", num=20) → list`
Search Indeed, Glassdoor, LinkedIn. 12h cache in `memory/job_cache.json`.

---

## connectors/freelance_monitor.py (Phase 5)

### `FreelanceMonitor`

| Method | Returns | Description |
|---|---|---|
| `check_upwork(keywords)` | `list[dict]` | Matching Upwork projects via RSS |
| `get_new_projects()` | `list[dict]` | Unseen projects filtered by keywords |

---

## memory/db.py

| Function | Description |
|---|---|
| `init_db()` | Create all tables (profiles, action_log, memory_store, content_log, cookies, pending_tasks, seen_projects, github_state) |
| `save_profile(data)` | Save/update user profile |
| `log_action(type, details, status)` | Log an agent action |
| `log_content(type, content, status, platform, model)` | Log generated content |
| `save_cookies(site, cookies)` | Store synced cookies |
| `get_cookies(site)` | Retrieve stored cookies |

---

## memory/excel_logger.py

### `log_application(job, score, status="applied", cover_letter_path="") → None`
Log to `applied_jobs.xlsx` with color-coded scores (green ≥80, yellow ≥60, red <60).

### `log_gig(platform, service_type, title, status, price="") → None`
Log to `gigs_created.xlsx` with gig details and status tracking.

### `log_post(post_type, preview, status, scheduled_time="", url="", mode="local") → None`
Log to `linkedin_posts.xlsx` with color-coded status (pending=yellow, approved=blue, posted=green, rejected=red).

### `get_applications(status=None) → list`
### `get_gigs(status=None) → list`
### `get_posts(status=None) → list`

---

## FastAPI Bridge — `bridge/server.py`

Base URL: `http://localhost:8000`

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Bridge status |
| `/extension/context_snap` | POST | Receive job data from extension |
| `/extension/approval` | POST | Receive approve/cancel from overlay |
| `/extension/get_task` | GET | Extension polls for pending tasks |
| `/extension/register_task` | POST | Agent registers task for overlay |
| `/extension/cookies` | POST | Receive synced cookies → SQLite |
| `/extension/cookies/{site}` | GET | Get stored cookies for a site |
| `/extension/ai_response` | POST | Receive Claude/ChatGPT captures (hybrid mode) |
| `/extension/status` | GET | Bridge health + task stats |

---

## ui/approval_cli.py

### `show_approval(content_type, content) → str | None`
CLI review: `[A]pprove` / `[E]dit` / `[C]ancel`. Returns `'approved'`, edited text, or `None`.
