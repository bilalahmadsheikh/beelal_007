/**
 * background.js — BilalAgent v3.0 Chrome Extension Service Worker
 * Handles: cookie sync, message relay, task polling, LinkedIn actions,
 * agent-driven LinkedIn posting, prompt forwarding, tab management
 *
 * IMPORTANT: ALL bridge (localhost:8000) fetches happen here.
 * Content scripts cannot fetch localhost directly because LinkedIn's
 * Content-Security-Policy blocks non-LinkedIn origins.
 * Pattern: background polls bridge → sendMessage to content script → DOM work
 */

const BRIDGE_URL = 'http://localhost:8000';
const SUPPORTED_DOMAINS = ['linkedin.com', 'upwork.com', 'fiverr.com', 'freelancer.com', 'peopleperhour.com'];
const AI_DOMAINS = ['claude.ai', 'chatgpt.com'];

// ─── Cookie Sync ───────────────────────────────────

async function syncCookies(domain) {
    try {
        const cookies = await chrome.cookies.getAll({ domain: `.${domain}` });
        if (cookies.length === 0) return;

        const response = await fetch(`${BRIDGE_URL}/extension/cookies`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ site: domain, cookies: cookies })
        });

        if (response.ok) {
            console.log(`[BilalAgent] Synced ${cookies.length} cookies for ${domain}`);
        }
    } catch (e) {
        console.log(`[BilalAgent] Bridge not available for cookie sync`);
    }
}

chrome.runtime.onInstalled.addListener(() => {
    console.log('[BilalAgent] Extension installed — syncing cookies...');
    SUPPORTED_DOMAINS.forEach(domain => syncCookies(domain));
});

chrome.cookies.onChanged.addListener((changeInfo) => {
    const domain = changeInfo.cookie.domain.replace(/^\./, '');
    if (SUPPORTED_DOMAINS.some(d => domain.includes(d))) {
        syncCookies(domain);
    }
});


// ─── Message Relay (from content scripts) ───────────

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {

    if (message.type === 'context_snap') {
        fetch(`${BRIDGE_URL}/extension/context_snap`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(message.data)
        })
            .then(r => r.json())
            .then(data => sendResponse({ success: true, task_id: data.task_id }))
            .catch(e => sendResponse({ success: false, error: e.message }));
        return true;
    }

    if (message.type === 'approval_action') {
        fetch(`${BRIDGE_URL}/extension/approval`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(message.data)
        })
            .then(r => r.json())
            .then(data => sendResponse({ success: true }))
            .catch(e => sendResponse({ success: false, error: e.message }));
        return true;
    }

    if (message.type === 'ai_response') {
        fetch(`${BRIDGE_URL}/extension/ai_response`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(message.data)
        })
            .then(r => r.json())
            .then(data => sendResponse({ success: true }))
            .catch(e => sendResponse({ success: false, error: e.message }));
        return true;
    }

    if (message.type === 'get_status') {
        fetch(`${BRIDGE_URL}/extension/status`)
            .then(r => r.json())
            .then(data => sendResponse({ success: true, ...data }))
            .catch(() => sendResponse({ success: false, status: 'Bridge offline' }));
        return true;
    }

    // ── LinkedIn: content script polls us for the next pending action ──
    // Content script runs setInterval in the page process (always alive).
    // Each call wakes this SW; we fetch bridge and return the action.
    if (message.type === 'POLL_LINKEDIN_ACTION') {
        fetch(`${BRIDGE_URL}/linkedin/action/pending`, { signal: AbortSignal.timeout(2000) })
            .then(r => r.json())
            .then(action => {
                if (action && action.action_id) {
                    sendResponse({ action });
                } else {
                    sendResponse({ action: null });
                }
            })
            .catch(() => sendResponse({ action: null }));
        return true; // async response
    }

    // ── LinkedIn Actor result relay ──────────────────
    // Content script calls chrome.runtime.sendMessage({type:'LINKEDIN_RESULT',...})
    // We relay it to the bridge (content script can't POST to localhost directly).
    if (message.type === 'LINKEDIN_RESULT') {
        const { action_id, status, result_message } = message;
        fetch(`${BRIDGE_URL}/linkedin/action/result`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action_id, status, message: result_message })
        })
            .then(() => sendResponse({ ok: true }))
            .catch(e => sendResponse({ ok: false, error: e.message }));
        return true;
    }

    // ── Page state relay ────────────────────────────
    if (message.type === 'PAGE_STATE') {
        fetch(`${BRIDGE_URL}/extension/page_state`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(message.data)
        }).catch(() => { });
        return false;
    }

    // ── Agent-driven LinkedIn Post (from popup) ─────
    if (message.type === 'AGENT_POST_LINKEDIN') {
        agentPostToLinkedIn(message.content, message.task_id, message.edit_mode)
            .then(result => sendResponse({ success: true, ...result }))
            .catch(e => sendResponse({ success: false, error: e.message }));
        return true;
    }

    // ── Agent prompt forwarding (popup → bridge) ────
    if (message.type === 'AGENT_SEND_PROMPT') {
        fetch(`${BRIDGE_URL}/agent/prompt`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: message.prompt, source: 'extension' })
        })
            .then(r => r.json())
            .then(data => sendResponse({ success: true, ...data }))
            .catch(e => sendResponse({ success: false, error: e.message }));
        return true;
    }

    // ── Agent-requested tab open ─────────────────────
    if (message.type === 'AGENT_OPEN_TAB') {
        chrome.tabs.create({ url: message.url, active: true }, (tab) => {
            sendResponse({ success: true, tabId: tab.id });
        });
        return true;
    }
});


