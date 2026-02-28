# Chrome Extension — BilalAgent v2.0

> This doc will be updated as the extension is built in later phases.

## Overview

The Chrome Extension is the primary UI for BilalAgent. It replaces Tkinter with a browser-native overlay for approvals, status display, and job interaction.

## Tech Stack

- **Manifest V3** (required for modern Chrome)
- **Content Scripts** for page interaction
- **Background Service Worker** for bridge communication
- **Popup / Overlay** for approval UI

## Location

```
D:\beelal_007\chrome_extension\
```

## Messaging Protocol (Planned)

```
Extension ←→ FastAPI Bridge (localhost:8000)
  - POST /command    → Send user command
  - POST /approve    → Approve/reject action
  - GET  /status     → Poll agent status
```

## Key Features (Planned)

- [ ] Approval overlay before any form submission
- [ ] Job listing scraper (LinkedIn, Upwork)
- [ ] Status indicator (idle / working / waiting for approval)
- [ ] One-click cover letter generation

## Security Rules

1. **NEVER submit any form without user approval**
2. Extension only talks to `localhost:8000`
3. No external API calls from the extension
