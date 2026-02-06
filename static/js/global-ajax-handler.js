
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
        // Use a compact spinner and inline sizing so it fits inside buttons/links
        const dim = size === 'sm' ? '1rem' : '1.25rem';
        return `<span class="spinner-border spinner-border-${size} me-2" role="status" aria-hidden="true" style="width:${dim};height:${dim};vertical-align:middle"></span>`;
    }

    // Resolve a possibly-relative URL to an absolute href for robust comparisons
    function resolveUrl(u){
        try{ return new URL(u, window.location.origin).href; }catch(e){ return String(u || ''); }
    }

    function setButtonLoading(btn, text){
        if(!btn) return;
        if(btn.dataset.originalHtml) return; // already loading
        btn.dataset.originalHtml = btn.innerHTML;

        const tag = btn.tagName && btn.tagName.toLowerCase();
        if(tag === 'a' || btn.classList.contains('btn-custom')){
            // anchor-like elements: add disabled state and prevent clicks
            btn.dataset.savedPointerEvents = btn.style.pointerEvents || '';
            btn.classList.add('disabled');
            btn.setAttribute('aria-disabled', 'true');
            btn.style.pointerEvents = 'none';
        } else {
            try { btn.disabled = true; } catch (e) {}
        }

        btn.innerHTML = createSpinnerHtml('sm') + (text || '');
    }

    function resetButton(btn){
        if(!btn) return;
        if(btn.dataset.originalHtml){
            btn.innerHTML = btn.dataset.originalHtml;
            delete btn.dataset.originalHtml;
        }

        const tag = btn.tagName && btn.tagName.toLowerCase();
        if(tag === 'a' || btn.classList.contains('btn-custom')){
            btn.classList.remove('disabled');
            btn.removeAttribute('aria-disabled');
            if(btn.dataset.savedPointerEvents !== undefined){
                btn.style.pointerEvents = btn.dataset.savedPointerEvents;
                delete btn.dataset.savedPointerEvents;
            } else {
                btn.style.pointerEvents = '';
            }
        } else {
            try { btn.disabled = false; } catch (e) {}
        }
    }

    function setFormLoading(form, text){
        if(!form) return;
        const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
        if(submitBtn){
            setButtonLoading(submitBtn, text);
            form.__submitBtn = submitBtn;
            return;
        }

        // If no submit button, create an overlay to indicate loading
        if(form.dataset.loadingOverlay) return;
        // ensure form has positioning context
        const prevPos = window.getComputedStyle(form).position;
        if(prevPos === 'static' || !prevPos){
            form.dataset.prevPosition = 'static';
            form.style.position = 'relative';
        }

        const overlay = document.createElement('div');
        overlay.className = 'form-loading-overlay';
        overlay.style.position = 'absolute';
        overlay.style.top = '0';
        overlay.style.left = '0';
        overlay.style.right = '0';
        overlay.style.bottom = '0';
        overlay.style.display = 'flex';
        overlay.style.alignItems = 'center';
        overlay.style.justifyContent = 'center';
        overlay.style.background = 'rgba(255,255,255,0.6)';
        overlay.style.zIndex = '9999';
        overlay.innerHTML = createSpinnerHtml('sm') + (text || 'Submitting...');
        form.appendChild(overlay);
        form.dataset.loadingOverlay = '1';
        form.__overlay = overlay;
    }

    function resetFormLoading(form){
        if(!form) return;
        if(form.__submitBtn){
            try{ resetButton(form.__submitBtn); }catch(e){}
            delete form.__submitBtn;
            return;
        }
        if(form.dataset.loadingOverlay && form.__overlay){
            try{ form.__overlay.remove(); }catch(e){}
            delete form.__overlay;
            delete form.dataset.loadingOverlay;
            if(form.dataset.prevPosition){
                form.style.position = '';
                delete form.dataset.prevPosition;
            }
        }
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
                
                // IMPORTANT: Ensure head-level stylesheets and inline styles are preserved
                // Copy stylesheet links from parsed document head into current head if missing
                const headLinks = Array.from(doc.head.querySelectorAll('link[rel="stylesheet"]'));
                headLinks.forEach(link => {
                    const href = link.getAttribute('href') || link.href;
                    if (!href) return;
                    const hrefAbs = resolveUrl(href);
                    const exists = Array.from(document.head.querySelectorAll('link[rel="stylesheet"]')).some(existing => resolveUrl(existing.getAttribute('href') || existing.href) === hrefAbs);
                    if (!exists) {
                        const newLink = document.createElement('link');
                        newLink.rel = 'stylesheet';
                        newLink.href = hrefAbs;
                        document.head.appendChild(newLink);
                    }
                });

                // Copy inline <style> blocks from parsed document head, avoid exact duplicates
                const headStyles = Array.from(doc.head.querySelectorAll('style'));
                headStyles.forEach(s => {
                    const text = (s.textContent || '').trim();
                    if (!text) return;
                    const exists = Array.from(document.head.querySelectorAll('style')).some(existing => (existing.textContent || '').trim() === text);
                    if (!exists) {
                        const ns = document.createElement('style');
                        ns.textContent = text;
                        document.head.appendChild(ns);
                    }
                });

                // Copy any <style> blocks that live in the fetched document's <body>
                const bodyStyles = Array.from(doc.body.querySelectorAll('style'));
                bodyStyles.forEach(s => {
                    const text = (s.textContent || '').trim();
                    if (!text) return;
                    const exists = Array.from(document.head.querySelectorAll('style')).some(existing => (existing.textContent || '').trim() === text);
                    if (!exists) {
                        const ns = document.createElement('style');
                        ns.textContent = text;
                        document.head.appendChild(ns);
                    }
                });

                // Find the main content container in both current and new documents
                const currentMainContent = document.querySelector('.main-content .container-custom');
                const newMainContent = doc.querySelector('.main-content .container-custom');
                
                if(newMainContent && currentMainContent) {
                    // Replace only the content inside the main container
                    // Preserve head-level assets by only swapping the main content
                    currentMainContent.innerHTML = newMainContent.innerHTML;

                    // Ensure any <link rel="stylesheet"> in the injected content is added to head
                    const newLinks = Array.from(newMainContent.querySelectorAll('link[rel="stylesheet"]'));
                    newLinks.forEach(link => {
                        const href = link.getAttribute('href') || link.href;
                        if (!href) return;
                        const hrefAbs = resolveUrl(href);
                        const exists = Array.from(document.head.querySelectorAll('link[rel="stylesheet"]')).some(existing => resolveUrl(existing.getAttribute('href') || existing.href) === hrefAbs);
                        if (!exists) {
                            const newLink = document.createElement('link');
                            newLink.rel = 'stylesheet';
                            newLink.href = hrefAbs;
                            document.head.appendChild(newLink);
                        }
                    });

                    // Copy inline <style> blocks from the injected content into head (avoid duplicates)
                    const injectedStyles = Array.from(newMainContent.querySelectorAll('style'));
                    injectedStyles.forEach(s => {
                        const text = (s.textContent || '').trim();
                        if (!text) return;
                        const exists = Array.from(document.head.querySelectorAll('style')).some(existing => (existing.textContent || '').trim() === text);
                        if (!exists) {
                            const ns = document.createElement('style');
                            ns.textContent = text;
                            document.head.appendChild(ns);
                        }
                    });

                    // Execute any scripts included in the new content (inline and external)
                    const scripts = Array.from(newMainContent.querySelectorAll('script'));
                    scripts.forEach(s => {
                        try {
                            if (s.src) {
                                // External script - load it and avoid duplicates
                                const srcAbs = resolveUrl(s.getAttribute('src') || s.src);
                                const existsScript = Array.from(document.querySelectorAll('script[src]')).some(existing => resolveUrl(existing.getAttribute('src') || existing.src) === srcAbs);
                                if (!existsScript) {
                                    const ext = document.createElement('script');
                                    ext.src = srcAbs;
                                    ext.async = false;
                                    document.body.appendChild(ext);
                                }
                            } else if (s.textContent && s.textContent.trim()) {
                                // Inline script - evaluate in global scope
                                const inline = document.createElement('script');
                                inline.text = s.textContent;
                                document.body.appendChild(inline);
                            }
                        } catch (err) {
                            console.warn('Failed to evaluate injected script', err);
                        }
                    });
                    
                    // Update history
                    history.pushState({}, doc.title || '', url);
                    
                    // Trigger custom event for page load
                    window.dispatchEvent(new CustomEvent('ajaxPageLoaded', {
                        detail: { url: url }
                    }));
                    
                    // Replace navigation fragments when provided in fetched HTML so auth/UI updates are reflected
                    try {
                        const newMainNav = doc.querySelector('.main-nav');
                        const currentMainNav = document.querySelector('.main-nav');
                        if (newMainNav && currentMainNav) {
                            currentMainNav.replaceWith(newMainNav.cloneNode(true));
                        }

                        const newSideNav = doc.querySelector('.side-nav');
                        const currentSideNav = document.querySelector('.side-nav');
                        if (newSideNav && currentSideNav) {
                            currentSideNav.replaceWith(newSideNav.cloneNode(true));
                        }
                    } catch (err) { console.warn('Failed to replace nav fragments', err); }

                    // Copy body attributes (classes, data-*) so page-level styling and attributes persist
                    try {
                        const attrs = Array.from(doc.body.attributes || []);
                        attrs.forEach(attr => {
                            if (!attr) return;
                            document.body.setAttribute(attr.name, attr.value);
                        });
                    } catch (err) { console.warn('Failed to copy body attributes', err); }

                    // Copy any inline styles from the fetched body (not inside main content)
                    try {
                        const injectedBodyStyles = Array.from(doc.body.querySelectorAll('style'));
                        injectedBodyStyles.forEach(s => {
                            const text = (s.textContent || '').trim();
                            if (!text) return;
                            const exists = Array.from(document.head.querySelectorAll('style')).some(existing => (existing.textContent || '').trim() === text);
                            if (!exists) {
                                const ns = document.createElement('style');
                                ns.textContent = text;
                                document.head.appendChild(ns);
                            }
                        });
                    } catch (err) { console.warn('Failed to inject body styles', err); }

                    // IMPORTANT: Re-initialize scripts and components for the new content
                    setTimeout(() => {
                        // Trigger DOMContentLoaded-like hook for page scripts
                        if (typeof initializePage === 'function') {
                            try { initializePage(); } catch (e) { console.warn(e); }
                        }

                        // Re-run badge manager initialization if available
                        if (window.BadgeManager && typeof window.BadgeManager.initialize === 'function') {
                            try { window.BadgeManager.initialize(); } catch (e) { console.warn(e); }
                        }

                        // Re-initialize scroll animations if handler exists
                        const scrollElements = document.querySelectorAll('.scroll-animate');
                        if (scrollElements.length > 0 && typeof handleScrollAnimation === 'function') {
                            try { handleScrollAnimation(); } catch (e) { console.warn(e); }
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
        // Option A: Show loading spinner for a few seconds, then reload the page
        const linkLabel = (a.innerText || a.textContent || a.dataset.loadingText || '').trim();
        setButtonLoading(a, linkLabel);
        
        // After 3 seconds (or when ready), perform full-page reload
        // This ensures proper CSS/style loading and auth state parity
        setTimeout(() => { 
            window.location.href = href; 
        }, 3000);
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
        const submitLabel = submitBtn && ((submitBtn.dataset && submitBtn.dataset.loadingText) || (submitBtn.innerText || submitBtn.value)) || 'Submitting...';
        setFormLoading(form, (submitLabel || 'Submitting...').trim());

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

            // If the response was an HTTP redirect, perform a full navigation
            if(response.redirected){
                window.location.href = response.url;
                return;
            }

            if(ct.indexOf('application/json') !== -1){
                const json = await response.json();
                // If server asks us to redirect, force a full page reload to that URL
                if(json.redirect){
                    window.location.href = json.redirect;
                    return;
                }

                if(json.success){
                    window.dispatchEvent(new CustomEvent('ajaxFormSuccess', { detail: json }));
                    if(window.showToast && json.message){ window.showToast(json.message, 'success'); }
                    return;
                } else {
                    window.dispatchEvent(new CustomEvent('ajaxFormError', { detail: json }));
                    if(window.showToast && json.error){ window.showToast(json.error, 'error'); }
                    return;
                }
            }

            // For HTML or unknown content types, do a full page navigation to ensure
            // CSS and scripts load properly (avoids partial DOM replacement which
            // can lose styles and initialization).
            window.location.href = response.url || action;
        }).catch(err => {
            console.error('AJAX form submit failed', err);
            // On failure, fallback to normal submit once (submit without interception)
            resetFormLoading(form);
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
            resetFormLoading(form);
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
