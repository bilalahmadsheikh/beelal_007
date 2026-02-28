/**
 * background.js — BilalAgent v2.0 Chrome Extension Service Worker
 * Handles: cookie sync, message relay, task polling
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
        // Bridge not running — silent fail
        console.log(`[BilalAgent] Bridge not available for cookie sync`);
    }
}

// Sync cookies on install
chrome.runtime.onInstalled.addListener(() => {
    console.log('[BilalAgent] Extension installed — syncing cookies...');
    SUPPORTED_DOMAINS.forEach(domain => syncCookies(domain));
});

// Re-sync when cookies change on supported sites
chrome.cookies.onChanged.addListener((changeInfo) => {
    const domain = changeInfo.cookie.domain.replace(/^\./, '');
    if (SUPPORTED_DOMAINS.some(d => domain.includes(d))) {
        syncCookies(domain);
    }
});

// ─── Message Relay ─────────────────────────────────

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'context_snap') {
        // Content script captured job data → relay to bridge
        fetch(`${BRIDGE_URL}/extension/context_snap`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(message.data)
        })
            .then(r => r.json())
            .then(data => sendResponse({ success: true, task_id: data.task_id }))
            .catch(e => sendResponse({ success: false, error: e.message }));
        return true; // async response
    }

    if (message.type === 'approval_action') {
        // Overlay approve/cancel → relay to bridge
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
        // MutationObserver captured AI response → relay to bridge
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
});

// ─── Task Polling ──────────────────────────────────

let pollingInterval = null;

function startPolling(tabId) {
    if (pollingInterval) return;

    pollingInterval = setInterval(async () => {
        try {
            const response = await fetch(`${BRIDGE_URL}/extension/get_task`);
            const task = await response.json();

            if (task && task.task_id) {
                // Tell content script to show overlay
                chrome.tabs.sendMessage(tabId, {
                    type: 'show_overlay',
                    task: task
                });
            }
        } catch (e) {
            // Bridge not running — silent
        }
    }, 2000);
}

function stopPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
}

// Start polling when on supported sites
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.status === 'complete' && tab.url) {
        const url = new URL(tab.url);
        const isSupported = [...SUPPORTED_DOMAINS, ...AI_DOMAINS].some(d => url.hostname.includes(d));
        if (isSupported) {
            startPolling(tabId);
        } else {
            stopPolling();
        }
    }
});

chrome.tabs.onRemoved.addListener(() => {
    stopPolling();
});
