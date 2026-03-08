# BilalAgent v3.1 — Personal AI Desktop Agent

## About Bilal Ahmad Sheikh
- GitHub: https://github.com/bilalahmadsheikh
- Degree: AI Engineering, 3rd year (6th semester), Pakistan
- Skills: Python, FastAPI, Web3.py, Blockchain, MLOps, Scikit-Learn, XGBoost, MLflow, Docker, PostgreSQL, Supabase, Geospatial, AsyncIO

## Projects
- basepy-sdk: Python SDK for Base L2 blockchain. 40% perf improvement over Web3.py.
- WhatsApp AI Chatbot: FastAPI + Supabase on Railway. Pakistani SME market (90k customers).
- Purchasing Power Prediction: MLOps, 87% accuracy, XGBoost, automated retraining.
- Route Optimization: Geospatial analysis, Kepler visualizations.
- IlmSeUrooj: University admission platform for Pakistani students (Next.js + Supabase).
- And more... (20 repos total)

## v3.1 Architecture (Phases 0-12 Complete)
- Orchestrator: Gemma 3 1B (always warm, keep_alive=5m, routes every command)
- Content Primary: Gemma 3 4B (best 4B content model, same family as orchestrator)
- Content Fallback: Gemma 2 9B (reliable, well-tested alternative)
- Logic/Scoring: Phi-4 Mini Instruct (load on demand for job scoring and routing)
- UI-TARS Vision: 2B/7B GGUF via llama.cpp on port 8081 (CPU-only, models at D:\local_models\bartowski\)
- Tiered keep_alive: Router=5m, Specialists=30s + explicit force_unload after generation
- Dynamic profile: All prompts read from config/profile.yaml (name, degree, GitHub)
- User prompt passthrough: Full user input passed as user_request to all generators
- Chrome Extension at D:\beelal_007\chrome_extension\ (Manifest V3)
- FastAPI bridge at localhost:8000 (connects extension to Python, 15+ endpoints)
- Intelligence Modes: local / web_copilot / hybrid
- PermissionGate: Every UI-TARS/browser action requires explicit user permission
- BrowserCopilot: Mode 2 full chain (extract context → draft prompt → fill Claude/ChatGPT → capture response)
- Desktop Overlay: PyQt5 floating always-on-top window (replaces Chrome extension as primary UI)

## New in v3.1 (Phase 12)
- **Desktop Overlay** (`ui/desktop_overlay.py`): Floating PyQt5 frameless window, always-on-top
  - `AgentOverlay`: Main window — conversation area, input bar, status bar, draggable titlebar
  - `PermissionPopup`: Cursor-positioned 5-button approval popup with confidence bar + countdown
  - `ScreenAnnotation`: Full-screen transparent crosshair/region overlay for vision actions
  - `AgentWorker`: QThread background agent execution with Qt signals
- **Hotkeys**: Ctrl+Space (toggle), Ctrl+Shift+S (emergency stop), Ctrl+Shift+B (snap screen)
- **Bridge**: POST /route endpoint for task classification via orchestrator
- **Agent**: `python agent.py --overlay` launches desktop overlay instead of CLI
- **Dashboard**: Command tab with live agent prompt (from Phase 11)

## New in v3.0 Build (Steps 1-5 Complete)
- **agent.py**: Full argparse — `--overlay` (PyQt5 GUI), `--bridge` (FastAPI :8000), positional command
- **Phi-4 Mini**: `microsoft_Phi-4-mini-instruct-Q4_K_S.gguf` at `D:\local_models\bartowski\microsoft_Phi-4-mini-instruct-GGUF\`
- **LlamaCppServer** (`tools/uitars_server.py`): Generic multi-model server manager replacing UITARSServer
  - `MODEL_REGISTRY`: uitars-2b (port 8081), uitars-7b (port 8081), phi4-mini (port 8082)
  - `_find_phi4_gguf()`: auto-detects best quantization in Phi-4 dir
  - `get_llamacpp_server()`: singleton accessor
- **LinkedIn Poster** (`tools/linkedin_poster.py`): Full Playwright flow with 3 permission gates
  - Permission 1: open browser → Permission 2: type post → Permission 3: click Post
  - Extension confirmation via `/extension/page_state` (waits for `post_confirmed` state)
  - Logs to `linkedin_posts.xlsx` + SQLite after posting
  - Upload triggered by keywords: "upload / post to linkedin / write and upload / go live"
- **Task Coordinator** (`tools/task_coordinator.py`): Unified task runner for overlay + agent pipeline
  - `TaskCoordinator.run(user_input)` → detect intent → generate → execute → report
  - `set_overlay_callback(fn)` for live status to desktop overlay
  - `get_coordinator()` singleton
- **Bridge v3** (`bridge/server.py`): New endpoints added
  - `GET /status` — health check (extension polls on load)
  - `POST /tasks/register`, `GET /tasks/active`, `POST /tasks/complete`, `GET /tasks/status/{id}`
  - `POST /extension/page_state`, `GET /extension/page_state/{task_id}`
- **Chrome Extension** (`chrome_extension/content_script.js`): LinkedIn watcher added
  - `pollActiveTasks()` — watches bridge for active linkedin_post tasks (every 2s)
  - `watchLinkedInPage(taskId)` — MutationObserver reports `page_loaded`, `composer_open`, `post_confirmed`
  - `checkBridge()` — liveness gate on `GET /status` (every 5s), gates all polling
- **Word Count Enforcement** (`tools/content_tools.py`): Hard 180-320 word enforcement
  - Auto-trims posts > 320 words via LLM call; auto-expands posts < 180 words
  - Auto-logs every generated LinkedIn post to Excel + SQLite
- **excel_logger** (`memory/excel_logger.py`): `log_linkedin_post()` added as wrapper over `log_post()`

## Rules
- All files in D:\beelal_007\
- Models served via Ollama (ollama pull gemma3:1b, ollama pull gemma3:4b)
- Vision models via llama.cpp (llama-server.exe at D:\local_models\llama.cpp\)
- Github Repo: https://github.com/bilalahmadsheikh/beelal_007
- NEVER submit any form without approval
- NEVER execute browser actions without PermissionGate approval
- No paid APIs — free/local only
- All model calls through safe_run() — never call Ollama directly