// ─── Task Polling (legacy overlay) ─────────────────

let pollingInterval = null;

function startPolling(tabId) {
    if (pollingInterval) return;
    pollingInterval = setInterval(async () => {
        try {
            const response = await fetch(`${BRIDGE_URL}/extension/get_task`);
            const task = await response.json();
            if (task && task.task_id) {
                chrome.tabs.sendMessage(tabId, { type: 'show_overlay', task });
            }
        } catch (e) { }
    }, 2000);
}

function stopPolling() {
    if (pollingInterval) { clearInterval(pollingInterval); pollingInterval = null; }
}

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.status === 'complete' && tab.url) {
        const url = new URL(tab.url);
        const isSupported = [...SUPPORTED_DOMAINS, ...AI_DOMAINS].some(d => url.hostname.includes(d));
        if (isSupported) startPolling(tabId);
        else stopPolling();
    }
});

chrome.tabs.onRemoved.addListener(() => stopPolling());


// ─── LinkedIn Action On-Demand (content-script-driven) ────────────────
//
// MV3 service workers sleep after ~30s idle — setInterval is unreliable.
// FIX: Content script (page process, always alive) polls background every
// second via chrome.runtime.sendMessage({type:'POLL_LINKEDIN_ACTION'}).
// Each message wakes the SW which fetches the bridge and returns the action.
//
// Flow:
//   1. Content script sends POLL_LINKEDIN_ACTION every 1s (on LinkedIn pages)
//   2. SW wakes, fetches /linkedin/action/pending, returns action in response
//   3. Content script executes DOM work
//   4. Content script sends LINKEDIN_RESULT → SW relays to bridge
// ──────────────────────────────────────────────────────────────────────


// ─── Agent-Driven LinkedIn Posting ──────────────────────────────────
// Uses chrome.scripting.executeScript to directly manipulate the
// LinkedIn tab DOM — no bridge round-trip needed.  Much more reliable.
// ────────────────────────────────────────────────────────────────────

