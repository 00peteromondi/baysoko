# users/middleware.py
import logging
from django.shortcuts import redirect
from django.contrib import messages

logger = logging.getLogger(__name__)

class SocialAuthExceptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        # Handle social auth exceptions
        if 'allauth.socialaccount' in str(type(exception)):
            logger.error(f"Social auth error: {str(exception)}")
            messages.error(request, "Error during social authentication. Please try manual registration.")
            return redirect('register')
        return None