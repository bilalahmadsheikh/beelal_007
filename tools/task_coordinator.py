"""
tools/task_coordinator.py — BilalAgent v3.0 Phase 5
Central coordinator — wires desktop overlay, agent pipeline,
Chrome extension, and Playwright into one unified task flow.

Every multi-step task runs through here.
"""

import os
import sys
import uuid
import requests
from datetime import datetime
from typing import Callable, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

BRIDGE = "http://localhost:8000"


# ═══════════════════════════════════════════════════════
#  Task — lightweight data class
# ═══════════════════════════════════════════════════════

class Task:
    def __init__(self, user_input: str):
        self.id = str(uuid.uuid4())[:8]
        self.user_input = user_input
        self.status = "pending"           # pending|running|generating|uploading|done|failed
        self.generated_content: Optional[str] = None
        self.result: Optional[dict] = None
        self.steps: list = []
        self.error: Optional[str] = None
        self.created_at = datetime.now()

    def log(self, step: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.steps.append({"step": step, "time": ts})
        print(f"  [TASK {self.id}] {step}")


# ═══════════════════════════════════════════════════════
#  TaskCoordinator
# ═══════════════════════════════════════════════════════

class TaskCoordinator:
    """
    Unified task runner.

    Usage (from desktop overlay or agent.py):
        coord = TaskCoordinator()
        coord.set_overlay_callback(lambda msg, t: print(msg))
        task = coord.run("write and upload a linkedin post about basepy-sdk")
    """

    def __init__(self):
        self.current_task: Optional[Task] = None
        self._overlay_cb: Optional[Callable] = None

    def set_overlay_callback(self, cb: Callable):
        """Desktop overlay registers this to receive live status messages."""
        self._overlay_cb = cb

    # ── Internal helpers ──────────────────────────────

    def _notify(self, message: str, msg_type: str = "system"):
        """Send update to overlay AND print to terminal."""
        if self._overlay_cb:
            try:
                self._overlay_cb(message, msg_type)
            except Exception:
                pass
        print(f"  [COORD] {message}")

    def _bridge_post(self, endpoint: str, data: dict):
        try:
            requests.post(f"{BRIDGE}{endpoint}", json=data, timeout=3)
        except Exception:
            pass

    # ── Intent detection ──────────────────────────────

    def _detect_intent(self, task: Task) -> dict:
        """
        Quick keyword-based intent detection.
        Returns a dict describing what to do and how.
        """
        lower = task.user_input.lower()

        upload_kws = [
            "upload", "post to linkedin", "publish", "go live",
            "write and upload", "write and post", "share on linkedin",
        ]
        content_kws = [
            "write", "generate", "create", "linkedin post",
            "cover letter", "gig", "proposal",
        ]
        job_kws = ["find jobs", "search jobs", "apply", "job search"]
        github_kws = ["github", "repos", "my projects", "commit"]

        needs_upload = any(k in lower for k in upload_kws)
        needs_content = any(k in lower for k in content_kws) or needs_upload
        is_job = any(k in lower for k in job_kws)
        is_github = any(k in lower for k in github_kws)

        if needs_upload and needs_content:
            return {
                "action": "post_linkedin",
                "method": "generate_then_upload",
                "needs_generation": True,
                "description": "generating LinkedIn post then uploading live",
            }
        if needs_content:
            return {
                "action": "generate_content",
                "method": "local",
                "needs_generation": True,
                "description": "generating content",
            }
        if is_job:
            return {
                "action": "job_search",
                "method": "local",
                "needs_generation": False,
                "description": "searching for jobs",
            }
        if is_github:
            return {
                "action": "github_query",
                "method": "local",
                "needs_generation": False,
                "description": "querying GitHub data",
            }

        # Default: run through normal agent pipeline
        return {
            "action": "agent_pipeline",
            "method": "local",
            "needs_generation": False,
            "description": "running through agent pipeline",
        }

    # ── Content generation step ───────────────────────

    def _generate(self, task: Task, intent: dict) -> Optional[str]:
        """Generate content via the existing content pipeline."""
        try:
            from agent import _parse_content_command, _handle_content
            parsed = _parse_content_command(task.user_input)
            if parsed and parsed["content_type"] == "linkedin_post":
                from tools.content_tools import generate_linkedin_post
                return generate_linkedin_post(
                    parsed["project_name"],
                    parsed.get("post_type", "project_showcase"),
                    user_request=task.user_input,
                )
            # Fallback: generic content agent
            from agents.content_agent import generate
            return generate(task.user_input, content_type="general")
        except Exception as e:
            task.error = str(e)
            return None

    # ── LinkedIn upload step ──────────────────────────

    def _post_linkedin(self, task: Task) -> dict:
        """Upload generated content to LinkedIn via LinkedInPoster."""
        if not task.generated_content:
            return {"status": "failed", "reason": "No content to upload"}
        try:
            from tools.linkedin_poster import LinkedInPoster
            return LinkedInPoster().post(
                content=task.generated_content,
                source_task=task.user_input,
            )
        except Exception as e:
            return {"status": "failed", "reason": str(e)}

    # ── Generic agent pipeline step ───────────────────

    def _run_pipeline(self, task: Task) -> str:
        """Run the normal agent pipeline for non-content tasks."""
        try:
            from agent import handle_command, load_profile_yaml
            profile = load_profile_yaml()
            return str(handle_command(task.user_input, profile))
        except Exception as e:
            return f"[ERROR] Pipeline failed: {e}"

    # ── MAIN ENTRY POINT ──────────────────────────────

    def run(self, user_input: str) -> Task:
        """
        Execute a task end-to-end.

        Steps:
        1. Detect intent
        2. Generate content (if needed)
        3. Execute action (upload / search / pipeline)
        4. Report result

        Returns the Task object with .status, .result, .steps.
        """
        task = Task(user_input)
        self.current_task = task

        try:
            task.status = "running"
            intent = self._detect_intent(task)
            task.log(f"Intent: {intent['action']} | {intent['description']}")
            self._notify(f"On it — {intent['description']}", "system")

            # ── Step 1: generate content ──────────────
            if intent["needs_generation"]:
                task.status = "generating"
                self._notify("Generating content...", "system")
                content = self._generate(task, intent)
                if not content:
                    raise RuntimeError(f"Content generation failed: {task.error}")
                task.generated_content = content
                task.log(f"Generated {len(content.split())} words")
                self._notify(content, "agent")

            # ── Step 2: execute action ────────────────
            action = intent["action"]

            if action == "post_linkedin":
                task.status = "uploading"
                self._notify("Starting LinkedIn upload...", "system")
                result = self._post_linkedin(task)
                task.result = result
                if result["status"] == "posted":
                    self._notify(
                        f"Posted to LinkedIn at {result['posted_at']}", "system"
                    )
                elif result["status"] == "cancelled":
                    self._notify("Upload cancelled — post saved to Excel", "system")
                else:
                    self._notify(f"Upload failed: {result['reason']}", "error")

            elif action == "generate_content":
                task.result = {"status": "done",
                               "content": task.generated_content}

            elif action in ("job_search", "github_query", "agent_pipeline"):
                task.status = "running"
                output = self._run_pipeline(task)
                task.result = {"status": "done", "output": output}
                self._notify(output, "agent")

            else:
                task.result = {"status": "unknown_action", "action": action}

            task.status = "done"
            task.log("Task complete")

        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.log(f"FAILED: {e}")
            self._notify(f"Task failed: {e}", "error")

        return task


# ── Module-level singleton ────────────────────────────

_coordinator: Optional[TaskCoordinator] = None


def get_coordinator() -> TaskCoordinator:
    """Get or create the global TaskCoordinator instance."""
    global _coordinator
    if _coordinator is None:
        _coordinator = TaskCoordinator()
    return _coordinator


if __name__ == "__main__":
    print("TaskCoordinator loaded OK")
    coord = TaskCoordinator()
    coord.set_overlay_callback(lambda msg, t: print(f"  [{t.upper()}] {msg[:80]}"))
    task = coord.run("what are my top projects")
    print(f"\nTask {task.id}: {task.status}")
    for s in task.steps:
        print(f"  {s['time']} — {s['step']}")
