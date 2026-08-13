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
        # Skip profile completion enforcement for delivery app routes
        if request.path.startswith('/delivery/'):
            return self.get_response(request)
        # List of paths that are exempt from verification/phone checks
        exempt_paths = [
            reverse('verify_email'),
            reverse('resend_code'),
            reverse('logout'),
            reverse('verification_required'),
            reverse('login'),
            reverse('register'),
        ]
        # Also exempt admin
        if request.path.startswith('/admin/'):
            return self.get_response(request)

        if request.user.is_authenticated:
            # Always allow admin/static/media
            if request.path.startswith('/admin/') or request.path.startswith('/static/') or request.path.startswith('/media/'):
                return self.get_response(request)

            # If user was created via delivery app, sync missing fields from delivery profile
            try:
                delivery_profile = getattr(request.user, 'delivery_profile', None)
                if delivery_profile:
                    updated = False
                    if not request.user.phone_number and getattr(delivery_profile, 'phone_number', None):
                        request.user.phone_number = delivery_profile.phone_number
                        updated = True
                    if not request.user.location:
                        loc = getattr(delivery_profile, 'city', '') or getattr(delivery_profile, 'address', '')
                        if loc:
                            request.user.location = loc
                            updated = True
                    if updated:
                        request.user.save(update_fields=['phone_number', 'location'])
                        if not request.session.get('profile_sync_notice'):
                            request.session['profile_sync_notice'] = True
                            messages.info(request, 'We synced your delivery profile details to your marketplace account.')
            except Exception:
                pass

            # If user not verified, force verification_required except on exempt paths
            if not request.user.email_verified:
                if not any(request.path.startswith(path) for path in exempt_paths):
                    return redirect('verification_required')

            # If user verified but has no phone_number, force profile-edit
            elif request.user.email_verified and not request.user.phone_number:
                # allow profile-edit and logout and verify endpoints
                allowed_for_phone = [reverse('profile-edit', kwargs={'pk': request.user.pk}), reverse('logout'), reverse('verification_required')]
                if not any(request.path.startswith(path) for path in allowed_for_phone):
                    try:
                        messages.info(request, 'Please add your phone number to complete your profile before continuing.')
                    except Exception:
                        pass
                    return redirect('profile-edit', pk=request.user.pk)
        return self.get_response(request)