async function agentPostToLinkedIn(content, taskId, editMode = false) {
    // 1. Find or open LinkedIn feed tab
    const linkedInTab = await findOrOpenLinkedInTab();
    if (!linkedInTab) throw new Error('Could not open LinkedIn tab');

    // 2. Wait for tab to be fully loaded
    await waitForTabLoad(linkedInTab.id);
    await sleep(4000); // extra time for LinkedIn SPA + content script init

    // 3. Send message to content script with retries
    let lastError = '';
    for (let attempt = 0; attempt < 5; attempt++) {
        try {
            const result = await new Promise((resolve, reject) => {
                chrome.tabs.sendMessage(linkedInTab.id, {
                    type: 'POST_LINKEDIN_CONTENT',
                    content: content,
                    task_id: taskId,
                }, (response) => {
                    if (chrome.runtime.lastError) {
                        reject(new Error(chrome.runtime.lastError.message));
                        return;
                    }
                    if (response?.error) {
                        reject(new Error(response.error));
                    } else {
                        resolve({ success: true, message: response?.message || 'Content posted' });
                    }
                });
            });
            return result; // success
        } catch (err) {
            lastError = err.message;
            console.log(`[BilalAgent] Attempt ${attempt + 1} failed:`, lastError);
            if (lastError.includes('not establish') || lastError.includes('not exist') || lastError.includes('not ready')) {
                console.log('[BilalAgent] Force injecting content script...');
                try {
                    await chrome.scripting.executeScript({
                        target: { tabId: linkedInTab.id },
                        files: ['content_script.js']
                    });
                } catch (injErr) {
                    console.error('[BilalAgent] Injection failed:', injErr);
                }
                await sleep(2000); // content script just loaded, wait and retry
                continue;
            }
            throw err; // real error, don't retry
        }
    }
    throw new Error('Content script not ready after 5 retries: ' + lastError);
}

