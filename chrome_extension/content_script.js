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

    console.log('[BilalAgent] Content script loaded');
})();
