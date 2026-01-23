// static/js/messaging-core.js
class MessagingCore {
    constructor() {
        this.currentUserId = null;
        this.init();
    }
    
    init() {
        // Get current user ID from meta tag or Django template
        const userMeta = document.querySelector('meta[name="current-user-id"]');
        this.currentUserId = userMeta ? parseInt(userMeta.content) : null;
        
        // If not found in meta, try to get from Django template variable
        if (!this.currentUserId && window.currentUserId) {
            this.currentUserId = window.currentUserId;
        }
        
        // Store reference in window
        window.messagingCore = this;
    }
    
    async updateUnreadCounts() {
        try {
            const response = await this.safeFetch('/chats/api/unread-messages-count/');
            
            // Update navbar badge
            const unreadBadge = document.getElementById('unreadMessagesBadge');
            if (unreadBadge) {
                if (response.count > 0) {
                    unreadBadge.textContent = response.count > 99 ? '99+' : response.count;
                    unreadBadge.classList.remove('d-none');
                } else {
                    unreadBadge.classList.add('d-none');
                }
            }
            
            // Update conversation list unread counts if available
            if (response.conversations) {
                response.conversations.forEach(conv => {
                    const convItem = document.querySelector(`[data-conversation-id="${conv.id}"]`);
                    if (convItem) {
                        if (conv.unread_count > 0) {
                            convItem.classList.add('unread');
                            let unreadBadge = convItem.querySelector('.conversation-unread');
                            if (!unreadBadge) {
                                unreadBadge = document.createElement('div');
                                unreadBadge.className = 'conversation-unread';
                                const preview = convItem.querySelector('.conversation-preview');
                                if (preview) {
                                    preview.appendChild(unreadBadge);
                                }
                            }
                            unreadBadge.textContent = conv.unread_count > 99 ? '99+' : conv.unread_count;
                        } else {
                            convItem.classList.remove('unread');
                            const unreadBadge = convItem.querySelector('.conversation-unread');
                            if (unreadBadge) unreadBadge.remove();
                        }
                    }
                });
            }
            
            return response.count || 0;
        } catch (error) {
            console.error('Error updating unread counts:', error);
            return 0;
        }
    }
    
    async safeFetch(url, options = {}) {
        try {
            // Add CSRF token for same-origin POST requests
            if (url.startsWith('/') && (!options.method || options.method === 'POST' || options.method === 'PUT' || options.method === 'DELETE' || options.method === 'PATCH')) {
                options.headers = {
                    ...options.headers,
                    'X-CSRFToken': this.getCookie('csrftoken'),
                    'X-Requested-With': 'XMLHttpRequest'
                };
            }
            
            const response = await fetch(url, options);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            // Check if response is JSON
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            }
            
            // If not JSON, return as text
            return await response.text();
        } catch (error) {
            console.error(`Fetch error for ${url}:`, error);
            throw error;
        }
    }
    
    getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    
    showToast(message, type = 'success') {
        // Check if global toast function exists
        if (window.showToast) {
            window.showToast(message, type);
        } else {
            // Fallback toast
            const toast = document.createElement('div');
            toast.className = `alert alert-${type === 'success' ? 'success' : 'danger'} alert-dismissible fade show`;
            toast.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 9999;
                min-width: 300px;
                animation: slideInRight 0.3s ease;
            `;
            toast.innerHTML = `
                ${type === 'success' ? '<i class="bi bi-check-circle me-2"></i>' : '<i class="bi bi-exclamation-triangle me-2"></i>'}
                ${message}
                <button type="button" class="btn-close" onclick="this.parentElement.remove()"></button>
            `;
            
            document.body.appendChild(toast);
            
            // Auto-remove after 5 seconds
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 5000);
        }
    }
    
    formatTime(timestamp) {
        if (!timestamp) return '';
        
        try {
            const date = new Date(timestamp);
            const now = new Date();
            const diffMs = now - date;
            const diffMins = Math.floor(diffMs / 60000);
            
            if (diffMins < 1) return 'Just now';
            if (diffMins < 60) return `${diffMins}m`;
            
            const diffHours = Math.floor(diffMins / 60);
            if (diffHours < 24) return `${diffHours}h`;
            
            return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
        } catch (e) {
            return '';
        }
    }
    
    truncateText(text, maxLength) {
        if (!text) return '';
        return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    }
    
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new MessagingCore();
});