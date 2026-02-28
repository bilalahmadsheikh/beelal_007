# Models — BilalAgent v2.0

## Active Models

| Model | Ollama Name | Size | RAM Usage | Role | keep_alive | Status |
|---|---|---|---|---|---|---|
| Gemma 3 1B | `gemma3:1b` | ~815 MB | ~1 GB | Orchestrator + NLP | `5m` (always warm) | ✅ Installed |
| Gemma 3 4B | `gemma3:4b` | ~3.3 GB | ~3.3 GB | Content Primary | `30s` + explicit unload | ✅ Installed |
| Gemma 2 9B | `gemma2:9b` | ~5.4 GB | ~6 GB | Content Fallback | `30s` | ⬜ Optional |
| Phi-4 Mini | `phi4-mini` | ~2.5 GB | ~3 GB | Logic / Scoring | `30s` | ⬜ Optional |

## Two-Tier System

### Tier 1: Orchestrator (Always Warm)
- **Gemma 3 1B** routes every command
- Output: JSON `{"agent", "task", "model"}`
- `keep_alive=5m` — stays warm for fast routing (1-2s TTFT on cache hit)
- KV cache reused when system prompt matches

### Tier 2: Specialists (On-Demand)
- **Gemma 3 4B** for writing, cover letters, proposals (~10 tok/s, 54s TTFT on 5KB prompts)
- **Phi-4 Mini** for scoring, analysis
- **Gemma 2 9B** as reliable fallback
- `keep_alive=30s` — short window for follow-up calls
- Explicitly unloaded via `force_unload()` after generation completes

## RAM Management

**Total system RAM:** ~8.5 GB  
**Usable for models:** ~4-7 GB (depends on other apps)

**Rules:**
- Only ONE specialist loaded at a time
- Router unloaded before loading specialist (`force_unload("gemma3:1b")`)
- Specialist unloaded after generation (`force_unload("gemma3:4b")`)
- `safe_run()` checks RAM before loading, auto-unloads if needed

**Observed in v16 test:**
- Before: 7.6GB free → Load gemma3:4b → During: 2.1GB free → After unload: RAM recovers

## Fallback Chain

```
Gemma 3 4B (primary, 3.0GB required)
  → Success? Return result + unload
  → Error or too short? Retry once
  → Still failing?
    → Gemma 2 9B (fallback, 6.0GB required)
    → Still failing?
      → Gemma 3 1B (last resort, 0.5GB required)
```

## Download Commands

```bash
ollama pull gemma3:1b     # Required — orchestrator
ollama pull gemma3:4b     # Required — content generation
ollama pull gemma2:9b     # Optional — fallback
ollama pull phi4-mini     # Optional — scoring
```
