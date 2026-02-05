
(function(){
    'use strict';

    function getCookie(name) {
        if (window.getCookie) return window.getCookie(name);
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

    function createSpinnerHtml(size='sm'){
        return `<span class="spinner-border spinner-border-${size} me-2" role="status" aria-hidden="true"></span>`;
    }

    function setButtonLoading(btn, text){
        if(!btn) return;
        if(btn.dataset.originalHtml) return; // already loading
        btn.dataset.originalHtml = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = createSpinnerHtml('sm') + (text || 'Loading...');
    }

    function resetButton(btn){
        if(!btn) return;
        if(btn.dataset.originalHtml){
            btn.innerHTML = btn.dataset.originalHtml;
            delete btn.dataset.originalHtml;
        }
        btn.disabled = false;
    }

    async function fetchHtmlAndReplace(url, opts){
        const response = await fetch(url, opts);
        const ct = response.headers.get('content-type') || '';
        const text = await response.text();

        if(ct.indexOf('text/html') !== -1){
            try{
                const parser = new DOMParser();
                const doc = parser.parseFromString(text, 'text/html');
                
                // CRITICAL FIX: Only replace the main content area and update title
                // Don't replace the entire body which includes navigation
                if(doc.title) document.title = doc.title;
                
                // Find the main content container in both current and new documents
                const currentMainContent = document.querySelector('.main-content .container-custom');
                const newMainContent = doc.querySelector('.main-content .container-custom');
                
                if(newMainContent && currentMainContent) {
                    // Replace only the content inside the main container
                    currentMainContent.innerHTML = newMainContent.innerHTML;
                    
                    // Update history
                    history.pushState({}, doc.title || '', url);
                    
                    // Trigger custom event for page load
                    window.dispatchEvent(new CustomEvent('ajaxPageLoaded', {
                        detail: { url: url }
                    }));
                    
                    // IMPORTANT: Re-initialize scripts for the new content
                    setTimeout(() => {
                        // Trigger DOMContentLoaded for scripts that depend on it
                        if (typeof initializePage === 'function') {
                            initializePage();
                        }
                        
                        // Re-run badge manager initialization
                        if (window.BadgeManager && typeof window.BadgeManager.initialize === 'function') {
                            window.BadgeManager.initialize();
                        }
                        
                        // Re-initialize any scroll animations
                        const scrollElements = document.querySelectorAll('.scroll-animate');
                        if (scrollElements.length > 0 && typeof handleScrollAnimation === 'function') {
                            handleScrollAnimation();
                        }
                        
                        // Update navigation active states
                        updateNavigationActiveStates();
                    }, 100);
                    
                    return { ok: true, html: text };
                } else {
                    // Fallback: If structure doesn't match, do a full page load
                    console.warn('AJAX: Page structure mismatch, falling back to normal navigation');
                    return { ok: false, error: 'Structure mismatch' };
                }
            }catch(e){
                console.error('AJAX parsing error:', e);
                return { ok: false, error: e };
            }
        }
        return { ok: false, text: text };
    }

    // Helper function to update navigation active states
    function updateNavigationActiveStates() {
        const currentPath = window.location.pathname;
        
        // Update bottom navigation
        const bottomNavLinks = document.querySelectorAll('.bottom-nav-link');
        bottomNavLinks.forEach(link => {
            const href = link.getAttribute('href');
            if (currentPath === href || (currentPath === '/' && href === '/')) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });
        
        // Update side navigation
        const sideNavLinks = document.querySelectorAll('.side-nav-link');
        sideNavLinks.forEach(link => {
            const href = link.getAttribute('href');
            if (currentPath === href || (currentPath === '/' && href === '/')) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });
    }

    document.addEventListener('click', function(e){
        const a = e.target.closest && e.target.closest('a');
        if(!a) return;
        
        // skip external links, targets, downloads, anchors, and opt-out
        const href = a.getAttribute('href');
        if(!href || href.startsWith('#') || href.startsWith('javascript:') || href.startsWith('mailto:') || href.startsWith('tel:')) return;
        if(a.target && a.target !== '_self') return;
        if(a.hasAttribute('download')) return;
        if(a.dataset.noAjax !== undefined || a.classList.contains('no-ajax')) return;
        
        // do not interfere with add-to-cart
        if(a.classList.contains('add-to-cart-btn') || a.classList.contains('action-cart')) return;
        
        // Only intercept UI buttons / nav that look like buttons or have data-ajax
        const isButtonLike = a.classList.contains('btn-custom') || 
                           a.dataset.ajax !== undefined || 
                           a.classList.contains('ajax-link') ||
                           a.classList.contains('nav-link') ||
                           a.classList.contains('side-nav-link') ||
                           a.classList.contains('bottom-nav-link');
        
        // Also intercept main navigation links (except external ones)
        const isInternalLink = href && (
            href.startsWith('/') || 
            href.startsWith(window.location.origin) || 
            !href.includes('://')
        );
        
        if(!isButtonLike && !isInternalLink) return;
        
        e.preventDefault();
        setButtonLoading(a, a.dataset.loadingText || 'Loading...');

        fetchHtmlAndReplace(href, { 
            credentials: 'same-origin', 
            headers: { 'X-Requested-With': 'XMLHttpRequest' } 
        })
        .then(res => {
            if(!res.ok){
                // fallback to normal navigation
                resetButton(a);
                window.location.href = href;
            } else {
                resetButton(a);
            }
        })
        .catch(err => {
            console.error('AJAX link navigation failed', err);
            resetButton(a);
            window.location.href = href;
        });
    });

    document.addEventListener('submit', function(e){
        const form = e.target;
        if(!(form && form.tagName && form.tagName.toLowerCase() === 'form')) return;
        if(form.dataset.noAjax !== undefined || form.classList.contains('no-ajax')) return;
        
        // do not intercept forms explicitly marked to allow normal submit
        // do not interfere with add-to-cart forms (they have add-to-cart class)
        if(form.classList.contains('add-to-cart-form') || form.querySelector('.add-to-cart-btn')) return;

        e.preventDefault();

        const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
        setButtonLoading(submitBtn, submitBtn && submitBtn.dataset.loadingText || 'Submitting...');

        const action = form.getAttribute('action') || window.location.href;
        const method = (form.getAttribute('method') || 'GET').toUpperCase();

        const formData = new FormData(form);

        // Ensure CSRF if POST
        const headers = { 'X-Requested-With': 'XMLHttpRequest' };
        if(method === 'POST' || method === 'PUT' || method === 'PATCH'){
            const csrftoken = getCookie('csrftoken');
            if(csrftoken) headers['X-CSRFToken'] = csrftoken;
        }

        fetch(action, {
            method: method,
            credentials: 'same-origin',
            headers: headers,
            body: method === 'GET' ? null : formData
        }).then(async response => {
            const ct = response.headers.get('content-type') || '';
            
            if(ct.indexOf('application/json') !== -1){
                const json = await response.json();
                if(json.redirect){
                    // try to fetch redirect HTML and replace to avoid full page load
                    try{
                        await fetchHtmlAndReplace(json.redirect, { 
                            credentials: 'same-origin', 
                            headers: { 'X-Requested-With': 'XMLHttpRequest' } 
                        });
                    }catch(err){
                        window.location.href = json.redirect;
                    }
                } else if(json.success){
                    // emit event; pages can listen
                    window.dispatchEvent(new CustomEvent('ajaxFormSuccess', { detail: json }));
                    
                    // Show toast notification if available
                    if(window.showToast && json.message){
                        window.showToast(json.message, 'success');
                    }
                } else {
                    window.dispatchEvent(new CustomEvent('ajaxFormError', { detail: json }));
                    
                    // Show error toast if available
                    if(window.showToast && json.error){
                        window.showToast(json.error, 'error');
                    }
                }
            } else if(ct.indexOf('text/html') !== -1){
                // Handle HTML responses (like search forms, etc.)
                const text = await response.text();
                try{
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(text, 'text/html');
                    
                    if(doc.title) document.title = doc.title;
                    
                    // Find and replace main content only
                    const currentMainContent = document.querySelector('.main-content .container-custom');
                    const newMainContent = doc.querySelector('.main-content .container-custom');
                    
                    if(newMainContent && currentMainContent) {
                        currentMainContent.innerHTML = newMainContent.innerHTML;
                        history.pushState({}, doc.title || '', response.url || action);
                        window.dispatchEvent(new Event('ajaxPageLoaded'));
                    } else {
                        // Fallback
                        window.location.href = response.url || action;
                    }
                }catch(err){
                    // fallback
                    window.location.href = response.url || action;
                }
            } else {
                // unknown response type -> fallback to normal submit
                window.location.href = response.url || action;
            }
        }).catch(err => {
            console.error('AJAX form submit failed', err);
            // On failure, fallback to normal submit once (submit without interception)
            resetButton(submitBtn);
            try{ 
                // Create a temporary form for fallback submission
                const tempForm = document.createElement('form');
                tempForm.method = form.method;
                tempForm.action = form.action;
                tempForm.style.display = 'none';
                
                // Copy all form data
                const formData = new FormData(form);
                for(let [name, value] of formData.entries()){
                    const input = document.createElement('input');
                    input.type = 'hidden';
                    input.name = name;
                    if(value instanceof File){
                        // Can't set File value, skip or handle differently
                        continue;
                    }
                    input.value = value;
                    tempForm.appendChild(input);
                }
                
                document.body.appendChild(tempForm);
                tempForm.submit();
            }catch(e){ 
                window.location.href = action; 
            }
        }).finally(() => {
            resetButton(submitBtn);
        });
    });

    // Provide utility to mark elements as loading programmatically
    window.UIHelpers = {
        setButtonLoading: setButtonLoading,
        resetButton: resetButton,
        fetchHtmlAndReplace: fetchHtmlAndReplace
    };

    // handle back/forward for pushState replacements
    window.addEventListener('popstate', function(e){
        // Load the page via AJAX when navigating back/forward
        fetchHtmlAndReplace(window.location.href, { 
            credentials: 'same-origin', 
            headers: { 'X-Requested-With': 'XMLHttpRequest' } 
        }).catch(err => {
            console.error('AJAX popstate navigation failed', err);
            window.location.reload();
        });
    });

    // Listen for ajaxPageLoaded event to reinitialize components
    window.addEventListener('ajaxPageLoaded', function(e) {
        console.log('AJAX page loaded:', e.detail?.url);
        
        // Reinitialize any page-specific scripts
        if (window.initializePageComponents) {
            window.initializePageComponents();
        }
        
        // Update navigation active states
        updateNavigationActiveStates();
        
        // Re-run scroll animations
        if (typeof handleScrollAnimation === 'function') {
            setTimeout(handleScrollAnimation, 50);
        }
    });

    // Global function to initialize page (can be called from base.html)
    window.initializePage = function() {
        // This function can be overridden by individual pages
        console.log('Page initialized');
    };

})();
