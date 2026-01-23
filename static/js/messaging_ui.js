// messaging_ui.js - Modern Messaging UI Enhancements
class MessagingUI {
    constructor(messagingSystem) {
        this.messaging = messagingSystem;
        this.currentConversationId = null;
        this.userTypingTimeouts = new Map();
        this.init();
    }
    
    init() {
        console.log('🎨 Initializing Messaging UI...');
        
        // DOM Elements
        this.elements = {
            conversationsList: document.getElementById('conversationsList'),
            chatPanel: document.getElementById('chatPanel'),
            activeChat: document.getElementById('activeChat'),
            chatEmptyState: document.getElementById('chatEmptyState'),
            newConversationPanel: document.getElementById('newConversationPanel'),
            messagesContainer: document.getElementById('messagesContainer'),
            messageInput: document.getElementById('messageInput'),
            typingIndicator: document.getElementById('typingIndicator'),
            typingText: document.getElementById('typingText'),
            searchConversations: document.getElementById('searchConversations'),
            newChatSearch: document.getElementById('newChatSearch'),
            searchResults: document.getElementById('searchResults'),
            selectedUserInfo: document.getElementById('selectedUserInfo'),
            newMessageText: document.getElementById('newMessageText'),
            sendNewMessageBtn: document.getElementById('sendNewMessageBtn'),
            newConversationBtn: document.getElementById('newConversationBtn'),
            emptyStateNewChatBtn: document.getElementById('emptyStateNewChatBtn'),
            backToChatBtn: document.getElementById('backToChatBtn'),
            backToListBtn: document.getElementById('backToListBtn'),
            viewProfileBtn: document.getElementById('viewProfileBtn'),
            archiveChatBtn: document.getElementById('archiveChatBtn'),
            deleteChatBtn: document.getElementById('deleteChatBtn'),
            muteChatBtn: document.getElementById('muteChatBtn'),
            globalUnreadBadge: document.getElementById('globalUnreadBadge'),
            unreadFilterBadge: document.getElementById('unreadFilterBadge')
        };
        
        // Event Listeners
        this.setupEventListeners();
        
        // Initialize filter badges
        this.updateFilterBadges();
        
        // Handle URL parameters
        this.handleUrlParams();
    }
    
