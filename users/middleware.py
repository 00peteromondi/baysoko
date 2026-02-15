# users/middleware.py
import logging
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse

logger = logging.getLogger(__name__)

class SocialAuthExceptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        if 'allauth.socialaccount' in str(type(exception)):
            logger.error(f"Social auth error: {str(exception)}")
            messages.error(request, "Error during social authentication. Please try manual registration.")
            return redirect('register')
        return None


class EmailVerificationMiddleware:
    """
    Redirect authenticated users who have not verified their email
    to the verification page, except for allowed paths.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # List of paths that are exempt from verification check
        exempt_paths = [
            reverse('verify_email'),
            reverse('resend_code'),
            reverse('logout'),
            reverse('verification_required'),
            '/static/',
            '/media/',
            '/users/profile/',   # allow profile pages (including edit) for unverified users
        ]
        # Also exempt admin
        if request.path.startswith('/admin/'):
            return self.get_response(request)

        if request.user.is_authenticated and not request.user.email_verified:
            # Check if current path is exempt
            if not any(request.path.startswith(path) for path in exempt_paths):
                return redirect('verification_required')
        
        return self.get_response(request)