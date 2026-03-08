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

## Rules
- All files in D:\beelal_007\
- Models served via Ollama (ollama pull gemma3:1b, ollama pull gemma3:4b)
- Vision models via llama.cpp (llama-server.exe at D:\local_models\llama.cpp\)
- Github Repo: https://github.com/bilalahmadsheikh/beelal_007
- NEVER submit any form without approval
- NEVER execute browser actions without PermissionGate approval
- No paid APIs — free/local only
- All model calls through safe_run() — never call Ollama directly

