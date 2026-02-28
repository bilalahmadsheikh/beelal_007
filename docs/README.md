# BilalAgent v2.0 — Documentation

Living documentation for the BilalAgent project. **Phases 0-6 complete.**

| Doc | Purpose |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design, model stack, data flow, directory structure |
| [SETUP.md](SETUP.md) | Environment setup, dependencies, first-run guide |
| [PHASE_LOG.md](PHASE_LOG.md) | Phase-by-phase progress tracker (0-6) with timestamps |
| [API_REFERENCE.md](API_REFERENCE.md) | All tool functions, bridge endpoints, connector methods |
| [MODELS.md](MODELS.md) | Ollama model config, RAM budgets, keep_alive strategy |
| [CHROME_EXTENSION.md](CHROME_EXTENSION.md) | Extension architecture, hybrid refiner flow, messaging |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Common errors and fixes (including Phase 6 issues) |
| [CHANGELOG.md](CHANGELOG.md) | All changes by date |

## Quick Start

```bash
cd D:\beelal_007
pip install -r requirements.txt  # or install packages manually
ollama pull gemma3:1b && ollama pull gemma3:4b

# Start bridge
python -m uvicorn bridge.server:app --port 8000 &

# Use the agent
python agent.py "write a linkedin post about IlmSeUrooj"
python agent.py "generate weekly posts"
python agent.py "find AI Engineer jobs remote"
python agent.py "check github activity"
```
