// static/js/messaging.js - COMPLETE UPDATED VERSION WITH ALL FIXES
class MessagingSystem {
    constructor() {
        // State
        this.state = {
            currentConversationId: null,
            currentParticipant: null,
            currentParticipantId: null,
            currentParticipantAvatar: null,
            conversations: [],
            messages: new Map(),
            onlineUsers: new Set(),
            unreadCount: 0,
            isMobile: window.innerWidth < 992,
            isTyping: false,
            userId: null,
            pollingEnabled: true,
            activePolling: false,
            tempMessages: new Map(),
            messageStatusPolling: new Map(),
            typingTimeouts: new Map(),
            lastMessageId: 0,
            initialLoadComplete: false,
            isOnline: navigator.onLine,
            newConversationRecipient: null,
            processedMessageIds: new Set(),
            pendingMessages: new Map(),
            userStatusCache: new Map(),
            lastSeenCache: new Map(),
            initialized: false,
            autoOpenConversationId: null,
            isDarkMode: document.documentElement.getAttribute('data-theme') === 'dark' || 
                        document.body.classList.contains('dark-mode')
        };

        // Configuration
        this.config = {
            pollInterval: 5000,
            typingTimeout: 3000,
            statusPollInterval: 5000,
            maxMessageLength: 1000,
            maxFileSize: 25 * 1024 * 1024,
            allowedFileTypes: ['image/jpeg', 'image/png', 'image/gif', 'application/pdf'],
            onlineThreshold: 180000
        };

        // Intervals and timeouts
        this.intervals = {
            messages: null,
            typing: null,
            conversations: null,
            online: null,
            status: null,
            conversationListSort: null
        };

        this.timeouts = {
            typing: null,
            search: null,
            scroll: null,
            statusUpdate: null,
            duplicateCheck: null,
            themeCheck: null
        };

        // Event listeners for cleanup
        this.eventListeners = [];
    }

    // Initialization
    init() {
        console.log('🚀 Initializing Enhanced Messaging System...');
        
        if (this.state.initialized) return;
        this.state.initialized = true;
        
        this.state.userId = this.getUserId();
        this.setupEventListeners();
        this.loadInitialData();
        this.setupPolling();
        this.handleUrlParams();
        this.setupNetworkListeners();
        this.setupThemeDetection();
        
        // Update mobile detection
        this.updateMobileDetection();
        window.addEventListener('resize', () => this.updateMobileDetection());
    }

    updateMobileDetection() {
        this.state.isMobile = window.innerWidth < 992;
    }

    setupEventListeners() {
        // Core event listeners
        const listeners = [
            // New conversation
            { element: document.getElementById('newConversationBtn'), type: 'click', handler: () => this.showNewConversation() },
            { element: document.getElementById('emptyStateNewChatBtn'), type: 'click', handler: () => this.showNewConversation() },
            
            // Back buttons
            { element: document.getElementById('backToChatBtn'), type: 'click', handler: () => this.hideNewConversation() },
            { element: document.getElementById('backToListBtn'), type: 'click', handler: () => this.closeActiveChat() },
            
            // Search conversations
            { element: document.getElementById('searchConversations'), type: 'input', handler: (e) => {
                clearTimeout(this.timeouts.search);
                this.timeouts.search = setTimeout(() => this.filterConversations(e.target.value), 300);
            }},
            
            // Filter tabs
            { elements: document.querySelectorAll('.filter-btn'), type: 'click', handler: (e) => {
                const filter = e.currentTarget.dataset.filter;
                this.setActiveFilter(filter);
            }, multiple: true },
            
            // Conversation item clicks
            { element: document, type: 'click', handler: (e) => {
                const convItem = e.target.closest('.conversation-item');
                if (convItem) {
                    const convId = parseInt(convItem.dataset.conversationId);
                    const participantName = convItem.dataset.participantName;
                    const participantId = convItem.dataset.participantId;
                    const participantAvatar = convItem.dataset.participantAvatar;
                    
                    // Open the existing conversation
                    this.openConversation(convId, participantName, participantId, participantAvatar);
                    
                    // Hide new conversation panel if open
                    this.hideNewConversation();
                    
                    // Update URL for mobile back button
                    if (this.state.isMobile) {
                        window.history.pushState({ chatOpen: true }, '', `?open=${convId}`);
                    }
                }
            }},
            
            // Message input
            { element: document, type: 'keydown', handler: (e) => {
                if (e.target.id === 'messageInput' && e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendCurrentMessage();
                }
            }},
            
            { element: document, type: 'input', handler: (e) => {
                if (e.target.id === 'messageInput') {
                    this.handleTyping();
                    this.updateCharCount(e.target, 'messageLength');
                }
                if (e.target.id === 'newMessageText') {
                    this.updateCharCount(e.target, 'newCharCount');
                }
            }},
            
            // Send buttons
            { element: document.getElementById('sendMessageBtn'), type: 'click', handler: () => this.sendCurrentMessage() },
            { element: document.getElementById('sendNewMessageBtn'), type: 'click', handler: () => this.sendNewMessage() },
            
            // Clear selection
            { element: document.getElementById('clearSelectionBtn'), type: 'click', handler: () => this.clearRecipientSelection() },
            
            // New conversation search
            { element: document.getElementById('newChatSearch'), type: 'input', handler: (e) => {
                clearTimeout(this.timeouts.search);
                this.timeouts.search = setTimeout(() => this.searchUsers(e.target.value), 300);
            }},
            
            // Window resize
            { element: window, type: 'resize', handler: () => this.handleResize() },
            
            // Popstate for mobile back button
            { element: window, type: 'popstate', handler: (e) => {
                if (this.state.isMobile) {
                    const urlParams = new URLSearchParams(window.location.search);
                    const isNewConversation = urlParams.get('new');
                    const openConversation = urlParams.get('open');
                    
                    if (openConversation && this.state.currentConversationId) {
                        this.closeActiveChat();
                    } else if (isNewConversation && document.getElementById('newConversationPanel').style.display === 'flex') {
                        this.hideNewConversation();
                    }
                }
            }},
            
            // User result clicks for new conversation
            { element: document, type: 'click', handler: (e) => {
                const userResult = e.target.closest('.user-result');
                if (userResult) {
                    const userId = userResult.dataset.userId;
                    const userName = userResult.dataset.userName;
                    this.handleUserSelection(userId, userName);
                }
            }}
        ];

        // Add all listeners
        listeners.forEach(config => {
            if (config.multiple && config.elements) {
                config.elements.forEach(el => {
                    el.addEventListener(config.type, config.handler);
                    this.eventListeners.push({ element: el, type: config.type, handler: config.handler });
                });
            } else if (config.element) {
                config.element.addEventListener(config.type, config.handler);
                this.eventListeners.push({ element: config.element, type: config.type, handler: config.handler });
            }
        });
    }

