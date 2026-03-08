# Chrome Extension — BilalAgent v3.0

## Overview

The Chrome Extension is the **primary browser UI** for BilalAgent. It provides a Claude-like interactive sidebar where the desktop agent pushes generated content, the user reviews and approves it, and the extension automates LinkedIn posting — all driven from the desktop agent with real-time SSE streaming.

**Fully redesigned in v3.0** with agent-driven prompting, SSE streaming, content preview cards, and interactive posting flow.

## Location

```
D:\beelal_007\chrome_extension\
├── manifest.json        # Manifest V3 config (v3.0)
├── background.js        # Service worker (cookie sync, message relay, LinkedIn orchestration)
├── content_script.js    # Page features (context snap, overlay, MutationObserver, LinkedIn actor)
├── popup.html           # Claude-like sidebar popup UI
├── popup.css            # Sidebar styles (dark theme, glassmorphism)
├── popup.js             # SSE connection, activity feed, content preview, prompt input
└── icons/               # 16, 48, 128px icons
```

## Loading the Extension

1. Open `chrome://extensions`
2. Enable **Developer Mode** (top right)
3. Click **Load unpacked**
4. Select `D:\beelal_007\chrome_extension\`
5. Start bridge: `uvicorn bridge.server:app --port 8000`

## Architecture — Agent-Driven Flow

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│  Desktop Agent   │───▶│  Bridge Server    │───▶│  Chrome Extension   │
│  (Python)        │    │  (FastAPI:8000)   │    │  (Popup + Content)  │
│                  │    │                   │    │                     │
│  generate_       │    │  /agent/content/  │    │  SSE EventSource    │
│  linkedin_post() │    │  ready            │    │  → Content Card     │
│                  │    │                   │    │  → Post/Edit/Reject │
│  push content    │───▶│  SSE push event   │───▶│  → AGENT_POST_      │
│  to bridge       │    │  content_ready    │    │    LINKEDIN          │
│                  │    │                   │    │                     │
│  wait for        │◀──│  /agent/content/  │◀──│  report decision     │
│  decision        │    │  status/{id}      │    │  approved/rejected  │
└─────────────────┘    └──────────────────┘    └─────────────────────┘
```

## Features

### 1. Claude-Like Popup UI (v3.0)
- **Activity Feed**: Scrollable message bubbles showing agent activity, content generation events, posting results
- **Content Preview Card**: When agent generates content, shows full preview with word count, highlighted hashtags, and action buttons
- **Action Buttons**: Post to LinkedIn, Copy to Clipboard, Edit First, Reject
- **Prompt Input**: Type commands to send back to the desktop agent
- **Status Tab**: Bridge/agent connection status, cookie sync info, task counts
- **Dark theme**: Premium gradient palette matching the agent aesthetic

### 2. SSE Real-Time Connection
- Popup connects to `GET /agent/stream` for real-time push events
- Events: `content_ready`, `agent_message`, `action_result`, `status_update`
- Auto-reconnect on disconnect, fallback polling via `/agent/content/latest`

### 3. Agent-Driven LinkedIn Posting
When user clicks "Post to LinkedIn" in the popup:
1. Background.js finds/opens a LinkedIn tab
2. Queues `open_composer` action via bridge
3. Queues `type_content` action with the generated post
4. Content script types content into LinkedIn composer
5. Upload confirmation overlay appears with Upload/Edit/Cancel
6. User confirms → extension clicks Post → success reported

### 4. Context Snap
- Floating **"Send to BilalAgent"** button on job pages
- Supported: LinkedIn, Upwork, Fiverr, Freelancer, PeoplePerHour
- Sends to `POST /extension/context_snap`

### 5. Approval Overlay + Permission Gate
- Slide-up panel for task approval
- Permission overlay with Allow Once/Allow All/Skip/Stop/Edit
- Crosshair indicator at target coordinates

### 6. MutationObserver (AI Response Capture)
- Watches Claude.ai and ChatGPT for AI responses
- Passes `window.__bilalAgentTaskId` for hybrid refiner

### 7. Cookie Sync
- Auto-sync cookies for all supported domains to bridge → SQLite
- Playwright reuses these for authenticated automation

## Messaging Protocol

```
Extension Popup ↔ Background.js ↔ Bridge Server

NEW in v3.0:
  - Popup SSE: GET /agent/stream (real-time push)  
  - Content Push: POST /agent/content/ready (agent → extension)
  - Content Decision: POST /agent/content/decision (extension → agent)
  - Content Status: GET /agent/content/status/{id} (agent polls)
  - Prompt: POST /agent/prompt (extension → agent)
  - Agent Message: POST /agent/message (agent → extension)
  
  Background Handlers:
  - AGENT_POST_LINKEDIN: orchestrates full LinkedIn posting
  - AGENT_SEND_PROMPT: forwards prompts to bridge
  - AGENT_OPEN_TAB: open URLs on agent request

Existing (unchanged):
  - POST /extension/context_snap
  - POST /extension/approval
  - POST /extension/ai_response
  - GET /extension/get_task
  - POST /extension/cookies
  - POST /linkedin/action (open_composer, type_content, click_post)
  - POST /permission/request + /permission/result
```

## Testing

```bash
# Run extension update tests
python tests/test_extension_update.py

# Tests cover (offline): imports, file existence, manifest version, file content checks
# Tests cover (online): content push, polling, decisions, prompts, SSE stream
```

## Permissions

| Permission | Why |
|---|---|
| `activeTab` | Read current page for context snap |
| `cookies` | Sync login cookies to bridge |
| `scripting` | Inject overlay + button |
| `storage` | Local extension settings |
| `tabs` | Detect navigation, open/focus LinkedIn |

## Security Rules

1. **NEVER submit any form without user approval**
2. Extension only talks to `localhost:8000`
3. No external API calls from the extension
4. Cookies stored in local SQLite only
5. Content always shown for review before posting