    setupEventListeners() {
        // New Conversation Button
        if (this.elements.newConversationBtn) {
            this.elements.newConversationBtn.addEventListener('click', () => this.showNewConversationPanel());
        }
        
        if (this.elements.emptyStateNewChatBtn) {
            this.elements.emptyStateNewChatBtn.addEventListener('click', () => this.showNewConversationPanel());
        }
        
        // Back buttons
        if (this.elements.backToChatBtn) {
            this.elements.backToChatBtn.addEventListener('click', () => this.hideNewConversationPanel());
        }
        
        if (this.elements.backToListBtn) {
            this.elements.backToListBtn.addEventListener('click', () => this.closeMobileChat());
        }
        
        // Conversation search
        if (this.elements.searchConversations) {
            let searchTimeout;
            this.elements.searchConversations.addEventListener('input', (e) => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    this.filterConversations(e.target.value);
                }, 300);
            });
        }
        
        // New chat search
        if (this.elements.newChatSearch) {
            let newSearchTimeout;
            this.elements.newChatSearch.addEventListener('input', (e) => {
                clearTimeout(newSearchTimeout);
                newSearchTimeout = setTimeout(() => {
                    this.searchUsers(e.target.value);
                }, 300);
            });
        }
        
        // Filter tabs
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const filter = e.currentTarget.dataset.filter;
                this.setActiveFilter(filter);
            });
        });
        
        // New message text area
        if (this.elements.newMessageText) {
            this.elements.newMessageText.addEventListener('input', (e) => {
                this.updateNewMessageCharCount(e.target.value.length);
                this.updateSendButtonState();
            });
        }
        
        // Send new message
        if (this.elements.sendNewMessageBtn) {
            this.elements.sendNewMessageBtn.addEventListener('click', () => this.sendNewMessage());
        }
        
        // Clear selection
        document.getElementById('clearSelectionBtn')?.addEventListener('click', () => {
            this.clearSelectedUser();
        });
        
        // Chat actions
        if (this.elements.viewProfileBtn) {
            this.elements.viewProfileBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.viewProfile();
            });
        }
        
        if (this.elements.archiveChatBtn) {
            this.elements.archiveChatBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.archiveConversation();
            });
        }
        
        if (this.elements.deleteChatBtn) {
            this.elements.deleteChatBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.deleteConversation();
            });
        }
        
        if (this.elements.muteChatBtn) {
            this.elements.muteChatBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggleMute();
            });
        }
        
        // Conversation item actions
        document.addEventListener('click', (e) => {
            // Archive chat from dropdown
            if (e.target.closest('.archive-chat')) {
                e.preventDefault();
                const conversationId = e.target.closest('.archive-chat').dataset.conversationId;
                this.archiveConversation(conversationId);
            }
            
            // Delete chat from dropdown
            if (e.target.closest('.delete-chat')) {
                e.preventDefault();
                const conversationId = e.target.closest('.delete-chat').dataset.conversationId;
                this.deleteConversation(conversationId);
            }
            
            // View profile from dropdown
            if (e.target.closest('.dropdown-item') && e.target.closest('.dropdown-item').href.includes('/profile/')) {
                // Let the link work normally
            }
        });
        
        // Window resize
        window.addEventListener('resize', () => this.handleResize());
        
        // Visibility change for online status
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.updateOnlineStatus(false);
            } else {
                this.updateOnlineStatus(true);
                this.refreshConversationList();
            }
        });
    }
    
    showNewConversationPanel() {
        this.elements.newConversationPanel.classList.add('active');
        this.elements.chatEmptyState.style.display = 'none';
        this.elements.activeChat.style.display = 'none';
        this.elements.newChatSearch.focus();
    }
    
    hideNewConversationPanel() {
        this.elements.newConversationPanel.classList.remove('active');
        this.showChatEmptyState();
        this.clearSelectedUser();
    }
    
    showChatEmptyState() {
        this.elements.chatEmptyState.style.display = 'flex';
        this.elements.activeChat.style.display = 'none';
    }
    
    showActiveChat() {
        this.elements.chatEmptyState.style.display = 'none';
        this.elements.activeChat.style.display = 'flex';
    }
    
    async searchUsers(query) {
        if (!query || query.length < 2) {
            this.showSearchPlaceholder();
            return;
        }
        
        try {
            this.showSearchLoading();
            
            const response = await fetch(`/chats/api/search-users/?q=${encodeURIComponent(query)}`);
            const data = await response.json();
            
            if (data.success && data.users && data.users.length > 0) {
                this.renderSearchResults(data.users);
            } else {
                this.showNoResults();
            }
        } catch (error) {
            console.error('Search error:', error);
            this.showSearchError();
        }
    }
    
    renderSearchResults(users) {
        const container = this.elements.searchResults;
        if (!container) return;
        
        container.innerHTML = '';
        
        // Group users by first letter
        const groupedUsers = users.reduce((groups, user) => {
            const firstLetter = user.name.charAt(0).toUpperCase();
            if (!groups[firstLetter]) groups[firstLetter] = [];
            groups[firstLetter].push(user);
            return groups;
        }, {});
        
        // Render groups
        Object.keys(groupedUsers).sort().forEach(letter => {
            const groupDiv = document.createElement('div');
            groupDiv.className = 'user-group';
            groupDiv.innerHTML = `<div class="group-letter">${letter}</div>`;
            
            groupedUsers[letter].forEach(user => {
                const userElement = this.createUserResultElement(user);
                groupDiv.appendChild(userElement);
            });
            
            container.appendChild(groupDiv);
        });
    }
    
    createUserResultElement(user) {
        const div = document.createElement('div');
        div.className = 'user-result';
        div.dataset.userId = user.id;
        
        div.innerHTML = `
            <div class="user-avatar">
                <img src="${user.avatar}" alt="${user.name}" onerror="this.src='/static/images/default-avatar.svg'">
            </div>
            <div class="user-info">
                <h6>${user.name}</h6>
                <span>@${user.username}</span>
            </div>
        `;
        
        div.addEventListener('click', () => this.selectUser(user));
        return div;
    }
    
    selectUser(user) {
        this.selectedUser = user;
        
        // Update UI
        document.querySelectorAll('.user-result').forEach(el => {
            el.classList.remove('selected');
            if (parseInt(el.dataset.userId) === user.id) {
                el.classList.add('selected');
            }
        });
        
        // Show selected user info
        this.elements.selectedUserInfo.style.display = 'block';
        document.getElementById('selectedUserName').textContent = user.name;
        document.getElementById('selectedUserUsername').textContent = `@${user.username}`;
        document.getElementById('selectedUserAvatar').src = user.avatar;
        
        // Enable send button if message exists
        this.updateSendButtonState();
    }
    
    clearSelectedUser() {
        this.selectedUser = null;
        this.elements.selectedUserInfo.style.display = 'none';
        this.elements.newMessageText.value = '';
        this.elements.sendNewMessageBtn.disabled = true;
        document.querySelectorAll('.user-result').forEach(el => {
            el.classList.remove('selected');
        });
    }
    
    async sendNewMessage() {
        if (!this.selectedUser) {
            this.showToast('Please select a recipient', 'error');
            return;
        }
        
        const message = this.elements.newMessageText.value.trim();
        if (!message) {
            this.showToast('Please enter a message', 'error');
            return;
        }
        
        const sendBtn = this.elements.sendNewMessageBtn;
        const originalText = sendBtn.innerHTML;
        sendBtn.disabled = true;
        sendBtn.innerHTML = '<i class="bi bi-hourglass"></i>';
        
        try {
            const response = await fetch('/chats/api/send-message/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCookie('csrftoken'),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    recipient_id: this.selectedUser.id,
                    message: message
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showToast('Message sent!', 'success');
                
                // Close new conversation panel and open the new conversation
                setTimeout(() => {
                    this.hideNewConversationPanel();
                    if (data.conversation_id) {
                        this.openConversation(data.conversation_id, this.selectedUser.name);
                    }
                }, 1000);
            } else {
                throw new Error(data.error || 'Failed to send message');
            }
        } catch (error) {
            console.error('Error sending message:', error);
            this.showToast('Failed to send message', 'error');
            sendBtn.disabled = false;
        } finally {
            sendBtn.innerHTML = originalText;
        }
    }
    
    async openConversation(conversationId, participantName) {
        this.currentConversationId = conversationId;
        
        // Update UI
        this.showActiveChat();
        this.updateActiveConversationUI(conversationId);
        
        // Load conversation content
        await this.loadConversation(conversationId, participantName);
        
        // Mark as read
        await this.markConversationAsRead(conversationId);
        
        // Update filter badges
        this.updateFilterBadges();
    }
    
    updateActiveConversationUI(conversationId) {
        // Update conversation list item
        document.querySelectorAll('.conversation-item').forEach(item => {
            item.classList.remove('active');
            if (parseInt(item.dataset.conversationId) === conversationId) {
                item.classList.add('active');
                
                // Clear unread badge
                const unreadBadge = item.querySelector('.conversation-unread');
                if (unreadBadge) {
                    unreadBadge.remove();
                    item.classList.remove('unread');
                }
            }
        });
        
        // Update mobile UI
        if (window.innerWidth < 992) {
            this.elements.chatPanel.classList.add('mobile-active');
        }
    }
    
    async loadConversation(conversationId, participantName) {
        const container = this.elements.messagesContainer;
        if (!container) return;
        
        // Show loading
        container.innerHTML = `
            <div class="chat-loading">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p>Loading conversation...</p>
            </div>
        `;
        
        try {
            const response = await fetch(`/chats/api/get-new-messages/${conversationId}/?last_id=0`);
            const data = await response.json();
            
            if (data.success) {
                this.renderMessages(data.new_messages || []);
                
                // Update participant info
                this.updateChatHeader(participantName, data.participant_info);
                
                // Start polling for new messages
                this.startMessagePolling(conversationId);
            } else {
                throw new Error(data.error || 'Failed to load conversation');
            }
        } catch (error) {
            console.error('Error loading conversation:', error);
            container.innerHTML = `
                <div class="chat-error">
                    <i class="bi bi-exclamation-triangle"></i>
                    <p>Failed to load conversation</p>
                    <button class="btn btn-sm btn-primary" onclick="messagingUI.loadConversation(${conversationId}, '${participantName}')">
                        Try Again
                    </button>
                </div>
            `;
        }
    }
    
    renderMessages(messages) {
        const container = this.elements.messagesContainer;
        if (!container) return;
        
        if (messages.length === 0) {
            container.innerHTML = `
                <div class="no-messages">
                    <i class="bi bi-chat-dots"></i>
                    <p>No messages yet. Start the conversation!</p>
                </div>
            `;
            return;
        }
        
        // Group messages by date and sender
        const groupedMessages = this.groupMessages(messages);
        
        let html = '';
        
        groupedMessages.forEach(group => {
            // Date separator
            html += `<div class="message-date"><span>${group.date}</span></div>`;
            
            // Messages in group
            group.messages.forEach(msg => {
                const isOwn = msg.is_own_message;
                const time = new Date(msg.timestamp).toLocaleTimeString([], { 
                    hour: '2-digit', 
                    minute: '2-digit' 
                });
                
                const statusIcon = isOwn ? 
                    (msg.is_read ? 'bi-check2-all text-primary' : 'bi-check2 text-muted') : 
                    '';
                
                html += `
                    <div class="message-bubble ${isOwn ? 'sent' : 'received'}">
                        ${!isOwn ? `
                            <div class="message-avatar">
                                <img src="${msg.sender_avatar}" alt="${msg.sender_name}">
                            </div>
                        ` : ''}
                        <div class="message-content">
                            <div class="message-text">${this.formatMessageContent(msg.content)}</div>
                            <div class="message-meta">
                                <span class="message-time">${time}</span>
                                ${statusIcon ? `<i class="bi ${statusIcon}"></i>` : ''}
                            </div>
                        </div>
                        ${isOwn ? `
                            <div class="message-avatar">
                                <img src="${msg.sender_avatar}" alt="You">
                            </div>
                        ` : ''}
                    </div>
                `;
            });
        });
        
        container.innerHTML = html;
        this.scrollToBottom();
    }
    
    groupMessages(messages) {
        const groups = [];
        let currentGroup = null;
        
        messages.forEach(msg => {
            const date = new Date(msg.timestamp).toDateString();
            const isOwn = msg.is_own_message;
            
            if (!currentGroup || currentGroup.date !== date) {
                currentGroup = {
                    date: this.formatDate(new Date(msg.timestamp)),
                    messages: []
                };
                groups.push(currentGroup);
            }
            
            currentGroup.messages.push(msg);
        });
        
        return groups;
    }
    
    formatDate(date) {
        const today = new Date();
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);
        
        if (date.toDateString() === today.toDateString()) {
            return 'Today';
        } else if (date.toDateString() === yesterday.toDateString()) {
            return 'Yesterday';
        } else {
            return date.toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric',
                year: date.getFullYear() !== today.getFullYear() ? 'numeric' : undefined
            });
        }
    }
    
    formatMessageContent(content) {
        // Convert URLs to links
        const urlRegex = /(https?:\/\/[^\s]+)/g;
        return content.replace(urlRegex, (url) => {
            return `<a href="${url}" target="_blank" rel="noopener noreferrer" class="message-link">${url}</a>`;
        });
    }
    
    updateChatHeader(participantName, participantInfo) {
        const nameEl = document.getElementById('chatParticipantName');
        const statusEl = document.getElementById('chatParticipantStatus');
        const avatarEl = document.getElementById('chatParticipantAvatar');
        
        if (nameEl) nameEl.textContent = participantName;
        if (avatarEl && participantInfo?.avatar) {
            avatarEl.src = participantInfo.avatar;
        }
        
        // Update status
        if (participantInfo?.is_online) {
            statusEl.textContent = 'Online';
            statusEl.style.color = 'var(--success-color)';
        } else if (participantInfo?.last_seen) {
            statusEl.textContent = `Last seen ${this.formatLastSeen(participantInfo.last_seen)}`;
            statusEl.style.color = 'var(--text-secondary)';
        }
    }
    
    async markConversationAsRead(conversationId) {
        try {
            await fetch(`/chats/api/mark-read/${conversationId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCookie('csrftoken'),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            // Update UI
            this.updateUnreadCounts();
        } catch (error) {
            console.error('Error marking as read:', error);
        }
    }
    
    startMessagePolling(conversationId) {
        // Clear existing interval
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
        }
        
        // Poll every 3 seconds
        this.pollingInterval = setInterval(async () => {
            if (this.currentConversationId === conversationId) {
                await this.pollNewMessages(conversationId);
                await this.pollTypingIndicator(conversationId);
            }
        }, 3000);
    }
    
    async pollNewMessages(conversationId) {
        try {
            const lastMessageId = this.getLastMessageId();
            const response = await fetch(`/chats/api/get-new-messages/${conversationId}/?last_id=${lastMessageId}`);
            const data = await response.json();
            
            if (data.success && data.new_messages && data.new_messages.length > 0) {
                // Add new messages
                this.appendMessages(data.new_messages);
                
                // Mark as read
                await this.markConversationAsRead(conversationId);
                
                // Play notification sound if not focused
                if (!document.hasFocus()) {
                    this.playNotificationSound();
                }
            }
        } catch (error) {
            console.error('Error polling messages:', error);
        }
    }
    
    async pollTypingIndicator(conversationId) {
        try {
            const response = await fetch(`/chats/api/check-typing/${conversationId}/`);
            const data = await response.json();
            
            if (data.typing && data.user_name) {
                this.showTypingIndicator(data.user_name);
            } else {
                this.hideTypingIndicator();
            }
        } catch (error) {
            // Silent fail
        }
    }
    
    showTypingIndicator(userName) {
        this.elements.typingIndicator.style.display = 'flex';
        this.elements.typingText.textContent = `${userName} is typing...`;
        
        // Clear previous timeout
        if (this.typingTimeout) {
            clearTimeout(this.typingTimeout);
        }
        
        // Hide after 3 seconds
        this.typingTimeout = setTimeout(() => {
            this.hideTypingIndicator();
        }, 3000);
    }
    
    hideTypingIndicator() {
        this.elements.typingIndicator.style.display = 'none';
    }
    
    async sendTypingIndicator() {
        if (!this.currentConversationId) return;
        
        // Clear previous timeout
        if (this.userTypingTimeouts.has(this.currentConversationId)) {
            clearTimeout(this.userTypingTimeouts.get(this.currentConversationId));
        }
        
        // Send typing indicator
        try {
            await fetch(`/chats/api/send-typing/${this.currentConversationId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCookie('csrftoken'),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
        } catch (error) {
            console.error('Error sending typing indicator:', error);
        }
        
        // Set timeout to prevent excessive requests
        const timeout = setTimeout(() => {}, 2000);
        this.userTypingTimeouts.set(this.currentConversationId, timeout);
    }
    
    async archiveConversation(conversationId = null) {
        const id = conversationId || this.currentConversationId;
        if (!id) return;
        
        const confirmed = await this.showConfirmation(
            'Archive Conversation',
            'Are you sure you want to archive this conversation? You can find it in the Archived folder.'
        );
        
        if (!confirmed) return;
        
        try {
            const response = await fetch(`/chats/api/delete-conversation/${id}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCookie('csrftoken'),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showToast('Conversation archived', 'success');
                
                // Remove from UI
                const item = document.querySelector(`[data-conversation-id="${id}"]`);
                if (item) item.remove();
                
                // If this was the active conversation, show empty state
                if (this.currentConversationId === id) {
                    this.showChatEmptyState();
                    this.currentConversationId = null;
                }
                
                // Update counts
                this.updateUnreadCounts();
            }
        } catch (error) {
            console.error('Error archiving conversation:', error);
            this.showToast('Failed to archive conversation', 'error');
        }
    }
    
    async deleteConversation(conversationId = null) {
        const id = conversationId || this.currentConversationId;
        if (!id) return;
        
        const confirmed = await this.showConfirmation(
            'Delete Conversation',
            'Are you sure you want to delete this conversation? This action cannot be undone.'
        );
        
        if (!confirmed) return;
        
        try {
            const response = await fetch(`/chats/api/delete-conversation/${id}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCookie('csrftoken'),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showToast('Conversation deleted', 'success');
                
                // Remove from UI
                const item = document.querySelector(`[data-conversation-id="${id}"]`);
                if (item) item.remove();
                
                // If this was the active conversation, show empty state
                if (this.currentConversationId === id) {
                    this.showChatEmptyState();
                    this.currentConversationId = null;
                }
                
                // Update counts
                this.updateUnreadCounts();
            }
        } catch (error) {
            console.error('Error deleting conversation:', error);
            this.showToast('Failed to delete conversation', 'error');
        }
    }
    
    viewProfile() {
        if (!this.currentConversationId) return;
        
        const conversationItem = document.querySelector(`[data-conversation-id="${this.currentConversationId}"]`);
        if (conversationItem) {
            const participantUsername = conversationItem.dataset.participantUsername;
            if (participantUsername) {
                window.open(`/profile/${participantUsername}/`, '_blank');
            }
        }
    }
    
    async toggleMute() {
        if (!this.currentConversationId) return;
        
        try {
            const response = await fetch(`/chats/api/mute-conversation/${this.currentConversationId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCookie('csrftoken'),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                const action = data.status === 'muted' ? 'muted' : 'unmuted';
                this.showToast(`Conversation ${action}`, 'success');
                
                // Update button text
                const btn = this.elements.muteChatBtn;
                const icon = btn.querySelector('i');
                const text = btn.querySelector('span');
                
                if (data.status === 'muted') {
                    icon.className = 'bi bi-bell me-2';
                    text.textContent = 'Unmute Notifications';
                } else {
                    icon.className = 'bi bi-bell-slash me-2';
                    text.textContent = 'Mute Notifications';
                }
            }
        } catch (error) {
            console.error('Error toggling mute:', error);
            this.showToast('Failed to update notifications', 'error');
        }
    }
    
    filterConversations(searchTerm) {
        const items = document.querySelectorAll('.conversation-item');
        const term = searchTerm.toLowerCase().trim();
        
        items.forEach(item => {
            const name = item.querySelector('.conversation-name').textContent.toLowerCase();
            const message = item.querySelector('.conversation-message').textContent.toLowerCase();
            const listing = item.querySelector('.conversation-listing')?.textContent.toLowerCase() || '';
            
            const matches = name.includes(term) || 
                           message.includes(term) || 
                           listing.includes(term);
            
            item.style.display = matches ? '' : 'none';
        });
    }
    
    setActiveFilter(filter) {
        // Update active button
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.dataset.filter === filter) {
                btn.classList.add('active');
            }
        });
        
        // Filter conversations
        const items = document.querySelectorAll('.conversation-item');
        
        items.forEach(item => {
            switch(filter) {
                case 'all':
                    item.style.display = '';
                    break;
                case 'unread':
                    item.style.display = item.classList.contains('unread') ? '' : 'none';
                    break;
                case 'with-listing':
                    const hasListing = item.querySelector('.conversation-listing');
                    item.style.display = hasListing ? '' : 'none';
                    break;
            }
        });
    }
    
    updateUnreadCounts() {
        // Count total unread
        const unreadItems = document.querySelectorAll('.conversation-item.unread');
        const totalUnread = Array.from(unreadItems).reduce((total, item) => {
            const badge = item.querySelector('.conversation-unread');
            return total + (badge ? parseInt(badge.textContent) || 1 : 1);
        }, 0);
        
        // Update global badge
        if (this.elements.globalUnreadBadge) {
            if (totalUnread > 0) {
                this.elements.globalUnreadBadge.textContent = totalUnread > 99 ? '99+' : totalUnread;
                this.elements.globalUnreadBadge.style.display = 'flex';
            } else {
                this.elements.globalUnreadBadge.style.display = 'none';
            }
        }
        
        // Update filter badge
        if (this.elements.unreadFilterBadge) {
            if (unreadItems.length > 0) {
                this.elements.unreadFilterBadge.textContent = unreadItems.length;
                this.elements.unreadFilterBadge.style.display = 'flex';
            } else {
                this.elements.unreadFilterBadge.style.display = 'none';
            }
        }
        
        // Update browser title
        document.title = totalUnread > 0 ? 
            `(${totalUnread}) Messages - Baysoko` : 
            'Messages - Baysoko';
    }
    
    updateFilterBadges() {
        this.updateUnreadCounts();
    }
    
    async updateOnlineStatus(isOnline) {
        try {
            await fetch('/chats/api/update-online-status/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCookie('csrftoken')
                },
                body: JSON.stringify({ is_online: isOnline })
            });
        } catch (error) {
            console.error('Error updating online status:', error);
        }
    }
    
    async refreshConversationList() {
        try {
            const response = await fetch('/chats/api/conversations-list/');
            const data = await response.json();
            
            if (data.success) {
                // Update conversation list
                this.updateConversationList(data.conversations);
                
                // Update online statuses
                this.updateOnlineStatuses();
            }
        } catch (error) {
            console.error('Error refreshing conversations:', error);
        }
    }
    
    updateConversationList(conversations) {
        // This would update the conversation list with new data
        // For now, just update online statuses
        this.updateOnlineStatuses();
    }
    
    updateOnlineStatuses() {
        document.querySelectorAll('.conversation-item').forEach(item => {
            const participantId = item.dataset.participantId;
            // In a real app, you'd fetch online status from server
            // For now, we'll simulate by checking last activity
            const lastSeenEl = item.querySelector('.last-seen');
            if (lastSeenEl) {
                // Update last seen time
                const now = new Date();
                const randomMinutes = Math.floor(Math.random() * 60);
                const lastSeen = new Date(now - randomMinutes * 60000);
                lastSeenEl.textContent = `Last seen ${this.formatLastSeen(lastSeen)}`;
            }
        });
    }
    
    formatLastSeen(timestamp) {
        const now = new Date();
        const diffMs = now - new Date(timestamp);
        const diffMins = Math.floor(diffMs / 60000);
        
        if (diffMins < 1) return 'just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
        return `${Math.floor(diffMins / 1440)}d ago`;
    }
    
    // UI Helper Methods
    showSearchPlaceholder() {
        if (this.elements.searchResults) {
            this.elements.searchResults.innerHTML = `
                <div class="search-placeholder">
                    <i class="bi bi-search"></i>
                    <p>Search for users to start a conversation</p>
                </div>
            `;
        }
    }
    
    showSearchLoading() {
        if (this.elements.searchResults) {
            this.elements.searchResults.innerHTML = `
                <div class="search-loading">
                    <div class="spinner-border spinner-border-sm"></div>
                    <p>Searching...</p>
                </div>
            `;
        }
    }
    
    showNoResults() {
        if (this.elements.searchResults) {
            this.elements.searchResults.innerHTML = `
                <div class="search-placeholder">
                    <i class="bi bi-search"></i>
                    <p>No users found. Try a different search.</p>
                </div>
            `;
        }
    }
    
    showSearchError() {
        if (this.elements.searchResults) {
            this.elements.searchResults.innerHTML = `
                <div class="search-error">
                    <i class="bi bi-exclamation-triangle"></i>
                    <p>Error searching users. Please try again.</p>
                </div>
            `;
        }
    }
    
    updateNewMessageCharCount(length) {
        const charCount = document.getElementById('newCharCount');
        if (charCount) {
            charCount.textContent = `${length}/1000`;
            
            if (length > 1000) {
                charCount.style.color = 'var(--danger-color)';
            } else {
                charCount.style.color = 'var(--text-secondary)';
            }
        }
    }
    
    updateSendButtonState() {
        if (!this.elements.sendNewMessageBtn) return;
        
        const hasMessage = this.elements.newMessageText.value.trim().length > 0;
        const hasUser = !!this.selectedUser;
        const withinLimit = this.elements.newMessageText.value.length <= 1000;
        
        this.elements.sendNewMessageBtn.disabled = !(hasMessage && hasUser && withinLimit);
    }
    
    getLastMessageId() {
        const messages = this.elements.messagesContainer.querySelectorAll('.message-bubble');
        if (messages.length === 0) return 0;
        
        const lastMessage = messages[messages.length - 1];
        return parseInt(lastMessage.dataset.messageId) || 0;
    }
    
    appendMessages(messages) {
        const container = this.elements.messagesContainer;
        if (!container) return;
        
        messages.forEach(msg => {
            const isOwn = msg.is_own_message;
            const time = new Date(msg.timestamp).toLocaleTimeString([], { 
                hour: '2-digit', 
                minute: '2-digit' 
            });
            
            const statusIcon = isOwn ? 
                (msg.is_read ? 'bi-check2-all text-primary' : 'bi-check2 text-muted') : 
                '';
            
            const messageEl = document.createElement('div');
            messageEl.className = `message-bubble ${isOwn ? 'sent' : 'received'}`;
            messageEl.dataset.messageId = msg.id;
            messageEl.style.animation = 'messageAppear 0.3s ease';
            
            messageEl.innerHTML = `
                ${!isOwn ? `
                    <div class="message-avatar">
                        <img src="${msg.sender_avatar}" alt="${msg.sender_name}">
                    </div>
                ` : ''}
                <div class="message-content">
                    <div class="message-text">${this.formatMessageContent(msg.content)}</div>
                    <div class="message-meta">
                        <span class="message-time">${time}</span>
                        ${statusIcon ? `<i class="bi ${statusIcon}"></i>` : ''}
                    </div>
                </div>
                ${isOwn ? `
                    <div class="message-avatar">
                        <img src="${msg.sender_avatar}" alt="You">
                    </div>
                ` : ''}
            `;
            
            container.appendChild(messageEl);
        });
        
        this.scrollToBottom();
    }
    
    scrollToBottom() {
        setTimeout(() => {
            const container = this.elements.messagesContainer;
            if (container) {
                container.scrollTop = container.scrollHeight;
            }
        }, 100);
    }
    
    closeMobileChat() {
        this.elements.chatPanel.classList.remove('mobile-active');
        this.showChatEmptyState();
        this.currentConversationId = null;
    }
    
    handleResize() {
        if (window.innerWidth >= 992) {
            this.elements.chatPanel.classList.remove('mobile-active');
        }
    }
    
    handleUrlParams() {
        const urlParams = new URLSearchParams(window.location.search);
        const openConversationId = urlParams.get('open');
        
        if (openConversationId) {
            // Find conversation and open it
            const conversationItem = document.querySelector(`[data-conversation-id="${openConversationId}"]`);
            if (conversationItem) {
                const participantName = conversationItem.querySelector('.conversation-name').textContent.split('\n')[0];
                setTimeout(() => {
                    this.openConversation(parseInt(openConversationId), participantName);
                }, 500);
            }
        }
    }
    
    async showConfirmation(title, message) {
        return new Promise((resolve) => {
            const modal = new bootstrap.Modal(document.getElementById('confirmationModal'));
            document.getElementById('confirmationTitle').textContent = title;
            document.getElementById('confirmationBody').textContent = message;
            
            const confirmBtn = document.getElementById('confirmActionBtn');
            const originalHandler = confirmBtn.onclick;
            
            confirmBtn.onclick = () => {
                modal.hide();
                resolve(true);
            };
            
            modal._element.addEventListener('hidden.bs.modal', () => {
                confirmBtn.onclick = originalHandler;
                resolve(false);
            });
            
            modal.show();
        });
    }
    
    showToast(message, type = 'success') {
        // Create toast element
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-bg-${type} border-0`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        
        const icon = type === 'success' ? 'bi-check-circle-fill' :
                    type === 'error' ? 'bi-exclamation-triangle-fill' :
                    'bi-info-circle-fill';
        
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <i class="bi ${icon} me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        
        // Add to container
        const container = document.getElementById('messagingErrorContainer');
        if (container) {
            container.appendChild(toast);
            
            // Initialize and show
            const bsToast = new bootstrap.Toast(toast, {
                autohide: true,
                delay: 3000
            });
            bsToast.show();
            
            // Remove after hide
            toast.addEventListener('hidden.bs.toast', () => {
                toast.remove();
            });
        }
    }
    
    playNotificationSound() {
        try {
            const audio = new Audio('/static/sounds/notification.mp3');
            audio.volume = 0.3;
            audio.play().catch(() => {
                // Silent fail if audio can't play
            });
        } catch (error) {
            // Silent fail
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
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    if (window.messaging && document.getElementById('conversationsList')) {
        console.log('🎨 Initializing Messaging UI...');
        window.messagingUI = new MessagingUI(window.messaging);
    }
    
    // Global helper functions
    window.startNewConversation = function() {
        if (window.messagingUI) {
            window.messagingUI.showNewConversationPanel();
        }
    };
    
    window.closeMobileChat = function() {
        if (window.messagingUI) {
            window.messagingUI.closeMobileChat();
        }
    };
    
    window.loadConversation = function(conversationId, participantName) {
        if (window.messagingUI) {
            window.messagingUI.openConversation(conversationId, participantName);
        }
    };
    
    window.attachFile = function() {
        // Implement file attachment
        console.log('Attach file clicked');
    };
    
    window.toggleEmojiPicker = function() {
        // Implement emoji picker
        console.log('Emoji picker clicked');
    };
    
    window.startVoiceCall = function() {
        // Implement voice call
        console.log('Start voice call');
    };
    
    window.startVideoCall = function() {
        // Implement video call
        console.log('Start video call');
    };
});