    setupThemeDetection() {
        // Check for theme changes
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.attributeName === 'data-theme' || 
                    mutation.attributeName === 'class' && 
                    (mutation.target === document.documentElement || mutation.target === document.body)) {
                    this.state.isDarkMode = document.documentElement.getAttribute('data-theme') === 'dark' || 
                                          document.body.classList.contains('dark-mode');
                    this.applyTheme();
                }
            });
        });

        observer.observe(document.documentElement, { attributes: true });
        observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });

        // Initial theme check
        clearTimeout(this.timeouts.themeCheck);
        this.timeouts.themeCheck = setTimeout(() => {
            this.state.isDarkMode = document.documentElement.getAttribute('data-theme') === 'dark' || 
                                  document.body.classList.contains('dark-mode');
            this.applyTheme();
        }, 100);
    }

    applyTheme() {
        const container = document.getElementById('messagesContainer');
        if (container) {
            if (this.state.isDarkMode) {
                container.classList.add('dark-mode');
                container.classList.remove('light-mode');
            } else {
                container.classList.add('light-mode');
                container.classList.remove('dark-mode');
            }
        }
        
        // Apply theme to other containers
        const conversationsList = document.getElementById('conversationsList');
        if (conversationsList) {
            if (this.state.isDarkMode) {
                conversationsList.classList.add('dark-mode');
                conversationsList.classList.remove('light-mode');
            } else {
                conversationsList.classList.add('light-mode');
                conversationsList.classList.remove('dark-mode');
            }
        }
    }

    // Handle user selection in new conversation flow
    async handleUserSelection(userId, userName) {
        // First check if conversation already exists with this user
        const existingConversation = this.state.conversations.find(
            conv => parseInt(conv.participant_id) === parseInt(userId)
        );
        
        if (existingConversation) {
            // Open existing conversation
            await this.openConversation(
                existingConversation.id,
                existingConversation.participant_name,
                existingConversation.participant_id,
                existingConversation.participant_avatar
            );
            
            // Hide new conversation panel
            this.hideNewConversation();
            return;
        }
        
        // If no existing conversation, proceed with new conversation
        this.selectRecipient(userId, userName);
    }

    async loadInitialData() {
        try {
            this.showInitialLoading();
            
            // Load conversations
            await this.loadConversations();
            
            // Load online users
            await this.loadOnlineUsers();
            
            // Load user statuses
            await this.loadUserStatuses();
            
            // Load unread count
            await this.loadUnreadCount();
            
            // Handle auto-open from URL
            this.handleAutoOpenConversation();
            
        } catch (error) {
            console.error('Failed to load initial data:', error);
            this.showToast('Failed to load messages. Please refresh the page.', 'error');
        } finally {
            this.hideInitialLoading();
            this.state.initialLoadComplete = true;
            this.applyTheme();
        }
    }

    async loadConversations() {
        try {
            const response = await this.fetchApi('/chats/api/conversations-list/');
            if (response.success && response.conversations) {
                // Sort conversations by last_message_time in descending order (newest first)
                const sortedConversations = response.conversations.sort((a, b) => {
                    const timeA = new Date(a.last_message_time || a.created_at);
                    const timeB = new Date(b.last_message_time || b.created_at);
                    return timeB - timeA; // Descending order
                });
                
                this.state.conversations = sortedConversations;
                this.renderConversations();
                
                // Update unread badge immediately
                this.updateUnreadBadgeFromConversations();
                
                // Cache last seen times
                this.cacheLastSeenTimes(sortedConversations);
            }
        } catch (error) {
            console.error('Failed to load conversations:', error);
            this.showConversationsError();
        }
    }

    // Cache last seen times for all conversations
    cacheLastSeenTimes(conversations) {
        conversations.forEach(conv => {
            if (conv.last_seen) {
                this.state.lastSeenCache.set(parseInt(conv.participant_id), conv.last_seen);
            }
        });
    }

    // Calculate unread count directly from conversations
    updateUnreadBadgeFromConversations() {
        let totalUnread = 0;
        this.state.conversations.forEach(conv => {
            totalUnread += conv.unread_count || 0;
        });
        
        this.state.unreadCount = totalUnread;
        this.updateUnreadBadge();
    }

    renderConversations() {
        const container = document.getElementById('conversationsList');
        if (!container) return;
        
        if (!this.state.conversations || this.state.conversations.length === 0) {
            container.innerHTML = `
                <div class="conversations-empty text-center py-5">
                    <i class="bi bi-chat-dots"></i>
                    <h4>No conversations yet</h4>
                    <p class="text-muted">Start a conversation by contacting sellers about their products.</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = this.state.conversations.map(conv => {
            const participantId = parseInt(conv.participant_id);
            const isOnline = this.state.onlineUsers.has(participantId);
            const lastSeen = this.getLastSeenDisplay(participantId, conv.last_seen);
            
            // Get correct avatar URL - ensure it's an absolute URL
            let avatarUrl = conv.participant_avatar || '';
            if (avatarUrl && !avatarUrl.startsWith('http') && !avatarUrl.startsWith('https') && !avatarUrl.startsWith('/')) {
                avatarUrl = '/' + avatarUrl;
            }
            
            // Default fallback avatar
            const defaultAvatar = window.STATIC_URL ? `${window.STATIC_URL}images/default-avatar.svg` : '/static/images/default-avatar.svg';
            
            return `
            <div class="conversation-item ${conv.unread_count > 0 ? 'unread' : ''} ${isOnline ? 'online' : ''}"
                 data-conversation-id="${conv.id}"
                 data-participant-id="${conv.participant_id}"
                 data-participant-name="${conv.participant_name}"
                 data-participant-avatar="${avatarUrl}"
                 data-unread-count="${conv.unread_count || 0}"
                 data-is-online="${isOnline}"
                 data-last-seen="${conv.last_seen || ''}"
                 data-last-message-time="${conv.last_message_time || conv.created_at}">
                <div class="conversation-avatar">
                    <img src="${avatarUrl || defaultAvatar}" 
                         alt="${conv.participant_name}"
                         onerror="this.src='${defaultAvatar}'; this.onerror=null;">
                    <span class="online-indicator"></span>
                </div>
                <div class="conversation-content">
                    <div class="conversation-header">
                        <div class="conversation-name">
                            ${conv.participant_name}
                            <span class="conversation-status">
                                ${isOnline ? 
                                    '<span class="online-status">● Online</span>' : 
                                    `<span class="last-seen">${lastSeen}</span>`}
                            </span>
                        </div>
                        <div class="conversation-time">
                            ${this.formatTime(conv.last_message_time || conv.created_at)}
                        </div>
                    </div>
                    <div class="conversation-preview">
                        <div class="conversation-message ${conv.last_message_sender_id === this.state.userId ? 'own' : ''}">
                            ${conv.last_message_sender_id === this.state.userId ? 'You: ' : ''}
                            ${this.truncateText(conv.last_message_content || 'Start conversation', 30)}
                        </div>
                        ${conv.unread_count > 0 ? `
                            <div class="conversation-unread">
                                ${conv.unread_count > 99 ? '99+' : conv.unread_count}
                            </div>
                        ` : ''}
                    </div>
                    ${conv.listing_title ? `
                        <div class="conversation-listing">
                            <i class="bi bi-tag"></i>
                            ${this.truncateText(conv.listing_title, 20)}
                        </div>
                    ` : ''}
                </div>
            </div>
            `;
        }).join('');
        
        // Apply theme
        if (this.state.isDarkMode) {
            container.classList.add('dark-mode');
            container.classList.remove('light-mode');
        } else {
            container.classList.add('light-mode');
            container.classList.remove('dark-mode');
        }
    }

    // Get last seen display text
    getLastSeenDisplay(userId, lastSeenFromServer = null) {
        const participantId = parseInt(userId);
        
        // Check cache first
        let lastSeen = lastSeenFromServer || this.state.lastSeenCache.get(participantId);
        
        if (!lastSeen) {
            return 'Last seen: Never';
        }
        
        // Format the last seen time
        return `Last seen ${this.formatLastSeen(lastSeen)}`;
    }

    async openConversation(conversationId, participantName, participantId = null, participantAvatar = null) {
        if (this.state.currentConversationId === conversationId) return;
        
        console.log(`Opening conversation ${conversationId} with ${participantName}`);
        
        // Update state
        this.state.currentConversationId = conversationId;
        this.state.currentParticipant = participantName;
        this.state.currentParticipantId = participantId;
        this.state.currentParticipantAvatar = participantAvatar;
        
        // Hide new conversation panel if open
        this.hideNewConversation();
        
        // Clear processed messages for this conversation
        this.state.processedMessageIds.clear();
        
        // Update UI
        this.updateConversationUI(conversationId);
        this.showChatPanel();
        
        // Load chat header info
        await this.updateChatHeader(conversationId, participantId, participantAvatar);
        
        // Load messages
        await this.loadConversationMessages(conversationId);
        
        // MARK AS READ IMMEDIATELY (Optimistic update)
        await this.markConversationAsRead(conversationId, true);
        
        // Scroll to bottom
        this.scrollToBottom(true);
        
        // Start polling for this conversation
        this.startConversationPolling(conversationId);
        
        // Update URL
        this.updateUrlWithConversation(conversationId);
        
        // Update body class for mobile
        if (this.state.isMobile) {
            document.body.classList.add('chat-active');
        }
    }

    async updateChatHeader(conversationId, participantId = null, participantAvatar = null) {
        // Find conversation
        const conversation = this.state.conversations.find(c => c.id === conversationId);
        if (!conversation) return;
        
        const participantIdInt = parseInt(participantId || conversation.participant_id);
        const isOnline = this.state.onlineUsers.has(participantIdInt);
        const lastSeen = this.getLastSeenDisplay(participantIdInt, conversation.last_seen);
        
        const avatarEl = document.getElementById('chatParticipantAvatar');
        const nameEl = document.getElementById('chatParticipantName');
        const statusEl = document.getElementById('chatParticipantStatus');
        
        // Get correct avatar URL
        let avatarUrl = participantAvatar || conversation.participant_avatar;
        if (avatarUrl && !avatarUrl.startsWith('http') && !avatarUrl.startsWith('https') && !avatarUrl.startsWith('/')) {
            avatarUrl = '/' + avatarUrl;
        }
        const defaultAvatar = window.STATIC_URL ? `${window.STATIC_URL}images/default-avatar.svg` : '/static/images/default-avatar.svg';
        
        if (avatarEl) {
            avatarEl.src = avatarUrl || defaultAvatar;
            avatarEl.onerror = function() {
                this.src = defaultAvatar;
                this.onerror = null;
            };
            
            // Update online status
            if (isOnline) {
                avatarEl.classList.add('online');
            } else {
                avatarEl.classList.remove('online');
            }
        }
        
        if (nameEl) {
            nameEl.textContent = conversation.participant_name;
        }
        
        if (statusEl) {
            if (isOnline) {
                statusEl.innerHTML = '<span class="online-status">● Online</span>';
            } else {
                statusEl.innerHTML = `<span class="last-seen">${lastSeen}</span>`;
            }
        }
    }

    async loadConversationMessages(conversationId) {
        const container = document.getElementById('messagesContainer');
        if (!container) return;
        
        // Show loading
        container.innerHTML = `
            <div class="chat-loading">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-2 text-muted">Loading messages...</p>
            </div>
        `;
        
        try {
            const response = await this.fetchApi(`/chats/api/get-new-messages/${conversationId}/?last_id=0`);
            if (response.success) {
                // Clear processed messages for fresh load
                this.state.processedMessageIds.clear();
                
                // Process and add messages
                const messages = response.new_messages || [];
                this.state.messages.set(conversationId, messages);
                
                // Add all message IDs to processed set to prevent duplicates
                messages.forEach(msg => {
                    if (msg.id) {
                        this.state.processedMessageIds.add(msg.id);
                    }
                });
                
                this.renderMessages(conversationId, messages);
                
                // Update last message ID
                if (messages.length > 0) {
                    this.state.lastMessageId = messages[messages.length - 1].id;
                }
            }
        } catch (error) {
            console.error('Failed to load messages:', error);
            container.innerHTML = `
                <div class="text-center py-4">
                    <i class="bi bi-exclamation-triangle text-danger fs-4"></i>
                    <p class="mt-2">Failed to load messages</p>
                    <button class="btn btn-sm btn-primary mt-2" onclick="window.messaging.loadConversationMessages(${conversationId})">
                        Retry
                    </button>
                </div>
            `;
        }
    }

    renderMessages(conversationId, messages) {
        const container = document.getElementById('messagesContainer');
        if (!container) return;
        
        if (!messages || messages.length === 0) {
            container.innerHTML = `
                <div class="no-messages text-center py-5">
                    <i class="bi bi-chat-dots fs-1 text-muted mb-3"></i>
                    <p class="text-muted">No messages yet. Start the conversation!</p>
                </div>
            `;
            return;
        }
        
        // Group messages by date
        const groupedMessages = this.groupMessagesByDate(messages);
        
        container.innerHTML = Object.entries(groupedMessages).map(([date, dateMessages]) => `
            <div class="date-separator">
                <span>${date}</span>
            </div>
            ${dateMessages.map(msg => this.renderMessageElement(msg)).join('')}
        `).join('');
        
        // Apply theme
        this.applyTheme();
    }

    renderMessageElement(msg) {
        const isOwn = msg.is_own_message;
        const time = new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const tempId = msg.tempId;
        
        // Determine status icon
        let statusIcon = '';
        let statusTitle = 'Sent';
        
        if (isOwn) {
            if (msg.is_read) {
                statusIcon = '<i class="bi bi-check2-all text-primary" title="Read"></i>';
                statusTitle = 'Read';
            } else if (msg.is_delivered) {
                statusIcon = '<i class="bi bi-check2-all" title="Delivered"></i>';
                statusTitle = 'Delivered';
            } else {
                statusIcon = '<i class="bi bi-check2" title="Sent"></i>';
                statusTitle = 'Sent';
            }
        }
        
        return `
            <div class="message-bubble ${isOwn ? 'sent' : 'received'} ${tempId ? 'temp' : ''}" 
                 data-message-id="${msg.id || tempId}"
                 data-temp-id="${tempId || ''}">
                ${isOwn ? `
                    <div class="message-actions">
                        <button class="message-actions-btn" onclick="window.messaging.editMessage('${msg.id || tempId}')" title="Edit">
                            <i class="bi bi-pencil"></i>
                        </button>
                        <button class="message-actions-btn delete" onclick="window.messaging.deleteMessage('${msg.id || tempId}')" title="Delete">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                ` : ''}
                <div class="message-content">${this.escapeHtml(msg.content)}</div>
                <div class="message-status-container">
                    <span class="message-time">${time}</span>
                    ${isOwn ? `
                        <span class="message-status" title="${statusTitle}">
                            ${statusIcon}
                        </span>
                    ` : ''}
                </div>
            </div>
        `;
    }

    async sendCurrentMessage() {
        const input = document.getElementById('messageInput');
        const message = input?.value.trim();
        
        if (!message) {
            this.showToast('Please enter a message', 'error');
            return;
        }
        
        if (!this.state.currentConversationId) {
            this.showToast('Please select a conversation first', 'error');
            return;
        }
        
        const sendBtn = document.getElementById('sendMessageBtn');
        if (sendBtn) {
            sendBtn.disabled = true;
            sendBtn.innerHTML = '<i class="bi bi-hourglass"></i>';
        }
        
        // Create unique temp ID
        const tempId = 'temp_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        
        // Create temporary message
        const tempMessage = {
            tempId: tempId,
            content: message,
            timestamp: new Date().toISOString(),
            is_own_message: true,
            is_read: false,
            is_delivered: false
        };
        
        // Store temp message
        this.state.tempMessages.set(tempId, tempMessage);
        
        // Remove any existing temp messages for this conversation
        this.removeExistingTempMessages();
        
        // Add to UI
        this.addMessageToUI(tempMessage, true);
        
        // Clear input
        if (input) {
            input.value = '';
            input.style.height = 'auto';
            this.updateCharCount(input, 'messageLength');
        }
        
        try {
            const response = await this.fetchApi('/chats/api/send-message/', {
                method: 'POST',
                body: JSON.stringify({
                    conversation_id: this.state.currentConversationId,
                    message: message
                })
            });
            
            if (response.success && response.message) {
                // Add message ID to processed set to prevent duplicates
                if (response.message.id) {
                    this.state.processedMessageIds.add(response.message.id);
                }
                
                // Replace temp message with real one
                this.replaceTempMessage(tempId, response.message);
                
                // Update conversation preview and sort list
                this.updateConversationPreview(this.state.currentConversationId, message);
                
                // Re-sort conversations to bring current one to top
                this.sortConversationsByLatest();
                
                this.showToast('Message sent', 'success');
                
                // Update last message ID
                this.state.lastMessageId = response.message.id;
                
                // Start polling for message status
                this.startMessageStatusPolling(response.message.id);
                
                // Reload conversations to update the list
                setTimeout(() => this.loadConversations(), 1000);
            }
        } catch (error) {
            console.error('Failed to send message:', error);
            this.markMessageAsFailed(tempId);
            this.showToast('Failed to send message', 'error');
        } finally {
            if (sendBtn) {
                sendBtn.disabled = false;
                sendBtn.innerHTML = '<i class="bi bi-send"></i>';
            }
        }
    }

    removeExistingTempMessages() {
        const container = document.getElementById('messagesContainer');
        if (!container) return;
        
        // Remove all temp messages
        const tempMessages = container.querySelectorAll('[data-temp-id]');
        tempMessages.forEach(msg => msg.remove());
        
        // Clear temp messages from state
        this.state.tempMessages.clear();
    }

    replaceTempMessage(tempId, realMessage) {
        // Remove temp message from state
        this.state.tempMessages.delete(tempId);
        
        // Find and replace in UI
        const tempEl = document.querySelector(`[data-temp-id="${tempId}"]`);
        if (tempEl) {
            tempEl.outerHTML = this.renderMessageElement(realMessage);
        }
        
        // Update messages in state
        const messages = this.state.messages.get(this.state.currentConversationId) || [];
        const updatedMessages = messages.filter(msg => msg.tempId !== tempId);
        updatedMessages.push(realMessage);
        this.state.messages.set(this.state.currentConversationId, updatedMessages);
    }

    startMessageStatusPolling(messageId) {
        // Stop existing polling for this message
        if (this.state.messageStatusPolling.has(messageId)) {
            clearInterval(this.state.messageStatusPolling.get(messageId));
        }
        
        // Start new polling
        const interval = setInterval(async () => {
            await this.checkMessageStatus(messageId);
        }, this.config.statusPollInterval);
        
        this.state.messageStatusPolling.set(messageId, interval);
        
        // Auto-stop after 30 seconds
        setTimeout(() => {
            this.stopMessageStatusPolling(messageId);
        }, 30000);
    }

    stopMessageStatusPolling(messageId) {
        if (this.state.messageStatusPolling.has(messageId)) {
            clearInterval(this.state.messageStatusPolling.get(messageId));
            this.state.messageStatusPolling.delete(messageId);
        }
    }

    async checkMessageStatus(messageId) {
        try {
            const response = await this.fetchApi(`/chats/api/message-status/${messageId}/`);
            if (response.success) {
                this.updateMessageStatusUI(messageId, response.status);
                
                // Stop polling if message is read
                if (response.status === 'read') {
                    this.stopMessageStatusPolling(messageId);
                }
            }
        } catch (error) {
            console.error('Failed to check message status:', error);
        }
    }

    updateMessageStatusUI(messageId, status) {
        const messageEl = document.querySelector(`[data-message-id="${messageId}"]`);
        if (!messageEl) return;
        
        const statusEl = messageEl.querySelector('.message-status');
        if (!statusEl) return;
        
        let statusIcon = '';
        let statusTitle = 'Sent';
        
        if (status === 'delivered') {
            statusIcon = '<i class="bi bi-check2-all" title="Delivered"></i>';
            statusTitle = 'Delivered';
        } else if (status === 'read') {
            statusIcon = '<i class="bi bi-check2-all text-primary" title="Read"></i>';
            statusTitle = 'Read';
        } else {
            statusIcon = '<i class="bi bi-check2" title="Sent"></i>';
            statusTitle = 'Sent';
        }
        
        statusEl.innerHTML = statusIcon;
        statusEl.title = statusTitle;
        
        // Update message in state
        const messages = this.state.messages.get(this.state.currentConversationId) || [];
        const messageIndex = messages.findIndex(msg => msg.id === messageId);
        if (messageIndex !== -1) {
            if (status === 'delivered') {
                messages[messageIndex].is_delivered = true;
            } else if (status === 'read') {
                messages[messageIndex].is_read = true;
                messages[messageIndex].is_delivered = true;
            }
        }
    }

    markMessageAsFailed(tempId) {
        const messageEl = document.querySelector(`[data-temp-id="${tempId}"]`);
        if (messageEl) {
            messageEl.classList.add('failed');
            messageEl.title = 'Failed to send. Click to retry.';
            messageEl.style.cursor = 'pointer';
            messageEl.addEventListener('click', () => this.retryFailedMessage(tempId));
        }
    }

    async retryFailedMessage(tempId) {
        const tempMessage = this.state.tempMessages.get(tempId);
        if (!tempMessage) return;
        
        // Remove failed styling
        const messageEl = document.querySelector(`[data-temp-id="${tempId}"]`);
        if (messageEl) {
            messageEl.classList.remove('failed');
            messageEl.title = '';
            messageEl.style.cursor = 'default';
        }
        
        // Resend message
        await this.sendCurrentMessage();
        
        // Remove temp message from UI
        if (messageEl) {
            messageEl.remove();
        }
        
        this.state.tempMessages.delete(tempId);
    }

    addMessageToUI(message, isOwn = false) {
        const container = document.getElementById('messagesContainer');
        if (!container) return;
        
        // Check if we have "no messages" placeholder
        const noMessages = container.querySelector('.no-messages');
        if (noMessages) {
            noMessages.remove();
        }
        
        // Check if this message already exists (prevent duplicates)
        const messageId = message.id || message.tempId;
        const existingMessage = container.querySelector(`[data-message-id="${messageId}"]`);
        if (existingMessage) {
            console.log('Duplicate message detected, skipping:', messageId);
            return;
        }
        
        // Add message
        const messageHtml = this.renderMessageElement(message);
        container.insertAdjacentHTML('beforeend', messageHtml);
        
        // Scroll to bottom
        this.scrollToBottom();
    }

    scrollToBottom(instant = false) {
        const container = document.getElementById('messagesContainer');
        if (!container) return;
        
        clearTimeout(this.timeouts.scroll);
        
        if (instant) {
            container.scrollTop = container.scrollHeight;
        } else {
            this.timeouts.scroll = setTimeout(() => {
                container.scrollTop = container.scrollHeight;
            }, 100);
        }
    }

    showChatPanel() {
        const chatPanel = document.getElementById('chatPanel');
        const conversationsPanel = document.getElementById('conversationsPanel');
        
        if (chatPanel) {
            chatPanel.classList.add('active');
        }
        
        if (this.state.isMobile && conversationsPanel) {
            conversationsPanel.style.display = 'none';
        }
        
        // Hide new conversation panel and empty state
        document.getElementById('newConversationPanel').style.display = 'none';
        document.getElementById('newConversationPanel').classList.remove('active');
        document.getElementById('chatEmptyState').style.display = 'none';
        
        // Show active chat
        document.getElementById('activeChat').style.display = 'flex';
    }

    closeActiveChat() {
        const chatPanel = document.getElementById('chatPanel');
        const conversationsPanel = document.getElementById('conversationsPanel');
        
        if (chatPanel) {
            chatPanel.classList.remove('active');
        }
        
        if (this.state.isMobile && conversationsPanel) {
            conversationsPanel.style.display = 'block';
            document.body.classList.remove('chat-active');
        }
        
        // Show empty state
        document.getElementById('chatEmptyState').style.display = 'flex';
        document.getElementById('activeChat').style.display = 'none';
        
        // Update URL
        const url = new URL(window.location);
        url.searchParams.delete('open');
        window.history.pushState({}, '', url);
        
        // Clear current conversation
        this.state.currentConversationId = null;
        this.state.currentParticipant = null;
        this.state.currentParticipantId = null;
        
        // Stop polling
        this.stopConversationPolling();
    }

    updateConversationUI(conversationId) {
        // Update active conversation in list
        document.querySelectorAll('.conversation-item').forEach(item => {
            item.classList.remove('active');
            if (parseInt(item.dataset.conversationId) === conversationId) {
                item.classList.add('active');
            }
        });
    }

    updateConversationPreview(conversationId, message) {
        const convItem = document.querySelector(`[data-conversation-id="${conversationId}"]`);
        if (convItem) {
            const preview = convItem.querySelector('.conversation-message');
            if (preview) {
                preview.textContent = 'You: ' + this.truncateText(message, 30);
                preview.classList.add('own');
            }
            const time = convItem.querySelector('.conversation-time');
            if (time) time.textContent = 'Just now';
            
            // Update the last message time attribute
            convItem.dataset.lastMessageTime = new Date().toISOString();
        }
    }

    // Sort conversations by latest message
    sortConversationsByLatest() {
        this.state.conversations.sort((a, b) => {
            const timeA = new Date(a.last_message_time || a.created_at);
            const timeB = new Date(b.last_message_time || b.created_at);
            return timeB - timeA; // Descending order
        });
        
        // Re-render conversations
        this.renderConversations();
    }

    // Mark conversation as read with optimistic update
    async markConversationAsRead(conversationId, optimistic = false) {
        try {
            // Get conversation unread count before marking as read
            const convItem = document.querySelector(`[data-conversation-id="${conversationId}"]`);
            const convUnreadCount = convItem ? parseInt(convItem.dataset.unreadCount || 0) : 0;
            
            // OPTIMISTIC UPDATE: Immediately update UI
            if (optimistic && convUnreadCount > 0) {
                // Update conversation item
                if (convItem) {
                    convItem.classList.remove('unread');
                    const unreadBadge = convItem.querySelector('.conversation-unread');
                    if (unreadBadge) unreadBadge.remove();
                    convItem.dataset.unreadCount = '0';
                }
                
                // Update global unread count immediately
                this.state.unreadCount = Math.max(0, this.state.unreadCount - convUnreadCount);
                this.updateUnreadBadge();
            }
            
            // Call API to mark as read
            await this.fetchApi(`/chats/api/mark-read/${conversationId}/`, {
                method: 'POST'
            });
            
        } catch (error) {
            console.error('Failed to mark as read:', error);
            
            // If optimistic update failed, revert
            if (optimistic) {
                await this.loadUnreadCount();
            }
        }
    }

    async loadUnreadCount() {
        try {
            const response = await this.fetchApi('/chats/api/unread-messages-count/');
            if (response.success) {
                this.state.unreadCount = response.count || 0;
                this.updateUnreadBadge();
            }
        } catch (error) {
            console.error('Failed to update unread count:', error);
        }
    }

    updateUnreadBadge() {
        const badge = document.getElementById('globalUnreadBadge');
        if (badge) {
            if (this.state.unreadCount > 0) {
                badge.textContent = this.state.unreadCount > 99 ? '99+' : this.state.unreadCount;
                badge.style.display = 'flex';
            } else {
                badge.style.display = 'none';
            }
        }
        
        // Update filter badge
        const filterBadge = document.getElementById('unreadFilterBadge');
        if (filterBadge) {
            if (this.state.unreadCount > 0) {
                filterBadge.textContent = this.state.unreadCount > 99 ? '99+' : this.state.unreadCount;
                filterBadge.style.display = 'flex';
            } else {
                filterBadge.style.display = 'none';
            }
        }
    }

    async loadOnlineUsers() {
        try {
            const response = await this.fetchApi('/chats/api/get-online-users/');
            if (response.success && response.online_users) {
                this.state.onlineUsers = new Set(response.online_users.map(id => parseInt(id)));
                this.updateOnlineStatusUI();
            }
        } catch (error) {
            console.error('Failed to load online users:', error);
        }
    }

    // Load user statuses with last seen times
    async loadUserStatuses() {
        try {
            const response = await this.fetchApi('/chats/api/user-statuses/');
            if (response.success && response.user_statuses) {
                // Update last seen cache
                response.user_statuses.forEach(status => {
                    if (status.last_seen) {
                        this.state.lastSeenCache.set(parseInt(status.user_id), status.last_seen);
                    }
                });
                
                // Update online users
                const onlineUsers = response.user_statuses
                    .filter(status => status.is_online)
                    .map(status => parseInt(status.user_id));
                
                this.state.onlineUsers = new Set(onlineUsers);
                this.updateOnlineStatusUI();
            }
        } catch (error) {
            console.error('Failed to load user statuses:', error);
        }
    }

    updateOnlineStatusUI() {
        // Update conversation list
        document.querySelectorAll('.conversation-item').forEach(item => {
            const participantId = parseInt(item.dataset.participantId);
            const isOnline = this.state.onlineUsers.has(participantId);
            const lastSeen = item.dataset.lastSeen || this.state.lastSeenCache.get(participantId);
            
            // Update online indicator
            if (isOnline) {
                item.classList.add('online');
                const indicator = item.querySelector('.online-indicator');
                if (indicator) indicator.style.display = 'block';
                
                const statusSpan = item.querySelector('.conversation-status');
                if (statusSpan) {
                    statusSpan.innerHTML = '<span class="online-status">● Online</span>';
                }
            } else {
                item.classList.remove('online');
                const indicator = item.querySelector('.online-indicator');
                if (indicator) indicator.style.display = 'none';
                
                const statusSpan = item.querySelector('.conversation-status');
                if (statusSpan) {
                    const lastSeenText = lastSeen ? `Last seen ${this.formatLastSeen(lastSeen)}` : 'Last seen: Never';
                    statusSpan.innerHTML = `<span class="last-seen">${lastSeenText}</span>`;
                }
            }
        });
        
        // Update active chat header if applicable
        if (this.state.currentConversationId) {
            const avatarEl = document.getElementById('chatParticipantAvatar');
            const statusEl = document.getElementById('chatParticipantStatus');
            
            if (avatarEl && this.state.currentParticipantId) {
                const participantIdInt = parseInt(this.state.currentParticipantId);
                const isOnline = this.state.onlineUsers.has(participantIdInt);
                const lastSeen = this.state.lastSeenCache.get(participantIdInt);
                
                if (isOnline) {
                    avatarEl.classList.add('online');
                } else {
                    avatarEl.classList.remove('online');
                }
                
                if (statusEl) {
                    if (isOnline) {
                        statusEl.innerHTML = '<span class="online-status">● Online</span>';
                    } else {
                        const lastSeenText = lastSeen ? `Last seen ${this.formatLastSeen(lastSeen)}` : 'Last seen: Never';
                        statusEl.innerHTML = `<span class="last-seen">${lastSeenText}</span>`;
                    }
                }
            }
        }
    }

    startConversationPolling(conversationId) {
        this.stopConversationPolling();
        
        if (!this.state.pollingEnabled) return;
        
        // Poll for new messages
        this.intervals.messages = setInterval(async () => {
            if (this.state.currentConversationId === conversationId) {
                await this.pollNewMessages(conversationId);
            }
        }, this.config.pollInterval);
        
        // Poll for typing indicators
        this.intervals.typing = setInterval(async () => {
            if (this.state.currentConversationId === conversationId) {
                await this.pollTypingIndicator(conversationId);
            }
        }, 2000);
        
        // Poll for user status updates
        this.intervals.status = setInterval(async () => {
            if (this.state.currentConversationId === conversationId) {
                await this.loadUserStatuses();
            }
        }, 30000);
        
        // Periodically sort conversations
        this.intervals.conversationListSort = setInterval(() => {
            this.sortConversationsByLatest();
        }, 60000); // Sort every minute
        
        this.state.activePolling = true;
    }

    stopConversationPolling() {
        // Clear all intervals
        Object.values(this.intervals).forEach(interval => {
            if (interval) clearInterval(interval);
        });
        
        // Clear all timeouts
        Object.values(this.timeouts).forEach(timeout => {
            if (timeout) clearTimeout(timeout);
        });
        
        // Clear message status polling
        this.state.messageStatusPolling.forEach(interval => clearInterval(interval));
        this.state.messageStatusPolling.clear();
        
        this.state.activePolling = false;
    }

    // Poll new messages without duplicates
    async pollNewMessages(conversationId) {
        if (!this.state.currentConversationId || this.state.currentConversationId !== conversationId) return;
        if (!this.state.pollingEnabled || document.hidden) return;
        
        try {
            const currentMessages = this.state.messages.get(conversationId) || [];
            const lastMessageId = this.state.lastMessageId || 0;
            
            const response = await this.fetchApi(
                `/chats/api/get-new-messages/${conversationId}/?last_id=${lastMessageId}`
            );
            
            if (response.success && response.new_messages && response.new_messages.length > 0) {
                // Filter out messages we've already processed
                const newMessages = response.new_messages.filter(msg => {
                    // Skip if we've already processed this message
                    if (msg.id && this.state.processedMessageIds.has(msg.id)) {
                        console.log('Skipping already processed message:', msg.id);
                        return false;
                    }
                    
                    // Skip if this looks like a duplicate pending message
                    if (this.state.pendingMessages.has(msg.id)) {
                        console.log('Skipping pending message:', msg.id);
                        return false;
                    }
                    
                    return true;
                });
                
                if (newMessages.length > 0) {
                    // Add new messages
                    newMessages.forEach(msg => {
                        // Mark as processed
                        if (msg.id) {
                            this.state.processedMessageIds.add(msg.id);
                        }
                        
                        this.addMessageToUI(msg, msg.is_own_message);
                    });
                    
                    // Update messages in state
                    const updatedMessages = [...currentMessages, ...newMessages];
                    this.state.messages.set(conversationId, updatedMessages);
                    
                    // Update last message ID
                    this.state.lastMessageId = newMessages[newMessages.length - 1].id;
                    
                    // Update conversation list to reflect new message
                    this.updateConversationAfterNewMessage(conversationId, newMessages[newMessages.length - 1]);
                    
                    // Play notification sound if window not focused
                    if (!document.hasFocus()) {
                        this.playNotificationSound();
                    }
                    
                    // Mark as read if we received messages
                    await this.markConversationAsRead(conversationId, true);
                    
                    // Reload and sort conversations
                    setTimeout(() => {
                        this.loadConversations();
                        this.sortConversationsByLatest();
                    }, 1000);
                }
            }
        } catch (error) {
            console.error('Failed to poll new messages:', error);
        }
    }

    updateConversationAfterNewMessage(conversationId, message) {
        const convItem = document.querySelector(`[data-conversation-id="${conversationId}"]`);
        if (convItem) {
            const preview = convItem.querySelector('.conversation-message');
            if (preview) {
                const isOwn = message.is_own_message || false;
                preview.textContent = isOwn ? 'You: ' + this.truncateText(message.content, 30) : this.truncateText(message.content, 30);
                preview.classList.toggle('own', isOwn);
            }
            
            const time = convItem.querySelector('.conversation-time');
            if (time) time.textContent = 'Just now';
            
            // Update the last message time attribute
            convItem.dataset.lastMessageTime = new Date().toISOString();
            
            // Update unread count if it's not our own message
            if (!message.is_own_message) {
                const unreadCount = parseInt(convItem.dataset.unreadCount || 0) + 1;
                convItem.dataset.unreadCount = unreadCount;
                convItem.classList.add('unread');
                
                const unreadBadge = convItem.querySelector('.conversation-unread');
                if (unreadBadge) {
                    unreadBadge.textContent = unreadCount > 99 ? '99+' : unreadCount;
                } else {
                    const previewDiv = convItem.querySelector('.conversation-preview');
                    if (previewDiv) {
                        previewDiv.insertAdjacentHTML('beforeend', `
                            <div class="conversation-unread">
                                ${unreadCount > 99 ? '99+' : unreadCount}
                            </div>
                        `);
                    }
                }
            }
        }
    }

    async pollTypingIndicator(conversationId) {
        if (!this.state.currentConversationId || this.state.currentConversationId !== conversationId) return;
        if (!this.state.pollingEnabled || document.hidden) return;
        
        try {
            const response = await this.fetchApi(`/chats/api/check-typing/${conversationId}/`);
            if (response.typing) {
                this.showTypingIndicator(response.user_name);
            } else {
                this.hideTypingIndicator();
            }
        } catch (error) {
            this.hideTypingIndicator();
        }
    }

    showTypingIndicator(userName) {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) {
            document.getElementById('typingText').textContent = `${userName} is typing...`;
            indicator.style.display = 'flex';
            this.scrollToBottom();
        }
    }

    hideTypingIndicator() {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) {
            indicator.style.display = 'none';
        }
    }

    async handleTyping() {
        if (!this.state.currentConversationId) return;
        
        if (!this.state.isTyping) {
            this.state.isTyping = true;
            await this.sendTypingIndicator();
        }
        
        clearTimeout(this.timeouts.typing);
        this.timeouts.typing = setTimeout(() => {
            this.state.isTyping = false;
        }, this.config.typingTimeout);
    }

    async sendTypingIndicator() {
        if (!this.state.currentConversationId) return;
        
        try {
            await this.fetchApi(`/chats/api/send-typing/${this.state.currentConversationId}/`, {
                method: 'POST'
            });
        } catch (error) {
            console.error('Failed to send typing indicator:', error);
        }
    }

    // New Conversation Flow - UPDATED
    showNewConversation() {
        // Hide other panels
        document.getElementById('chatEmptyState').style.display = 'none';
        document.getElementById('activeChat').style.display = 'none';
        
        // Show new conversation panel
        document.getElementById('newConversationPanel').style.display = 'flex';
        document.getElementById('newConversationPanel').classList.add('active');
        
        // Clear any previous selection
        this.clearRecipientSelection();
        
        // Focus search input
        document.getElementById('newChatSearch').focus();
        
        // Update URL for mobile back button
        if (this.state.isMobile) {
            window.history.pushState({ newConversation: true }, '', '?new=true');
        }
    }

    hideNewConversation() {
        document.getElementById('newConversationPanel').style.display = 'none';
        document.getElementById('newConversationPanel').classList.remove('active');
        
        // Show appropriate panel based on state
        if (this.state.currentConversationId) {
            document.getElementById('activeChat').style.display = 'flex';
        } else {
            document.getElementById('chatEmptyState').style.display = 'flex';
        }
        
        // Clear selection
        this.clearRecipientSelection();
        
        // Update URL
        if (this.state.isMobile) {
            const url = new URL(window.location);
            url.searchParams.delete('new');
            window.history.pushState({}, '', url);
        }
    }

    async searchUsers(query) {
        const resultsDiv = document.getElementById('searchResults');
        
        if (!query || query.length < 2) {
            this.showSearchPlaceholder();
            return;
        }
        
        // Show loading state
        resultsDiv.innerHTML = `
            <div class="text-center py-4">
                <div class="spinner-border spinner-border-sm text-primary"></div>
                <p class="mt-2 text-muted">Searching...</p>
            </div>
        `;
        
        try {
            const response = await this.fetchApi(`/chats/api/search-users/?q=${encodeURIComponent(query)}`);
            if (response.success && response.users) {
                this.renderSearchResults(response.users);
            } else {
                this.showSearchPlaceholder();
            }
        } catch (error) {
            console.error('Failed to search users:', error);
            resultsDiv.innerHTML = `
                <div class="text-center py-4">
                    <i class="bi bi-exclamation-triangle text-danger"></i>
                    <p class="mt-2 text-muted">Failed to search users</p>
                </div>
            `;
        }
    }

    renderSearchResults(users) {
        const resultsDiv = document.getElementById('searchResults');
        
        if (!users || users.length === 0) {
            resultsDiv.innerHTML = `
                <div class="search-placeholder">
                    <i class="bi bi-search"></i>
                    <p>No users found</p>
                </div>
            `;
            return;
        }
        
        resultsDiv.innerHTML = users.map(user => {
            // Ensure avatar URL is correct
            let avatarUrl = user.avatar || '';
            if (avatarUrl && !avatarUrl.startsWith('http') && !avatarUrl.startsWith('https') && !avatarUrl.startsWith('/')) {
                avatarUrl = '/' + avatarUrl;
            }
            const defaultAvatar = window.STATIC_URL ? `${window.STATIC_URL}images/default-avatar.svg` : '/static/images/default-avatar.svg';
            
            return `
            <div class="user-result" data-user-id="${user.id}" data-user-name="${user.name}">
                <div class="user-avatar">
                    <img src="${avatarUrl || defaultAvatar}" 
                         alt="${user.name}"
                         onerror="this.src='${defaultAvatar}'; this.onerror=null;">
                </div>
                <div class="user-info">
                    <h6>${user.name}</h6>
                    <span class="text-muted">@${user.username}</span>
                </div>
            </div>
            `;
        }).join('');
    }

    selectRecipient(userId, userName) {
        // Store recipient
        this.state.newConversationRecipient = { id: userId, name: userName };
        
        // Update UI
        document.getElementById('selectedUserInfo').style.display = 'flex';
        document.getElementById('selectedUserName').textContent = userName;
        
        // Set avatar - try to find it in search results first
        const avatarEl = document.getElementById('selectedUserAvatar');
        const userResultImg = document.querySelector(`[data-user-id="${userId}"] img`);
        const defaultAvatar = window.STATIC_URL ? `${window.STATIC_URL}images/default-avatar.svg` : '/static/images/default-avatar.svg';
        
        if (userResultImg) {
            avatarEl.src = userResultImg.src;
        } else {
            avatarEl.src = defaultAvatar;
        }
        
        // Clear search results and hide search container on desktop
        if (!this.state.isMobile) {
            document.getElementById('searchResults').innerHTML = '';
            document.querySelector('.search-results-container').style.display = 'none';
        }
        
        // Enable send button
        document.getElementById('sendNewMessageBtn').disabled = false;
        
        // Focus message input
        setTimeout(() => {
            document.getElementById('newMessageText').focus();
        }, 100);
    }

    clearRecipientSelection() {
        this.state.newConversationRecipient = null;
        
        // Hide selected user info
        document.getElementById('selectedUserInfo').style.display = 'none';
        
        // Clear message input
        document.getElementById('newMessageText').value = '';
        this.updateCharCount(document.getElementById('newMessageText'), 'newCharCount');
        
        // Disable send button
        document.getElementById('sendNewMessageBtn').disabled = true;
        
        // Show search container again
        const searchContainer = document.querySelector('.search-results-container');
        if (searchContainer) {
            searchContainer.style.display = 'flex';
        }
        
        // Show search placeholder
        this.showSearchPlaceholder();
        
        // Refocus search input
        document.getElementById('newChatSearch').focus();
    }

    async sendNewMessage() {
        const input = document.getElementById('newMessageText');
        const message = input?.value.trim();
        const recipient = this.state.newConversationRecipient;
        
        if (!message || !recipient) {
            this.showToast('Please select a recipient and enter a message', 'error');
            return;
        }
        
        if (message.length > this.config.maxMessageLength) {
            this.showToast(`Message is too long. Maximum ${this.config.maxMessageLength} characters.`, 'error');
            return;
        }
        
        const sendBtn = document.getElementById('sendNewMessageBtn');
        if (sendBtn) {
            sendBtn.disabled = true;
            sendBtn.innerHTML = '<i class="bi bi-hourglass me-2"></i>Sending...';
        }
        
        try {
            const response = await this.fetchApi('/chats/api/send-message/', {
                method: 'POST',
                body: JSON.stringify({
                    recipient_id: recipient.id,
                    message: message
                })
            });
            
            if (response.success) {
                this.showToast('Message sent', 'success');
                
                // Clear the form
                input.value = '';
                this.updateCharCount(input, 'newCharCount');
                
                // Hide new conversation panel
                this.hideNewConversation();
                
                // If a new conversation was created, open it
                if (response.conversation_id) {
                    // Reload conversations to include the new one
                    await this.loadConversations();
                    
                    // Find and open the new conversation
                    const newConversation = this.state.conversations.find(
                        conv => conv.id === response.conversation_id
                    );
                    
                    if (newConversation) {
                        setTimeout(() => {
                            this.openConversation(
                                newConversation.id,
                                newConversation.participant_name,
                                newConversation.participant_id,
                                newConversation.participant_avatar
                            );
                        }, 500);
                    }
                }
            } else {
                throw new Error(response.error || 'Failed to send message');
            }
        } catch (error) {
            console.error('Failed to send new message:', error);
            this.showToast(error.message || 'Failed to send message', 'error');
        } finally {
            if (sendBtn) {
                sendBtn.disabled = false;
                sendBtn.innerHTML = '<i class="bi bi-send me-2"></i>Send';
            }
        }
    }

    // Utility Methods
    updateCharCount(input, counterId) {
        const counter = document.getElementById(counterId);
        if (counter && input) {
            const length = input.value.length;
            counter.textContent = `${length}/${this.config.maxMessageLength}`;
            counter.style.color = length > this.config.maxMessageLength ? '#dc3545' : '#6c757d';
            
            // Update send button state for new messages
            if (counterId === 'newCharCount') {
                const sendBtn = document.getElementById('sendNewMessageBtn');
                if (sendBtn) {
                    sendBtn.disabled = length === 0 || length > this.config.maxMessageLength;
                }
            }
        }
    }

    formatTime(timestamp) {
        if (!timestamp) return '';
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;
        
        if (diff < 60000) return 'Just now';
        if (diff < 3600000) return Math.floor(diff / 60000) + 'm ago';
        if (diff < 86400000) return Math.floor(diff / 3600000) + 'h ago';
        if (diff < 604800000) return Math.floor(diff / 86400000) + 'd ago';
        return date.toLocaleDateString();
    }

    formatLastSeen(timestamp) {
        if (!timestamp) return 'Never';
        
        const lastSeen = new Date(timestamp);
        const now = new Date();
        const diffMs = now - lastSeen;
        
        // If less than 1 minute, show "Just now"
        if (diffMs < 60000) return 'Just now';
        
        // If less than 1 hour, show minutes
        if (diffMs < 3600000) {
            const minutes = Math.floor(diffMs / 60000);
            return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`;
        }
        
        // If less than 24 hours, show hours
        if (diffMs < 86400000) {
            const hours = Math.floor(diffMs / 3600000);
            return `${hours} hour${hours !== 1 ? 's' : ''} ago`;
        }
        
        // If less than 7 days, show days
        if (diffMs < 604800000) {
            const days = Math.floor(diffMs / 86400000);
            return `${days} day${days !== 1 ? 's' : ''} ago`;
        }
        
        // Otherwise show date
        return lastSeen.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: lastSeen.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
        });
    }

    truncateText(text, maxLength) {
        if (!text) return '';
        return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    groupMessagesByDate(messages) {
        const groups = {};
        
        messages.forEach(msg => {
            const date = new Date(msg.timestamp).toLocaleDateString('en-US', {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            });
            
            if (!groups[date]) groups[date] = [];
            groups[date].push(msg);
        });
        
        return groups;
    }

    setupPolling() {
        // Poll for conversation updates every 30 seconds
        this.intervals.conversations = setInterval(async () => {
            if (this.state.pollingEnabled && !document.hidden) {
                await this.loadConversations();
                await this.loadUserStatuses();
                // Ensure conversations are sorted by latest
                this.sortConversationsByLatest();
            }
        }, 30000);
        
        // Poll for online users every 45 seconds
        this.intervals.online = setInterval(async () => {
            if (this.state.pollingEnabled && !document.hidden) {
                await this.loadUserStatuses();
            }
        }, 45000);
    }

    handleUrlParams() {
        const urlParams = new URLSearchParams(window.location.search);
        const openConversationId = urlParams.get('open');
        
        if (openConversationId) {
            this.state.autoOpenConversationId = parseInt(openConversationId);
        }
    }

    handleAutoOpenConversation() {
        if (this.state.autoOpenConversationId && this.state.conversations.length > 0) {
            const conversation = this.state.conversations.find(
                c => c.id === this.state.autoOpenConversationId
            );
            
            if (conversation) {
                setTimeout(() => {
                    this.openConversation(
                        conversation.id,
                        conversation.participant_name,
                        conversation.participant_id,
                        conversation.participant_avatar
                    );
                }, 1000);
            }
        }
    }

    updateUrlWithConversation(conversationId) {
        const url = new URL(window.location);
        url.searchParams.set('open', conversationId);
        window.history.pushState({}, '', url);
    }

    filterConversations(searchTerm) {
        const term = searchTerm.toLowerCase().trim();
        document.querySelectorAll('.conversation-item').forEach(item => {
            const name = item.dataset.participantName.toLowerCase();
            const preview = item.querySelector('.conversation-message')?.textContent.toLowerCase() || '';
            const listing = item.querySelector('.conversation-listing')?.textContent.toLowerCase() || '';
            
            const matches = name.includes(term) || preview.includes(term) || listing.includes(term);
            item.style.display = matches ? '' : 'none';
        });
    }

    setActiveFilter(filter) {
        // Update active button
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.dataset.filter === filter) btn.classList.add('active');
        });
        
        document.querySelectorAll('.conversation-item').forEach(item => {
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

    handleResize() {
        this.state.isMobile = window.innerWidth < 992;
        
        // Update body class
        if (!this.state.isMobile) {
            document.body.classList.remove('chat-active');
            // On desktop, ensure search container is visible when no recipient selected
            if (!this.state.newConversationRecipient) {
                const searchContainer = document.querySelector('.search-results-container');
                if (searchContainer) {
                    searchContainer.style.display = 'flex';
                }
            }
        } else if (this.state.currentConversationId) {
            document.body.classList.add('chat-active');
        }
        
        // Adjust UI based on screen size
        this.adjustUIForScreenSize();
    }

    adjustUIForScreenSize() {
        const searchContainer = document.querySelector('.search-results-container');
        const selectedInfo = document.getElementById('selectedUserInfo');
        
        if (!this.state.isMobile) {
            // Desktop: Hide search container when recipient is selected
            if (this.state.newConversationRecipient && searchContainer) {
                searchContainer.style.display = 'none';
            } else if (searchContainer) {
                searchContainer.style.display = 'flex';
            }
        } else {
            // Mobile: Always show search container in new conversation panel
            if (searchContainer) {
                searchContainer.style.display = 'flex';
            }
        }
    }

    setupNetworkListeners() {
        window.addEventListener('online', () => {
            this.state.isOnline = true;
            this.state.pollingEnabled = true;
            this.showToast('Back online', 'success');
            
            // Resume polling
            if (this.state.currentConversationId) {
                this.startConversationPolling(this.state.currentConversationId);
            }
        });
        
        window.addEventListener('offline', () => {
            this.state.isOnline = false;
            this.state.pollingEnabled = false;
            this.showToast('You are offline', 'warning');
            this.stopConversationPolling();
        });
    }

    handleTabHidden() {
        this.state.pollingEnabled = false;
        this.stopConversationPolling();
    }

    handleTabVisible() {
        this.state.pollingEnabled = true;
        
        if (this.state.currentConversationId) {
            this.startConversationPolling(this.state.currentConversationId);
        }
        
        // Refresh data and sort conversations
        if (this.state.initialLoadComplete) {
            this.loadConversations();
            this.loadUserStatuses();
            this.sortConversationsByLatest();
        }
    }

    showInitialLoading() {
        const overlay = document.getElementById('messagingLoadingOverlay');
        if (overlay) overlay.style.display = 'flex';
    }

    hideInitialLoading() {
        const overlay = document.getElementById('messagingLoadingOverlay');
        if (overlay) overlay.style.display = 'none';
    }

    showConversationsError() {
        const container = document.getElementById('conversationsList');
        if (container) {
            container.innerHTML = `
                <div class="conversations-error text-center py-5">
                    <i class="bi bi-exclamation-triangle text-danger fs-1 mb-3"></i>
                    <h4>Failed to load conversations</h4>
                    <p class="text-muted">Please try refreshing the page.</p>
                    <button class="btn btn-primary mt-3" onclick="location.reload()">
                        <i class="bi bi-arrow-clockwise me-2"></i>Refresh Page
                    </button>
                </div>
            `;
        }
    }

    showSearchPlaceholder() {
        const resultsDiv = document.getElementById('searchResults');
        resultsDiv.innerHTML = `
            <div class="search-placeholder">
                <i class="bi bi-search"></i>
                <p>Search for users to start a conversation</p>
                <small class="text-muted mt-2">Type at least 2 characters to search</small>
            </div>
        `;
    }

    getUserId() {
        const meta = document.querySelector('meta[name="user-id"]');
        return meta ? parseInt(meta.content) : null;
    }

    getCsrfToken() {
        const cookie = document.cookie.match(/csrftoken=([^;]+)/);
        return cookie ? cookie[1] : '';
    }

    async fetchApi(url, options = {}) {
        const csrfToken = this.getCsrfToken();
        const defaultHeaders = {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest'
        };
        
        try {
            const response = await fetch(url, {
                ...options,
                headers: { ...defaultHeaders, ...options.headers },
                credentials: 'same-origin'
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    }

    showToast(message, type = 'success') {
        // Create toast element
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type} border-0`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        
        const icon = {
            success: 'bi-check-circle-fill',
            error: 'bi-exclamation-triangle-fill',
            warning: 'bi-exclamation-circle-fill',
            info: 'bi-info-circle-fill'
        }[type] || 'bi-info-circle-fill';
        
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
        let container = document.getElementById('messagingErrorContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'messagingErrorContainer';
            container.className = 'toast-container position-fixed top-0 end-0 p-3';
            document.body.appendChild(container);
        }
        
        container.appendChild(toast);
        
        // Initialize and show
        const bsToast = new bootstrap.Toast(toast, {
            autohide: true,
            delay: 3000
        });
        bsToast.show();
        
        // Remove after hide
        toast.addEventListener('hidden.bs.toast', () => toast.remove());
    }

    playNotificationSound() {
        try {
            const audio = new Audio('data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEAQB8AAEAfAAABAAgAZGF0YQ');
            audio.volume = 0.3;
            audio.play().catch(() => {});
        } catch (e) {}
    }

    cleanup() {
        console.log('Cleaning up messaging system...');
        
        // Stop all polling
        this.stopConversationPolling();
        
        // Clear all timeouts
        Object.values(this.timeouts).forEach(timeout => {
            if (timeout) clearTimeout(timeout);
        });
        
        // Remove event listeners
        this.eventListeners.forEach(listener => {
            if (listener.element && listener.handler) {
                listener.element.removeEventListener(listener.type, listener.handler);
            }
        });
        
        this.eventListeners = [];
        this.state.initialized = false;
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on the messages page
    if (document.getElementById('conversationsList')) {
        // Initialize the messaging system
        window.messaging = new MessagingSystem();
        window.messaging.init();
    }
});

// Handle page unload
window.addEventListener('beforeunload', function() {
    if (window.messaging) {
        window.messaging.cleanup();
    }
});

// Export for debugging
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MessagingSystem;
}