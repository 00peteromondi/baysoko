"""
CSRF Referer Bypass Middleware for Local Development

This middleware relaxes CSRF referer checking in local development environments
while maintaining full CSRF token validation. This prevents false-positive CSRF
rejections when the browser doesn't send a Referer header.

In production, standard Django CSRF validation is used.
"""

from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.middleware.csrf import get_token
import logging

logger = logging.getLogger(__name__)


class CSRFRefererBypassMiddleware(MiddlewareMixin):
    """
    Middleware to allow missing/mismatched Referers in local development.
    
    This is safe because:
    1. CSRF tokens are still validated
    2. CSRF_TRUSTED_ORIGINS restricts which domains can submit
    3. This only applies in DEBUG/local development mode
    
    Why this is needed:
    - Some browsers don't send Referer headers by default
    - Local development with HTTP (not HTTPS) sometimes has referer issues
    - Django's default behavior rejects these as CSRF violations
    """
    
    def process_request(self, request):
        """
        Bypass referer check for local development.
        This is applied before CSRF middleware runs.
        """
        # Ensure CSRF token is generated for ALL requests
        # This must happen early so token is available in forms
        token = get_token(request)
        
        # Only in local development, bypass referer check
        if not (settings.DEBUG or getattr(settings, 'RUNNING_RUNSERVER', False)):
            return None
        
        # Mark request to bypass referer check in CSRF middleware
        # The CSRF middleware will still validate the token itself
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            # Add a flag that CSRF middleware can check
            request._csrf_bypass_referer_check = True
            
            # Ensure the request has a META.HTTP_REFERER key
            # If missing, prevent CSRF middleware from rejecting based on missing referer
            if 'HTTP_REFERER' not in request.META:

                # Set a dummy referer to match the host
                request.META['HTTP_REFERER'] = f"{request.scheme}://{request.get_host()}/"
                request._referer_was_missing = True
        
        return None


class CSRFCookieEnsureMiddleware(MiddlewareMixin):
    """
    Ensure CSRF cookie is set for all authenticated users.
    
    This ensures that the CSRF token cookie is present when users
    access forms that need CSRF tokens.
    """
    
    def process_response(self, request, response):
        """Add CSRF token cookie to response if not present."""
        from django.views.decorators.csrf import ensure_csrf_cookie
        
        if request.user.is_authenticated and 'csrftoken' not in request.COOKIES:
            # Mark response to include CSRF token cookie
            response['Set-Cookie'] = f"csrftoken={request.META.get('CSRF_COOKIE', '')}; Path=/; SameSite=Lax"
        
        return response
