/**
 * content_script.js — BilalAgent v2.0 Chrome Extension Content Script
 * Features:
 * 1. Context Snap — "Send to BilalAgent" button on job pages
 * 2. Approval Overlay — bottom-screen overlay with Approve/Cancel
 * 3. MutationObserver — watches Claude.ai / ChatGPT for AI responses
 */

(() => {
    'use strict';

    // Prevent double injection
    if (window.__bilalAgentInjected) return;
    window.__bilalAgentInjected = true;

    const hostname = window.location.hostname;

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

            chrome.runtime.sendMessage(
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
            chrome.runtime.sendMessage({
                type: 'approval_action',
                data: { task_id: task.task_id, action: 'approve' }
            });
            overlay.remove();
        });

        document.getElementById('bilal-overlay-cancel').addEventListener('click', () => {
            chrome.runtime.sendMessage({
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

                    chrome.runtime.sendMessage({
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

    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        if (message.type === 'show_overlay' && message.task) {
            showOverlay(message.task);
            sendResponse({ shown: true });
        }
    });

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

    console.log('[BilalAgent] Content script loaded (with Permission Gate)');
})();
