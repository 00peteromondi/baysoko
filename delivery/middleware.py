"""
Middleware for delivery app
"""
import logging
from django.utils import timezone
from django.contrib.auth import logout
from django.shortcuts import redirect

logger = logging.getLogger('delivery')

class DeliveryAppSessionMiddleware:
    """Force delivery app sessions to be isolated from main app logins."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or ''
        if path.startswith('/delivery/'):
            # For AJAX/JSON probes, avoid redirects that can disrupt main-app sessions
            is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
            accepts_json = 'application/json' in (request.headers.get('accept') or '').lower()
            is_probe = path.startswith('/delivery/quick-stats') or path.startswith('/delivery/notification-count')
            if getattr(request, 'user', None) and request.user.is_authenticated:
                if not request.session.get('delivery_auth', False):
                    # If user just authenticated via social login from delivery app, honor intent
                    try:
                        if request.session.get('delivery_login_intent'):
                            request.session['delivery_auth'] = True
                            request.session.pop('delivery_login_intent', None)
                            return self.get_response(request)
                    except Exception:
                        pass
                    if is_ajax or accepts_json or is_probe:
                        from django.http import JsonResponse
                        return JsonResponse({'detail': 'Delivery login required.'}, status=401)
                    # Redirect protected areas to delivery login
                    allowed_prefixes = ['/delivery/login', '/delivery/register', '/delivery/driver/register', '/delivery/home', '/delivery/profile/complete', '/delivery/track']
                    if not (path == '/delivery/' or any(path.startswith(p) for p in allowed_prefixes)):
                        return redirect('delivery:login')
                else:
                    # Enforce delivery profile completion for sellers (buyers can track without completing)
                    allowed_prefixes = ['/delivery/login', '/delivery/register', '/delivery/driver/register', '/delivery/home', '/delivery/profile/complete', '/delivery/logout']
                    if not (path == '/delivery/' or any(path.startswith(p) for p in allowed_prefixes)):
                        try:
                            if not (request.user.is_staff or request.user.is_superuser or hasattr(request.user, 'delivery_person')):
                                from storefront.models import Store
                                is_seller = Store.objects.filter(owner=request.user).exists()
                                if is_seller and not hasattr(request.user, 'delivery_profile'):
                                    return redirect('delivery:profile_complete')
                        except Exception:
                            pass
                    # Buyers should have full access to delivery app features (not just tracking)
                    # so we do not restrict non-seller users here.
        return self.get_response(request)


class DeliveryLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Log delivery-related requests
        if request.path.startswith('/delivery/'):
            start_time = timezone.now()
            
            response = self.get_response(request)
            
            duration = timezone.now() - start_time
            
            logger.info(
                f"Delivery request: {request.method} {request.path} "
                f"Duration: {duration.total_seconds():.2f}s "
                f"User: {request.user.username if request.user.is_authenticated else 'Anonymous'}"
            )
            
            return response
        
        return self.get_response(request)
    
class SellerStoreMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Add stores and role flags to request for downstream use
        request.stores = None
        request.is_seller = False
        request.is_delivery_person = False

        user = getattr(request, 'user', None)
        if user and getattr(user, 'is_authenticated', False):
            try:
                from storefront.models import Store
                stores_qs = Store.objects.filter(owner=user)
                request.stores = stores_qs
                request.is_seller = stores_qs.exists()
            except Exception:
                # Ensure attributes exist even on import errors
                request.stores = Store.objects.none() if 'Store' in globals() else []
                request.is_seller = False

            # Delivery person flag - prefer attribute if attached to user
            try:
                request.is_delivery_person = hasattr(user, 'delivery_person') and user.delivery_person is not None
            except Exception:
                request.is_delivery_person = False

            # Do not modify user permissions here; scoping is enforced in views
        
        response = self.get_response(request)
        return response
