# BilalAgent v3.0 — Personal AI Desktop Agent

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

## v3.0 Architecture (Phases 0-10 Complete)
- Orchestrator: Gemma 3 1B (always warm, keep_alive=5m, routes every command)
- Content Primary: Gemma 3 4B (best 4B content model, same family as orchestrator)
- Content Fallback: Gemma 2 9B (reliable, well-tested alternative)
- Logic/Scoring: Phi-4 Mini Instruct (load on demand for job scoring and routing)
- UI-TARS Vision: 2B/7B GGUF via llama.cpp on port 8081 (CPU-only, models at D:\local_models\bartowski\)
- Tiered keep_alive: Router=5m, Specialists=30s + explicit force_unload after generation
- Dynamic profile: All prompts read from config/profile.yaml (name, degree, GitHub)
- User prompt passthrough: Full user input passed as user_request to all generators
- Chrome Extension at D:\beelal_007\chrome_extension\ (Manifest V3)
- FastAPI bridge at localhost:8000 (connects extension to Python, 14+ endpoints)
- Intelligence Modes: local / web_copilot / hybrid
- Approval: Chrome Extension overlay (NOT Tkinter)
- PermissionGate: Every UI-TARS/browser action requires explicit user permission
- BrowserCopilot: Mode 2 full chain (extract context → draft prompt → fill Claude/ChatGPT → capture response)
- Job Search: CDP + JobSpy multi-site scraping + profile scoring
- Freelance Automation: Upwork RSS monitor + gig generator + proposal pipeline
- LinkedIn Brand Engine: GitHub activity monitor + weekly post generation (3 modes)
- Hybrid Refiner: Local draft (gemma3:4b) → Claude web UI polish via Playwright + extension
- Background Scheduler: schedule lib (Monday 9am posts, hourly approved post checks)
- Excel Tracking: applied_jobs.xlsx, gigs_created.xlsx, linkedin_posts.xlsx

## New in v3.0 (Phases 8-10)
- **UI-TARS Server** (`tools/uitars_server.py`): llama.cpp subprocess manager for vision model
- **UI-TARS Runner** (`tools/uitars_runner.py`): Screenshot → vision API → action execution
- **Screen Monitor** (`tools/screen_monitor.py`): Background thread, 2s interval cached screenshots
- **Permission Gate** (`tools/permission_gate.py`): Allow All timer + skip types + bridge polling
- **Browser Copilot** (`tools/browser_copilot.py`): Full-chain Mode 2 automation
- **Bridge**: 6 new permission endpoints (/permission/request, /pending, /result, /set_allow_all)
- **Extension**: Permission overlay (5 buttons, crosshair, Allow All badge)
- **Dashboard**: UI-TARS section + Permission Controls
- **Total files**: 55+

## Rules
- All files in D:\beelal_007\
- Models served via Ollama (ollama pull gemma3:1b, ollama pull gemma3:4b)
- Vision models via llama.cpp (llama-server.exe at D:\local_models\llama.cpp\)
- Github Repo: https://github.com/bilalahmadsheikh/beelal_007
- NEVER submit any form without approval
- NEVER execute browser actions without PermissionGate approval
- No paid APIs — free/local only
- All model calls through safe_run() — never call Ollama directly
