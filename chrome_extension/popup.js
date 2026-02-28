/**
 * popup.js — BilalAgent v2.0 Extension Popup Logic
 * Updates status display by polling bridge server
 */

document.addEventListener('DOMContentLoaded', () => {
    const bridgeStatus = document.getElementById('bridge-status');
    const cookieSites = document.getElementById('cookie-sites');
    const pendingCount = document.getElementById('pending-count');
    const overlayCount = document.getElementById('overlay-count');
    const totalCount = document.getElementById('total-count');

    // Poll bridge status
    chrome.runtime.sendMessage({ type: 'get_status' }, (response) => {
        if (response?.success && response.status === 'running') {
            bridgeStatus.textContent = 'Connected';
            bridgeStatus.className = 'badge badge-green';

            // Update stats
            const tasks = response.tasks || {};
            pendingCount.textContent = tasks.pending || 0;
            overlayCount.textContent = tasks.show_overlay || 0;
            totalCount.textContent = tasks.total || 0;

            // Cookie sites
            const sites = response.cookie_sites || [];
            cookieSites.textContent = sites.length > 0 ? sites.join(', ') : 'None';
        } else {
            bridgeStatus.textContent = 'Offline';
            bridgeStatus.className = 'badge badge-red';
            cookieSites.textContent = 'Bridge offline';
        }
    });
});
