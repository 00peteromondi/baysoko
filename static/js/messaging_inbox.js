// static/js/messaging-inbox.js
class InboxMessaging extends MessagingCore {
    constructor() {
        super();
        this.currentConversationId = null;
        this.currentParticipant = null;
        this.conversations = [];
        this.onlineUsers = new Set();
        this.pollingIntervals = new Map();
        this.typingTimeout = null;
        this.isTyping = false;
        this.searchQuery = '';
        this.currentFilter = 'all';
        
        this.initInbox();
    }
    
    initInbox() {
        console.log('Initializing Inbox Messaging...');
        
        // Setup event listeners
        this.setupInboxEventListeners();
        
        // Load conversations
        this.loadConversations();
        
        // Start periodic updates
        this.startPeriodicUpdates();
        
        // Initialize modals
        this.initModals();
    }
    
    setupInboxEventListeners() {
        // Conversation search
        const searchInput = document.getElementById('searchConversations');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.searchQuery = e.target.value.trim().toLowerCase();
                this.filterConversations();
            });
        }
        
        // Filter tabs
        document.querySelectorAll('.conversation-filters .btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.setActiveFilter(e.target.dataset.filter);
            });
        });
        
        // New conversation button
        const newConversationBtn = document.querySelector('[onclick="startNewConversation()"]');
        if (newConversationBtn) {
            newConversationBtn.addEventListener('click', () => this.startNewConversation());
        }
        
        // Mobile chat back button
        const mobileBackBtn = document.querySelector('.mobile-chat-nav .btn-custom');
        if (mobileBackBtn) {
            mobileBackBtn.addEventListener('click', () => this.closeMobileChat());
        }
        
        // Call buttons
        const callButtons = document.querySelectorAll('[data-call-user]');
        callButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const userId = e.target.dataset.callUser;
                this.startCallWithUser(userId);
            });
        });
        
        // Window resize handling
        window.addEventListener('resize', () => this.handleResize());
        
        // Prevent form submission on enter in search
        if (searchInput) {
            searchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                }
            });
        }
    }
    
    initModals() {
        // Initialize new conversation modal if exists
        const newMessageModal = document.getElementById('newMessageModal');
        if (newMessageModal) {
            this.initNewConversationModal();
        }
        
        // Initialize call modal if exists
        const callModal = document.getElementById('callModal');
        if (callModal) {
            this.initCallModal();
        }
    }
    
    async loadConversations() {
        try {
            this.showConversationsLoading();
            
            const response = await this.safeFetch('/chats/api/conversations-list/');
            
            if (response.success && response.conversations) {
                this.conversations = response.conversations;
                this.onlineUsers = new Set(response.online_users || []);
                this.renderConversationList();
                
                // Auto-select first conversation on desktop if none selected
                if (window.innerWidth >= 992 && !this.currentConversationId && this.conversations.length > 0) {
                    const firstConv = this.conversations[0];
                    this.loadConversation(firstConv.id, firstConv.participant_name);
                }
            } else {
                this.showNoConversations();
            }
        } catch (error) {
            console.error('Error loading conversations:', error);
            this.showConversationsError();
            this.showToast('Failed to load conversations', 'error');
        }
    }
    
    renderConversationList() {
        const container = document.getElementById('conversationsList');
        if (!container) return;
        
        // Clear existing content
        container.innerHTML = '';
        
        if (this.conversations.length === 0) {
            this.showNoConversations();
            return;
        }
        
        // Filter conversations based on search and active filter
        const filteredConversations = this.conversations.filter(conv => {
            // Apply search filter
            if (this.searchQuery) {
                const matchesName = conv.participant_name.toLowerCase().includes(this.searchQuery);
                const matchesMessage = conv.last_message_content.toLowerCase().includes(this.searchQuery);
                if (!matchesName && !matchesMessage) return false;
            }
            
            // Apply category filter
            switch (this.currentFilter) {
                case 'unread':
                    return conv.unread_count > 0;
                case 'with-listing':
                    return conv.listing_id !== null;
                case 'archived':
                    return conv.archived === true;
                default: // 'all'
                    return true;
            }
        });
        
        if (filteredConversations.length === 0) {
            this.showNoConversations('No conversations match your search');
            return;
        }
        
        filteredConversations.forEach(conversation => {
            const item = this.createConversationItem(conversation);
            container.appendChild(item);
        });
    }
    
    createConversationItem(conversation) {
        const item = document.createElement('div');
        item.className = `conversation-item ${conversation.unread_count > 0 ? 'unread' : ''} ${this.currentConversationId === conversation.id ? 'active' : ''}`;
        item.dataset.conversationId = conversation.id;
        item.dataset.listing = conversation.listing_id ? 'true' : 'false';
        
        // Check if participant is online
        const isOnline = this.onlineUsers.has(conversation.participant_id);
        
        // Format time
        const time = this.formatTime(conversation.last_message_time);
        const isOwnMessage = conversation.last_message_sender_id === this.currentUserId;
        
        item.innerHTML = `
            <div class="conversation-avatar">
                <img src="${conversation.participant_avatar}" 
                     alt="${conversation.participant_name}"
                     onerror="this.src='https://placehold.co/48x48/c2c2c2/1f1f1f?text=User'">
                ${isOnline ? '<span class="online-indicator"></span>' : ''}
            </div>
            <div class="conversation-content">
                <div class="conversation-header">
                    <div class="conversation-name">
                        ${conversation.participant_name}
                        ${isOnline ? '<span class="badge bg-success badge-sm ms-1">●</span>' : ''}
                    </div>
                    <div class="conversation-time" title="${new Date(conversation.last_message_time).toLocaleString()}">
                        ${time}
                    </div>
                </div>
                <div class="conversation-preview">
                    <div class="conversation-message ${isOwnMessage ? 'you' : ''}">
                        ${isOwnMessage ? 'You: ' : ''}
                        ${this.truncateText(conversation.last_message_content, 30)}
                    </div>
                    ${conversation.unread_count > 0 ? `
                        <div class="conversation-unread">
                            ${conversation.unread_count > 99 ? '99+' : conversation.unread_count}
                        </div>
                    ` : ''}
                </div>
                ${conversation.listing_title ? `
                    <div class="conversation-listing">
                        <i class="bi bi-tag"></i>
                        ${this.truncateText(conversation.listing_title, 20)}
                    </div>
                ` : ''}
            </div>
        `;
        
        item.addEventListener('click', () => {
            this.loadConversation(conversation.id, conversation.participant_name);
        });
        
        // Add context menu for conversation actions
        item.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            this.showConversationContextMenu(e, conversation);
        });
        
        return item;
    }
    
    async loadConversation(conversationId, participantName) {
        if (this.currentConversationId === conversationId) return;
        
        this.currentConversationId = conversationId;
        this.currentParticipant = { 
            name: participantName,
            id: this.conversations.find(c => c.id === conversationId)?.participant_id
        };
        
        // Update UI for mobile
        if (window.innerWidth < 992) {
            document.getElementById('chatPanel').classList.add('active');
            document.getElementById('mobileChatNav').classList.remove('d-none');
            document.getElementById('mobileChatName').textContent = participantName;
            
            const conversation = this.conversations.find(c => c.id === conversationId);
            if (conversation) {
                document.getElementById('mobileChatAvatar').src = conversation.participant_avatar;
            }
        }
        
        // Update active conversation in list
        document.querySelectorAll('.conversation-item').forEach(item => {
            item.classList.remove('active');
            if (parseInt(item.dataset.conversationId) === conversationId) {
                item.classList.add('active');
            }
        });
        
        // Hide empty state, show active chat
        document.getElementById('chatEmptyState').style.display = 'none';
        document.getElementById('activeChat').style.display = 'block';
        
        // Show loading state
        this.showChatLoading();
        
        try {
            // Load conversation content
            const response = await this.safeFetch(`/chats/conversation/${conversationId}/?ajax=true`);
            
            if (typeof response === 'string') {
                // Parse HTML response
                const parser = new DOMParser();
                const doc = parser.parseFromString(response, 'text/html');
                const conversationContent = doc.querySelector('.conversation-container');
                
                if (conversationContent) {
                    document.getElementById('activeChat').innerHTML = conversationContent.innerHTML;
                    
                    // Initialize chat functionality
                    this.initChatFunctionality(conversationId);
                    
                    // Mark conversation as read
                    await this.markConversationAsRead(conversationId);
                    
                    // Start real-time updates for this conversation
                    this.startConversationPolling(conversationId);
                } else {
                    throw new Error('Failed to parse conversation content');
                }
            } else if (response.messages) {
                // JSON response with messages
                this.renderChatFromJSON(response, conversationId);
                
                // Initialize chat functionality
                this.initChatFunctionality(conversationId);
                
                // Mark conversation as read
                await this.markConversationAsRead(conversationId);
                
                // Start real-time updates for this conversation
                this.startConversationPolling(conversationId);
            }
            
        } catch (error) {
            console.error('Error loading conversation:', error);
            this.showChatError();
            this.showToast('Failed to load conversation', 'error');
        }
    }
    
    renderChatFromJSON(data, conversationId) {
        const activeChat = document.getElementById('activeChat');
        if (!activeChat) return;
        
        // Get participant info
        const participant = data.participants?.find(p => !p.is_current_user) || {};
        
        const chatHTML = `
            <!-- Chat Header -->
            <div class="conversation-header-detailed">
                <div class="conversation-header-content">
                    <div class="conversation-back-btn d-lg-none">
                        <button class="btn-custom btn-ghost" onclick="window.messaging.closeMobileChat()">
                            <i class="bi bi-arrow-left"></i>
                            <span class="d-none d-md-inline">Back</span>
                        </button>
                    </div>
                    
                    <div class="conversation-participant-info">
                        <div class="conversation-participant-avatar">
                            <img src="${participant.avatar || 'https://placehold.co/56x56/c2c2c2/1f1f1f?text=User'}" 
                                 alt="${participant.full_name}">
                            <span class="online-indicator" id="onlineIndicator" style="display: none;"></span>
                        </div>
                        <div class="conversation-participant-details">
                            <h2>${participant.full_name}</h2>
                            <div class="conversation-participant-status" id="participantStatus">
                                <i class="bi bi-circle-fill"></i>
                                <span id="statusText">Loading...</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="conversation-header-actions">
                        <button class="btn-custom btn-ghost" title="Call" onclick="window.messaging.startCallWithCurrentUser()">
                            <i class="bi bi-telephone"></i>
                            <span class="d-none d-md-inline">Call</span>
                        </button>
                        <button class="btn-custom btn-ghost" title="More options" data-bs-toggle="dropdown">
                            <i class="bi bi-three-dots"></i>
                        </button>
                        <ul class="dropdown-menu">
                            <li><a class="dropdown-item" href="#"><i class="bi bi-person me-2"></i>View Profile</a></li>
                            <li><a class="dropdown-item" href="#"><i class="bi bi-share me-2"></i>Share Contact</a></li>
                            <li><hr class="dropdown-divider"></li>
                            <li><a class="dropdown-item text-danger" href="#"><i class="bi bi-bell-slash me-2"></i>Mute</a></li>
                            <li><a class="dropdown-item text-danger" href="#"><i class="bi bi-trash me-2"></i>Delete Chat</a></li>
                        </ul>
                    </div>
                </div>
            </div>

            <!-- Conversation Area -->
            <div class="conversation-area">
                <!-- About Listing Card -->
                ${data.listing ? `
                    <div class="listing-card-conversation">
                        <img src="${data.listing.image || 'https://placehold.co/60x60/c2c2c2/1f1f1f?text=Listing'}" 
                             alt="${data.listing.title}">
                        <div class="listing-card-conversation-info">
                            <h4>${data.listing.title}</h4>
                            <div class="price">KSh ${data.listing.price}</div>
                        </div>
                        <a href="${data.listing.url || '#'}" class="btn-custom btn-primary btn-sm">
                            View
                        </a>
                    </div>
                ` : ''}

                <!-- Messages Container -->
                <div class="messages-container-detailed" id="messagesContainer">
                    ${data.messages && data.messages.length > 0 ? 
                        this.renderMessages(data.messages) : 
                        '<div class="text-center p-5 text-muted">No messages yet. Start the conversation!</div>'
                    }
                </div>

                <!-- Typing Indicator -->
                <div class="typing-indicator-enhanced" id="typingIndicator" style="display: none;">
                    <img src="${participant.avatar || 'https://placehold.co/28x28/c2c2c2/1f1f1f?text=User'}" 
                         alt="${participant.full_name}">
                    <div class="typing-text" id="typingName">Someone</div>
                    <div class="typing-dots-enhanced">
                        <span></span>
                        <span></span>
                        <span></span>
                    </div>
                </div>

                <!-- Input Area -->
                <div class="input-area-enhanced">
                    <form method="post" id="messageForm">
                        <input type="hidden" name="csrfmiddlewaretoken" value="${this.getCookie('csrftoken')}">
                        <div class="input-wrapper-enhanced">
                            <button type="button" class="btn-custom btn-ghost" title="Attach file" data-bs-toggle="dropdown">
                                <i class="bi bi-paperclip"></i>
                            </button>
                            <ul class="dropdown-menu">
                                <li><a class="dropdown-item" href="#"><i class="bi bi-image me-2"></i>Photo</a></li>
                                <li><a class="dropdown-item" href="#"><i class="bi bi-file-earmark me-2"></i>Document</a></li>
                                <li><a class="dropdown-item" href="#"><i class="bi bi-camera-video me-2"></i>Video</a></li>
                                <li><hr class="dropdown-divider"></li>
                                <li><a class="dropdown-item" href="#"><i class="bi bi-folder me-2"></i>Choose from files</a></li>
                            </ul>
                            
                            <textarea class="chat-input-enhanced" id="messageInput" name="content" 
                                      placeholder="Type your message..." rows="1" required></textarea>
                            
                            <div class="input-actions-enhanced">
                                <button type="button" class="btn-custom btn-ghost" title="Emoji">
                                    <i class="bi bi-emoji-smile"></i>
                                </button>
                                <button type="submit" class="btn-custom send-btn-enhanced" id="sendMessageBtn">
                                    <i class="bi bi-send"></i>
                                </button>
                            </div>
                        </div>
                    </form>
                </div>
            </div>
        `;
        
        activeChat.innerHTML = chatHTML;
        
        // Scroll to bottom
        setTimeout(() => {
            const messagesContainer = document.getElementById('messagesContainer');
            if (messagesContainer) {
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }
        }, 100);
    }
    
    renderMessages(messages) {
        let html = '';
        let currentDate = null;
        
        messages.forEach(msg => {
            // Add date divider if needed
            const messageDate = new Date(msg.timestamp).toDateString();
            if (messageDate !== currentDate) {
                currentDate = messageDate;
                html += `
                    <div class="date-divider">
                        <span>${this.formatMessageDate(msg.timestamp)}</span>
                    </div>
                `;
            }
            
            // Message bubble
            const isOwnMessage = msg.is_own_message;
            const statusIcon = msg.is_read ? 'bi-check2-all read' : 'bi-check2';
            const time = this.formatMessageTime(msg.timestamp);
            
            html += `
                <div class="message-bubble-enhanced ${isOwnMessage ? 'sent' : 'received'}" data-message-id="${msg.id}">
                    ${!isOwnMessage ? `
                        <div class="message-sender-avatar">
                            <img src="${msg.sender_avatar || 'https://placehold.co/32x32/c2c2c2/1f1f1f?text=User'}" 
                                 alt="${msg.sender}">
                        </div>
                    ` : ''}
                    <div class="message-content-enhanced">
                        <div class="message-text-enhanced">${this.escapeHtml(msg.content)}</div>
                        <div class="message-time-enhanced">
                            ${time}
                            ${isOwnMessage ? `
                                <div class="message-status-icons">
                                    <i class="bi ${statusIcon}"></i>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                    <div class="message-actions">
                        ${isOwnMessage ? `
                            <button class="message-action-btn" title="Delete" onclick="window.messaging.showDeleteModal(${msg.id})">
                                <i class="bi bi-trash"></i>
                            </button>
                        ` : ''}
                        <button class="message-action-btn" title="Copy" onclick="window.messaging.copyMessage('${this.escapeHtml(msg.content).replace(/'/g, "\\'")}')">
                            <i class="bi bi-copy"></i>
                        </button>
                    </div>
                </div>
            `;
        });
        
        return html;
    }
    
    initChatFunctionality(conversationId) {
        // Message form submission
        const messageForm = document.getElementById('messageForm');
        if (messageForm) {
            messageForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                await this.sendMessage(conversationId);
            });
        }
        
        // Message input events
        const messageInput = document.getElementById('messageInput');
        if (messageInput) {
            // Auto-resize
            messageInput.addEventListener('input', function() {
                this.style.height = 'auto';
                this.style.height = (this.scrollHeight) + 'px';
                
                // Send typing indicator
                window.messaging.sendTypingIndicator(conversationId);
            });
            
            // Enter key to send (without shift)
            messageInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    if (messageForm) {
                        messageForm.dispatchEvent(new Event('submit'));
                    }
                }
            });
        }
        
        // Update mobile chat info
        this.updateMobileChatInfo();
    }
    
    async sendMessage(conversationId) {
        const messageInput = document.getElementById('messageInput');
        const message = messageInput ? messageInput.value.trim() : '';
        
        if (!message) {
            this.showToast('Please enter a message', 'error');
            return;
        }
        
        const sendBtn = document.getElementById('sendMessageBtn');
        const originalText = sendBtn.innerHTML;
        sendBtn.disabled = true;
        sendBtn.innerHTML = '<i class="bi bi-hourglass"></i>';
        
        try {
            const formData = new FormData(document.getElementById('messageForm'));
            
            const response = await this.safeFetch(`/chats/conversation/${conversationId}/`, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            if (response.success) {
                // Clear input
                if (messageInput) {
                    messageInput.value = '';
                    messageInput.style.height = 'auto';
                }
                
                // Add message to UI
                const container = document.getElementById('messagesContainer');
                const messageDiv = document.createElement('div');
                messageDiv.className = 'message-bubble-enhanced sent';
                messageDiv.dataset.messageId = response.message_id;
                
                messageDiv.innerHTML = `
                    <div class="message-content-enhanced">
                        <div class="message-text-enhanced">${message}</div>
                        <div class="message-time-enhanced">
                            Just now
                            <div class="message-status-icons">
                                <i class="bi bi-check2"></i>
                            </div>
                        </div>
                    </div>
                    <div class="message-actions">
                        <button class="message-action-btn" title="Delete" onclick="window.messaging.showDeleteModal(${response.message_id})">
                            <i class="bi bi-trash"></i>
                        </button>
                        <button class="message-action-btn" title="Copy" onclick="window.messaging.copyMessage('${message.replace(/'/g, "\\'")}')">
                            <i class="bi bi-copy"></i>
                        </button>
                    </div>
                `;
                
                container.appendChild(messageDiv);
                
                // Scroll to bottom
                setTimeout(() => {
                    container.scrollTop = container.scrollHeight;
                }, 100);
                
                // Update conversation in list
                await this.updateConversationInList(conversationId, message);
                
                // Update unread counts
                await this.updateUnreadCounts();
                
                this.showToast('Message sent', 'success');
            } else {
                this.showToast(response.error || 'Failed to send message', 'error');
            }
            
        } catch (error) {
            console.error('Error sending message:', error);
            this.showToast('Error sending message', 'error');
        } finally {
            // Re-enable send button
            sendBtn.disabled = false;
            sendBtn.innerHTML = originalText;
        }
    }
    
    async updateConversationInList(conversationId, lastMessage) {
        // Update the conversation in our data
        const conversationIndex = this.conversations.findIndex(c => c.id === conversationId);
        if (conversationIndex !== -1) {
            this.conversations[conversationIndex].last_message_content = lastMessage;
            this.conversations[conversationIndex].last_message_sender_id = this.currentUserId;
            this.conversations[conversationIndex].last_message_time = new Date().toISOString();
            
            // Move to top
            const conversation = this.conversations.splice(conversationIndex, 1)[0];
            this.conversations.unshift(conversation);
            
            // Re-render list
            this.renderConversationList();
        }
    }
    
    startConversationPolling(conversationId) {
        // Stop existing polling for this conversation
        this.stopConversationPolling(conversationId);
        
        const intervalId = setInterval(async () => {
            await this.pollNewMessages(conversationId);
            await this.pollTypingStatus(conversationId);
            await this.pollOnlineStatus(conversationId);
        }, 3000);
        
        this.pollingIntervals.set(conversationId, intervalId);
    }
    
    stopConversationPolling(conversationId) {
        if (this.pollingIntervals.has(conversationId)) {
            clearInterval(this.pollingIntervals.get(conversationId));
            this.pollingIntervals.delete(conversationId);
        }
    }
    
    async pollNewMessages(conversationId) {
        try {
            const lastMessageId = this.getLastMessageId();
            const response = await this.safeFetch(`/chats/api/get-new-messages/${conversationId}/?last_id=${lastMessageId || 0}`);
            
            if (response.new_messages && response.new_messages.length > 0) {
                // Add messages to UI
                response.new_messages.forEach(msg => {
                    this.addMessageToChat(msg, false);
                });
                
                // Mark as read
                await this.markConversationAsRead(conversationId);
                
                // Scroll to bottom
                setTimeout(() => {
                    const container = document.getElementById('messagesContainer');
                    if (container) {
                        container.scrollTop = container.scrollHeight;
                    }
                }, 100);
            }
        } catch (error) {
            console.error('Error polling new messages:', error);
        }
    }
    
    async pollTypingStatus(conversationId) {
        try {
            const response = await this.safeFetch(`/chats/api/check-typing/${conversationId}/`);
            
            const typingIndicator = document.getElementById('typingIndicator');
            if (typingIndicator) {
                if (response.typing && !response.is_self) {
                    typingIndicator.style.display = 'flex';
                    document.getElementById('typingName').textContent = response.user_name || 'Someone';
                    
                    // Auto-hide after 5 seconds
                    clearTimeout(this.typingTimeout);
                    this.typingTimeout = setTimeout(() => {
                        typingIndicator.style.display = 'none';
                    }, 5000);
                } else {
                    typingIndicator.style.display = 'none';
                }
            }
        } catch (error) {
            // Silently fail for typing checks
            console.debug('Error checking typing:', error);
        }
    }
    
    async pollOnlineStatus(conversationId) {
        try {
            const response = await this.safeFetch(`/chats/api/check-online/${conversationId}/`);
            
            const statusElement = document.getElementById('participantStatus');
            const indicator = document.getElementById('onlineIndicator');
            
            if (statusElement && indicator) {
                if (response.online) {
                    statusElement.classList.add('online');
                    const statusText = statusElement.querySelector('#statusText');
                    if (statusText) statusText.textContent = 'Online';
                    indicator.style.display = 'block';
                } else {
                    statusElement.classList.remove('online');
                    const statusText = statusElement.querySelector('#statusText');
                    if (statusText) statusText.textContent = response.last_seen ? `Active ${response.last_seen}` : 'Offline';
                    indicator.style.display = 'none';
                }
            }
        } catch (error) {
            console.error('Error checking online status:', error);
        }
    }
    
    async sendTypingIndicator(conversationId) {
        if (this.isTyping) return;
        
        this.isTyping = true;
        
        try {
            await this.safeFetch(`/chats/api/send-typing/${conversationId}/`, {
                method: 'POST'
            });
        } catch (error) {
            console.error('Error sending typing indicator:', error);
        }
        
        // Reset typing flag after 2 seconds
        setTimeout(() => {
            this.isTyping = false;
        }, 2000);
    }
    
    addMessageToChat(messageData, isOwn = false) {
        const container = document.getElementById('messagesContainer');
        if (!container) return;
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message-bubble-enhanced ${isOwn ? 'sent' : 'received'}`;
        messageDiv.dataset.messageId = messageData.id;
        
        const time = new Date(messageData.timestamp).toLocaleTimeString([], { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        
        const statusIcon = messageData.is_read ? 'bi-check2-all read' : 'bi-check2';
        
        // Avatar for received messages
        let avatarHtml = '';
        if (!isOwn) {
            avatarHtml = `
                <div class="message-sender-avatar">
                    <img src="${messageData.sender_avatar || 'https://placehold.co/32x32/c2c2c2/1f1f1f?text=User'}" 
                         alt="${messageData.sender}">
                </div>
            `;
        }
        
        messageDiv.innerHTML = `
            ${avatarHtml}
            <div class="message-content-enhanced">
                <div class="message-text-enhanced">${this.escapeHtml(messageData.content)}</div>
                <div class="message-time-enhanced">
                    ${time}
                    ${isOwn ? `
                        <div class="message-status-icons">
                            <i class="bi ${statusIcon}"></i>
                        </div>
                    ` : ''}
                </div>
            </div>
            <div class="message-actions">
                ${isOwn ? `
                    <button class="message-action-btn" title="Delete" onclick="window.messaging.showDeleteModal(${messageData.id})">
                        <i class="bi bi-trash"></i>
                    </button>
                ` : ''}
                <button class="message-action-btn" title="Copy" onclick="window.messaging.copyMessage('${this.escapeHtml(messageData.content).replace(/'/g, "\\'")}')">
                    <i class="bi bi-copy"></i>
                </button>
            </div>
        `;
        
        container.appendChild(messageDiv);
        
        // Remove "no messages" message if it exists
        const noMessages = container.querySelector('.text-center');
        if (noMessages) {
            noMessages.remove();
        }
    }
    
    getLastMessageId() {
        const container = document.getElementById('messagesContainer');
        if (!container) return null;
        
        const lastMessage = container.querySelector('.message-bubble-enhanced:last-child');
        if (lastMessage) {
            return parseInt(lastMessage.dataset.messageId);
        }
        return null;
    }
    
    async markConversationAsRead(conversationId) {
        try {
            await this.safeFetch(`/chats/api/mark-read/${conversationId}/`, {
                method: 'POST'
            });
            
            // Update UI
            document.querySelectorAll('.message-bubble-enhanced.sent .bi-check2').forEach(icon => {
                icon.className = 'bi bi-check2-all read';
            });
            
            // Update conversation in list
            const convItem = document.querySelector(`[data-conversation-id="${conversationId}"]`);
            if (convItem) {
                convItem.classList.remove('unread');
                const unreadBadge = convItem.querySelector('.conversation-unread');
                if (unreadBadge) unreadBadge.remove();
            }
            
            // Update unread counts
            await this.updateUnreadCounts();
            
        } catch (error) {
            console.error('Error marking conversation as read:', error);
        }
    }
    
    filterConversations() {
        this.renderConversationList();
    }
    
    setActiveFilter(filter) {
        this.currentFilter = filter;
        
        // Update active button
        document.querySelectorAll('.conversation-filters .btn').forEach(button => {
            button.classList.remove('active');
            if (button.dataset.filter === filter) {
                button.classList.add('active');
            }
        });
        
        this.renderConversationList();
    }
    
    closeMobileChat() {
        document.getElementById('chatPanel').classList.remove('active');
        document.getElementById('mobileChatNav').classList.add('d-none');
        document.getElementById('chatEmptyState').style.display = 'flex';
        document.getElementById('activeChat').style.display = 'none';
        this.currentConversationId = null;
        
        // Stop polling for the conversation
        if (this.currentConversationId) {
            this.stopConversationPolling(this.currentConversationId);
        }
    }
    
    updateMobileChatInfo() {
        const mobileChatName = document.getElementById('mobileChatName');
        const mobileChatAvatar = document.getElementById('mobileChatAvatar');
        
        if (mobileChatName && this.currentParticipant) {
            mobileChatName.textContent = this.currentParticipant.name;
        }
        
        if (mobileChatAvatar && this.currentParticipant) {
            const conversation = this.conversations.find(c => c.id === this.currentConversationId);
            if (conversation) {
                mobileChatAvatar.src = conversation.participant_avatar;
            }
        }
    }
    
    startPeriodicUpdates() {
        // Update conversations list every 30 seconds
        setInterval(() => {
            this.loadConversations();
        }, 30000);
        
        // Update online status every minute for active conversation
        setInterval(() => {
            if (this.currentConversationId) {
                this.pollOnlineStatus(this.currentConversationId);
            }
        }, 60000);
    }
    
    handleResize() {
        // Handle responsive layout changes
        if (window.innerWidth >= 992) {
            // Desktop: Show both panels
            document.getElementById('chatPanel').classList.remove('active');
            document.getElementById('mobileChatNav').classList.add('d-none');
        } else {
            // Mobile: Hide chat panel if no conversation selected
            if (!this.currentConversationId) {
                document.getElementById('chatPanel').classList.remove('active');
                document.getElementById('mobileChatNav').classList.add('d-none');
            }
        }
    }
    
    // Modal Functions
    initNewConversationModal() {
        // Implementation from new_conversation_modal.html
        // This would be moved here for better organization
        console.log('New conversation modal initialized');
    }
    
    initCallModal() {
        console.log('Call modal initialized');
    }
    
    startCallWithCurrentUser() {
        if (!this.currentParticipant) return;
        
        const userData = {
            id: this.currentParticipant.id,
            name: this.currentParticipant.name,
            avatar: this.conversations.find(c => c.id === this.currentConversationId)?.participant_avatar || 
                   'https://placehold.co/100x100/c2c2c2/1f1f1f?text=User'
        };
        
        this.startCallWithUser(userData);
    }
    
    startCallWithUser(userData) {
        // Update call modal
        document.getElementById('callUserName').textContent = userData.name;
        document.getElementById('callAvatar').src = userData.avatar;
        
        // Show call modal
        const callModal = new bootstrap.Modal(document.getElementById('callModal'));
        callModal.show();
        
        // Store user data for call initiation
        window.selectedUserForCall = userData;
    }
    
    // Utility Methods
    formatTime(timestamp) {
        if (!timestamp) return '';
        
        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        
        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m`;
        
        const diffHours = Math.floor(diffMins / 60);
        if (diffHours < 24) return `${diffHours}h`;
        
        return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    }
    
    formatMessageTime(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    
    formatMessageDate(timestamp) {
        const date = new Date(timestamp);
        const today = new Date();
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);
        
        if (date.toDateString() === today.toDateString()) return 'Today';
        if (date.toDateString() === yesterday.toDateString()) return 'Yesterday';
        
        return date.toLocaleDateString('en-US', { 
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric'
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
    
    showConversationsLoading() {
        const container = document.getElementById('conversationsList');
        if (container) {
            container.innerHTML = `
                <div class="conversations-loading">
                    <i class="bi bi-arrow-repeat"></i>
                    <p>Loading conversations...</p>
                </div>
            `;
        }
    }
    
    showNoConversations(message = 'No conversations yet') {
        const container = document.getElementById('conversationsList');
        if (container) {
            container.innerHTML = `
                <div class="conversations-empty">
                    <i class="bi bi-chat-dots"></i>
                    <h4>${message}</h4>
                    <p>Start a conversation by contacting sellers about their products.</p>
                    <button class="btn-custom btn-primary" onclick="window.messaging.startNewConversation()">
                        <i class="bi bi-plus-circle"></i> Start a Conversation
                    </button>
                </div>
            `;
        }
    }
    
    showConversationsError() {
        const container = document.getElementById('conversationsList');
        if (container) {
            container.innerHTML = `
                <div class="conversations-empty">
                    <i class="bi bi-exclamation-triangle text-danger"></i>
                    <h4>Failed to load conversations</h4>
                    <p>Please try refreshing the page.</p>
                    <button class="btn-custom btn-primary" onclick="window.location.reload()">
                        <i class="bi bi-arrow-clockwise"></i> Refresh Page
                    </button>
                </div>
            `;
        }
    }
    
    showChatLoading() {
        const activeChat = document.getElementById('activeChat');
        if (activeChat) {
            activeChat.innerHTML = `
                <div class="chat-loading">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <p class="mt-3">Loading conversation...</p>
                </div>
            `;
        }
    }
    
    showChatError() {
        const activeChat = document.getElementById('activeChat');
        if (activeChat) {
            activeChat.innerHTML = `
                <div class="chat-error">
                    <i class="bi bi-exclamation-triangle display-1 text-danger"></i>
                    <h4 class="mt-3">Failed to load conversation</h4>
                    <p class="text-muted">Please try again.</p>
                    <button class="btn-custom btn-primary" onclick="window.location.reload()">
                        <i class="bi bi-arrow-clockwise"></i> Reload
                    </button>
                </div>
            `;
        }
    }
    
    showConversationContextMenu(event, conversation) {
        // Create context menu
        const menu = document.createElement('div');
        menu.className = 'dropdown-menu show';
        menu.style.position = 'absolute';
        menu.style.left = `${event.pageX}px`;
        menu.style.top = `${event.pageY}px`;
        menu.innerHTML = `
            <a class="dropdown-item" href="#" onclick="window.messaging.markConversationAsRead(${conversation.id})">
                <i class="bi bi-check2-all me-2"></i>Mark as read
            </a>
            <a class="dropdown-item" href="#" onclick="window.messaging.muteConversation(${conversation.id})">
                <i class="bi bi-bell-slash me-2"></i>Mute
            </a>
            <a class="dropdown-item" href="#" onclick="window.messaging.archiveConversation(${conversation.id})">
                <i class="bi bi-archive me-2"></i>Archive
            </a>
            <div class="dropdown-divider"></div>
            <a class="dropdown-item text-danger" href="#" onclick="window.messaging.deleteConversation(${conversation.id})">
                <i class="bi bi-trash me-2"></i>Delete
            </a>
        `;
        
        document.body.appendChild(menu);
        
        // Remove menu on click elsewhere
        const removeMenu = () => {
            document.body.removeChild(menu);
            document.removeEventListener('click', removeMenu);
        };
        
        setTimeout(() => {
            document.addEventListener('click', removeMenu);
        }, 100);
    }
    
    // Public API methods
    startNewConversation() {
        const modal = new bootstrap.Modal(document.getElementById('newMessageModal'));
        modal.show();
    }
    
    showDeleteModal(messageId) {
        // Implementation for delete modal
        console.log('Show delete modal for message:', messageId);
    }
    
    copyMessage(text) {
        navigator.clipboard.writeText(text).then(() => {
            this.showToast('Message copied to clipboard', 'success');
        }).catch(err => {
            console.error('Failed to copy: ', err);
            this.showToast('Failed to copy message', 'error');
        });
    }
    
    async muteConversation(conversationId) {
        try {
            const response = await this.safeFetch(`/chats/api/mute-conversation/${conversationId}/`, {
                method: 'POST'
            });
            
            if (response.success) {
                this.showToast(`Conversation ${response.status}`, 'success');
            }
        } catch (error) {
            console.error('Error muting conversation:', error);
            this.showToast('Failed to mute conversation', 'error');
        }
    }
    
    async archiveConversation(conversationId) {
        try {
            const response = await this.safeFetch(`/chats/api/delete-conversation/${conversationId}/`, {
                method: 'POST'
            });
            
            if (response.success) {
                this.showToast('Conversation archived', 'success');
                // Remove from list
                this.conversations = this.conversations.filter(c => c.id !== conversationId);
                this.renderConversationList();
            }
        } catch (error) {
            console.error('Error archiving conversation:', error);
            this.showToast('Failed to archive conversation', 'error');
        }
    }
    
    async deleteConversation(conversationId) {
        if (!confirm('Are you sure you want to delete this conversation? This action cannot be undone.')) {
            return;
        }
        
        try {
            const response = await this.safeFetch(`/chats/api/delete-conversation/${conversationId}/`, {
                method: 'POST'
            });
            
            if (response.success) {
                this.showToast('Conversation deleted', 'success');
                // Remove from list
                this.conversations = this.conversations.filter(c => c.id !== conversationId);
                this.renderConversationList();
                
                // If this was the current conversation, close it
                if (this.currentConversationId === conversationId) {
                    this.closeMobileChat();
                }
            }
        } catch (error) {
            console.error('Error deleting conversation:', error);
            this.showToast('Failed to delete conversation', 'error');
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.messaging = new InboxMessaging();
    
    // Expose public methods
    window.loadConversation = function(conversationId, participantName) {
        if (window.messaging) {
            window.messaging.loadConversation(conversationId, participantName);
        }
    };
    
    window.startNewConversation = function() {
        if (window.messaging) {
            window.messaging.startNewConversation();
        }
    };
    
    window.closeMobileChat = function() {
        if (window.messaging) {
            window.messaging.closeMobileChat();
        }
    };
    
    window.startCallWithCurrentUser = function() {
        if (window.messaging) {
            window.messaging.startCallWithCurrentUser();
        }
    };
});