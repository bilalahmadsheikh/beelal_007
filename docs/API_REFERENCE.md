# API Reference — BilalAgent v2.0

## tools/model_runner.py

### `run_model(model, prompt, system="") → str`
Run an Ollama model with `keep_alive:0` (auto-unload after generation).

| Param | Type | Description |
|---|---|---|
| `model` | `str` | Model name (e.g. `gemma3:1b`, `qwen3-4b-thinking`) |
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

| Param | Type | Description |
|---|---|---|
| `user_input` | `str` | Raw user command |
| **Returns** | `dict` | `{"agent": str, "task": str, "model": str}` |

**Supported agents:** `nlp`, `content`, `navigation`, `memory`
**Supported models:** `gemma3:1b`, `phi4-mini`, `qwen3-4b-thinking`, `gemma2:9b`

---

## agents/nlp_agent.py

### `analyze(task, context="", model="gemma3:1b") → str`
Run NLP analysis using profile data and optional context.

| Param | Type | Description |
|---|---|---|
| `task` | `str` | User question or analysis task |
| `context` | `str` | Additional context (e.g. GitHub data) |
| `model` | `str` | Model to use (falls back to gemma3:1b if needed) |
| **Returns** | `str` | Analysis result |

---

## agents/content_agent.py

### `generate(prompt, content_type="general") → str`
Generate content using best available model (Qwen3 8B → Gemma 2 9B → Gemma3 1B fallback). Strips Qwen3 `<think>` tags. Auto-retries if output < 150 chars.

---

## tools/content_tools.py

### `generate_linkedin_post(project_name, post_type="project_showcase") → str`
Max 1300 chars. Types: `project_showcase`, `learning_update`, `achievement`, `opinion`.

### `generate_cover_letter(job_title, company, job_description="") → str`
3-paragraph cover letter, 250-350 word target.

### `generate_gig_description(service_type, platform="fiverr") → dict`
JSON with title, description, tags, packages. Services: `mlops`, `chatbot`, `blockchain`, `data_science`, `backend`.

---

## ui/approval_cli.py

### `show_approval(content_type, content) → str | None`
CLI review: `[A]pprove` / `[E]dit` / `[C]ancel`. Returns `'approved'`, edited text, or `None`.

---

## connectors/github_connector.py

### `GitHubConnector` class

| Method | Returns | Description |
|---|---|---|
| `get_repos()` | `list[dict]` | All public repos (cached 24h) |
| `get_readme(repo)` | `str` | README content for a repo |
| `get_recent_commits(days=30)` | `list[dict]` | Recent commits across repos |
| `get_summary()` | `str` | Human-readable GitHub summary |

---

## memory/db.py

| Function | Description |
|---|---|
| `init_db()` | Create tables (profiles, action_log, memory_store, content_log) |
| `save_profile(data: dict)` | Save/update user profile |
| `get_profile() → dict` | Retrieve stored profile |
| `log_action(type, details, status)` | Log an agent action |
| `get_recent_actions(limit=20) → list` | Get recent action log entries |
| `save_memory(key, value, category)` | Save key-value to memory store |
| `get_memory(key) → str` | Retrieve value from memory store |
| `log_content(type, content, status, platform, model)` | Log generated content |
| `get_recent_content(type, limit) → list` | Get recent content entries |

---

## agent.py (CLI Entry Point)

### Usage
```bash
python agent.py "your command here"
```

### Startup Sequence
1. Check RAM
2. Initialize SQLite database
3. Load profile from `config/profile.yaml`
4. Sync GitHub repos

### Command Pipeline
1. **Route** via orchestrator (gemma3:1b) → JSON routing
2. **Execute** via appropriate agent (nlp, content, navigation, memory)
3. **Display** result with RAM delta

---

## FastAPI Bridge (Phase 3+)

| Endpoint | Method | Description |
|---|---|---|
| `/command` | POST | *Planned* — Send command to orchestrator |
| `/approve` | POST | *Planned* — Approve/reject pending action |
| `/status` | GET | *Planned* — Get agent status |
