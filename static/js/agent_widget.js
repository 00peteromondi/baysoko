// Agent Widget – handles rich platform entities, apply to form (including title), and creative answers
(function() {
  function wsUrl() {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    return `${proto}://${window.location.host}/ws/agent/`;
  }

  function escapeHtml(unsafe) {
    return String(unsafe)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Convert Cloudinary URL to local media URL (same as inbox)
  function cloudinaryToLocalUrl(cloudinaryUrl) {
    if (!cloudinaryUrl) return null;
    try {
      const url = new URL(cloudinaryUrl);
      const uploadIndex = url.pathname.indexOf('/upload/');
      if (uploadIndex !== -1) {
        let localPath = url.pathname.substring(uploadIndex + 7);
        localPath = localPath.replace(/^v\d+\//, '');
        localPath = localPath.replace(/^media\//, '');
        // Prefer global LOCAL_MEDIA_URL if provided by page (inbox.html sets this)
        const globalBase = (typeof window !== 'undefined' && window.LOCAL_MEDIA_URL) ? window.LOCAL_MEDIA_URL : '/media/';
        const base = globalBase.endsWith('/') ? globalBase.slice(0, -1) : globalBase;
        const path = localPath.startsWith('/') ? localPath.slice(1) : localPath;
        return ensureHttps(base + '/' + path);
      }
    } catch (e) {}
    return null;
  }

  function ensureHttps(url) {
    if (!url) return url;
    if (window.location.protocol === 'https:' && url.startsWith('http://')) {
      return url.replace(/^http:\/\//i, 'https://');
    }
    return url;
  }

  class AgentWidget {
    constructor(container) {
      this.container = container;
      this.input = container.querySelector('[data-agent-input]');
      this.btn = container.querySelector('[data-agent-send]');
      this.applyBtn = container.querySelector('[data-agent-apply]');
      this.closeBtn = container.querySelector('.agent-close');
      this.toggleBtn = container.querySelector('.agent-toggle');
      this.minimizeBtn = container.querySelector('.agent-minimize');
      this.panel = container.querySelector('.agent-panel');
      this.messagesEl = container.querySelector('[data-agent-messages]');
      this.typingEl = container.querySelector('[data-agent-typing]');
      this.unreadBadge = container.querySelector('[data-agent-unread]');
      this.lastData = null;
      this.ws = null;
      this._connect();
      this._bind();
      // restore panel state
      try {
        const s = localStorage.getItem('agent_panel_open');
        if (s === 'true') this.container.classList.add('open');
      } catch (e) {}
      // auto‑generate on listing title input
      try {
        const listingTitle = document.getElementById('id_title');
        if (listingTitle && this.applyBtn) {
          // Keep apply button visible, but also use it for title
          let tmr;
          listingTitle.addEventListener('input', () => {
            clearTimeout(tmr);
            tmr = setTimeout(() => {
              const v = listingTitle.value.trim();
              if (v.length > 4) {
                this._showTyping(true);
                this._sendGenerate(v);
              }
            }, 900);
          });
        }
      } catch (e) {}
    }

    _setStatus(text) {}

    _connect() {
      try {
        this.ws = new WebSocket(wsUrl());
        this.ws.onopen = () => this._setStatus('connected');
        this.ws.onclose = () => {
          this._setStatus('disconnected');
          setTimeout(() => this._connect(), 3000);
        };
        this.ws.onerror = (e) => console.error('WS error', e);
        this.ws.onmessage = (evt) => {
          try {
            const data = JSON.parse(evt.data);
            this._handleMessage(data);
          } catch (e) {
            console.error('Invalid message', e);
          }
        };
      } catch (e) {
        console.error('WS connect failed', e);
      }
    }

    _bind() {
      if (this.toggleBtn) {
        this.toggleBtn.addEventListener('click', () => {
          const open = this.container.classList.toggle('open');
          if (this.panel) this.panel.setAttribute('aria-hidden', (!open).toString());
          this.toggleBtn.setAttribute('aria-expanded', open);
          if (open) {
            this.input?.focus();
            if (this.unreadBadge) this.unreadBadge.hidden = true;
            localStorage.setItem('agent_panel_open', 'true');
          } else {
            localStorage.setItem('agent_panel_open', 'false');
          }
        });
      }

      if (this.minimizeBtn) {
        this.minimizeBtn.addEventListener('click', () => this._closePanel());
      }
      if (this.closeBtn) {
        this.closeBtn.addEventListener('click', () => {
          this._closePanel();
          if (this.input) this.input.value = '';
        });
      }

      if (this.btn && this.input) {
        this.btn.addEventListener('click', () => {
          const text = this.input.value.trim();
          if (!text) return;
          this._appendMessage('user', text);
          this.persistMessage('user', text);
          this.input.value = '';
          this._showTyping(true);
          this._sendGenerate(text);
        });

        if (this.applyBtn) {
          this.applyBtn.addEventListener('click', () => {
            if (this.lastData) applyToListingForm(this.lastData);
          });
        }

        this.input.addEventListener('keydown', (e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            this.btn.click();
          }
        });
        }

        // Offline queue: send queued messages when back online
        window.addEventListener('online', () => {
          this._flushOfflineQueue();
        });
    }

    // Offline message queue persisted in localStorage
    _enqueueOfflineMessage(msg) {
      try {
        const key = 'agent_offline_queue_v1';
        const arr = JSON.parse(localStorage.getItem(key) || '[]');
        arr.push(msg);
        localStorage.setItem(key, JSON.stringify(arr.slice(-50)));
      } catch (e) {}
    }

    async _flushOfflineQueue() {
      try {
        const key = 'agent_offline_queue_v1';
        const arr = JSON.parse(localStorage.getItem(key) || '[]');
        if (!arr || !arr.length) return;
        for (const m of arr) {
          // attempt sending via websocket or fetch
          if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'user_message', conversation_id: m.conversation_id || null, content: m.content }));
          } else {
            await fetch('/chats/api/agent-send/', { method: 'POST', credentials: 'same-origin', headers: {'Content-Type':'application/json'}, body: JSON.stringify(m) });
          }
        }
        localStorage.removeItem(key);
      } catch (e) {
        console.warn('flushOfflineQueue failed', e);
      }
    }

    _showPopupPrompt(text) {
      try {
        // small transient bubble near the toggle button
        const bubble = document.createElement('div');
        bubble.className = 'agent-proactive-bubble';
        bubble.textContent = text;
        bubble.style.position = 'fixed';
        bubble.style.right = '20px';
        bubble.style.bottom = '120px';
        bubble.style.background = 'rgba(0,0,0,0.8)';
        bubble.style.color = 'white';
        bubble.style.padding = '10px 14px';
        bubble.style.borderRadius = '18px';
        bubble.style.zIndex = 99999;
        document.body.appendChild(bubble);
        setTimeout(() => { bubble.classList.add('visible'); }, 50);
        bubble.addEventListener('click', () => { this.container.classList.add('open'); if (this.input) this.input.focus(); bubble.remove(); });
        setTimeout(() => { try{ bubble.remove(); }catch(e){} }, 10000);
      } catch (e) {}
    }

    _closePanel() {
      this.container.classList.remove('open');
      if (this.panel) this.panel.setAttribute('aria-hidden', 'true');
      if (this.toggleBtn) this.toggleBtn.setAttribute('aria-expanded', 'false');
      localStorage.setItem('agent_panel_open', 'false');
      this.input?.blur();
    }

    async loadHistory() {
      try {
        const r = await fetch('/chats/api/agent-history/', { credentials: 'same-origin' });
        if (r.ok) {
          const j = await r.json();
          if (j.success && Array.isArray(j.history)) {
            j.history.forEach(h => this._renderStoredMessage(h));
            return;
          }
        }
      } catch (e) {}
      try {
        const raw = localStorage.getItem('agent_chat_history_v1');
        if (raw) {
          JSON.parse(raw).forEach(h => this._renderStoredMessage(h));
        }
      } catch (e) {}
    }

    _renderStoredMessage(h) {
      const role = h.role === 'user' ? 'user' : 'bot';
      const content = h.content;
      if (role === 'bot' && content && (content.startsWith('{') || content.startsWith('['))) {
        try {
          const parsed = JSON.parse(content);
          if (typeof parsed === 'object' && parsed !== null) {
            const html = this._formatStructuredMessage(parsed);
            this._appendMessage('bot', html, true, h.timestamp);
            return;
          }
        } catch (e) {}

      // Proactive trigger: suggest help when main product image is visible
      try {
        const heroImage = document.querySelector('.main-image');
        if (heroImage && 'IntersectionObserver' in window) {
          const obs = new IntersectionObserver(entries => {
            entries.forEach(en => {
              if (en.isIntersecting) {
                // Wait a short while to ensure user is lingering
                setTimeout(() => {
                  if (!this.container.classList.contains('open')) {
                    // show a gentle prompt (non-intrusive)
                    this._showPopupPrompt("Need help with this item? Ask me anything.");
                  }
                }, 2000);
              }
            });
          }, { threshold: 0.6 });
          obs.observe(heroImage);
        }
      } catch (e) {}
      }
      this._appendMessage(role, escapeHtml(content), false, h.timestamp);
    }

    async persistMessage(role, content, meta, timestamp) {
      const msg = { role, content, meta: meta || null, timestamp: timestamp || new Date().toISOString() };
      try {
        const key = 'agent_chat_history_v1';
        const arr = JSON.parse(localStorage.getItem(key) || '[]');
        arr.push(msg);
        localStorage.setItem(key, JSON.stringify(arr.slice(-200)));
      } catch (e) {}
      try {
        await fetch('/chats/api/agent-history/', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(msg)
        });
      } catch (e) {}
    }

    _sendGenerate(text) {
      let history = null;
      try {
        const raw = localStorage.getItem('agent_chat_history_v1');
        if (raw) history = JSON.parse(raw).slice(-40).map(h => ({ role: h.role, content: h.content }));
      } catch (e) {}
      const payload = { type: 'generate', title: text, history };
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify(payload));
      } else {
        setTimeout(() => {
          if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(payload));
          } else {
            this._showTyping(false);
            const msg = 'Unable to reach assistant. Please try again later.';
            this._appendMessage('bot', msg);
            this.persistMessage('assistant', msg);
            if (this.unreadBadge) this.unreadBadge.hidden = false;
          }
        }, 1000);
      }
    }

    _handleMessage(data) {
      if (data.type === 'generate_response') {
        this._showTyping(false);
        if (data.ok) {
          this.lastData = data.data;
          const html = this._formatStructuredMessage(data.data);
          this._appendMessage('bot', html, true);
          this.persistMessage('assistant', typeof data.data === 'object' ? JSON.stringify(data.data) : String(data.data));
          if (!this.container.classList.contains('open') && this.unreadBadge) this.unreadBadge.hidden = false;
          if (document.getElementById('id_title') && typeof data.data === 'object') {
            this._showApplyModal(data.data);
          }
        } else {
          this._appendMessage('bot', 'Error: ' + (data.error || 'unknown'));
        }
      } else if (data.type === 'error') {
        this._showTyping(false);
        this._appendMessage('bot', 'Error: ' + (data.error || 'unknown'));
      }
    }

    _formatStructuredMessage(d) {
      let html = '';
      // Plain text response
      if (d.text) html += '<div class="agent-desc">' + escapeHtml(d.text) + '</div>';
      else if (d.description) html += '<div class="agent-desc">' + escapeHtml(d.description) + '</div>';

      // Key features (for listing generation)
      if (d.key_features && Array.isArray(d.key_features)) {
        html += '<ul class="agent-features">' + d.key_features.map(f => '<li>' + escapeHtml(f) + '</li>').join('') + '</ul>';
      }
      if (d.category) html += '<div class="agent-meta"><strong>Category:</strong> ' + escapeHtml(d.category) + '</div>';

      // Platform items (listings, stores, orders, subscriptions)
      const items = d.platform_items || d.items || [];
      if (items.length) {
        html += '<div class="agent-suggestions"><strong>Suggestions:</strong><ul>';
        items.forEach(it => {
          let imgUrl = it.image || it.image_url || it.avatar || null;
          if (imgUrl) {
            imgUrl = ensureHttps(imgUrl);
            const localUrl = cloudinaryToLocalUrl(imgUrl);
            if (localUrl) imgUrl = localUrl;
          } else {
            imgUrl = '/static/images/placeholder.png';
          }

          // Build meta info based on type
          let metaHtml = '';
          let actionsHtml = '';

          if (it.type === 'listing' || it.type === 'cart_item') {
            if (it.price) metaHtml += `<span class="agent-suggestion-price">${escapeHtml(it.price)}</span>`;
            if (it.location) metaHtml += `<span class="agent-suggestion-location"><i class="bi bi-geo-alt"></i> ${escapeHtml(it.location)}</span>`;
            if (it.seller) metaHtml += `<span><i class="bi bi-person"></i> ${escapeHtml(it.seller)}</span>`;
            if (it.quantity) metaHtml += `<span><i class="bi bi-box"></i> Qty: ${it.quantity}</span>`;
            actionsHtml = `
              <a href="${it.url || '#'}" class="agent-action-link" target="_blank">View</a>
              ${it.id ? '<button class="agent-action-add" onclick="window.agentAddToCart(' + it.id + ')">Add to cart</button>' : ''}
            `;
          } else if (it.type === 'store') {
            metaHtml += `<span><i class="bi bi-shop"></i> ${escapeHtml(it.owner || '')}</span>`;
            if (it.is_premium) metaHtml += `<span class="badge premium">Premium</span>`;
            if (it.subscription_status) metaHtml += `<span>${escapeHtml(it.subscription_status)}</span>`;
            actionsHtml = `<a href="${it.url || '#'}" class="agent-action-link" target="_blank">Visit store</a>`;
          } else if (it.type === 'order') {
            metaHtml += `<span><i class="bi bi-truck"></i> Status: ${escapeHtml(it.status)}</span>`;
            metaHtml += `<span><i class="bi bi-currency-dollar"></i> Total: ${escapeHtml(it.total)}</span>`;
            if (it.items_preview) metaHtml += `<span>${escapeHtml(it.items_preview)}</span>`;
            actionsHtml = it.url ? `<a href="${it.url}" class="agent-action-link" target="_blank">View order</a>` : '';
          } else if (it.type === 'subscription') {
            metaHtml += `<span>Store: ${escapeHtml(it.store_name)}</span>`;
            metaHtml += `<span>Plan: ${escapeHtml(it.plan)}</span>`;
            metaHtml += `<span>Status: ${escapeHtml(it.status)}</span>`;
            if (it.expires) metaHtml += `<span>Expires: ${new Date(it.expires).toLocaleDateString()}</span>`;
            // No actions by default, maybe manage link later
          }

          html += `
            <li data-item-id="${it.id}" data-item-type="${it.type}">
              <img src="${escapeHtml(imgUrl)}" class="agent-suggestion-image" alt="" onerror="this.onerror=null; this.src='/static/images/placeholder.png';">
              <div class="agent-suggestion-info">
                <div class="agent-suggestion-title">${escapeHtml(it.name || it.title || '')}</div>
                <div class="agent-suggestion-meta">${metaHtml}</div>
              </div>
              <div class="agent-suggestion-actions">${actionsHtml}</div>
            </li>`;
        });
        html += '</ul></div>';
      }
      return html;
    }

    _showTyping(show) {
      if (!this.typingEl) return;
      this.typingEl.hidden = !show;
    }

    _sendFeedback(kind, value) {
      try {
        fetch('/chats/api/agent-feedback/', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message_id: null, feedback: kind, value: !!value })
        }).catch(e => console.warn('feedback send failed', e));
      } catch (e) {}
    }

    _appendMessage(kind, htmlOrText, allowHtml = false, timestamp) {
      if (!this.messagesEl) return;
      const el = document.createElement('div');
      el.className = 'agent-msg ' + kind;
      const contentWrap = document.createElement('div');
      contentWrap.className = 'agent-msg-content';
      if (allowHtml) contentWrap.innerHTML = htmlOrText;
      else contentWrap.textContent = htmlOrText;
      contentWrap.style.whiteSpace = 'pre-wrap';
      contentWrap.style.wordBreak = 'break-word';
      el.appendChild(contentWrap);

      if (timestamp) {
        const ts = document.createElement('div');
        ts.className = 'agent-msg-ts';
        ts.textContent = this._formatTime(timestamp);
        el.appendChild(ts);
      }

      if (kind === 'bot') {
        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'agent-message-actions';
        const copyBtn = document.createElement('button');
        copyBtn.className = 'agent-action-btn';
        copyBtn.innerHTML = '<i class="bi bi-files"></i> Copy';
        copyBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          const text = contentWrap.innerText || contentWrap.textContent;
          navigator.clipboard.writeText(text).then(() => {
            copyBtn.innerHTML = '<i class="bi bi-check-lg"></i> Copied!';
            setTimeout(() => { copyBtn.innerHTML = '<i class="bi bi-files"></i> Copy'; }, 2000);
          }).catch(() => alert('Failed to copy'));
        });
        actionsDiv.appendChild(copyBtn);

        const likeBtn = document.createElement('button');
        likeBtn.className = 'agent-action-btn';
        likeBtn.innerHTML = '<i class="bi bi-hand-thumbs-up"></i>';
        likeBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          likeBtn.classList.toggle('active');
          this._sendFeedback('like', likeBtn.classList.contains('active'));
        });
        actionsDiv.appendChild(likeBtn);

        const dislikeBtn = document.createElement('button');
        dislikeBtn.className = 'agent-action-btn';
        dislikeBtn.innerHTML = '<i class="bi bi-hand-thumbs-down"></i>';
        dislikeBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          dislikeBtn.classList.toggle('active');
          this._sendFeedback('dislike', dislikeBtn.classList.contains('active'));
        });
        actionsDiv.appendChild(dislikeBtn);

        el.appendChild(actionsDiv);
      }

      // Update like/dislike buttons to call feedback endpoint with message id when available
      el.addEventListener('click', (e) => {
        const like = el.querySelector('.agent-action-btn .bi-hand-thumbs-up');
        const dislike = el.querySelector('.agent-action-btn .bi-hand-thumbs-down');
        // nothing to do here — feedback handlers already attached when creating buttons
      });

      this.messagesEl.appendChild(el);
      this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
    }

    _sendFeedback(type, active) {
      console.log(`Feedback: ${type} = ${active}`);
      if (window.showToast) {
        window.showToast(active ? 'Thanks for your feedback!' : 'Feedback removed', 'info');
      }
    }

    _formatTime(iso) {
      try {
        const d = new Date(iso);
        const now = new Date();
        const diff = Math.floor((now - d) / 1000);
        if (diff < 10) return 'just now';
        if (diff < 60) return diff + 's';
        if (diff < 3600) return Math.floor(diff / 60) + 'm';
        if (diff < 86400) return Math.floor(diff / 3600) + 'h';
        return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
      } catch (e) {
        return iso;
      }
    }

    _ensureApplyModal() {
      if (this._applyModal) return this._applyModal;
      const m = document.createElement('div');
      m.className = 'agent-apply-modal';
      m.innerHTML = `
        <div class="agent-apply-preview"></div>
        <div style="text-align:right">
          <button class="agent-apply-cancel btn btn-outline-secondary">Cancel</button>
          <button class="agent-apply-confirm btn btn-primary">Apply</button>
        </div>
      `;
      document.body.appendChild(m);
      m.querySelector('.agent-apply-cancel').addEventListener('click', () => { m.style.display = 'none'; });
      m.querySelector('.agent-apply-confirm').addEventListener('click', () => {
        if (this._pendingApplyData) applyToListingForm(this._pendingApplyData);
        m.style.display = 'none';
      });
      this._applyModal = m;
      return m;
    }

    _showApplyModal(data) {
      try {
        const modal = this._ensureApplyModal();
        this._pendingApplyData = data;
        const preview = modal.querySelector('.agent-apply-preview');
        let html = '';
        if (typeof data === 'object') {
          if (data.title) html += '<p><strong>Title:</strong> ' + escapeHtml(data.title) + '</p>';
          if (data.description) html += '<p><strong>Description:</strong> ' + escapeHtml(data.description) + '</p>';
          if (data.key_features && Array.isArray(data.key_features)) {
            html += '<p><strong>Key features:</strong><ul>' + data.key_features.map(f => '<li>' + escapeHtml(f) + '</li>').join('') + '</ul></p>';
          }
          if (data.category) html += '<p><strong>Category:</strong> ' + escapeHtml(data.category) + '</p>';
        } else {
          html = '<p>' + escapeHtml(String(data)) + '</p>';
        }
        preview.innerHTML = html;
        modal.style.display = 'block';
      } catch (e) {
        console.warn('ShowApplyModal failed', e);
      }
    }
  }

  window.agentAddToCart = function(listingId) {
    const csrftoken = (window.getCookie && window.getCookie('csrftoken')) ||
      (function() {
        const v = document.cookie.split(';').map(c => c.trim()).find(c => c.startsWith('csrftoken='));
        return v ? decodeURIComponent(v.split('=')[1]) : '';
      })();
    fetch('/cart/add/' + listingId + '/', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': csrftoken
      },
      body: JSON.stringify({ quantity: 1 })
    })
      .then(async r => {
        const j = await r.json();
        if (r.ok && j.success) alert(j.message || 'Added to cart');
        else alert(j.error || 'Failed to add to cart');
      })
      .catch(() => alert('Failed to add to cart'));
  };

  function applyToListingForm(data) {
    try {
      // Title
      if (data.title) {
        const titleField = document.getElementById('id_title');
        if (titleField && (!titleField.value || titleField.value.length < 5)) titleField.value = data.title;
      }
      // Description
      if (data.description) {
        const desc = document.getElementById('id_description');
        if (desc && (!desc.value || desc.value.length < 20)) desc.value = data.description;
        const meta = document.getElementById('id_meta_description');
        if (meta && (!meta.value || meta.value.length < 20)) meta.value = (data.meta_description || data.description).slice(0, 160);
      }
      // Category
      if (data.category_id) {
        const cat = document.getElementById('id_category');
        if (cat) {
          cat.value = String(data.category_id);
          cat.dispatchEvent(new Event('change'));
        }
      }
      // Other fields
      const fields = Object.assign({}, data.dynamic_fields || {}, {
        brand: data.brand, model: data.model, color: data.color,
        material: data.material, dimensions: data.dimensions,
        weight: data.weight, price: data.price
      });
      Object.keys(fields).forEach(fn => {
        if (fields[fn] === undefined || fields[fn] === null) return;
        const std = document.getElementById('id_' + fn);
        if (std) {
          if (std.type === 'checkbox') std.checked = !!fields[fn];
          else std.value = fields[fn];
        }
        const dyn = document.getElementById('dynamic_' + fn);
        if (dyn) {
          if (dyn.type === 'checkbox') dyn.checked = !!fields[fn];
          else dyn.value = fields[fn];
        }
      });
    } catch (e) {
      console.warn('applyToListingForm error', e);
    }
  }

  function initAll() {
    document.querySelectorAll('[data-agent-widget]').forEach(el => {
      if (!el.__agent_inited) {
        const aw = new AgentWidget(el);
        aw.loadHistory();
        el.__agent_inited = true;
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }
})();