// Fixed New Conversation Modal
class NewConversationModal {
    constructor() {
        this.selectedUser = null;
        this.selectedListing = null;
        this.attachments = [];
        this.searchTimeout = null;
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.loadUserListings();
    }
    
    setupEventListeners() {
        // User search
        const searchInput = document.getElementById('recipientSearch');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.handleSearch(e.target.value.trim());
            });
        }
        
        // Clear selection
        const clearBtn = document.getElementById('clearSelectionBtn');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearSelection());
        }
        
        // Send message button
        const sendBtn = document.getElementById('sendNewMessageBtn');
        if (sendBtn) {
            sendBtn.addEventListener('click', () => this.sendNewMessage());
        }
        
        // Message input character count
        const messageText = document.getElementById('messageText');
        if (messageText) {
            messageText.addEventListener('input', (e) => {
                this.updateCharCount(e.target.value.length);
                this.updateMessagePreview(e.target.value);
            });
        }
        
        // File attachment
        const fileInput = document.getElementById('fileInput');
        if (fileInput) {
            fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
        }
        
        // Listing selection
        const listingSelect = document.getElementById('listingSelect');
        if (listingSelect) {
            listingSelect.addEventListener('change', (e) => {
                this.selectedListing = e.target.value === 'none' ? null : e.target.value;
            });
        }
    }
    
    handleSearch(query) {
        clearTimeout(this.searchTimeout);
        
        if (query.length < 2) {
            this.showInitialState();
            return;
        }
        
        this.searchTimeout = setTimeout(() => {
            this.searchUsers(query);
        }, 300);
    }
    
    async searchUsers(query) {
        try {
            this.showLoadingState();
            
            const response = await fetch(`/chats/api/search-users/?q=${encodeURIComponent(query)}`);
            const data = await response.json();
            
            if (data.success && data.users && data.users.length > 0) {
                this.renderUserResults(data.users);
            } else {
                this.showNoResults();
            }
        } catch (error) {
            console.error('Search error:', error);
            this.showErrorState();
        }
    }
    
    renderUserResults(users) {
        const container = document.getElementById('recipientResults');
        if (!container) return;
        
        container.innerHTML = '';
        
        users.forEach(user => {
            const userElement = this.createUserResultItem(user);
            container.appendChild(userElement);
        });
    }
    
    createUserResultItem(user) {
        const item = document.createElement('div');
        item.className = 'user-result-item';
        item.dataset.userId = user.id;
        
        const isSelected = this.selectedUser && this.selectedUser.id === user.id;
        
        item.innerHTML = `
            <div class="user-avatar">
                <img src="${user.avatar}" alt="${user.name}"
                     onerror="this.src='https://placehold.co/48x48/c2c2c2/1f1f1f?text=User'">
            </div>
            <div class="user-info">
                <div class="user-name">${user.name}</div>
                <div class="user-meta">
                    <span>@${user.username}</span>
                    ${user.last_login ? `<span class="ms-2"><i class="bi bi-circle-fill text-success small"></i> ${user.last_login}</span>` : ''}
                </div>
            </div>
            ${isSelected ? '<i class="bi bi-check-circle-fill text-primary"></i>' : ''}
        `;
        
        item.addEventListener('click', () => this.selectUser(user));
        
        return item;
    }
    
    selectUser(user) {
        this.selectedUser = user;
        
        // Update UI
        document.querySelectorAll('.user-result-item').forEach(item => {
            item.classList.remove('selected');
            if (parseInt(item.dataset.userId) === user.id) {
                item.classList.add('selected');
            }
        });
        
        // Show selected user info
        document.getElementById('selectedUserInfo').style.display = 'block';
        document.getElementById('selectedUserName').textContent = user.name;
        document.getElementById('selectedUserAvatar').src = user.avatar;
        document.getElementById('selectedUserMeta').textContent = `@${user.username}`;
        
        // Enable send button
        const messageText = document.getElementById('messageText');
        const sendBtn = document.getElementById('sendNewMessageBtn');
        if (sendBtn) {
            sendBtn.disabled = !messageText.value.trim() && this.attachments.length === 0;
        }
        
        // Update message preview
        this.updateMessagePreview(messageText ? messageText.value : '');
    }
    
    clearSelection() {
        this.selectedUser = null;
        this.attachments = [];
        
        // Update UI
        document.getElementById('selectedUserInfo').style.display = 'none';
        document.querySelectorAll('.user-result-item').forEach(item => {
            item.classList.remove('selected');
        });
        
        // Reset message input
        const messageText = document.getElementById('messageText');
        if (messageText) messageText.value = '';
        
        // Reset file input
        const fileInput = document.getElementById('fileInput');
        if (fileInput) fileInput.value = '';
        
        // Disable send button
        const sendBtn = document.getElementById('sendNewMessageBtn');
        if (sendBtn) sendBtn.disabled = true;
        
        // Update preview
        this.updateMessagePreview('');
        this.updateCharCount(0);
    }
    
    async sendNewMessage() {
        if (!this.selectedUser) {
            this.showToast('Please select a recipient', 'error');
            return;
        }
        
        const messageText = document.getElementById('messageText');
        const message = messageText ? messageText.value.trim() : '';
        
        if (!message && this.attachments.length === 0) {
            this.showToast('Please enter a message or attach a file', 'error');
            return;
        }
        
        const sendBtn = document.getElementById('sendNewMessageBtn');
        const originalText = sendBtn.innerHTML;
        sendBtn.disabled = true;
        sendBtn.innerHTML = '<i class="bi bi-hourglass me-2"></i> Sending...';
        
        try {
            const formData = new FormData();
            formData.append('recipient_id', this.selectedUser.id);
            formData.append('message', message);
            
            if (this.selectedListing) {
                formData.append('listing_id', this.selectedListing);
            }
            
            // Add attachments
            this.attachments.forEach((file, index) => {
                formData.append(`attachment_${index}`, file);
            });
            
            const response = await fetch('/chats/api/send-message/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCookie('csrftoken'),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: formData
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showToast('Message sent successfully!', 'success');
                
                // Close modal and redirect to conversation
                setTimeout(() => {
                    const modal = bootstrap.Modal.getInstance(document.getElementById('newMessageModal'));
                    if (modal) modal.hide();
                    
                    // Redirect to the new conversation
                    if (data.conversation_id) {
                        window.location.href = `/chats/?open=${data.conversation_id}`;
                    }
                }, 1500);
            } else {
                this.showToast(data.error || 'Failed to send message', 'error');
                sendBtn.disabled = false;
            }
            
        } catch (error) {
            console.error('Error sending message:', error);
            this.showToast('Error sending message. Please try again.', 'error');
            sendBtn.disabled = false;
        } finally {
            sendBtn.innerHTML = originalText;
        }
    }
    
    handleFileSelect(event) {
        const files = Array.from(event.target.files);
        const maxSize = 25 * 1024 * 1024; // 25MB
        const allowedTypes = [
            'image/jpeg', 'image/png', 'image/gif', 'image/webp',
            'application/pdf', 'application/msword', 
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'text/plain', 'application/zip'
        ];
        
        files.forEach(file => {
            if (!allowedTypes.includes(file.type)) {
                this.showToast(`File type not allowed: ${file.name}`, 'error');
                return;
            }
            
            if (file.size > maxSize) {
                this.showToast(`File too large (max 25MB): ${file.name}`, 'error');
                return;
            }
            
            this.attachments.push(file);
        });
        
        // Update preview
        this.updateMessagePreview(document.getElementById('messageText')?.value || '');
        event.target.value = '';
    }
    
    updateMessagePreview(message) {
        const previewArea = document.getElementById('messagePreviewArea');
        if (!previewArea) return;
        
        if (!this.selectedUser) {
            previewArea.innerHTML = `
                <div class="text-center py-5 text-muted">
                    <i class="bi bi-chat-left-text display-6 opacity-25 mb-3"></i>
                    <h6 class="mb-2">No user selected</h6>
                    <p class="small mb-0">Select a user to start writing your message</p>
                </div>
            `;
            return;
        }
        
        let previewHTML = `
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h6 class="mb-0">Message Preview</h6>
                <span class="badge bg-primary">To: ${this.selectedUser.name}</span>
            </div>
        `;
        
        if (message || this.attachments.length > 0) {
            previewHTML += `
                <div class="message-preview-bubble">
                    <div class="message-content bg-primary text-white rounded-3 p-3">
                        ${message ? `<div class="message-text">${this.escapeHtml(message)}</div>` : ''}
            `;
            
            // Add attachments preview
            if (this.attachments.length > 0) {
                previewHTML += '<div class="mt-3">';
                this.attachments.forEach((file, index) => {
                    if (file.type.startsWith('image/')) {
                        const reader = new FileReader();
                        reader.onload = (e) => {
                            const img = document.createElement('img');
                            img.src = e.target.result;
                            img.className = 'img-thumbnail me-2';
                            img.style.maxWidth = '60px';
                            previewArea.querySelector('.attachments-container')?.appendChild(img);
                        };
                        reader.readAsDataURL(file);
                    }
                    
                    previewHTML += `
                        <div class="attachment-preview d-flex align-items-center mb-2">
                            <i class="bi bi-file-earmark-text me-2"></i>
                            <div class="flex-grow-1">
                                <div class="small">${file.name}</div>
                                <div class="text-white-50 small">${this.formatFileSize(file.size)}</div>
                            </div>
                        </div>
                    `;
                });
                previewHTML += '</div>';
            }
            
            previewHTML += `
                    </div>
                </div>
            `;
        } else {
            previewHTML += `
                <div class="text-center py-4 text-muted">
                    <i class="bi bi-chat-left-text display-6 opacity-25 mb-3"></i>
                    <p class="mb-0">Your message will appear here</p>
                </div>
            `;
        }
        
        previewArea.innerHTML = previewHTML;
    }
    
    updateCharCount(length) {
        const charCount = document.getElementById('charCount');
        if (charCount) {
            charCount.textContent = `${length}/1000`;
            
            if (length > 1000) {
                charCount.classList.add('text-danger');
                document.getElementById('sendNewMessageBtn').disabled = true;
            } else {
                charCount.classList.remove('text-danger');
                const sendBtn = document.getElementById('sendNewMessageBtn');
                if (sendBtn && this.selectedUser && (length > 0 || this.attachments.length > 0)) {
                    sendBtn.disabled = false;
                }
            }
        }
    }
    
    async loadUserListings() {
        try {
            const response = await fetch('/chats/api/my-listings/');
            const data = await response.json();
            
            const select = document.getElementById('listingSelect');
            if (!select) return;
            
            // Clear existing options except the first two
            while (select.options.length > 2) {
                select.remove(2);
            }
            
            if (data.listings && data.listings.length > 0) {
                data.listings.forEach(listing => {
                    const option = document.createElement('option');
                    option.value = listing.id;
                    option.textContent = `${listing.title} ($${listing.price})`;
                    select.appendChild(option);
                });
            }
            
        } catch (error) {
            console.error('Error loading listings:', error);
        }
    }
    
    // UI State Helpers
    showLoadingState() {
        const container = document.getElementById('recipientResults');
        if (container) {
            container.innerHTML = `
                <div class="text-center py-5">
                    <div class="spinner-border spinner-border-sm text-primary mb-3" role="status"></div>
                    <p class="mb-0 text-muted">Searching...</p>
                </div>
            `;
        }
    }
    
    showNoResults() {
        const container = document.getElementById('recipientResults');
        if (container) {
            container.innerHTML = `
                <div class="text-center py-5 text-muted">
                    <i class="bi bi-search display-6 opacity-25 mb-3"></i>
                    <h6 class="mb-2">No users found</h6>
                    <p class="small mb-0">Try a different search term</p>
                </div>
            `;
        }
    }
    
    showErrorState() {
        const container = document.getElementById('recipientResults');
        if (container) {
            container.innerHTML = `
                <div class="text-center py-5 text-danger">
                    <i class="bi bi-exclamation-triangle display-6 mb-3"></i>
                    <p class="mb-0">Error searching users</p>
                </div>
            `;
        }
    }
    
    showInitialState() {
        const container = document.getElementById('recipientResults');
        if (container) {
            container.innerHTML = `
                <div class="text-center py-5 text-muted">
                    <i class="bi bi-search display-6 opacity-25 mb-3"></i>
                    <p class="mb-0">Start typing to search for users</p>
                </div>
            `;
        }
    }
    
    // Utility Methods
    formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' bytes';
        else if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
        else return (bytes / 1048576).toFixed(1) + ' MB';
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
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
        // Simple toast implementation
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} alert-dismissible fade show`;
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            min-width: 300px;
        `;
        toast.innerHTML = `
            ${type === 'success' ? '<i class="bi bi-check-circle me-2"></i>' : '<i class="bi bi-exclamation-triangle me-2"></i>'}
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 5000);
    }
}

// Initialize modal when shown
document.addEventListener('DOMContentLoaded', () => {
    const newMessageModal = document.getElementById('newMessageModal');
    if (newMessageModal) {
        let newConversationModal = null;
        
        newMessageModal.addEventListener('show.bs.modal', () => {
            newConversationModal = new NewConversationModal();
        });
        
        newMessageModal.addEventListener('hidden.bs.modal', () => {
            newConversationModal = null;
        });
    }
});