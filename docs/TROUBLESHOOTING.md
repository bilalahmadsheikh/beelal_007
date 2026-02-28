# Troubleshooting — BilalAgent v2.0

## Common Issues

### Ollama not responding

**Error:** `[ERROR] Cannot connect to Ollama. Is it running?`

**Fix:**
```bash
ollama list    # Check if running
ollama serve   # Start if not
```

---

### Not enough RAM

**Error:** `[ERROR] Not enough RAM. Need X GB, only Y GB free.`

**Fix:**
1. Close browser tabs and other apps
2. Force unload stuck models:
   ```python
   from tools.model_runner import force_unload
   force_unload("qwen3:8b")
   ```
3. Check RAM: `python -c "from tools.model_runner import get_free_ram; print(f'{get_free_ram():.1f}GB')"`

---

### Model not found

**Error:** `pulling manifest... Error: pull model manifest: file does not exist`

**Fix:**
```bash
ollama pull gemma3:1b  # or whichever model is missing
```

---

### Orchestrator returns invalid JSON

**Symptom:** `[ORCHESTRATOR] Failed to parse JSON from: ...`

**Cause:** Gemma 3 1B sometimes wraps JSON in markdown or adds explanation.

**Built-in fix:** The orchestrator auto-strips markdown fences and extracts JSON. If it still fails, it falls back to `{"agent": "nlp", "task": "general", "model": "gemma3:1b"}`.

---

### GitHub API errors (409)

**Symptom:** `[GITHUB] API error: 409 Client Error`

**Cause:** Empty repos return 409 when fetching commits. This is normal and handled gracefully — the connector skips empty repos.

---

### Unicode encoding in PowerShell

**Error:** `UnicodeEncodeError: 'charmap' codec can't encode characters`

**Fix:** Set encoding before running:
```powershell
$env:PYTHONIOENCODING='utf-8'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
python agent.py "your command"
```

---

### Import errors

**Error:** `ModuleNotFoundError: No module named 'dotenv'`

**Fix:**
```bash
pip install python-dotenv pyyaml
```

---

### Request timeout

**Error:** `[ERROR] Ollama request timed out (120s).`

**Fix:** Large prompts on slow machines can exceed 120s. Try a shorter prompt or check if another model is using RAM.

---

*More issues will be added as the project progresses.*
