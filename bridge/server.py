"""
server.py — BilalAgent v2.0 FastAPI Bridge
Connects Chrome Extension ↔ Python Agent via REST API.
Start: uvicorn bridge.server:app --port 8000 --reload
"""

import os
import sys
import json
import uuid
import sqlite3
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "memory", "agent_memory.db")


# ─── Pydantic Models ────────────────────────────────

class ContextSnap(BaseModel):
    url: str
    title: str
    description: str = ""
    budget: str = ""
    platform: str = ""


class ApprovalAction(BaseModel):
    task_id: str
    action: str  # "approve" | "cancel" | "edit"
    edited_content: str = ""


class CookieSync(BaseModel):
    site: str
    cookies: list


class AIResponse(BaseModel):
    source: str  # "claude" | "chatgpt"
    response_text: str
    task_id: str = ""


class TaskRegister(BaseModel):
    task_type: str  # "approval" | "context_snap" | "ai_response"
    content_preview: str = ""
    action_label: str = "Approve"


# ─── App Setup ───────────────────────────────────────

app = FastAPI(title="BilalAgent Bridge", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── Endpoints ───────────────────────────────────────

@app.get("/")
async def root():
    return {"status": "running", "agent": "BilalAgent v2.0", "bridge": "active"}


@app.post("/extension/context_snap")
async def context_snap(data: ContextSnap):
    """Receive job/gig data from 'Send to Agent' button in extension."""
    task_id = str(uuid.uuid4())[:8]
    
    conn = _get_conn()
    conn.execute(
        """INSERT INTO pending_tasks (task_id, task_type, content_preview, status)
           VALUES (?, ?, ?, ?)""",
        (task_id, "context_snap", json.dumps(data.model_dump()), "pending")
    )
    conn.commit()
    conn.close()
    
    print(f"[BRIDGE] Context snap received: {data.title} ({data.platform})")
    return {"task_id": task_id, "status": "queued", "message": f"Job '{data.title}' queued for processing"}


@app.post("/extension/approval")
async def approval(data: ApprovalAction):
    """Receive approve/cancel/edit from extension overlay."""
    conn = _get_conn()
    
    task = conn.execute("SELECT * FROM pending_tasks WHERE task_id = ?", (data.task_id,)).fetchone()
    if not task:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Task {data.task_id} not found")
    
    result = data.action
    if data.action == "edit" and data.edited_content:
        result = data.edited_content
    
    conn.execute(
        """UPDATE pending_tasks SET status = ?, result = ?, updated_at = ? WHERE task_id = ?""",
        (data.action, result, datetime.now().isoformat(), data.task_id)
    )
    conn.commit()
    conn.close()
    
    print(f"[BRIDGE] Task {data.task_id}: {data.action}")
    return {"task_id": data.task_id, "action": data.action, "status": "processed"}


@app.get("/extension/get_task")
async def get_task():
    """Extension polls this to know what overlay to show."""
    conn = _get_conn()
    task = conn.execute(
        "SELECT * FROM pending_tasks WHERE status = 'show_overlay' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    
    if task:
        return {
            "task_id": task["task_id"],
            "task_type": task["task_type"],
            "content_preview": task["content_preview"],
            "action_label": task["action_label"],
        }
    return None


@app.post("/extension/register_task")
async def register_task(data: TaskRegister):
    """Register a task for extension to show overlay."""
    task_id = str(uuid.uuid4())[:8]
    
    conn = _get_conn()
    conn.execute(
        """INSERT INTO pending_tasks (task_id, task_type, content_preview, action_label, status)
           VALUES (?, ?, ?, ?, ?)""",
        (task_id, data.task_type, data.content_preview, data.action_label, "show_overlay")
    )
    conn.commit()
    conn.close()
    
    print(f"[BRIDGE] Task registered: {task_id} ({data.task_type})")
    return {"task_id": task_id, "status": "show_overlay"}


@app.post("/extension/cookies")
async def sync_cookies(data: CookieSync):
    """Receive synced cookies from extension — saved to SQLite for Playwright reuse."""
    conn = _get_conn()
    
    # Upsert: delete old cookies for this site, insert new
    conn.execute("DELETE FROM cookies WHERE site = ?", (data.site,))
    conn.execute(
        "INSERT INTO cookies (site, cookie_data, updated_at) VALUES (?, ?, ?)",
        (data.site, json.dumps(data.cookies), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    
    print(f"[BRIDGE] Cookies synced: {data.site} ({len(data.cookies)} cookies)")
    return {"site": data.site, "count": len(data.cookies), "status": "saved"}


@app.get("/extension/cookies/{site}")
async def get_cookies(site: str):
    """Get stored cookies for a site (used by Playwright for session reuse)."""
    conn = _get_conn()
    row = conn.execute("SELECT cookie_data FROM cookies WHERE site = ?", (site,)).fetchone()
    conn.close()
    
    if row:
        return {"site": site, "cookies": json.loads(row["cookie_data"])}
    return {"site": site, "cookies": []}


@app.post("/extension/ai_response")
async def ai_response(data: AIResponse):
    """Receive AI response from Web Copilot mode (Claude/ChatGPT MutationObserver)."""
    conn = _get_conn()
    
    if data.task_id:
        conn.execute(
            """UPDATE pending_tasks SET status = ?, result = ?, updated_at = ? WHERE task_id = ?""",
            ("ai_response", data.response_text[:5000], datetime.now().isoformat(), data.task_id)
        )
    else:
        task_id = str(uuid.uuid4())[:8]
        conn.execute(
            """INSERT INTO pending_tasks (task_id, task_type, content_preview, status, result)
               VALUES (?, ?, ?, ?, ?)""",
            (task_id, "ai_response", f"From {data.source}", "completed", data.response_text[:5000])
        )
    
    conn.commit()
    conn.close()
    
    print(f"[BRIDGE] AI response from {data.source}: {len(data.response_text)} chars")
    return {"source": data.source, "length": len(data.response_text), "status": "received"}


@app.get("/extension/status")
async def bridge_status():
    """Get bridge status and stats."""
    conn = _get_conn()
    
    pending = conn.execute("SELECT COUNT(*) as c FROM pending_tasks WHERE status = 'pending'").fetchone()["c"]
    overlay = conn.execute("SELECT COUNT(*) as c FROM pending_tasks WHERE status = 'show_overlay'").fetchone()["c"]
    total = conn.execute("SELECT COUNT(*) as c FROM pending_tasks").fetchone()["c"]
    cookie_sites = conn.execute("SELECT DISTINCT site FROM cookies").fetchall()
    
    conn.close()
    
    return {
        "status": "running",
        "tasks": {"pending": pending, "show_overlay": overlay, "total": total},
        "cookie_sites": [r["site"] for r in cookie_sites],
    }
