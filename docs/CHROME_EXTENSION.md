# Chrome Extension — BilalAgent v2.0

## Overview

The Chrome Extension is the primary UI for BilalAgent. It replaces Tkinter with a browser-native overlay for approvals, status display, and job interaction. **Fully implemented in Phase 4.**

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
- Supported sites: LinkedIn, Upwork, Fiverr, Freelancer
- Captures: title, company, description, salary, URL
- Sends to `POST /extension/context_snap`

### 2. Approval Overlay
- Slide-up dark panel at bottom of page
- Shows task preview + **Approve** / **Cancel** buttons
- Extension polls `GET /extension/get_task` every 2s
- Sends decision to `POST /extension/approval`

### 3. MutationObserver (AI Response Capture)
- Watches Claude.ai (`div.font-claude-message`) and ChatGPT (`div.markdown`)
- Captures completed responses and sends to `POST /extension/ai_response`
- Detects streaming completion vs static content

### 4. Cookie Sync
- On install: syncs cookies for all supported domains
- On cookie change: auto-syncs to bridge → SQLite
- Supported domains: `.linkedin.com`, `.upwork.com`, `.fiverr.com`, `.freelancer.com`, `.claude.ai`, `.chatgpt.com`
- Playwright reuses these cookies for authenticated browser automation

## Messaging Protocol

```
Extension ←→ FastAPI Bridge (localhost:8000)

Content Script → Background.js → Bridge Server → SQLite
  - POST /extension/context_snap    (job data from button click)
  - POST /extension/approval        (approve/cancel from overlay)
  - POST /extension/ai_response     (Claude/ChatGPT output)

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
