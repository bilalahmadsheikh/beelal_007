"""
post_scheduler.py — BilalAgent v2.0 LinkedIn Post Scheduler
Generates weekly posts with 3 modes: local, hybrid, web_copilot.
Hybrid mode: local draft → Claude web UI polish via extension.
"""

import os
import sys
import json
import time
import uuid
import sqlite3
import requests
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from connectors.github_monitor import GitHubActivityMonitor
from agents.content_agent import generate
from tools.content_tools import generate_linkedin_post, _get_deep_repo_context, _load_profile
from memory.db import log_content

DB_PATH = os.path.join(PROJECT_ROOT, "memory", "agent_memory.db")
DRAFTS_DIR = os.path.join(PROJECT_ROOT, "memory", "post_drafts")
BRIDGE_URL = os.getenv("BRIDGE_URL", "http://localhost:8000")


def generate_weekly_posts(mode: str = "local") -> list:
    """
    Generate 3 weekly LinkedIn posts using GitHub activity as topics.
    
    Args:
        mode: "local" (gemma3:4b only), "hybrid" (local + Claude polish), 
              "web_copilot" (full Claude generation)
    
    Returns:
        List of post dicts: {type, draft, final, path, status, mode}
    """
    print(f"\n{'=' * 60}")
    print(f"  Weekly Post Generation — Mode: {mode}")
    print(f"{'=' * 60}")
    
    # Get content ideas from GitHub activity
    monitor = GitHubActivityMonitor()
    ideas = monitor.get_content_ideas()
    
    if not ideas:
        print("[SCHEDULER] No content ideas generated")
        return []
    
    # Load profile for name injection
    profile = _load_profile()
    profile_name = profile.get("personal", {}).get("name", "the developer")
    
    os.makedirs(DRAFTS_DIR, exist_ok=True)
    posts = []
    
    for i, idea in enumerate(ideas[:3], 1):
        print(f"\n[POST {i}/3] Type: {idea['type']} | Project: {idea['project']}")
        print(f"  Hook: {idea['hook'][:80]}")
        
        # Build the prompt based on idea type
        project_name = idea.get("project", "")
        
        if project_name and idea["type"] in ("project_showcase", "learning_update", "achievement"):
            # Use the full content pipeline for project posts
            print(f"  [SCHEDULER] Generating via full pipeline for: {project_name}")
            
            post_type_map = {
                "project_showcase": "project_showcase",
                "learning_update": "learning_update",
                "achievement": "achievement",
                "opinion": "opinion",
            }
            post_type = post_type_map.get(idea["type"], "project_showcase")
            
            if mode == "local":
                # Use the proven content pipeline (gemma3:4b via content_agent)
                draft = generate_linkedin_post(
                    project_name, 
                    post_type=post_type,
                    user_request=idea["hook"]
                )
            else:
                # For hybrid/web_copilot, generate local draft first
                draft = generate_linkedin_post(
                    project_name,
                    post_type=post_type,
                    user_request=idea["hook"]
                )
        else:
            # Opinion/general post — use direct prompt
            prompt = f"""Write a LinkedIn thought-leadership post.

Topic: {idea['hook']}

About the author: {profile_name}, AI Engineering student (3rd year), builds real projects.
Link back to a relevant project from github.com/bilalahmadsheikh if applicable.

Write 300-500 words. Be personal, thoughtful, technical. First person.
End with 4-6 hashtags. NO preamble — output ONLY the post."""
            
            draft = generate(prompt, content_type="linkedin_opinion")
        
        if not draft or draft.startswith("[ERROR]") or len(draft) < 50:
            print(f"  [SCHEDULER] Draft generation failed, skipping")
            continue
        
        # Apply hybrid refinement if mode is hybrid
        final = draft
        if mode == "hybrid" and len(draft) > 100:
            print(f"  [SCHEDULER] Sending to Claude for hybrid refinement...")
            refined = hybrid_refine(draft)
            if refined and len(refined) > 100:
                final = refined
                print(f"  [SCHEDULER] Hybrid refinement successful ({len(refined)} chars)")
            else:
                print(f"  [SCHEDULER] Hybrid refinement failed, using local draft")
        
        # Save to file
        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"{date_str}_{idea['type']}_{i}.txt"
        filepath = os.path.join(DRAFTS_DIR, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"Type: {idea['type']}\n")
            f.write(f"Project: {project_name}\n")
            f.write(f"Hook: {idea['hook']}\n")
            f.write(f"Mode: {mode}\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n")
            f.write(f"Words: {len(final.split())}\n")
            f.write(f"{'─' * 50}\n\n")
            f.write(final)
        
        print(f"  [SCHEDULER] Saved: {filename} ({len(final)} chars, {len(final.split())} words)")
        
        # Log to content_log
        log_content(idea["type"], final, status="pending_approval", 
                    platform="linkedin", model_used=f"gemma3:4b+{mode}")
        
        # Log to Excel
        try:
            from memory.excel_logger import log_post
            log_post(
                post_type=idea["type"],
                preview=final[:100],
                status="pending_approval",
                mode=mode,
            )
        except ImportError:
            pass  # Excel logger update may not be applied yet
        
        post = {
            "type": idea["type"],
            "project": project_name,
            "hook": idea["hook"],
            "draft": draft[:200] + "..." if len(draft) > 200 else draft,
            "final": final,
            "path": filepath,
            "words": len(final.split()),
            "status": "pending_approval",
            "mode": mode,
        }
        posts.append(post)
    
    print(f"\n{'=' * 60}")
    print(f"  Generated {len(posts)} posts — Mode: {mode}")
    print(f"{'=' * 60}")
    
    return posts