// This function is serialized and injected into the LinkedIn tab.
// It runs in the page context — full DOM access.
function linkedInPostInjection(postContent, taskId) {
    return new Promise((resolve) => {
        // ─── Step 1: Click "Start a post" button ─────────
        console.log('[BilalAgent] Injection running on:', window.location.href);

        // ─── Step 1: Click "Start a post" ─────────
        // Strategy: Find the share box container at top of feed, then click inside it.
        // DO NOT scan all buttons broadly — that matches feed post icons.
        let startBtn = null;

        // A) Look for the share box container first
        const shareBoxContainer = document.querySelector(
            '.share-box-feed-entry__top-bar, ' +
            '.share-box-feed-entry__closed-share-box, ' +
            'div[class*="share-box-feed-entry"], ' +
            '.share-box'
        );
        if (shareBoxContainer) {
            // Click the trigger button/span INSIDE the share box
            startBtn = shareBoxContainer.querySelector(
                'button, span, [role="button"], [tabindex]'
            ) || shareBoxContainer;
            console.log('[BilalAgent] Found share box container:', shareBoxContainer.className);
        }

        // B) Direct selector for the trigger button
        if (!startBtn) {
            startBtn = document.querySelector('button.share-box-feed-entry__trigger');
        }

        // C) Look for element with EXACT text "Start a post" that is NOT inside a feed post
        if (!startBtn) {
            const allEls = document.querySelectorAll('button, span, div[role="button"], [tabindex="0"]');
            for (const el of allEls) {
                const text = (el.textContent || '').trim();
                // Must be short text (not a whole feed post) and contain "Start a post"
                if (text === 'Start a post' || (text.length < 30 && text.includes('Start a post'))) {
                    // Make sure it's not inside a feed-update (post card)
                    if (!el.closest('.feed-shared-update-v2, .occludable-update')) {
                        startBtn = el;
                        console.log('[BilalAgent] Found "Start a post" text element:', el.tagName);
                        break;
                    }
                }
            }
        }

        if (!startBtn) {
            const btns = Array.from(document.querySelectorAll('[class*="share-box"]')).map(
                b => b.tagName + '.' + (b.className || '').slice(0, 50));
            resolve({ error: 'Could not find Start a post. share-box elements: ' + btns.join('; ') + ' URL: ' + window.location.href });
            return;
        }

        startBtn.click();
        console.log('[BilalAgent] Clicked Start a Post element');

        // ─── Step 2: Wait for composer modal ─────────
        let attempts = 0;
        const waitForComposer = setInterval(() => {
            attempts++;

            // Try specific selectors first (note: [contenteditable] without ="true")
            let editor = document.querySelector(
                '.ql-editor[contenteditable], ' +
                'div[data-placeholder*="want to talk about"], ' +
                'div[role="textbox"][contenteditable], ' +
                '.ql-editor, ' +
                'div[aria-label*="Text editor"][contenteditable], ' +
                'div[aria-label*="text editor"][contenteditable]'
            );

            // Fallback: find ANY contenteditable inside a dialog/modal
            if (!editor) {
                const modal = document.querySelector('div[role="dialog"], .artdeco-modal, .share-box-modal, .share-creation-state');
                if (modal) {
                    editor = modal.querySelector('[contenteditable]');
                    if (editor) console.log('[BilalAgent] Found editor in modal:', editor.tagName, editor.className);
                }
            }

            // Ultimate fallback: ANY element with contenteditable on the page
            if (!editor) {
                const allEditable = document.querySelectorAll('[contenteditable]');
                console.log('[BilalAgent] All contenteditable elements:', allEditable.length,
                    Array.from(allEditable).map(e => e.tagName + '.' + (e.className || '').slice(0, 30)).join(', '));
                // Filter out tiny ones (nav elements etc), pick the largest
                let best = null;
                for (const el of allEditable) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 100 && rect.height > 50) {
                        best = el;
                    }
                }
                if (best) {
                    editor = best;
                    console.log('[BilalAgent] Using size-based fallback:', editor.tagName, editor.className);
                } else if (allEditable.length > 0) {
                    editor = allEditable[allEditable.length - 1];
                    console.log('[BilalAgent] Using last contenteditable:', editor.tagName, editor.className);
                }
            }

            if (editor) {
                clearInterval(waitForComposer);
                console.log('[BilalAgent] Composer found:', editor.className);

                // ─── Step 3: Activate editor with mouse events + click ────
                // LinkedIn requires a real click to activate the editor
                editor.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                editor.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                editor.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                editor.focus();

                // Small delay for editor activation
                setTimeout(() => {
                    editor.innerHTML = '';

                    // Type using paragraph elements for proper LinkedIn formatting
                    const lines = postContent.split('\n');
                    lines.forEach(line => {
                        const p = document.createElement('p');
                        p.textContent = line || '\u200B'; // zero-width space for empty lines
                        editor.appendChild(p);
                    });

                    // Dispatch input events so LinkedIn registers the change
                    editor.dispatchEvent(new Event('input', { bubbles: true }));
                    editor.dispatchEvent(new Event('change', { bubbles: true }));

                    // ─── Step 4: Show confirmation overlay ─
                    setTimeout(() => {
                        showPostOverlay(postContent, taskId, resolve);
                    }, 500);
                }, 300);  // end of setTimeout for editor activation
            }

            if (attempts > 75) { // ~15 seconds
                clearInterval(waitForComposer);
                resolve({ error: 'Composer did not open within 15 seconds' });
            }
        }, 200);

        function showPostOverlay(content, tId, done) {
            const existing = document.getElementById('bilal-agent-post-overlay');
            if (existing) existing.remove();

            const wordCount = content.split(/\s+/).filter(Boolean).length;
            const bar = document.createElement('div');
            bar.id = 'bilal-agent-post-overlay';
            bar.style.cssText = `
                position:fixed;bottom:0;left:0;right:0;z-index:2147483647;
                background:linear-gradient(to top, rgba(10,10,30,0.98), rgba(15,23,42,0.96));
                border-top:3px solid #4ECDC4;backdrop-filter:blur(20px);
                padding:16px 24px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                animation:bilalSlideUp 0.3s ease;
            `;
            bar.innerHTML = `
                <style>
                    @keyframes bilalSlideUp { from { transform:translateY(100%); } to { transform:translateY(0); } }
                    .ba-btn { border:none; padding:10px 22px; border-radius:8px; cursor:pointer; font-size:14px; font-weight:600; transition:all 0.2s; font-family:inherit; }
                    .ba-btn:hover { transform:translateY(-1px); filter:brightness(1.1); }
                </style>
                <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
                    <span style="background:linear-gradient(135deg,#2563eb,#7c3aed);color:#fff;padding:4px 12px;border-radius:12px;font-weight:700;font-size:10px;text-transform:uppercase;letter-spacing:0.5px">
                        ⚡ BilalAgent
                    </span>
                    <span style="background:#4ECDC4;color:#000;padding:3px 10px;border-radius:12px;font-weight:bold;font-size:11px">POST READY</span>
                    <span style="color:#94a3b8;font-size:12px">${wordCount} words typed</span>
                    <div style="margin-left:auto;display:flex;gap:10px">
                        <button id="ba-post-now" class="ba-btn" style="background:linear-gradient(135deg,#059669,#10b981);color:#fff;box-shadow:0 2px 10px rgba(16,185,129,0.3)">
                            ✓ Post Now
                        </button>
                        <button id="ba-edit-first" class="ba-btn" style="background:rgba(59,130,246,0.15);color:#60a5fa;border:1px solid rgba(59,130,246,0.3)">
                            ✏ Edit First
                        </button>
                        <button id="ba-cancel" class="ba-btn" style="background:rgba(239,68,68,0.15);color:#f87171;border:1px solid rgba(239,68,68,0.3)">
                            ✕ Cancel
                        </button>
                    </div>
                </div>
            `;
            document.body.appendChild(bar);

            document.getElementById('ba-post-now').onclick = () => {
                bar.remove();
                // Click the actual LinkedIn Post button
                const postBtns = document.querySelectorAll('button');
                let posted = false;
                for (const btn of postBtns) {
                    const label = btn.getAttribute('aria-label') || btn.textContent || '';
                    if (label.trim() === 'Post' || label.includes('Post') && btn.classList.contains('share-actions__primary-action')) {
                        btn.click();
                        posted = true;
                        break;
                    }
                }
                if (!posted) {
                    // Broader search
                    const shareBtn = document.querySelector(
                        'button.share-actions__primary-action, ' +
                        'button[data-control-name="share.post"]'
                    );
                    if (shareBtn) { shareBtn.click(); posted = true; }
                }

                if (posted) {
                    // Show success banner
                    const banner = document.createElement('div');
                    banner.style.cssText = 'position:fixed;top:20px;right:20px;z-index:2147483647;background:#10b981;color:#fff;padding:14px 24px;border-radius:12px;font-family:sans-serif;font-weight:600;font-size:14px;animation:bilalSlideUp 0.3s ease;box-shadow:0 4px 20px rgba(0,0,0,0.3)';
                    banner.textContent = '✅ Posted to LinkedIn!';
                    document.body.appendChild(banner);
                    setTimeout(() => banner.remove(), 4000);
                }
                done({ success: true, message: posted ? 'posted' : 'post_button_not_found' });
            };

            document.getElementById('ba-edit-first').onclick = () => {
                bar.remove();
                done({ success: true, message: 'user_editing' });
            };

            document.getElementById('ba-cancel').onclick = () => {
                bar.remove();
                // Close the LinkedIn composer
                const closeBtn = document.querySelector('button[aria-label="Dismiss"], button[aria-label="Close"]');
                if (closeBtn) closeBtn.click();
                done({ success: true, message: 'cancelled' });
            };
        }
    });
}

