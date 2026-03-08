/**
 * popup.js — BilalAgent v3.0 Extension Popup Logic
 * Claude-like sidebar with SSE streaming, activity feed, content preview,
 * and agent-driven LinkedIn posting orchestration.
 */

(() => {
    'use strict';

    const BRIDGE_URL = 'http://localhost:8000';
    let sseSource = null;
    let feedMessages = [];
    let pendingContentCount = 0;

    // ─── DOM References ─────────────────────────────
    const feedEl = document.getElementById('feed');
    const feedEmpty = document.getElementById('feed-empty');
    const feedBadge = document.getElementById('feed-badge');
    const statusDot = document.getElementById('status-dot');
    const bridgeStatus = document.getElementById('bridge-status');
    const agentStatus = document.getElementById('agent-status');
    const sseStatus = document.getElementById('sse-status');
    const cookieSites = document.getElementById('cookie-sites');
    const pendingCount = document.getElementById('pending-count');
    const contentCount = document.getElementById('content-count');
    const totalCount = document.getElementById('total-count');
    const promptInput = document.getElementById('prompt-input');
    const promptSend = document.getElementById('prompt-send');

    // ─── Tab Switching ──────────────────────────────
    document.querySelectorAll('.tab-bar button').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-bar button').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(`panel-${btn.dataset.tab}`).classList.add('active');
        });
    });

    // ─── Time Formatting ────────────────────────────
    function timeAgo(ts) {
        if (!ts) return '';
        const diff = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
        if (diff < 60) return 'just now';
        if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
        return `${Math.floor(diff / 86400)}d ago`;
    }

    function nowISO() { return new Date().toISOString(); }

    // ─── Feed Message Rendering ─────────────────────
    function addMessage(type, text, extra = {}) {
        const msg = { type, text, ts: nowISO(), ...extra };
        feedMessages.push(msg);

        // Remove empty state
        if (feedEmpty) feedEmpty.style.display = 'none';

        const el = document.createElement('div');
        el.className = `msg ${type}`;

        const labels = {
            agent: '<span class="msg-label agent-label">Agent</span>',
            system: '<span class="msg-label system-label">System</span>',
            success: '<span class="msg-label" style="background:#10b981;color:#fff">Done</span>',
            error: '<span class="msg-label" style="background:#ef4444;color:#fff">Error</span>',
        };

        el.innerHTML = `
            <div class="msg-header">
                ${labels[type] || labels.system}
                <span class="msg-time">${timeAgo(msg.ts)}</span>
            </div>
            <div class="msg-text">${escapeHtml(text)}</div>
        `;

        feedEl.appendChild(el);
        feedEl.scrollTop = feedEl.scrollHeight;

        // Update badge
        pendingContentCount++;
        feedBadge.textContent = pendingContentCount;
        feedBadge.style.display = pendingContentCount > 0 ? 'inline' : 'none';
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ─── Content Preview Card ───────────────────────
    function showContentCard(data) {
        const { content, content_type, task_id, word_count, hashtags } = data;
        console.log('[BilalAgent Popup] showContentCard called:', task_id, content_type);

        // Highlight hashtags in content
        let displayContent = escapeHtml(content || '');
        displayContent = displayContent.replace(/(#\w+)/g, '<span class="hashtag">$1</span>');

        const wc = word_count || (content || '').split(/\s+/).filter(Boolean).length;

        const card = document.createElement('div');
        card.className = 'content-card';
        card.id = `content-card-${task_id}`;
        card.innerHTML = `
            <div class="content-card-header">
                <span class="content-card-badge">${content_type || 'LinkedIn Post'}</span>
                <span class="content-card-meta">${wc} words</span>
            </div>
            <div class="content-card-actions">
                <button class="btn btn-primary" data-action="post" data-task="${task_id}">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M22 2L11 13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
                    </svg>
                    Post to LinkedIn
                </button>
                <button class="btn btn-secondary btn-sm" data-action="copy" data-task="${task_id}">📋 Copy</button>
                <button class="btn btn-ghost btn-sm" data-action="edit" data-task="${task_id}">✏️</button>
                <button class="btn btn-danger btn-sm" data-action="reject" data-task="${task_id}">✕</button>
            </div>
            <div class="content-card-body">${displayContent}</div>
        `;

        // Remove empty state
        if (feedEmpty) feedEmpty.style.display = 'none';
        feedEl.appendChild(card);

        // Scroll the card into view
        setTimeout(() => card.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);

        // Action handlers
        card.querySelectorAll('[data-action]').forEach(btn => {
            btn.addEventListener('click', () => handleContentAction(btn.dataset.action, task_id, content, card));
        });
    }

    async function handleContentAction(action, taskId, content, cardEl) {
        if (action === 'post') {
            // Disable buttons while posting
            cardEl.querySelectorAll('.btn').forEach(b => { b.disabled = true; b.style.opacity = '0.5'; });

            addMessage('agent', '🚀 Opening LinkedIn and preparing your post...');

            // Tell background to orchestrate LinkedIn posting
            chrome.runtime.sendMessage({
                type: 'AGENT_POST_LINKEDIN',
                content: content,
                task_id: taskId,
            }, (response) => {
                if (response?.success) {
                    addMessage('success', '✅ Content sent to LinkedIn! Check the LinkedIn tab for the upload confirmation.');
                    // Report to bridge
                    reportContentDecision(taskId, 'approved');
                } else {
                    addMessage('error', `LinkedIn posting failed: ${response?.error || 'Unknown error'}`);
                    // Re-enable buttons
                    cardEl.querySelectorAll('.btn').forEach(b => { b.disabled = false; b.style.opacity = '1'; });
                }
            });

        } else if (action === 'copy') {
            try {
                await navigator.clipboard.writeText(content);
                addMessage('success', '📋 Content copied to clipboard!');
            } catch (e) {
                // Fallback
                const ta = document.createElement('textarea');
                ta.value = content;
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                ta.remove();
                addMessage('success', '📋 Content copied to clipboard!');
            }

        } else if (action === 'edit') {
            addMessage('system', '✏️ Edit mode — modify the content in the LinkedIn composer after posting.');
            // Post with edit intent
            chrome.runtime.sendMessage({
                type: 'AGENT_POST_LINKEDIN',
                content: content,
                task_id: taskId,
                edit_mode: true,
            });
            reportContentDecision(taskId, 'editing');

        } else if (action === 'reject') {
            cardEl.style.opacity = '0.3';
            cardEl.style.pointerEvents = 'none';
            addMessage('system', '✕ Content rejected.');
            reportContentDecision(taskId, 'rejected');
        }
    }

    function reportContentDecision(taskId, decision) {
        fetch(`${BRIDGE_URL}/agent/content/decision`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_id: taskId, decision: decision }),
        }).catch(() => { });
    }

    // ─── SSE Connection ─────────────────────────────
    function connectSSE() {
        if (sseSource) {
            sseSource.close();
            sseSource = null;
        }

        try {
            sseSource = new EventSource(`${BRIDGE_URL}/agent/stream`);

            sseSource.onopen = () => {
                sseStatus.textContent = 'Connected';
                sseStatus.className = 'badge badge-green';
                addMessage('system', '🔗 Connected to desktop agent stream.');
            };

            sseSource.addEventListener('agent_message', (e) => {
                try {
                    const data = JSON.parse(e.data);
                    addMessage('agent', data.message || data.text || e.data);
                } catch {
                    addMessage('agent', e.data);
                }
            });

            sseSource.addEventListener('content_ready', (e) => {
                try {
                    const data = JSON.parse(e.data);
                    addMessage('agent', `📝 New ${data.content_type || 'content'} generated! Review below:`);
                    showContentCard(data);
                } catch {
                    addMessage('error', 'Failed to parse content data');
                }
            });

            sseSource.addEventListener('action_result', (e) => {
                try {
                    const data = JSON.parse(e.data);
                    const type = data.status === 'done' ? 'success' : 'error';
                    addMessage(type, data.message || `Action ${data.status}`);
                } catch {
                    addMessage('system', e.data);
                }
            });

            sseSource.addEventListener('status_update', (e) => {
                try {
                    const data = JSON.parse(e.data);
                    if (data.agent_status) {
                        agentStatus.textContent = data.agent_status;
                        agentStatus.className = `badge badge-${data.agent_status === 'active' ? 'green' : 'amber'}`;
                    }
                } catch { }
            });

            sseSource.onerror = () => {
                sseStatus.textContent = 'Reconnecting...';
                sseStatus.className = 'badge badge-amber';
                // EventSource auto-reconnects
            };

        } catch (e) {
            sseStatus.textContent = 'Failed';
            sseStatus.className = 'badge badge-red';
        }
    }

    // ─── Bridge Status Polling ──────────────────────
    function checkBridgeStatus() {
        chrome.runtime.sendMessage({ type: 'get_status' }, (response) => {
            if (chrome.runtime.lastError) {
                setBridgeOffline();
                return;
            }

            if (response?.success && response.status === 'running') {
                statusDot.className = 'status-dot online';
                statusDot.title = 'Bridge: Connected';
                bridgeStatus.textContent = 'Connected';
                bridgeStatus.className = 'badge badge-green';

                // Update stats
                const tasks = response.tasks || {};
                pendingCount.textContent = tasks.pending || 0;
                contentCount.textContent = tasks.show_overlay || 0;
                totalCount.textContent = tasks.total || 0;

                // Cookie sites
                const sites = response.cookie_sites || [];
                cookieSites.textContent = sites.length > 0 ? sites.join(', ') : 'None';

                // Start SSE if not connected
                if (!sseSource || sseSource.readyState === EventSource.CLOSED) {
                    connectSSE();
                }
            } else {
                setBridgeOffline();
            }
        });
    }

    function setBridgeOffline() {
        statusDot.className = 'status-dot offline';
        statusDot.title = 'Bridge: Offline';
        bridgeStatus.textContent = 'Offline';
        bridgeStatus.className = 'badge badge-red';
        cookieSites.textContent = 'Bridge offline';
    }

    // ─── Polling for Content (fallback + startup check) ──
    function pollAgentContent() {
        fetch(`${BRIDGE_URL}/agent/content/latest`, { signal: AbortSignal.timeout(3000) })
            .then(r => r.json())
            .then(data => {
                console.log('[BilalAgent Popup] pollAgentContent:', data?.task_id, data?.status);
                if (data && data.content && data.status === 'pending_review') {
                    // Check if we already have this card
                    const existing = document.getElementById(`content-card-${data.task_id}`);
                    if (!existing) {
                        addMessage('agent', `📝 New ${data.content_type || 'content'} ready for review:`);
                        showContentCard(data);
                    }
                }
            })
            .catch(() => { });
    }

    // ─── Prompt Sending ─────────────────────────────
    function sendPrompt() {
        const text = promptInput.value.trim();
        if (!text) return;

        promptInput.value = '';
        promptSend.disabled = true;

        addMessage('system', `You: ${text}`);

        // Send to bridge via background (avoid CSP issues)
        chrome.runtime.sendMessage({
            type: 'AGENT_SEND_PROMPT',
            prompt: text,
        }, (response) => {
            promptSend.disabled = false;
            if (response?.success) {
                addMessage('system', '📨 Prompt sent to desktop agent.');
            } else {
                addMessage('error', 'Failed to send prompt — bridge offline?');
            }
        });
    }

    promptSend.addEventListener('click', sendPrompt);
    promptInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendPrompt();
        }
    });

    // ─── Initialize ─────────────────────────────────
    addMessage('system', `BilalAgent v3.0 — popup ready.`);
    checkBridgeStatus();
    setInterval(checkBridgeStatus, 5000);

    // Fetch pending content IMMEDIATELY on popup open (don't wait for SSE or 4s poll)
    setTimeout(pollAgentContent, 500);
    setInterval(pollAgentContent, 4000);
})();