def hybrid_refine(draft: str, task_id: str = "") -> str:
    """
    Send a draft to Claude web UI for polishing via Playwright + extension.
    
    Flow:
    1. Open claude.ai in Playwright with stealth + extension
    2. Type refinement prompt
    3. MutationObserver in extension captures Claude's response
    4. Response sent to /extension/ai_response via bridge
    5. We poll the bridge until response arrives
    
    Args:
        draft: The local model's draft post
        task_id: Optional task ID for tracking
        
    Returns:
        Polished text from Claude, or original draft on failure
    """
    if not task_id:
        task_id = str(uuid.uuid4())[:8]
    
    refinement_prompt = (
        f"Refine this LinkedIn post to sound natural and human, not AI-generated. "
        f"Keep all technical details and facts. Make it more conversational, compelling, "
        f"and authentic. Keep the same structure but improve flow and word choice. "
        f"Output ONLY the refined post, no commentary:\n\n{draft}"
    )
    
    # Step 1: Register a pending task for the response
    try:
        r = requests.post(f"{BRIDGE_URL}/extension/register_task", json={
            "task_type": "ai_response_wait",
            "content_preview": f"Hybrid refine: {draft[:100]}...",
            "action_label": "Waiting for Claude",
        }, timeout=5)
        task_data = r.json()
        task_id = task_data.get("task_id", task_id)
        print(f"  [HYBRID] Registered task: {task_id}")
    except Exception as e:
        print(f"  [HYBRID] Bridge not available: {e}")
        return draft
    
    # Step 2: Open Claude.ai via Playwright with stealth
    try:
        from playwright.sync_api import sync_playwright
        from playwright_stealth import Stealth
        
        print(f"  [HYBRID] Opening Claude.ai...")
        
        with sync_playwright() as p:
            # Launch browser with extension
            ext_path = os.path.join(PROJECT_ROOT, "chrome_extension")
            
            browser = p.chromium.launch(
                headless=False,
                args=[
                    f"--disable-extensions-except={ext_path}",
                    f"--load-extension={ext_path}",
                    "--no-first-run",
                ]
            )
            
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            # Apply stealth
            stealth = Stealth()
            stealth.apply_stealth_sync(page)
            
            # Navigate to Claude
            page.goto("https://claude.ai", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            
            # Set task_id for extension to pass back
            page.evaluate(f"window.__bilalAgentTaskId = '{task_id}'")
            
            # Find the input box and type the refinement prompt
            # Claude.ai uses a contenteditable div or textarea
            input_selectors = [
                '[contenteditable="true"]',
                'div[data-placeholder]',
                'textarea',
                '.ProseMirror',
            ]
            
            input_found = False
            for selector in input_selectors:
                try:
                    el = page.wait_for_selector(selector, timeout=5000)
                    if el:
                        el.click()
                        page.wait_for_timeout(500)
                        
                        # Type the refinement prompt (chunk by line to avoid issues)
                        for line in refinement_prompt.split("\n"):
                            page.keyboard.type(line, delay=5)
                            page.keyboard.press("Shift+Enter")
                        
                        page.wait_for_timeout(500)
                        
                        # Press Enter to send
                        page.keyboard.press("Enter")
                        input_found = True
                        print(f"  [HYBRID] Prompt sent to Claude ({len(refinement_prompt)} chars)")
                        break
                except Exception:
                    continue
            
            if not input_found:
                print(f"  [HYBRID] Could not find Claude input box")
                browser.close()
                return draft
            
            # Step 3: Poll bridge for AI response (MutationObserver will capture it)
            print(f"  [HYBRID] Waiting for Claude response (timeout: 120s)...")
            
            polished = _poll_for_response(task_id, timeout=120)
            
            browser.close()
            
            if polished:
                return polished
            else:
                print(f"  [HYBRID] No response received, using original draft")
                return draft
    
    except ImportError:
        print(f"  [HYBRID] Playwright not available, using original draft")
        return draft
    except Exception as e:
        print(f"  [HYBRID] Error: {e}")
        return draft


def _poll_for_response(task_id: str, timeout: int = 120) -> str:
    """
    Poll the bridge for an AI response with the given task_id.
    
    The MutationObserver in content_script.js captures Claude's response
    and sends it to /extension/ai_response, which updates the pending_task.
    """
    start = time.time()
    poll_interval = 3  # seconds
    
    while (time.time() - start) < timeout:
        try:
            # Check the pending_tasks table for our task
            conn = sqlite3.connect(DB_PATH)
            row = conn.execute(
                "SELECT status, result FROM pending_tasks WHERE task_id = ?",
                (task_id,)
            ).fetchone()
            conn.close()
            
            if row and row[0] == "ai_response" and row[1]:
                elapsed = time.time() - start
                print(f"  [HYBRID] Response received ({elapsed:.1f}s, {len(row[1])} chars)")
                return row[1]
            
        except Exception:
            pass
        
        time.sleep(poll_interval)
    
    print(f"  [HYBRID] Timed out after {timeout}s")
    return ""


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="BilalAgent Post Scheduler")
    parser.add_argument("--mode", default="local", choices=["local", "hybrid", "web_copilot"],
                        help="Generation mode (default: local)")
    parser.add_argument("--count", type=int, default=3, help="Number of posts (default: 3)")
    args = parser.parse_args()
    
    posts = generate_weekly_posts(mode=args.mode)
    
    if posts:
        print(f"\n{'─' * 60}")
        print(f"Generated {len(posts)} posts:")
        print(f"{'─' * 60}")
        
        for i, p in enumerate(posts, 1):
            print(f"\n📝 Post {i}: [{p['type']}] {p['project']}")
            print(f"   Words: {p['words']} | Mode: {p['mode']} | Status: {p['status']}")
            print(f"   Saved: {p['path']}")
            print(f"   Preview: {p['final'][:150]}...")
    else:
        print("\nNo posts generated.")