async function findOrOpenLinkedInTab() {
    return new Promise((resolve) => {
        chrome.tabs.query({}, (tabs) => {
            const existing = tabs.find(t => t.url && t.url.includes('linkedin.com'));
            if (existing) {
                // ALWAYS navigate to feed — Start a Post only exists there
                if (!existing.url.includes('/feed')) {
                    console.log('[BilalAgent] Navigating LinkedIn tab to /feed/');
                    chrome.tabs.update(existing.id, { active: true, url: 'https://www.linkedin.com/feed/' }, () => resolve(existing));
                } else {
                    chrome.tabs.update(existing.id, { active: true }, () => resolve(existing));
                }
                return;
            }
            chrome.tabs.create({ url: 'https://www.linkedin.com/feed/', active: true }, (tab) => resolve(tab));
        });
    });
}

function waitForTabLoad(tabId) {
    return new Promise((resolve) => {
        const listener = (id, changeInfo) => {
            if (id === tabId && changeInfo.status === 'complete') {
                chrome.tabs.onUpdated.removeListener(listener);
                resolve();
            }
        };
        chrome.tabs.onUpdated.addListener(listener);
        // Fallback timeout
        setTimeout(() => {
            chrome.tabs.onUpdated.removeListener(listener);
            resolve();
        }, 10000);
    });
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }


console.log('[BilalAgent] Background service worker started (v3.1)');

// ─── Side Panel: open persistent sidebar on icon click ───
chrome.sidePanel
    .setPanelBehavior({ openPanelOnActionClick: true })
    .catch((error) => console.error('[BilalAgent] sidePanel error:', error));
