# BilalAgent v2.0 — Personal AI Desktop Agent
 
## About Bilal Ahmad Sheikh
- GitHub: https://github.com/bilalahmadsheikh
- Degree: AI Engineering, 3rd year (6th semester), Pakistan
- Skills: Python, FastAPI, Web3.py, Blockchain, MLOps, Scikit-Learn, XGBoost, MLflow, Docker, PostgreSQL, Supabase, Geospatial, AsyncIO
 
## Projects
- basepy-sdk: Python SDK for Base L2 blockchain. 40% perf improvement over Web3.py.
- WhatsApp AI Chatbot: FastAPI + Supabase on Railway. Pakistani SME market (90k customers).
- Purchasing Power Prediction: MLOps, 87% accuracy, XGBoost, automated retraining.
- Route Optimization: Geospatial analysis, Kepler visualizations.
- And more...
 
## v2.0 Architecture
- Orchestrator: Gemma 3 1B (always on, 1GB RAM only, routes every command)
- Content Primary: Qwen3 8B (best 2025 output, hybrid thinking mode)
- Content Fallback: Gemma 2 9B (reliable, well-tested alternative)
- Logic/Scoring: Phi-4 Mini Instruct (load on demand for job scoring and routing)
- All model calls use keep_alive:0 (load -> generate -> unload immediately)
- Chrome Extension at D:\beelal_007\chrome_extension\ (Manifest V3)
- FastAPI bridge at localhost:8000 (connects extension to Python)
- Intelligence Modes: local / web_copilot / hybrid
- Approval: Chrome Extension overlay (NOT Tkinter)
 
## Rules
- All files in D:\beelal_007\
- Models in D:\local_models\
- Github Repo: https://github.com/bilalahmadsheikh/beelal_007
- NEVER submit any form without approval
- No paid APIs — free/local only
- keep_alive:0 on EVERY model call
