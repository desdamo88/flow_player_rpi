/**
 * Flow Player - Web Interface JavaScript
 */

// API Base URL
const API_BASE = '/api';

// Status polling interval (ms)
const STATUS_POLL_INTERVAL = 1000;

let statusPollTimer = null;

/**
 * Fetch wrapper with error handling
 */
async function apiFetch(endpoint) {
    try {
        const response = await fetch(`${API_BASE}${endpoint.replace('/api', '')}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`API Error (${endpoint}):`, error);
        return null;
    }
}

/**
 * POST request wrapper
 */
async function apiPost(endpoint, data = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint.replace('/api', '')}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });
        return await response.json();
    } catch (error) {
        console.error(`API Error (POST ${endpoint}):`, error);
        return null;
    }
}

/**
 * PUT request wrapper
 */
async function apiPut(endpoint, data = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint.replace('/api', '')}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });
        return await response.json();
    } catch (error) {
        console.error(`API Error (PUT ${endpoint}):`, error);
        return null;
    }
}

/**
 * DELETE request wrapper
 */
async function apiDelete(endpoint) {
    try {
        const response = await fetch(`${API_BASE}${endpoint.replace('/api', '')}`, {
            method: 'DELETE',
        });
        return await response.json();
    } catch (error) {
        console.error(`API Error (DELETE ${endpoint}):`, error);
        return null;
    }
}

/**
 * Format milliseconds to MM:SS or HH:MM:SS
 */
function formatTime(ms) {
    if (!ms || ms < 0) return '00:00';

    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);

    if (hours > 0) {
        return `${hours}:${String(minutes % 60).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
    }
    return `${String(minutes).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}

/**
 * Format uptime in seconds to human-readable string
 */
function formatUptime(seconds) {
    if (!seconds || seconds < 0) return '--';

    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (days > 0) {
        return `${days}j ${hours}h`;
    }
    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
}

/**
 * Update common UI elements from status
 */
function updateCommonUI(status) {
    // Device info in navbar
    if (status.device) {
        const hostnameEl = document.getElementById('device-hostname');
        const ipEl = document.getElementById('device-ip');
        if (hostnameEl) hostnameEl.textContent = status.device.hostname || '--';
        if (ipEl) ipEl.textContent = status.device.ip || '--';
    }

    // System stats in footer
    if (status.system) {
        const cpuEl = document.getElementById('stat-cpu');
        const ramEl = document.getElementById('stat-ram');
        const tempEl = document.getElementById('stat-temp');
        const uptimeEl = document.getElementById('stat-uptime');

        if (cpuEl) cpuEl.textContent = status.system.cpu_percent?.toFixed(1) || '--';
        if (ramEl) ramEl.textContent = status.system.memory_percent?.toFixed(1) || '--';
        if (tempEl) tempEl.textContent = status.system.temperature?.toFixed(1) || '--';
        if (uptimeEl) uptimeEl.textContent = formatUptime(status.system.uptime);
    }
}

/**
 * Start status polling
 */
function startStatusPolling(callback) {
    async function poll() {
        const status = await apiFetch('/status');
        if (status) {
            updateCommonUI(status);
            if (callback) {
                callback(status);
            }
        }
    }

    // Initial poll
    poll();

    // Start polling timer
    if (statusPollTimer) {
        clearInterval(statusPollTimer);
    }
    statusPollTimer = setInterval(poll, STATUS_POLL_INTERVAL);
}

/**
 * Stop status polling
 */
function stopStatusPolling() {
    if (statusPollTimer) {
        clearInterval(statusPollTimer);
        statusPollTimer = null;
    }
}

// Start basic status polling on all pages
document.addEventListener('DOMContentLoaded', () => {
    // Only poll common UI if not on dashboard (dashboard has its own polling)
    if (window.location.pathname !== '/') {
        startStatusPolling(null);
    }
});

// Stop polling when page is hidden
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        stopStatusPolling();
    } else {
        // Restart polling when page becomes visible
        startStatusPolling(window.currentStatusCallback || null);
    }
});
