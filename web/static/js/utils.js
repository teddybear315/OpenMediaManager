/**
 * Utility functions for Open Media Manager web interface
 */

// Format file size in human-readable format
function formatFileSize(bytes) {
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let size = bytes;
    let unitIndex = 0;

    while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024;
        unitIndex++;
    }

    return `${size.toFixed(1)} ${units[unitIndex]}`;
}

// Format duration in human-readable format
function formatDuration(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hours > 0) {
        return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
        return `${minutes}m ${secs}s`;
    } else {
        return `${secs}s`;
    }
}

// Format bitrate in human-readable format
function formatBitrate(kbps) {
    if (kbps >= 1000) {
        return `${(kbps / 1000).toFixed(1)} Mbps`;
    }
    return `${kbps} kbps`;
}

// Escape HTML special characters
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

// Debounce function for search and filter
function debounce(func, delay) {
    let timeoutId;
    return function(...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func.apply(this, args), delay);
    };
}

// Throttle function for scroll events
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// API helper functions
const API = {
    async getConfig() {
        const response = await fetch('/api/config');
        if (!response.ok) throw new Error('Failed to fetch config');
        return response.json();
    },

    async updateConfig(config) {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        if (!response.ok) throw new Error('Failed to update config');
        return response.json();
    },

    async restartServer() {
        try {
            const response = await fetch('/api/server/restart', { method: 'POST' });
            if (!response.ok) throw new Error('Failed to restart server');
            return response.json();
        } catch (error) {
            // Server may have already restarted, so don't fail hard
            console.warn('Server restart request sent (may have restarted):', error);
            return { status: 'restart_requested' };
        }
    },

    async getMedia() {
        const response = await fetch('/api/media');
        if (!response.ok) throw new Error('Failed to fetch media list');
        return response.json();
    },

    async scanMedia() {
        const response = await fetch('/api/media/scan');
        if (!response.ok) throw new Error('Failed to scan media');
        return response.json();
    },

    async startEncoding(files = null, encodingSettings = null) {
        const response = await fetch('/api/encode/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                files: files,
                encoding_settings: encodingSettings
            })
        });
        if (!response.ok) throw new Error('Failed to start encoding');
        return response.json();
    },

    async stopEncoding() {
        const response = await fetch('/api/encode/stop', { method: 'POST' });
        if (!response.ok) throw new Error('Failed to stop encoding');
        return response.json();
    },

    async getEncodingStatus() {
        const response = await fetch('/api/encode/status');
        if (!response.ok) throw new Error('Failed to fetch encoding status');
        return response.json();
    },

    async getEncodingProfiles() {
        const response = await fetch('/api/encoding-profiles');
        if (!response.ok) throw new Error('Failed to fetch encoding profiles');
        return response.json();
    },

    async saveEncodingProfile(profileName, settings) {
        const response = await fetch(`/api/encoding-profiles/${encodeURIComponent(profileName)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
        if (!response.ok) throw new Error('Failed to save encoding profile');
        return response.json();
    },

    async deleteEncodingProfile(profileName) {
        const response = await fetch(`/api/encoding-profiles/${encodeURIComponent(profileName)}`, {
            method: 'DELETE'
        });
        if (!response.ok) throw new Error('Failed to delete encoding profile');
        return response.json();
    }
};

// WebSocket helper
class LogWebSocket {
    constructor(url = 'ws://localhost:8000/ws/logs') {
        this.url = url;
        this.ws = null;
        this.callbacks = [];
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 3000;
    }

    connect() {
        return new Promise((resolve, reject) => {
            try {
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const host = window.location.host;
                const finalUrl = `${protocol}//${host}/ws/logs`;

                this.ws = new WebSocket(finalUrl);

                this.ws.onopen = () => {
                    console.log('WebSocket connected');
                    this.reconnectAttempts = 0;
                    resolve();
                };

                this.ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        this.callbacks.forEach(cb => cb(data));
                    } catch (e) {
                        console.error('Failed to parse WebSocket message:', e);
                    }
                };

                this.ws.onerror = (error) => {
                    console.error('WebSocket error:', error);
                    reject(error);
                };

                this.ws.onclose = () => {
                    console.log('WebSocket disconnected');
                    this.attemptReconnect();
                };
            } catch (error) {
                reject(error);
            }
        });
    }

    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Reconnecting WebSocket (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
            setTimeout(() => this.connect(), this.reconnectDelay);
        }
    }

    onMessage(callback) {
        this.callbacks.push(callback);
    }

    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }

    close() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
}

// Logger utility
const Logger = {
    logs: [],
    maxLogs: 1000,

    add(type, message, color = 'inherit') {
        const timestamp = new Date().toLocaleTimeString();
        const entry = {
            type,
            message,
            color,
            timestamp,
            html: this.formatLogEntry(type, message, timestamp, color)
        };

        this.logs.push(entry);
        if (this.logs.length > this.maxLogs) {
            this.logs.shift();
        }

        return entry;
    },

    formatLogEntry(type, message, timestamp, color) {
        const timeHtml = `<span class="log-entry timestamp">[${timestamp}]</span>`;
        // Convert newlines to <br> tags and escape HTML
        const escapedMessage = escapeHtml(message).replace(/\n/g, '<br>');
        const contentHtml = `<span class="log-entry ${type}" style="color: ${color}">${escapedMessage}</span>`;
        return `<div class="log-line">${timeHtml} ${contentHtml}</div>`;
    },

    info(message) {
        return this.add('info', message);
    },

    success(message) {
        return this.add('success', message, '#6a9955');
    },

    warning(message) {
        return this.add('warning', message, '#dcdcaa');
    },

    error(message) {
        return this.add('error', message, '#f48771');
    },

    clear() {
        this.logs = [];
    }
};

// Responsive helper
const Responsive = {
    isMobile() {
        return window.innerWidth < 768;
    },

    isTablet() {
        return window.innerWidth >= 768 && window.innerWidth < 1024;
    },

    isDesktop() {
        return window.innerWidth >= 1024;
    },

    getLayoutMode() {
        if (this.isDesktop()) {
            return 'horizontal'; // Horizontal split
        } else {
            return 'vertical'; // Vertical split
        }
    }
};

// Create a global state manager
const State = {
    data: {
        config: null,
        mediaFiles: [],
        selectedFiles: new Set(),
        isScanning: false,
        isEncoding: false,
        encodingJobs: []
    },

    set(key, value) {
        const keys = key.split('.');
        let obj = this.data;
        for (let i = 0; i < keys.length - 1; i++) {
            obj = obj[keys[i]];
        }
        obj[keys[keys.length - 1]] = value;
    },

    get(key) {
        const keys = key.split('.');
        let obj = this.data;
        for (let k of keys) {
            obj = obj[k];
        }
        return obj;
    }
};

// Export for use in other files
window.Utils = {
    formatFileSize,
    formatDuration,
    formatBitrate,
    escapeHtml,
    debounce,
    throttle,
    API,
    LogWebSocket,
    Logger,
    Responsive,
    State
};
