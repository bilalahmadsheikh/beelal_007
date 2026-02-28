# Chrome Extension — BilalAgent v2.0

## Overview

The Chrome Extension is the primary UI for BilalAgent. It replaces Tkinter with a browser-native overlay for approvals, status display, and job interaction. Also provides MutationObserver-based AI response capture for the **Hybrid Refiner** mode. **Fully implemented in Phase 4, enhanced in Phase 6.**

## Location

```
D:\beelal_007\chrome_extension\
├── manifest.json        # Manifest V3 config
├── background.js        # Service worker (cookie sync, message relay, polling)
├── content_script.js    # Page features (context snap, overlay, MutationObserver)
├── popup.html           # Status popup UI
├── popup.js             # Popup logic
└── icons/               # 16, 48, 128px icons
```

## Loading the Extension

1. Open `chrome://extensions`
2. Enable **Developer Mode** (top right)
3. Click **Load unpacked**
4. Select `D:\beelal_007\chrome_extension\`
5. Start bridge: `python -m uvicorn bridge.server:app --port 8000`

## Features

### 1. Context Snap
- Floating **"Send to BilalAgent"** button appears on job pages
- Supported sites: LinkedIn, Upwork, Fiverr, Freelancer, PeoplePerHour
- Captures: title, company, description, salary, URL
- Sends to `POST /extension/context_snap`

### 2. Approval Overlay
- Slide-up dark panel at bottom of page
- Shows task preview + **Approve** / **Cancel** buttons
- Extension polls `GET /extension/get_task` every 2s
- Sends decision to `POST /extension/approval`

### 3. MutationObserver (AI Response Capture)
- Watches Claude.ai and ChatGPT for AI responses
- Captures completed responses when stop button disappears (2s debounce)
- **Phase 6:** Passes `window.__bilalAgentTaskId` for hybrid refiner task matching
- Sends to `POST /extension/ai_response` via bridge

### 4. Cookie Sync
- On install: syncs cookies for all supported domains
- On cookie change: auto-syncs to bridge → SQLite
- Supported domains: `.linkedin.com`, `.upwork.com`, `.fiverr.com`, `.freelancer.com`, `.claude.ai`, `.chatgpt.com`
- Playwright reuses these cookies for authenticated browser automation

## Hybrid Refiner Flow (Phase 6)

```
1. post_scheduler.py calls hybrid_refine(draft)
2. Playwright opens claude.ai with extension loaded
3. Sets window.__bilalAgentTaskId for tracking
4. Types refinement prompt into Claude's input
5. MutationObserver detects Claude's response (stop button gone)
6. Response sent to /extension/ai_response with task_id
7. Python polls bridge for the response → returns polished text
```

## Messaging Protocol

```
Extension ←→ FastAPI Bridge (localhost:8000)

Content Script → Background.js → Bridge Server → SQLite
  - POST /extension/context_snap    (job data from button click)
  - POST /extension/approval        (approve/cancel from overlay)
  - POST /extension/ai_response     (Claude/ChatGPT output + task_id)

Bridge Server → Background.js → Content Script
  - GET  /extension/get_task        (polls every 2s for overlay tasks)
  - GET  /extension/status          (popup status display)

Background.js → Bridge Server
  - POST /extension/cookies         (cookie sync on install/change)
```

## Permissions

| Permission | Why |
|---|---|
| `activeTab` | Read current page for context snap |
| `cookies` | Sync login cookies to bridge |
| `scripting` | Inject overlay + button |
| `storage` | Local extension settings |
| `tabs` | Detect navigation changes |

## Security Rules

1. **NEVER submit any form without user approval**
2. Extension only talks to `localhost:8000`
3. No external API calls from the extension
4. Cookies stored in local SQLite only
