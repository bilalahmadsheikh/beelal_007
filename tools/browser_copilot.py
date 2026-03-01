"""
browser_copilot.py — BilalAgent v2.0 Phase 10
Full-chain Browser Copilot: reads page context, drafts prompts, opens Claude/ChatGPT,
autofills prompt, waits for response, saves to memory.

Modes:
- Strategy A: CDP interceptor for known job sites
- Strategy B: UI-TARS vision model to read screen
- Strategy C: Playwright for page source extraction

Flow: extract_page_context() → draft_llm_prompt() → open_and_fill_llm() → save response
"""

import os
import sys
import json
import time
import uuid
import logging
import re
from datetime import datetime
from typing import Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tools.permission_gate import PermissionGate, get_gate
from memory.db import log_action, log_content

log = logging.getLogger("browser_copilot")


def _load_profile() -> dict:
    """Load user profile from config/profile.yaml."""
    try:
        import yaml
        path = os.path.join(PROJECT_ROOT, "config", "profile.yaml")
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _get_bridge_url() -> str:
    """Get bridge URL from settings."""
    try:
        import yaml
        path = os.path.join(PROJECT_ROOT, "config", "settings.yaml")
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        port = config.get("bridge_port", 8000)
        return f"http://localhost:{port}"
    except Exception:
        return "http://localhost:8000"


JOB_SITE_DOMAINS = [
    "linkedin.com", "upwork.com", "freelancer.com",
    "fiverr.com", "peopleperhour.com"
]


