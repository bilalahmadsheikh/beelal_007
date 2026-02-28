# Models — BilalAgent v2.0

## Active Models

| Model | Ollama Name | Size | RAM Usage | Role | Status |
|---|---|---|---|---|---|
| Gemma 3 1B | `gemma3:1b` | ~815 MB | ~1 GB | Orchestrator + NLP fallback | ✅ Installed & Tested |
| Qwen3 8B | `qwen3:8b` | ~5 GB | ~5 GB | Content Primary | ⬜ Pending |
| Gemma 2 9B | `gemma2:9b` | ~5.4 GB | ~6 GB | Content Fallback | ⬜ Optional |
| Phi-4 Mini | `phi4-mini` | ~2.5 GB | ~3 GB | Logic / Scoring | ⬜ Optional |

## Two-Tier System (Phase 1)

### Tier 1: Orchestrator (Always First)
- **Gemma 3 1B** routes every command
- Output: JSON `{"agent", "task", "model"}`
- RAM: ~1GB, fast loading
- Called via `safe_run("gemma3:1b", prompt, required_gb=0.5)`

### Tier 2: Specialist (On-Demand)
- **Phi-4 Mini** for complex analysis, scoring, structured tasks
- **Qwen3 8B** for writing, cover letters, proposals
- **Gemma 2 9B** as reliable fallback
- All load on-demand, unload immediately via `keep_alive:0`

## RAM Budget

**Total system RAM:** ~8 GB (varies)
**Usable for models:** ~4-5 GB (OS + apps take the rest)

**Rule:** Only ONE heavy model loaded at a time. Orchestrator (1B) can coexist briefly.

**Observed in testing:**
- Before model call: 2.6GB free
- During model call: ~1.4GB free (model loaded)
- After keep_alive:0 unload: RAM recovers

## keep_alive:0 Strategy

Every Ollama API call includes `"keep_alive": 0` via `safe_run()`:

```python
# ALL agent code MUST use safe_run() — never call Ollama directly
from tools.model_runner import safe_run

result = safe_run(
    model="gemma3:1b",
    prompt="classify this command",
    required_gb=0.5,  # RAM gate
    system="You are a router."
)
```

## Model Fallback Chain

```
Requested model (e.g. phi4-mini)
  → Check RAM via get_free_ram()
    → Enough RAM? → Load and run
    → Not enough? → Fall back to gemma3:1b
```

## Download Commands

```bash
ollama pull gemma3:1b     # Phase 0 — ✅ installed
ollama pull qwen3:8b      # Phase 1+ — for content generation
ollama pull gemma2:9b     # Optional fallback
ollama pull phi4-mini     # Optional for scoring
```
