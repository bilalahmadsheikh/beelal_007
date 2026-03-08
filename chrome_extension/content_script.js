/**
 * content_script.js — BilalAgent v3.0 Chrome Extension Content Script
 * Features:
 * 1. Context Snap — "Send to BilalAgent" button on job pages
 * 2. Approval Overlay — bottom-screen overlay with Approve/Cancel
 * 3. MutationObserver — watches Claude.ai / ChatGPT for AI responses
 * 4. Permission Overlay — permission gate UI
 * 5. LinkedIn Actor — executes LinkedIn actions
 */

(() => {
    'use strict';

    // Prevent double injection
    if (window.__bilalAgentInjected) return;
    window.__bilalAgentInjected = true;

    const hostname = window.location.hostname;

    // ─── Extension Context Guard ─────────────────────
    // When extension is reloaded, old content scripts lose their context.
    // All chrome.runtime calls must go through this wrapper to avoid
    // "Extension context invalidated" errors.
    let _contextAlive = true;
    const _intervalIds = [];  // track all setInterval IDs for cleanup

    function safeSendMessage(msg, callback) {
        if (!_contextAlive) return;
        try {
            chrome.runtime.sendMessage(msg, (response) => {
                if (chrome.runtime.lastError) {
                    // Context invalidated — kill all polling
                    if (chrome.runtime.lastError.message?.includes('context invalidated')) {
                        _contextAlive = false;
                        _intervalIds.forEach(id => clearInterval(id));
                        console.log('[BilalAgent] Extension reloaded — old content script stopping.');
                        return;
                    }
                    // Other errors (SW not ready) — just skip
                    return;
                }
                if (callback) callback(response);
            });
        } catch (e) {
            // chrome.runtime.sendMessage itself threw (context dead)
            _contextAlive = false;
            _intervalIds.forEach(id => clearInterval(id));
            console.log('[BilalAgent] Extension context lost — content script stopped.');
        }
    }

    function safeSetInterval(fn, ms) {
        const id = setInterval(() => {
            if (!_contextAlive) { clearInterval(id); return; }
            fn();
        }, ms);
        _intervalIds.push(id);
        return id;
    }

    // ─── Feature 1: Context Snap Button ──────────────

    const JOB_PAGE_PATTERNS = [
        { domain: 'linkedin.com', paths: ['/jobs/view/', '/jobs/search/', '/jobs/collections/'] },
        { domain: 'upwork.com', paths: ['/jobs/', '/freelance-jobs/'] },
        { domain: 'fiverr.com', paths: ['/categories/', '/search/gigs/'] },
        { domain: 'freelancer.com', paths: ['/projects/'] },
        { domain: 'peopleperhour.com', paths: ['/freelance-'] },
    ];

    function isJobPage() {
        const path = window.location.pathname;
        return JOB_PAGE_PATTERNS.some(p =>
            hostname.includes(p.domain) && p.paths.some(pp => path.includes(pp))
        );
    }

    function extractJobData() {
        const data = {
            url: window.location.href,
            title: '',
            description: '',
            budget: '',
            platform: hostname.replace('www.', '').split('.')[0],
        };

        // LinkedIn
        if (hostname.includes('linkedin.com')) {
            data.title = document.querySelector('.job-details-jobs-unified-top-card__job-title, .t-24.t-bold, h1')?.textContent?.trim() || document.title;
            data.description = document.querySelector('.jobs-description__content, .jobs-box__html-content')?.textContent?.trim()?.slice(0, 2000) || '';
            data.budget = document.querySelector('.salary-main-rail__data-badge, .compensation__salary')?.textContent?.trim() || '';
        }
        // Upwork
        else if (hostname.includes('upwork.com')) {
            data.title = document.querySelector('.job-title, h1')?.textContent?.trim() || document.title;
            data.description = document.querySelector('.job-description, .break.mb-0')?.textContent?.trim()?.slice(0, 2000) || '';
            data.budget = document.querySelector('.budget, .client-budget')?.textContent?.trim() || '';
        }
        // Fiverr
        else if (hostname.includes('fiverr.com')) {
            data.title = document.querySelector('.gig-title, h1')?.textContent?.trim() || document.title;
            data.description = document.querySelector('.gig-description, .description-content')?.textContent?.trim()?.slice(0, 2000) || '';
            data.budget = document.querySelector('.price-wrapper, .price')?.textContent?.trim() || '';
        }
        // Freelancer
        else if (hostname.includes('freelancer.com')) {
            data.title = document.querySelector('.PageProjectViewLogout-detail-title, h1')?.textContent?.trim() || document.title;
            data.description = document.querySelector('.PageProjectViewLogout-detail-description')?.textContent?.trim()?.slice(0, 2000) || '';
            data.budget = document.querySelector('.PageProjectViewLogout-detail-budget')?.textContent?.trim() || '';
        }
        // Fallback
        else {
            data.title = document.title;
            data.description = document.querySelector('main, article, .content')?.textContent?.trim()?.slice(0, 1000) || '';
        }

        return data;
    }

    function injectContextSnapButton() {
        if (!isJobPage() || document.getElementById('bilal-agent-snap-btn')) return;

        const btn = document.createElement('div');
        btn.id = 'bilal-agent-snap-btn';
        btn.innerHTML = `
      <div style="
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 99999;
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 12px 20px;
        background: linear-gradient(135deg, #2563eb, #7c3aed);
        color: white;
        border-radius: 50px;
        cursor: pointer;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        font-size: 14px;
        font-weight: 600;
        box-shadow: 0 4px 20px rgba(37, 99, 235, 0.4);
        transition: all 0.2s ease;
        user-select: none;
      " id="bilal-agent-snap-inner">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 2L2 7l10 5 10-5-10-5z"/>
          <path d="M2 17l10 5 10-5"/>
          <path d="M2 12l10 5 10-5"/>
        </svg>
        Send to BilalAgent
      </div>
    `;

        const inner = btn.querySelector('#bilal-agent-snap-inner');
        inner.addEventListener('mouseenter', () => {
            inner.style.transform = 'scale(1.05)';
            inner.style.boxShadow = '0 6px 25px rgba(37, 99, 235, 0.5)';
        });
        inner.addEventListener('mouseleave', () => {
            inner.style.transform = 'scale(1)';
            inner.style.boxShadow = '0 4px 20px rgba(37, 99, 235, 0.4)';
        });

        inner.addEventListener('click', async () => {
            inner.textContent = '⏳ Sending...';
            inner.style.opacity = '0.7';

            const jobData = extractJobData();

            safeSendMessage(
                { type: 'context_snap', data: jobData },
                (response) => {
                    if (response?.success) {
                        inner.innerHTML = '✅ Sent to Agent!';
                        inner.style.background = 'linear-gradient(135deg, #059669, #10b981)';
                        setTimeout(() => {
                            inner.innerHTML = `
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                  <path d="M2 17l10 5 10-5"/>
                  <path d="M2 12l10 5 10-5"/>
                </svg>
                Send to BilalAgent
              `;
                            inner.style.background = 'linear-gradient(135deg, #2563eb, #7c3aed)';
                            inner.style.opacity = '1';
                        }, 2000);
                    } else {
                        inner.innerHTML = '❌ Bridge offline';
                        inner.style.background = '#dc2626';
                        setTimeout(() => {
                            inner.innerHTML = 'Send to BilalAgent';
                            inner.style.background = 'linear-gradient(135deg, #2563eb, #7c3aed)';
                            inner.style.opacity = '1';
                        }, 2000);
                    }
                }
            );
        });

        document.body.appendChild(btn);
    }

    // ─── Feature 2: Approval Overlay ─────────────────

    function showOverlay(task) {
        // Remove existing overlay
        const existing = document.getElementById('bilal-agent-overlay');
        if (existing) existing.remove();

        const overlay = document.createElement('div');
        overlay.id = 'bilal-agent-overlay';
        overlay.innerHTML = `
      <div style="
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        z-index: 999999;
        background: linear-gradient(to top, rgba(15, 23, 42, 0.98), rgba(30, 41, 59, 0.95));
        backdrop-filter: blur(20px);
        border-top: 2px solid #3b82f6;
        padding: 20px 32px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        color: white;
        animation: slideUp 0.3s ease;
      ">
        <style>
          @keyframes slideUp { from { transform: translateY(100%); } to { transform: translateY(0); } }
        </style>
        
        <div style="display: flex; justify-content: space-between; align-items: flex-start; max-width: 1200px; margin: 0 auto;">
          <div style="flex: 1; margin-right: 24px;">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
              <span style="font-size: 12px; background: #3b82f6; padding: 2px 8px; border-radius: 4px; text-transform: uppercase; letter-spacing: 0.5px;">
                ${task.task_type.replace('_', ' ')}
              </span>
              <span style="font-size: 12px; color: #94a3b8;">Task: ${task.task_id}</span>
            </div>
            <p style="margin: 0; font-size: 14px; color: #e2e8f0; line-height: 1.5; max-height: 80px; overflow-y: auto;">
              ${(task.content_preview || '').slice(0, 300)}${(task.content_preview || '').length > 300 ? '...' : ''}
            </p>
          </div>
          
          <div style="display: flex; gap: 12px; align-items: center; flex-shrink: 0;">
            <button id="bilal-overlay-approve" style="
              padding: 10px 28px;
              background: linear-gradient(135deg, #059669, #10b981);
              color: white;
              border: none;
              border-radius: 8px;
              font-size: 14px;
              font-weight: 600;
              cursor: pointer;
              transition: all 0.2s;
            ">${task.action_label || 'Approve'}</button>
            
            <button id="bilal-overlay-cancel" style="
              padding: 10px 28px;
              background: transparent;
              color: #f87171;
              border: 1px solid #f87171;
              border-radius: 8px;
              font-size: 14px;
              font-weight: 600;
              cursor: pointer;
              transition: all 0.2s;
            ">Cancel</button>
          </div>
        </div>
      </div>
    `;

        document.body.appendChild(overlay);

        // Button handlers
        document.getElementById('bilal-overlay-approve').addEventListener('click', () => {
            safeSendMessage({
                type: 'approval_action',
                data: { task_id: task.task_id, action: 'approve' }
            });
            overlay.remove();
        });

        document.getElementById('bilal-overlay-cancel').addEventListener('click', () => {
            safeSendMessage({
                type: 'approval_action',
                data: { task_id: task.task_id, action: 'cancel' }
            });
            overlay.remove();
        });
    }

    // ─── Feature 3: MutationObserver for AI Sites ────

    function startAIObserver() {
        if (!hostname.includes('claude.ai') && !hostname.includes('chatgpt.com')) return;

        const source = hostname.includes('claude.ai') ? 'claude' : 'chatgpt';
        let lastResponseText = '';
        let debounceTimer = null;

        const observer = new MutationObserver(() => {
            if (debounceTimer) clearTimeout(debounceTimer);

            debounceTimer = setTimeout(() => {
                let responseText = '';

                if (source === 'claude') {
                    // Claude.ai response container
                    const responses = document.querySelectorAll('[data-testid="chat-message-content"], .contents .markup');
                    if (responses.length > 0) {
                        responseText = responses[responses.length - 1].textContent.trim();
                    }
                } else {
                    // ChatGPT response container
                    const responses = document.querySelectorAll('.markdown.prose, [data-message-author-role="assistant"]');
                    if (responses.length > 0) {
                        responseText = responses[responses.length - 1].textContent.trim();
                    }
                }

                // Only send if response changed and generation seems complete
                // (check if stop button is gone — indicates generation finished)
                const stopBtn = document.querySelector(
                    source === 'claude'
                        ? 'button[aria-label="Stop response"], .stop-button'
                        : 'button[data-testid="stop-button"], button[aria-label="Stop generating"]'
                );

                if (responseText && responseText !== lastResponseText && !stopBtn) {
                    lastResponseText = responseText;

                    // Use task_id set by Playwright (hybrid mode) if available
                    const taskId = window.__bilalAgentTaskId || '';

                    safeSendMessage({
                        type: 'ai_response',
                        data: {
                            source: source,
                            response_text: responseText.slice(0, 5000),
                            task_id: taskId
                        }
                    });

                    console.log(`[BilalAgent] AI response captured from ${source}: ${responseText.length} chars`);
                }
            }, 2000); // 2s debounce — wait for generation to finish
        });

        // Observe the main content area
        const target = document.querySelector('main, #__next, .app-container, body');
        if (target) {
            observer.observe(target, { childList: true, subtree: true, characterData: true });
            console.log(`[BilalAgent] MutationObserver started for ${source}`);
        }
    }

    // ─── Message Listener ───────────────────────────

    try {
        chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
            if (message.type === 'show_overlay' && message.task) {
                showOverlay(message.task);
                sendResponse({ shown: true });
            }
            if (message.type === 'POST_LINKEDIN_CONTENT' && hostname.includes('linkedin.com')) {
                console.log('[BilalAgent] POST_LINKEDIN_CONTENT received');
                handleLinkedInPost(message.content, message.task_id)
                    .then(result => sendResponse(result))
                    .catch(err => sendResponse({ error: err.message }));
                return true;
            }
        });
    } catch (e) { _contextAlive = false; }

    // ─── LinkedIn Post Handler ─────────────────────────
    async function handleLinkedInPost(postContent, taskId) {
        // Step 1: Click "Start a post"
        const shareBox = document.querySelector(
            '.share-box-feed-entry__top-bar, .share-box-feed-entry__closed-share-box, div[class*="share-box-feed-entry"], .share-box'
        );
        let clickTarget = shareBox ? (shareBox.querySelector('button, span, [role="button"]') || shareBox) : null;
        if (!clickTarget) {
            for (const el of document.querySelectorAll('button, span, div[role="button"], [tabindex="0"]')) {
                const t = (el.textContent || '').trim();
                if ((t === 'Start a post' || (t.length < 30 && t.includes('Start a post'))) && !el.closest('.feed-shared-update-v2, .occludable-update')) {
                    clickTarget = el; break;
                }
            }
        }
        if (!clickTarget) return { error: 'Start a post not found on: ' + location.href };
        clickTarget.click();
        console.log('[BilalAgent] Clicked Start a Post');

        // Step 2: Wait for Quill editor or contenteditable to appear
        const editor = await _waitForEditor(12000);
        if (!editor) return { error: 'LinkedIn editor never appeared after clicking Start a Post' };

        console.log('[BilalAgent] Editor found:', editor.tagName, editor.className?.slice(0, 50), 'ce=' + editor.getAttribute('contenteditable'));

        // Step 3: Click on editor to focus/activate it
        editor.click();
        editor.focus();
        await new Promise(r => setTimeout(r, 500));

        // Step 4: Type the content
        editor.innerHTML = '';
        postContent.split('\n').forEach(line => {
            const p = document.createElement('p');
            p.textContent = line || '\u200B';
            editor.appendChild(p);
        });
        editor.dispatchEvent(new Event('input', { bubbles: true }));
        editor.dispatchEvent(new Event('change', { bubbles: true }));

        await new Promise(r => setTimeout(r, 500));
        _showPostBar(postContent, taskId);
        return { success: true, message: 'content_typed' };
    }

    function _waitForEditor(timeout) {
        return new Promise(resolve => {
            const start = Date.now();
            const iv = setInterval(() => {
                let editor = null;

                // 1. Find all potential modals/dialogs (Start a Post ALWAYS opens a modal)
                const modals = Array.from(document.querySelectorAll('div[role="dialog"], .share-creation-state, .share-box-modal, .artdeco-modal'));
                // Search from last to first (most recently added / top-most modal)
                for (let i = modals.length - 1; i >= 0; i--) {
                    editor = _deepFindEditable(modals[i]);
                    if (editor) break;
                }

                // 2. If no modal found, try document.activeElement
                if (!editor) {
                    if (document.activeElement &&
                        document.activeElement.hasAttribute('contenteditable') &&
                        document.activeElement.getAttribute('contenteditable') !== 'false') {
                        editor = document.activeElement;
                    }
                }

                // 3. Fallback: try finding ANY ql-editor on the page that is visible
                if (!editor) {
                    const qls = document.querySelectorAll('.ql-editor[contenteditable], div[role="textbox"][contenteditable="true"]');
                    for (const ql of qls) {
                        const r = ql.getBoundingClientRect();
                        if (r.width > 50 && r.height > 20) { editor = ql; break; }
                    }
                }

                if (editor) {
                    clearInterval(iv);
                    resolve(editor);
                } else if (Date.now() - start > timeout) {
                    clearInterval(iv);
                    resolve(null);
                }
            }, 250);
        });
    }

    // Recursively pierces all Shadow DOMs to find a visible editor
    function _deepFindEditable(root) {
        if (!root) return null;

        if (root.nodeType === 1) { // Node.ELEMENT_NODE
            // Check if it's a visible contenteditable
            if (root.hasAttribute('contenteditable') && root.getAttribute('contenteditable') !== 'false') {
                const r = root.getBoundingClientRect();
                if (r.width > 50 && r.height > 20) return root;
            }
            // Check if it's a textarea
            if (root.tagName === 'TEXTAREA') {
                const r = root.getBoundingClientRect();
                if (r.width > 50 && r.height > 20) return root;
            }

            // If it has a shadow root, pierce it
            if (root.shadowRoot) {
                const found = _deepFindEditable(root.shadowRoot);
                if (found) return found;
            }
        }

        // Traverse all children (from shadow root if exists, else normal children)
        const children = root.shadowRoot ? root.shadowRoot.children : root.children;
        if (children) {
            for (let i = 0; i < children.length; i++) {
                const found = _deepFindEditable(children[i]);
                if (found) return found;
            }
        }

        return null;
    }

    function _showPostBar(content, taskId) {
        const old = document.getElementById('bilal-agent-post-overlay'); if (old) old.remove();
        const wc = content.split(/\s+/).filter(Boolean).length;
        const bar = document.createElement('div');
        bar.id = 'bilal-agent-post-overlay';
        bar.style.cssText = 'position:fixed;bottom:0;left:0;right:0;z-index:2147483647;background:linear-gradient(to top,rgba(10,10,30,.98),rgba(15,23,42,.96));border-top:3px solid #4ECDC4;backdrop-filter:blur(20px);padding:16px 24px;font-family:-apple-system,BlinkMacSystemFont,sans-serif;';
        bar.innerHTML = '<style>.ba-btn{border:none;padding:10px 22px;border-radius:8px;cursor:pointer;font-size:14px;font-weight:600;transition:all .2s;font-family:inherit}.ba-btn:hover{transform:translateY(-1px);filter:brightness(1.1)}</style><div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap"><span style="background:linear-gradient(135deg,#2563eb,#7c3aed);color:#fff;padding:4px 12px;border-radius:12px;font-weight:700;font-size:10px;text-transform:uppercase">⚡ BilalAgent</span><span style="background:#4ECDC4;color:#000;padding:3px 10px;border-radius:12px;font-weight:bold;font-size:11px">POST READY</span><span style="color:#94a3b8;font-size:12px">' + wc + ' words</span><div style="margin-left:auto;display:flex;gap:10px"><button id="ba-post-now" class="ba-btn" style="background:linear-gradient(135deg,#059669,#10b981);color:#fff;box-shadow:0 2px 10px rgba(16,185,129,.3)">✓ Post Now</button><button id="ba-edit-first" class="ba-btn" style="background:rgba(59,130,246,.15);color:#60a5fa;border:1px solid rgba(59,130,246,.3)">✏ Edit First</button><button id="ba-cancel" class="ba-btn" style="background:rgba(239,68,68,.15);color:#f87171;border:1px solid rgba(239,68,68,.3)">✕ Cancel</button></div></div>';
        document.body.appendChild(bar);
        document.getElementById('ba-post-now').onclick = () => { bar.remove(); const pb = document.querySelector('button.share-actions__primary-action') || Array.from(document.querySelectorAll('button')).find(b => (b.textContent || '').trim() === 'Post' && b.closest('div[role="dialog"]')); if (pb) { pb.click(); const bn = document.createElement('div'); bn.style.cssText = 'position:fixed;top:20px;right:20px;z-index:2147483647;background:#10b981;color:#fff;padding:14px 24px;border-radius:12px;font-family:sans-serif;font-weight:600;box-shadow:0 4px 20px rgba(0,0,0,.3)'; bn.textContent = '✅ Posted to LinkedIn!'; document.body.appendChild(bn); setTimeout(() => bn.remove(), 4000); } };
        document.getElementById('ba-edit-first').onclick = () => bar.remove();
        document.getElementById('ba-cancel').onclick = () => { bar.remove(); const cb = document.querySelector('button[aria-label="Dismiss"], button[aria-label="Close"]'); if (cb) cb.click(); };
    }

    // ─── Initialize ──────────────────────────────────

    // Wait for page to be fully loaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            injectContextSnapButton();
            startAIObserver();
        });
    } else {
        injectContextSnapButton();
        startAIObserver();
    }

    // Re-inject on URL changes (SPA navigation)
    let lastUrl = window.location.href;
    const urlObserver = new MutationObserver(() => {
        if (window.location.href !== lastUrl) {
            lastUrl = window.location.href;
            setTimeout(() => {
                const existing = document.getElementById('bilal-agent-snap-btn');
                if (existing) existing.remove();
                injectContextSnapButton();
            }, 1000);
        }
    });
    urlObserver.observe(document.body, { childList: true, subtree: true });

    // ─── Feature 4: Permission Overlay (Phase 9) ──────

    const BRIDGE_URL = 'http://localhost:8000';
    let activePermissionOverlay = null;
    let permissionPollInterval = null;
    let allowAllBadge = null;

    const ACTION_COLORS = {
        click: '#FF6B6B',
        type: '#4ECDC4',
        scroll: '#45B7D1',
        extract: '#96CEB4',
        done: '#A8E6CF',
        ask: '#FFEAA7',
    };

    function createPermissionOverlay(request) {
        // Remove existing
        if (activePermissionOverlay) {
            activePermissionOverlay.remove();
            activePermissionOverlay = null;
        }

        const color = ACTION_COLORS[request.action_type] || ACTION_COLORS.ask;
        const confidence = Math.round((request.confidence || 0) * 100);

        const overlay = document.createElement('div');
        overlay.id = 'bilal-permission-overlay';
        overlay.innerHTML = `
      <div style="
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        z-index: 999999;
        background: rgba(0,0,0,0.92);
        border-top: 3px solid ${color};
        padding: 12px 20px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
        display: flex;
        align-items: center;
        gap: 16px;
        animation: permSlideUp 0.25s ease;
      ">
        <style>
          @keyframes permSlideUp { from { transform: translateY(100%); } to { transform: translateY(0); } }
          @keyframes permPulse { 0%, 100% { opacity: 0.7; transform: scale(1); } 50% { opacity: 1; transform: scale(1.5); } }
          .perm-btn { padding: 8px 16px; border: none; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.15s; font-family: inherit; }
          .perm-btn:hover { transform: scale(1.05); filter: brightness(1.1); }
        </style>

        <!-- Left: Info -->
        <div style="flex: 1; min-width: 0;">
          <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 6px;">
            <span style="
              display: inline-block;
              padding: 3px 10px;
              background: ${color};
              color: #000;
              border-radius: 12px;
              font-size: 11px;
              font-weight: 700;
              text-transform: uppercase;
              letter-spacing: 0.5px;
            ">${request.action_type}</span>
            <span style="color: #aaa; font-size: 11px;">${request.task_id}</span>
          </div>
          <p style="margin: 0; color: #fff; font-size: 14px; line-height: 1.4; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
            ${request.description || 'No description'}
          </p>
          <div style="margin-top: 6px; display: flex; align-items: center; gap: 8px;">
            <div style="flex: 1; max-width: 200px; background: #333; height: 4px; border-radius: 2px; overflow: hidden;">
              <div style="width: ${confidence}%; height: 100%; background: ${color}; border-radius: 2px;"></div>
            </div>
            <span style="color: #888; font-size: 11px;">${confidence}% confidence</span>
            ${request.x != null ? `<span style="color: #666; font-size: 11px;">@ (${request.x}, ${request.y})</span>` : ''}
          </div>
        </div>

        <!-- Right: Buttons -->
        <div style="display: flex; gap: 8px; flex-shrink: 0;">
          <button class="perm-btn" data-decision="allow" style="background: #10b981; color: #fff;">Allow Once</button>
          <button class="perm-btn" data-decision="allow_all" style="background: #f59e0b; color: #000; font-weight: 700;">Allow All 30min</button>
          <button class="perm-btn" data-decision="skip" style="background: #6b7280; color: #fff;">Skip</button>
          <button class="perm-btn" data-decision="stop" style="background: #ef4444; color: #fff;">Stop</button>
          <button class="perm-btn" data-decision="edit" style="background: #3b82f6; color: #fff;">Edit</button>
        </div>
      </div>
    `;

        document.body.appendChild(overlay);
        activePermissionOverlay = overlay;

        // Button click handlers
        overlay.querySelectorAll('.perm-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const decision = btn.dataset.decision;
                try {
                    await fetch(`${BRIDGE_URL}/permission/result`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            task_id: request.task_id,
                            decision: decision
                        })
                    });
                } catch (e) {
                    console.error('[BilalAgent] Failed to send permission decision:', e);
                }
                overlay.remove();
                activePermissionOverlay = null;
            });
        });

        // Crosshair indicator at target coordinates
        if (request.x != null && request.y != null) {
            const crosshair = document.createElement('div');
            crosshair.style.cssText = `
                position: fixed;
                left: ${request.x - 12}px;
                top: ${request.y - 12}px;
                width: 24px;
                height: 24px;
                border: 2px solid ${color};
                border-radius: 50%;
                pointer-events: none;
                z-index: 999998;
                animation: permPulse 1s ease infinite;
                box-shadow: 0 0 10px ${color}80;
            `;
            document.body.appendChild(crosshair);
            setTimeout(() => crosshair.remove(), 3000);
        }
    }

    // Permission polling loop
    function startPermissionPolling() {
        if (permissionPollInterval) return;

        permissionPollInterval = setInterval(async () => {
            try {
                // Check for pending permissions
                const resp = await fetch(`${BRIDGE_URL}/permission/pending`);
                if (resp.ok) {
                    const pending = await resp.json();
                    if (pending.length > 0 && !activePermissionOverlay) {
                        createPermissionOverlay(pending[0]);
                    }
                }

                // Check Allow All status
                const aaResp = await fetch(`${BRIDGE_URL}/permission/allow_all_status`);
                if (aaResp.ok) {
                    const aaData = await aaResp.json();
                    updateAllowAllBadge(aaData);
                }
            } catch (e) {
                // Bridge offline — ignore silently
            }
        }, 1000);
    }

    function updateAllowAllBadge(data) {
        if (data.active) {
            const mins = Math.floor(data.time_remaining_seconds / 60);
            const secs = data.time_remaining_seconds % 60;
            if (!allowAllBadge) {
                allowAllBadge = document.createElement('div');
                allowAllBadge.id = 'bilal-allow-all-badge';
                allowAllBadge.style.cssText = `
                    position: fixed;
                    top: 8px;
                    right: 8px;
                    z-index: 999998;
                    background: #ef4444;
                    color: #fff;
                    padding: 6px 14px;
                    border-radius: 20px;
                    font-family: -apple-system, sans-serif;
                    font-size: 12px;
                    font-weight: 600;
                    cursor: pointer;
                    box-shadow: 0 2px 10px rgba(239,68,68,0.4);
                `;
                allowAllBadge.title = 'Click to revoke Allow All';
                allowAllBadge.addEventListener('click', async () => {
                    try {
                        await fetch(`${BRIDGE_URL}/permission/set_allow_all`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ duration_minutes: 0 })
                        });
                        if (allowAllBadge) { allowAllBadge.remove(); allowAllBadge = null; }
                    } catch (e) { }
                });
                document.body.appendChild(allowAllBadge);
            }
            allowAllBadge.textContent = `AUTO: ${mins}m ${secs}s`;
        } else {
            if (allowAllBadge) { allowAllBadge.remove(); allowAllBadge = null; }
        }
    }

    // Start permission polling alongside existing features
    startPermissionPolling();

    // ─── Feature 5: LinkedIn Task Watcher ────────────

    // bridgeAlive must be declared BEFORE any function that uses it
    // (let does not hoist like var — temporal dead zone otherwise)
    let bridgeAlive = true;
    let watchingLinkedIn = false;

    async function pollActiveTasks() {
        if (!bridgeAlive) return;
        try {
            const r = await fetch(`${BRIDGE_URL}/tasks/active`);
            if (!r.ok) return;
            const tasks = await r.json();
            for (const task of tasks) {
                if (task.status === 'active' &&
                    task.type === 'linkedin_post' &&
                    window.location.href.includes('linkedin.com') &&
                    !watchingLinkedIn) {
                    watchingLinkedIn = true;
                    watchLinkedInPage(task.task_id);
                }
            }
        } catch (e) { }
    }
    safeSetInterval(pollActiveTasks, 2000);

    function watchLinkedInPage(taskId) {
        const reportState = (state) => {
            fetch(`${BRIDGE_URL}/extension/page_state`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    task_id: taskId,
                    state: state,
                    url: window.location.href,
                    ts: Date.now()
                })
            }).catch(() => { });
            console.log(`[BilalAgent] LinkedIn state: ${state}`);
        };

        const observer = new MutationObserver(() => {
            // Composer opened
            const composer = document.querySelector(
                'div.ql-editor, ' +
                'div[data-placeholder="What do you want to talk about?"], ' +
                'div.share-creation-state__text-editor div[contenteditable="true"]'
            );
            if (composer) reportState('composer_open');

            // Post confirmed (success toast)
            const toast = document.querySelector(
                '.artdeco-toast-item--visible, ' +
                '[data-test-artdeco-toast-type="success"]'
            );
            if (toast && toast.textContent.toLowerCase().includes('post')) {
                reportState('post_confirmed');
                observer.disconnect();
                watchingLinkedIn = false;
            }
        });

        observer.observe(document.body, { childList: true, subtree: true });
        reportState('page_loaded');
    }

    // Bridge liveness check (gates pollActiveTasks + pollPermissions)
    // NOTE: bridgeAlive is declared above (before pollActiveTasks) to avoid
    // temporal dead zone with `let`.
    async function checkBridge() {
        try {
            const r = await fetch(`${BRIDGE_URL}/status`,
                { signal: AbortSignal.timeout(2000) });
            bridgeAlive = r.ok;
        } catch (e) {
            bridgeAlive = false;
        }
    }
    safeSetInterval(checkBridge, 5000);
    checkBridge();

    // ═══════════════════════════════════════════════════════
    // LINKEDIN ACTOR — executes actions in the current tab
    // Content-script-driven polling (page process is always alive,
    // unlike MV3 service workers which sleep after ~30s idle).
    // ═══════════════════════════════════════════════════════

    let executingLinkedInAction = false;

    // Poll background every second for pending LinkedIn actions.
    // Only runs on LinkedIn pages. Background does the bridge fetch (no CSP).
    if (hostname.includes('linkedin.com')) {
        console.log('[BilalAgent] LinkedIn tab detected — starting action poll');
        safeSetInterval(() => {
            if (executingLinkedInAction) return;
            safeSendMessage({ type: 'POLL_LINKEDIN_ACTION' }, (response) => {
                if (!response || !response.action) return;
                const action = response.action;
                executingLinkedInAction = true;
                console.log('[BilalAgent] Received LinkedIn action:', action.type, action.action_id);
                executeLinkedInAction(action)
                    .catch(e => reportLinkedInResult(action.action_id, 'failed', e.message))
                    .finally(() => { executingLinkedInAction = false; });
            });
        }, 1000);
    }

    // Results go via background SW (LinkedIn CSP blocks direct fetch to localhost)
    function reportLinkedInResult(actionId, status, message) {
        safeSendMessage({
            type: 'LINKEDIN_RESULT',
            action_id: actionId,
            status: status,
            result_message: message
        });
    }

    async function executeLinkedInAction(action) {
        const { action_id, type, content } = action;

        if (type === 'open_composer') {
            const opened = await openLinkedInComposer();
            if (opened) {
                await reportLinkedInResult(action_id, 'done', 'composer_opened');
            } else {
                await reportLinkedInResult(action_id, 'failed',
                    'Could not find Start a post button');
            }
        } else if (type === 'type_content') {
            const typed = await typeIntoComposer(content);
            if (typed) {
                showPostPreviewOverlay(action_id, content);
                // result reported later by user clicking Upload/Edit/Cancel
            } else {
                await reportLinkedInResult(action_id, 'failed',
                    'Could not find composer editor');
            }
        } else if (type === 'click_post') {
            const posted = await clickPostButton();
            if (posted) {
                await reportLinkedInResult(action_id, 'done', 'post_clicked');
            } else {
                await reportLinkedInResult(action_id, 'failed', 'Could not find Post button');
            }
        }
    }

    async function openLinkedInComposer() {
        // Already open?
        const existingEditor = document.querySelector(
            'div.ql-editor[contenteditable="true"], ' +
            'div[data-placeholder="What do you want to talk about?"]'
        );
        if (existingEditor) {
            existingEditor.click();
            console.log('[BilalAgent] Composer already open');
            return true;
        }

        // Try click triggers
        const selectors = [
            'button.share-box-feed-entry__trigger',
            '[data-control-name="share.sharebox_prompt_open"]',
            '.share-box-feed-entry__closed-share-box button',
            'div.share-box-feed-entry__trigger',
            // Current LinkedIn 2024/2025 selectors
            'button[aria-label="Start a post"]',
            'div[aria-label="Start a post"]',
            '[data-view-name="share-box-feed-entry"] button',
        ];
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el) {
                el.click();
                await sleep(1800);
                const editor = document.querySelector(
                    'div.ql-editor[contenteditable="true"], ' +
                    'div[data-placeholder="What do you want to talk about?"]'
                );
                if (editor) {
                    console.log('[BilalAgent] Composer opened via', sel);
                    return true;
                }
            }
        }

        // Last resort: find any button whose text mentions "post"
        for (const btn of document.querySelectorAll('button, div[role="button"]')) {
            const text = btn.textContent.trim().toLowerCase();
            if (text === 'start a post' || text.includes('start a post')) {
                btn.click();
                await sleep(1800);
                const editor = document.querySelector('div.ql-editor[contenteditable="true"]');
                if (editor) { console.log('[BilalAgent] Composer opened via text match'); return true; }
            }
        }
        return false;
    }

    async function typeIntoComposer(content) {
        // Wait up to 3s for editor to appear after composer opened
        let editor = null;
        for (let attempt = 0; attempt < 6; attempt++) {
            editor = document.querySelector(
                'div.ql-editor[contenteditable="true"], ' +
                'div[data-placeholder="What do you want to talk about?"][contenteditable="true"]'
            );
            if (editor) break;
            await sleep(500);
        }
        // Broader fallback
        if (!editor) {
            editor = document.querySelector(
                'div.share-creation-state__text-editor div[contenteditable="true"], ' +
                'div[contenteditable="true"]'
            );
        }
        if (!editor) return false;

        editor.focus();
        editor.click();
        await sleep(400);

        // Clear existing content
        document.execCommand('selectAll', false, null);
        document.execCommand('delete', false, null);
        await sleep(200);

        // Insert content line by line
        const lines = content.split('\n');
        for (let i = 0; i < lines.length; i++) {
            document.execCommand('insertText', false, lines[i]);
            if (i < lines.length - 1) {
                editor.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', bubbles: true }));
                await sleep(30);
            }
        }
        await sleep(500);
        console.log('[BilalAgent] Content typed into composer:', content.length, 'chars');
        return true;
    }

    async function clickPostButton() {
        const selectors = [
            'button.share-actions__primary-action',
            'button[data-control-name="share.post"]',
            '.share-creation-state__post-btn',
        ];
        for (const sel of selectors) {
            const btn = document.querySelector(sel);
            if (btn && !btn.disabled) { btn.click(); await sleep(2000); return true; }
        }
        // XPath fallback
        for (const btn of document.querySelectorAll('button')) {
            if (btn.textContent.trim() === 'Post' && !btn.disabled) {
                btn.click(); await sleep(2000); return true;
            }
        }
        return false;
    }

    function showPostPreviewOverlay(actionId, content) {
        const existing = document.getElementById('bilal-post-preview');
        if (existing) existing.remove();

        const wordCount = content.split(/\s+/).filter(Boolean).length;
        const overlay = document.createElement('div');
        overlay.id = 'bilal-post-preview';
        overlay.style.cssText = `
            position:fixed;bottom:0;left:0;right:0;z-index:2147483647;
            background:linear-gradient(to top, rgba(10,10,30,0.98), rgba(15,23,42,0.96));
            border-top:3px solid #4ECDC4;backdrop-filter:blur(20px);
            padding:16px 24px 14px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
            animation:bilalSlideUp 0.3s ease;
        `;
        overlay.innerHTML = `
            <style>
                @keyframes bilalSlideUp { from { transform: translateY(100%); } to { transform: translateY(0); } }
                .bilal-preview-btn { border:none; padding:10px 22px; border-radius:8px; cursor:pointer; font-size:13px; font-weight:600; transition:all 0.2s; font-family:inherit; }
                .bilal-preview-btn:hover { transform:translateY(-1px); filter:brightness(1.1); }
            </style>
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;flex-wrap:wrap">
                <span style="background:linear-gradient(135deg,#2563eb,#7c3aed);color:#fff;padding:4px 12px;border-radius:12px;font-weight:700;font-size:10px;text-transform:uppercase;letter-spacing:0.5px">
                    ⚡ Generated by BilalAgent
                </span>
                <span style="background:#4ECDC4;color:#000;padding:3px 10px;border-radius:12px;font-weight:bold;font-size:11px">POST READY</span>
                <span style="color:#94a3b8;font-size:12px">${wordCount} words typed into LinkedIn</span>
                <span style="color:#64748b;font-size:11px;margin-left:auto">Review post above, then decide:</span>
            </div>
            <div style="display:flex;gap:10px;flex-wrap:wrap">
                <button id="bilal-upload-btn" class="bilal-preview-btn" style="background:linear-gradient(135deg,#059669,#10b981);color:#fff;font-size:14px;box-shadow:0 2px 10px rgba(16,185,129,0.3)">
                    ✓ Upload Now
                </button>
                <button id="bilal-edit-btn" class="bilal-preview-btn" style="background:rgba(59,130,246,0.15);color:#60a5fa;border:1px solid rgba(59,130,246,0.3)">
                    ✏ Edit First
                </button>
                <button id="bilal-cancel-btn" class="bilal-preview-btn" style="background:rgba(239,68,68,0.15);color:#f87171;border:1px solid rgba(239,68,68,0.3)">
                    ✕ Cancel
                </button>
                <span style="color:#475569;font-size:11px;align-self:center;margin-left:8px">(Esc to cancel)</span>
            </div>
        `;
        document.body.appendChild(overlay);

        document.getElementById('bilal-upload-btn').onclick = async () => {
            overlay.remove();
            const posted = await clickPostButton();
            if (posted) {
                showBanner('✓ Posted to LinkedIn!', '#10b981');
                reportLinkedInResult(actionId, 'done', 'posted');
                safeSendMessage({
                    type: 'PAGE_STATE',
                    data: { task_id: actionId, state: 'post_confirmed', url: window.location.href, ts: Date.now() }
                });
            } else {
                await reportLinkedInResult(actionId, 'failed', 'Post button not found');
            }
        };

        document.getElementById('bilal-edit-btn').onclick = () => {
            overlay.remove();
            reportLinkedInResult(actionId, 'done', 'user_editing');
            showBanner('✏ Edit the post above, then click Post', '#3b82f6');
        };

        document.getElementById('bilal-cancel-btn').onclick = async () => {
            overlay.remove();
            const closeBtn = document.querySelector('button[aria-label="Dismiss"],button.share-creation-state__close-btn');
            if (closeBtn) closeBtn.click();
            await reportLinkedInResult(actionId, 'done', 'cancelled');
        };

        const onEsc = (e) => {
            if (e.key === 'Escape') {
                overlay.remove();
                reportLinkedInResult(actionId, 'done', 'cancelled');
                document.removeEventListener('keydown', onEsc);
            }
        };
        document.addEventListener('keydown', onEsc);
    }

    function showBanner(text, color) {
        const b = document.createElement('div');
        b.style.cssText = `position:fixed;top:20px;right:20px;background:${color};color:#fff;padding:12px 20px;border-radius:8px;font-family:Arial;font-size:14px;font-weight:bold;z-index:2147483647;box-shadow:0 4px 12px rgba(0,0,0,0.3)`;
        b.textContent = text;
        document.body.appendChild(b);
        setTimeout(() => b.remove(), 4000);
    }

    function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

    // ═══════════════════════════════════════════════════════
    // END LINKEDIN ACTOR
    // ═══════════════════════════════════════════════════════

    console.log('[BilalAgent] Content script loaded (Permission Gate + LinkedIn Watcher + Actor)');
})();