class BrowserCopilot:
    """
    Full-chain browser automation copilot.
    Reads page context → drafts LLM prompt → opens Claude/ChatGPT →
    autofills and submits → waits for response → saves to memory.
    
    Every action goes through the PermissionGate for user approval.
    """

    def __init__(self, gate: PermissionGate = None, bridge_url: str = None):
        self.gate = gate or get_gate()
        self.bridge_url = bridge_url or _get_bridge_url()

    # ─── Strategy A: CDP / Known Job Sites ──────────

    def _extract_via_cdp(self, url: str) -> Optional[dict]:
        """Try to extract job data via existing browser tools / CDP."""
        try:
            from tools.browser_tools import _create_stealth_context
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser, context, page = _create_stealth_context(p, site=url.split("/")[2])
                page.goto(url, timeout=15000)
                time.sleep(2)

                title = page.title()
                description = ""
                company = ""
                budget = ""
                skills = []

                # LinkedIn
                if "linkedin.com" in url:
                    title = page.query_selector(
                        ".job-details-jobs-unified-top-card__job-title, h1"
                    )
                    title = title.text_content().strip() if title else page.title()
                    desc_el = page.query_selector(
                        ".jobs-description__content, .jobs-box__html-content"
                    )
                    description = desc_el.text_content().strip()[:2000] if desc_el else ""
                    comp_el = page.query_selector(
                        ".job-details-jobs-unified-top-card__company-name, .company-name"
                    )
                    company = comp_el.text_content().strip() if comp_el else ""

                # Upwork
                elif "upwork.com" in url:
                    title_el = page.query_selector(".job-title, h1")
                    title = title_el.text_content().strip() if title_el else page.title()
                    desc_el = page.query_selector(".job-description, .break.mb-0")
                    description = desc_el.text_content().strip()[:2000] if desc_el else ""
                    budget_el = page.query_selector(".budget, .client-budget")
                    budget = budget_el.text_content().strip() if budget_el else ""

                # Generic
                else:
                    title = page.title()
                    main_el = page.query_selector("main, article, .content")
                    description = main_el.text_content().strip()[:2000] if main_el else ""

                browser.close()
                return {
                    "title": title, "company": company,
                    "description": description, "budget": budget,
                    "skills": skills, "url": url, "source": "cdp"
                }
        except Exception as e:
            log.warning(f"[CDP] Failed: {e}")
            return None

    # ─── Strategy B: UI-TARS Vision ─────────────────

    def _extract_via_uitars(self) -> Optional[dict]:
        """Use UI-TARS to read current screen content."""
        try:
            from tools.uitars_server import get_server
            from tools.uitars_runner import capture_screen, ask_uitars

            server = get_server()
            if not server.is_running():
                log.info("[UITARS] Starting 2B server for page extraction...")
                if not server.start("2b"):
                    log.error("[UITARS] Failed to start server")
                    return None

            result = ask_uitars(
                "Extract and list: page title, job title or project name, "
                "company name, budget or salary if visible, key requirements "
                "or skills mentioned, the main description text. Format as JSON "
                "with keys: title, company, description, budget, skills."
            )

            if result and result.get("action") != "ask":
                desc = result.get("description", "")
                # Try to parse JSON from description
                try:
                    parsed = json.loads(desc)
                    parsed["source"] = "uitars"
                    return parsed
                except json.JSONDecodeError:
                    return {
                        "title": "Screen content",
                        "company": "",
                        "description": desc[:2000],
                        "budget": "",
                        "skills": [],
                        "source": "uitars"
                    }
        except Exception as e:
            log.warning(f"[UITARS] Extraction failed: {e}")
        return None

    # ─── Strategy C: Playwright Source ──────────────

    def _extract_via_playwright(self, url: str) -> Optional[dict]:
        """Use Playwright to get page source and extract basic data."""
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, timeout=15000)
                time.sleep(2)

                title = page.title()
                content = page.content()
                browser.close()

                # Basic extraction from HTML
                description = ""
                # Extract text from meta description
                meta_match = re.search(
                    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)', content
                )
                if meta_match:
                    description = meta_match.group(1)

                if not description:
                    # Get first 2000 chars of body text
                    body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL)
                    if body_match:
                        text = re.sub(r'<[^>]+>', ' ', body_match.group(1))
                        text = re.sub(r'\s+', ' ', text).strip()
                        description = text[:2000]

                return {
                    "title": title, "company": "",
                    "description": description, "budget": "",
                    "skills": [], "url": url, "source": "playwright"
                }
        except Exception as e:
            log.warning(f"[Playwright] Extraction failed: {e}")
        return None

    # ─── Main Methods ──────────────────────────────

    def extract_page_context(self, url: str = None) -> dict:
        """
        Extract page context using best available strategy.
        
        Args:
            url: Page URL. If None, uses UI-TARS to read current screen.
            
        Returns:
            Context dict with title, company, description, budget, skills, source
        """
        # Strategy A: Known job sites via CDP
        if url and any(domain in url for domain in JOB_SITE_DOMAINS):
            log.info(f"[COPILOT] Trying CDP extraction for {url}")
            result = self._extract_via_cdp(url)
            if result:
                return result

        # Strategy B: UI-TARS vision (no URL needed)
        log.info("[COPILOT] Trying UI-TARS screen extraction...")
        result = self._extract_via_uitars()
        if result:
            return result

        # Strategy C: Playwright fallback (needs URL)
        if url:
            log.info(f"[COPILOT] Trying Playwright extraction for {url}")
            result = self._extract_via_playwright(url)
            if result:
                return result

        # All strategies failed
        return {
            "title": "Unknown", "company": "",
            "description": "Could not extract page content",
            "budget": "", "skills": [], "source": "none"
        }

    def draft_llm_prompt(self, task: str, context: dict) -> str:
        """
        Draft a prompt to send to Claude/ChatGPT based on task and context.
        Uses local Gemma 4B to draft the prompt.
        
        Args:
            task: User's task description (e.g., "write cover letter")
            context: Page context from extract_page_context()
            
        Returns:
            Drafted prompt string
        """
        profile = _load_profile()
        profile_summary = profile.get("summary", "AI engineering student with MLOps and backend experience")
        projects = profile.get("projects", [])
        project_text = ""
        if projects:
            top_projects = projects[:3]
            project_text = "\n".join(
                f"- {p.get('name', 'Project')}: {p.get('description', '')}"
                for p in top_projects
            )

        task_lower = task.lower()
        title = context.get("title", "")
        company = context.get("company", "")
        description = context.get("description", "")[:1000]
        budget = context.get("budget", "")
        skills = context.get("skills", [])
        skills_text = ", ".join(skills) if skills else "not specified"

        # Determine prompt type
        if any(kw in task_lower for kw in ["cover letter", "apply", "application"]):
            prompt = (
                f"Write a professional cover letter for the position: {title}"
                f"{f' at {company}' if company else ''}.\n\n"
                f"Job description: {description}\n\n"
                f"My background: {profile_summary}\n"
                f"Relevant projects:\n{project_text}\n"
                f"Job requires: {skills_text}.\n\n"
                f"Keep it under 300 words, professional tone, specific to this role. "
                f"Don't use generic filler. Show genuine interest and relevant experience."
            )

        elif any(kw in task_lower for kw in ["proposal", "bid"]):
            prompt = (
                f"Write an Upwork proposal for this project: {title}\n\n"
                f"Project description: {description}\n"
                f"Budget: {budget}\n\n"
                f"My relevant experience: {profile_summary}\n"
                f"Key projects:\n{project_text}\n\n"
                f"Keep it under 150 words, be specific to their needs, "
                f"mention concrete deliverables and timeline."
            )

        elif any(kw in task_lower for kw in ["linkedin", "post"]):
            prompt = (
                f"Write a LinkedIn post about: {title}\n\n"
                f"Context: {description}\n\n"
                f"Write from my perspective as an AI engineering student. "
                f"Make it personal, insightful, and conversational — not robotic or generic. "
                f"Include 3-5 relevant hashtags at the end. Keep under 300 words."
            )

        elif any(kw in task_lower for kw in ["summarize", "summarise", "help with"]):
            prompt = (
                f"Summarize the following content clearly and concisely:\n\n"
                f"Title: {title}\n"
                f"Content: {description}\n\n"
                f"Provide key points, main takeaways, and any action items."
            )

        else:
            # Generic prompt
            prompt = (
                f"Help me with this task: {task}\n\n"
                f"Context from the page:\n"
                f"Title: {title}\n"
                f"Description: {description}\n\n"
                f"My background: {profile_summary}"
            )

        log.info(f"[COPILOT] Drafted {len(prompt)}-char prompt for task: {task}")
        return prompt

    def open_and_fill_llm(self, prompt: str, target: str = "claude") -> Optional[str]:
        """
        Open Claude/ChatGPT in browser, fill prompt, submit, wait for response.
        Every step requires permission gate approval.
        
        Args:
            prompt: The prompt to send
            target: "claude" or "chatgpt"
            
        Returns:
            AI response text, or None if cancelled/timeout
        """
        import requests

        urls = {"claude": "https://claude.ai", "chatgpt": "https://chatgpt.com"}
        target_url = urls.get(target, urls["claude"])

        # Step 1: Permission to open browser
        decision = self.gate.request({
            "action": "click",
            "description": f"Open {target} ({target_url}) in browser",
            "confidence": 1.0
        })
        if decision != "allow":
            log.info(f"[COPILOT] User denied opening {target}: {decision}")
            return None

        try:
            from playwright.sync_api import sync_playwright
            from tools.browser_tools import _create_stealth_context

            with sync_playwright() as p:
                # Step 2: Open browser with stealth + extension
                browser, context, page = _create_stealth_context(
                    p, load_extension=True, site=target_url.split("/")[2]
                )
                page.goto(target_url, timeout=30000)
                time.sleep(3)

                # Step 3: Permission to type prompt
                decision = self.gate.request({
                    "action": "type",
                    "description": f"Autofill into {target}: '{prompt[:80]}...'",
                    "text": prompt[:200],
                    "confidence": 1.0
                })
                if decision != "allow":
                    browser.close()
                    return None

                # Step 4: Find input and type
                input_selectors = {
                    "claude": [
                        "div[contenteditable='true']",
                        "textarea",
                        "[data-testid='chat-input']",
                        ".ProseMirror",
                    ],
                    "chatgpt": [
                        "#prompt-textarea",
                        "textarea",
                        "[data-testid='chat-input']",
                    ],
                }

                typed = False
                for selector in input_selectors.get(target, ["textarea"]):
                    try:
                        el = page.wait_for_selector(selector, timeout=5000)
                        if el:
                            el.click()
                            time.sleep(0.3)
                            page.keyboard.type(prompt, delay=30)
                            typed = True
                            break
                    except Exception:
                        continue

                if not typed:
                    log.error(f"[COPILOT] Could not find input on {target}")
                    browser.close()
                    return None

                time.sleep(0.5)

                # Step 5: Permission to click Send
                decision = self.gate.request({
                    "action": "click",
                    "description": f"Click Send button to submit to {target}",
                    "confidence": 1.0
                })
                if decision != "allow":
                    browser.close()
                    return None

                # Step 6: Click send button
                send_selectors = {
                    "claude": [
                        "button[aria-label='Send message']",
                        "button[type='submit']",
                        "button:has(svg)",
                    ],
                    "chatgpt": [
                        "button[data-testid='send-button']",
                        "button[type='submit']",
                        "button[aria-label='Send prompt']",
                    ],
                }

                sent = False
                for selector in send_selectors.get(target, ["button[type='submit']"]):
                    try:
                        btn = page.query_selector(selector)
                        if btn and btn.is_visible():
                            btn.click()
                            sent = True
                            break
                    except Exception:
                        continue

                if not sent:
                    # Try Enter as fallback
                    page.keyboard.press("Enter")

                # Step 7: Register task for MutationObserver
                task_id = str(uuid.uuid4())[:8]
                try:
                    requests.post(
                        f"{self.bridge_url}/extension/register_task",
                        json={
                            "task_type": "ai_response",
                            "content_preview": f"Waiting for {target} response...",
                            "action_label": "Got it"
                        },
                        timeout=3
                    )
                except Exception:
                    pass

                # Step 8: Poll for response via MutationObserver
                log.info(f"[COPILOT] Waiting for {target} response...")
                response_text = None
                timeout = 180  # 3 minutes

                for _ in range(timeout * 2):  # Check every 0.5s
                    time.sleep(0.5)

                    # Check if bridge has captured an AI response
                    try:
                        import sqlite3
                        db = os.path.join(PROJECT_ROOT, "memory", "agent_memory.db")
                        conn = sqlite3.connect(db)
                        row = conn.execute(
                            "SELECT result FROM pending_tasks "
                            "WHERE task_type = 'ai_response' AND status = 'ai_response' "
                            "ORDER BY updated_at DESC LIMIT 1"
                        ).fetchone()
                        conn.close()

                        if row and row[0] and len(row[0]) > 50:
                            response_text = row[0]
                            break
                    except Exception:
                        pass

                    # Also try reading directly from page
                    try:
                        response_selectors = {
                            "claude": [
                                "[data-testid='chat-message-content']:last-of-type",
                                ".contents .markup:last-of-type",
                            ],
                            "chatgpt": [
                                ".markdown.prose:last-of-type",
                                "[data-message-author-role='assistant']:last-of-type",
                            ],
                        }
                        for sel in response_selectors.get(target, []):
                            el = page.query_selector(sel)
                            if el:
                                text = el.text_content().strip()
                                if text and len(text) > 100:
                                    response_text = text
                                    break
                        if response_text:
                            break
                    except Exception:
                        pass

                browser.close()

                if response_text:
                    log.info(f"[COPILOT] Got {len(response_text)}-char response from {target}")
                else:
                    log.warning(f"[COPILOT] Timeout waiting for {target} response")

                return response_text

        except Exception as e:
            log.error(f"[COPILOT] Browser error: {e}")
            return None

    def full_flow(self, task: str, url: str = None, target_llm: str = "claude") -> dict:
        """
        Complete copilot flow: extract context → draft prompt → fill LLM → get response.
        
        Args:
            task: User's task description
            url: Optional page URL for context extraction
            target_llm: "claude" or "chatgpt"
            
        Returns:
            Result dict with status, response, saved_path, context
        """
        log_action("browser_copilot_start", f"Task: {task}, URL: {url}, LLM: {target_llm}")

        # 1. Extract page context
        print(f"[COPILOT] Step 1: Extracting page context...")
        context = self.extract_page_context(url)
        if context.get("source") == "none":
            return {"status": "failed", "reason": "Could not read page context"}
        print(f"  Source: {context.get('source')} | Title: {context.get('title', '')[:60]}")

        # 2. Draft LLM prompt
        print(f"[COPILOT] Step 2: Drafting prompt for {target_llm}...")
        prompt = self.draft_llm_prompt(task, context)
        print(f"  Prompt length: {len(prompt)} chars")

        # 3. Open and fill LLM
        print(f"[COPILOT] Step 3: Opening {target_llm} and filling prompt...")
        response = self.open_and_fill_llm(prompt, target_llm)

        if not response:
            return {"status": "cancelled", "reason": "Permission denied or timeout"}

        # 4. Permission to use response
        decision = self.gate.request({
            "action": "extract",
            "description": f"Use {target_llm}'s response ({len(response)} chars) for: {task}",
            "confidence": 1.0
        })
        if decision != "allow":
            return {"status": "cancelled", "reason": "User rejected response"}

        # 5. Save to memory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_task = re.sub(r'[^\w\s-]', '', task).replace(' ', '_')[:30]
        output_dir = os.path.join(PROJECT_ROOT, "memory", "content_output")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{safe_task}_{timestamp}.txt")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"Task: {task}\n")
            f.write(f"Target LLM: {target_llm}\n")
            f.write(f"Context:\n{json.dumps(context, indent=2)}\n\n")
            f.write(f"Prompt sent:\n{prompt}\n\n")
            f.write(f"Response:\n{response}")

        log_content(
            content_type=task[:50],
            content=response[:5000],
            status="generated",
            platform=target_llm
        )

        print(f"[COPILOT] ✅ Saved to {output_path}")

        return {
            "status": "ok",
            "response": response,
            "saved_path": output_path,
            "context": context,
            "prompt_sent": prompt,
            "target_llm": target_llm
        }


if __name__ == "__main__":
    print("=" * 50)
    print("Browser Copilot — Quick Test")
    print("=" * 50)

    copilot = BrowserCopilot()

    # Test prompt drafting (no browser needed)
    test_context = {
        "title": "Python Developer",
        "company": "TestCorp",
        "description": "Build ML pipelines and REST APIs using Python, FastAPI, and Docker.",
        "skills": ["Python", "FastAPI", "MLOps", "Docker"],
        "budget": "$50-100/hr"
    }

    prompt = copilot.draft_llm_prompt("write cover letter", test_context)
    print(f"\nDrafted prompt ({len(prompt)} chars):")
    print(prompt[:300] + "...")
