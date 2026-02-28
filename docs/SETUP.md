# Setup Guide — BilalAgent v2.0

## Prerequisites

| Tool | Required Version | Install |
|---|---|---|
| Python | 3.12+ | [python.org](https://python.org) |
| Node.js | 22+ | [nodejs.org](https://nodejs.org) |
| Ollama | Latest | [ollama.com](https://ollama.com) |

## Python Packages

```bash
pip install crewai playwright psutil fastapi uvicorn playwright-stealth python-dotenv requests pyyaml
```

## Ollama Models

```bash
# Required (Phase 0)
ollama pull gemma3:1b

# Required (Phase 1+)
ollama pull qwen3-4b-thinking

# Optional fallback
ollama pull gemma2:9b

# Optional logic/scoring
ollama pull phi4-mini
```

## Environment Variables

Create `D:\beelal_007\.env`:

```env
GITHUB_PAT=your_github_token_here
GITHUB_USERNAME=bilalahmadsheikh
OLLAMA_BASE_URL=http://localhost:11434
BRIDGE_PORT=8000
```

## Verify Installation

```bash
# 1. Python
python --version  # → 3.12+

# 2. Packages
pip show crewai playwright psutil fastapi uvicorn playwright-stealth pyyaml

# 3. Ollama
ollama list  # → gemma3:1b at minimum

# 4. Node
node --version  # → 22+

# 5. Model Runner
python -c "from tools.model_runner import run_model, get_free_ram; print(f'RAM: {get_free_ram():.1f}GB'); print(run_model('gemma3:1b', 'Say: OK'))"
```

## Running the Agent

```bash
cd D:\beelal_007

# Basic usage
python agent.py "your command here"

# Examples
python agent.py "what are my 4 projects and their tech stacks"
python agent.py "write a cover letter for a Python developer role"
python agent.py "what commits did I make this month"
```

### What Happens on Startup
1. **RAM check** — displays available memory
2. **Database init** — creates SQLite tables if not present
3. **Profile load** — reads `config/profile.yaml` into memory
4. **GitHub sync** — fetches repos and caches for 24h
5. **Command routing** — orchestrator classifies → agent executes
