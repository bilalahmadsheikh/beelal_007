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
   force_unload("gemma3:4b")
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

**Cause:** Empty repos return 409 when fetching commits. This is normal and handled gracefully.

---

### Unicode encoding in PowerShell

**Error:** `UnicodeEncodeError: 'charmap' codec can't encode characters`

**Fix:**
```powershell
$env:PYTHONIOENCODING='utf-8'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
python agent.py "your command"
```

---

### Bridge not starting

**Error:** `Address already in use` or `Connection refused`

**Fix:**
```bash
# Check if port 8000 is already in use
netstat -ano | findstr :8000

# Kill the process using it
taskkill /PID <pid> /F

# Restart bridge
python -m uvicorn bridge.server:app --port 8000
```

---

### Chrome Extension not loading

**Symptom:** Extension doesn't appear in Chrome

**Fix:**
1. Go to `chrome://extensions`
2. Enable **Developer Mode** (top right toggle)
3. Click **Load unpacked**
4. Select `D:\beelal_007\chrome_extension\`
5. If errors: click **Errors** button on the extension card to see details

---

### Extension shows "Bridge Offline"

**Symptom:** Popup shows red "Offline" badge

**Fix:**
1. Start bridge: `python -m uvicorn bridge.server:app --port 8000`
2. Check bridge: `curl http://localhost:8000/`
3. Should return `{"status": "running", "agent": "BilalAgent v2.0"}`

---

### Cookie sync not working

**Symptom:** Playwright can't reuse login sessions

**Fix:**
1. Make sure you're logged in to the site in Chrome
2. Open extension popup — check "Cookies" section shows the site
3. Check SQLite: `python -c "from memory.db import *; init_db()"`
4. Manually trigger sync: reinstall extension (Remove → Load unpacked again)

---

### JobSpy returns no results

**Symptom:** `[JOBSPY] Search error: ...` or empty results

**Fix:**
1. Check internet connection
2. Try different search terms
3. Clear cache: `python -c "from connectors.jobspy_connector import clear_cache; clear_cache()"`
4. JobSpy may be rate-limited — wait 5 minutes and retry

---

### Import errors

**Error:** `ModuleNotFoundError: No module named '...'`

**Fix:**
```bash
pip install python-dotenv pyyaml openpyxl python-jobspy playwright-stealth fastapi uvicorn schedule
```

---

### Request timeout

**Error:** `[ERROR] Ollama request timed out (300s).`

**Fix:**
1. Check if another model is consuming RAM: `ollama ps`
2. Force unload stuck models:
   ```python
   from tools.model_runner import unload_all_specialists
   unload_all_specialists()
   ```
3. Try a shorter prompt or reduce context size.

---

### Hybrid refinement timeout

**Symptom:** `[HYBRID] Timed out after 120s`

**Cause:** Claude.ai didn't respond in time, or MutationObserver didn't capture the response.

**Fix:**
1. Make sure you're logged into claude.ai in Chrome
2. Ensure the Chrome Extension is loaded and active
3. Start the bridge: `python -m uvicorn bridge.server:app --port 8000`
4. Check that claude.ai is accessible (no CAPTCHA, account active)
5. The refinement falls back to the original local draft on timeout

---

### Weekly posts generate 0 posts

**Symptom:** `No posts generated — check GitHub activity.`

**Fix:**
1. Verify GitHub PAT is valid: `python -c "from connectors.github_connector import *; print(len(GitHubConnector().get_repos()))"`
2. Check `.env` has `GITHUB_PAT` set
3. Run manually: `python tools/post_scheduler.py --mode local`

---

### Windows scheduler not starting

**Symptom:** `setup_scheduler_windows.py` fails

**Fix:**
1. Run as Administrator
2. Check: `python setup_scheduler_windows.py check`
3. Manual create: `schtasks /create /tn BilalAgent_Scheduler /tr "pythonw scheduler.py" /sc ONLOGON /f`

---

*Last updated: 2026-03-01 (Phase 6 complete)*
