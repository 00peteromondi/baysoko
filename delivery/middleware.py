"""
Middleware for delivery app
"""
import logging
from django.utils import timezone

logger = logging.getLogger('delivery')


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