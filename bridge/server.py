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
    return {"status": "running", "agent": "BilalAgent v3.0", "bridge": "active"}


@app.get("/status")
async def status():
    """Health check — extension polls this at startup."""
    return {"status": "ok", "bridge": "BilalAgent", "version": "3.0"}


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


# ─── Phase 9: Permission Gate Endpoints ──────────────

import time as _time

# In-memory permission queue (fast — no DB overhead for real-time permission flow)
pending_permissions: dict = {}  # task_id -> {action data, decision, created_at}

# Server-level Allow All state
server_allow_all: bool = False
server_allow_all_expires: float = 0.0


class PermissionRequest(BaseModel):
    task_id: str
    action_type: str
    description: str
    x: Optional[int] = None
    y: Optional[int] = None
    text: Optional[str] = None
    confidence: float = 0.0


class PermissionDecision(BaseModel):
    task_id: str
    decision: str  # "allow" | "allow_all" | "skip" | "stop" | "edit"
    edit_data: Optional[str] = None


class AllowAllRequest(BaseModel):
    duration_minutes: int = 30


@app.post("/permission/request")
async def permission_request(data: PermissionRequest):
    """Queue a permission request for the Chrome Extension overlay."""
    global server_allow_all, server_allow_all_expires

    # If server-level allow_all is active, auto-approve
    if server_allow_all and _time.time() < server_allow_all_expires:
        pending_permissions[data.task_id] = {
            **data.model_dump(),
            "decision": "allow",
            "created_at": _time.time(),
        }
        return {"status": "auto_allowed", "task_id": data.task_id}

    pending_permissions[data.task_id] = {
        **data.model_dump(),
        "decision": None,
        "created_at": _time.time(),
    }
    print(f"[BRIDGE] Permission queued: {data.task_id} — {data.action_type}: {data.description}")
    return {"status": "queued", "task_id": data.task_id}


@app.get("/permission/pending")
async def permission_pending():
    """Return all pending (undecided) permission requests. Extension polls this."""
    pending = [
        {
            "task_id": tid,
            "action_type": info.get("action_type", "unknown"),
            "description": info.get("description", ""),
            "x": info.get("x"),
            "y": info.get("y"),
            "text": info.get("text"),
            "confidence": info.get("confidence", 0),
            "created_at": info.get("created_at", 0),
        }
        for tid, info in pending_permissions.items()
        if info.get("decision") is None
    ]
    return pending


@app.post("/permission/result")
async def permission_result_set(data: PermissionDecision):
    """Receive a decision from the Chrome Extension overlay."""
    global server_allow_all, server_allow_all_expires

    if data.task_id not in pending_permissions:
        raise HTTPException(status_code=404, detail=f"Permission {data.task_id} not found")

    pending_permissions[data.task_id]["decision"] = data.decision
    if data.edit_data:
        pending_permissions[data.task_id]["edit_data"] = data.edit_data

    # If user chose "allow_all", activate server-level auto-approve
    if data.decision == "allow_all":
        server_allow_all = True
        server_allow_all_expires = _time.time() + (30 * 60)  # 30 minutes
        print(f"[BRIDGE] Allow All activated for 30 minutes")

    print(f"[BRIDGE] Permission {data.task_id}: {data.decision}")
    return {"status": "received", "task_id": data.task_id, "decision": data.decision}


@app.get("/permission/result/{task_id}")
async def permission_result_get(task_id: str):
    """Poll for decision on a specific permission request."""
    if task_id not in pending_permissions:
        return {"decision": "not_found"}

    decision = pending_permissions[task_id].get("decision")
    if decision is None:
        return {"decision": "pending"}

    result = {"decision": decision}
    if "edit_data" in pending_permissions[task_id]:
        result["edit_data"] = pending_permissions[task_id]["edit_data"]
    return result


@app.post("/permission/set_allow_all")
async def set_allow_all(data: AllowAllRequest):
    """Enable auto-approve for N minutes."""
    global server_allow_all, server_allow_all_expires

    server_allow_all = True
    server_allow_all_expires = _time.time() + (data.duration_minutes * 60)

    print(f"[BRIDGE] Allow All set for {data.duration_minutes} minutes")
    return {
        "status": "ok",
        "expires_at": server_allow_all_expires,
        "duration_minutes": data.duration_minutes,
    }


@app.get("/permission/allow_all_status")
async def allow_all_status():
    """Get current Allow All status."""
    global server_allow_all, server_allow_all_expires

    if server_allow_all and _time.time() >= server_allow_all_expires:
        server_allow_all = False  # Expired

    remaining = max(0, int(server_allow_all_expires - _time.time())) if server_allow_all else 0

    return {
        "active": server_allow_all,
        "expires_at": server_allow_all_expires if server_allow_all else 0,
        "time_remaining_seconds": remaining,
    }


# ─── Phase 12: Task Tracking Endpoints ──────────────

# In-memory task registry (key: task_id)
active_tasks: dict = {}
page_states: dict = {}


class TaskBody(BaseModel):
    task_id: str
    type: str = "generic"
    content_preview: str = ""
    status: str = "active"


class TaskComplete(BaseModel):
    task_id: str
    status: str = "completed"
    posted_at: str = ""


class PageStateBody(BaseModel):
    task_id: str
    state: str
    url: str = ""
    ts: int = 0


@app.post("/tasks/register")
async def tasks_register(body: TaskBody):
    active_tasks[body.task_id] = {
        **body.model_dump(),
        "registered_at": _time.time(),
    }
    print(f"[BRIDGE] Task registered: {body.task_id} ({body.type})")
    return {"status": "registered", "task_id": body.task_id}


@app.get("/tasks/active")
async def tasks_active():
    return list(active_tasks.values())


@app.post("/tasks/complete")
async def tasks_complete(body: TaskComplete):
    if body.task_id in active_tasks:
        active_tasks[body.task_id].update({
            **body.model_dump(),
            "completed_at": _time.time(),
        })
    return {"status": "ok"}


@app.get("/tasks/status/{task_id}")
async def task_status(task_id: str):
    return active_tasks.get(task_id, {"status": "not_found"})


@app.post("/extension/page_state")
async def report_page_state(body: PageStateBody):
    page_states[body.task_id] = {**body.model_dump(), "reported_at": _time.time()}
    print(f"[EXTENSION] {body.task_id}: {body.state}")
    return {"status": "ok"}


@app.get("/extension/page_state/{task_id}")
async def get_page_state(task_id: str):
    return page_states.get(task_id, {"state": "unknown"})


# ─── Phase 12: Route Endpoint ───────────────────────

class RouteRequest(BaseModel):
    task: str

@app.post("/route")
async def route_task(data: RouteRequest):
    """Route a task through the orchestrator (gemma3:1b) to classify it."""
    try:
        from agents.orchestrator import route_command
        result = route_command(data.task)
        # Ensure expected fields
        if isinstance(result, dict):
            result.setdefault("needs_screen", False)
            result.setdefault("mode", "local")
            return result
        return {"agent": "nlp", "model": "gemma3:1b", "mode": "local", "needs_screen": False}
    except Exception as e:
        return {"agent": "nlp", "model": "gemma3:1b", "mode": "local",
                "needs_screen": False, "error": str(e)}

