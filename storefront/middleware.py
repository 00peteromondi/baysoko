# storefront/middleware.py
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import re
from .utils.subscription_utils import enforce_expired_trials_for_user

class SubscriptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # Define premium-only URL patterns
        self.premium_patterns = [
            r'^/dashboard/store/[^/]+/bulk/',
            r'^/dashboard/store/[^/]+/bundles/',
            r'^/dashboard/store/[^/]+/inventory/(?!list|dashboard)',
            r'^/dashboard/analytics/advanced/',
            r'^/dashboard/store/[^/]+/product/create-batch/',
        ]
        
        # Define enterprise-only URL patterns
        self.enterprise_patterns = [
            r'^/dashboard/store/[^/]+/analytics/custom/',
            r'^/api/v1/analytics/',
            r'^/dashboard/store/[^/]+/api/',
        ]
    
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        """Check subscription status before serving premium/enterprise features"""
        
        # Skip for non-authenticated users
        if not request.user.is_authenticated:
            return None
        
        # Skip for staff/admin
        if request.user.is_staff:
            return None

        # Enforce any expired trials immediately for this user (locks stores/listings)
        try:
            enforce_expired_trials_for_user(request.user)
        except Exception:
            # Don't block the request if enforcement fails; log later if needed
            pass
        
        # Get current path
        path = request.path
        
        # Get store slug from URL if available
        store_slug = view_kwargs.get('slug') or view_kwargs.get('store_slug')
        
        # If we're accessing a store-specific page
        if store_slug:
            from .models import Store, Subscription
            
            try:
                store = Store.objects.get(slug=store_slug, owner=request.user)
                
                # Get active subscription
                subscription = Subscription.objects.filter(
                    store=store
                ).order_by('-created_at').first()
                
                # Check if subscription is active (including valid trial)
                has_active_sub = False
                is_trialing = False
                plan = None
                
                if subscription:
                    has_active_sub = subscription.is_active()
                    is_trialing = subscription.status == 'trialing'
                    plan = subscription.plan
                    
                    # Check trial expiration
                    if is_trialing and subscription.trial_ends_at:
                        if timezone.now() > subscription.trial_ends_at:
                            # Trial expired - downgrade to free
                            subscription.status = 'canceled'
                            store.is_premium = False
                            store.is_featured = False
                            subscription.save()
                            store.save()
                            has_active_sub = False
                            is_trialing = False
                
                # Store in request for easy access
                request.store_subscription = {
                    'has_active': has_active_sub,
                    'is_trialing': is_trialing,
                    'plan': plan,
                    'subscription': subscription,
                }
                
                # Check access to premium features
                if any(re.match(pattern, path) for pattern in self.premium_patterns):
                    if not has_active_sub:
                        messages.error(
                            request,
                            "Premium feature requires an active subscription. "
                            "Please upgrade to access this feature."
                        )
                        return redirect('storefront:subscription_plan_select', slug=store_slug)
                    
                    # Basic plan can't access premium features
                    if plan == 'basic':
                        messages.error(
                            request,
                            "This feature requires at least a Premium plan. "
                            "Please upgrade your subscription."
                        )
                        return redirect('storefront:subscription_plan_select', slug=store_slug)
                
                # Check access to enterprise features
                if any(re.match(pattern, path) for pattern in self.enterprise_patterns):
                    if not has_active_sub or plan != 'enterprise':
                        messages.error(
                            request,
                            "This feature requires an Enterprise subscription."
                        )
                        return redirect('storefront:subscription_plan_select', slug=store_slug)
                
            except Store.DoesNotExist:
                pass
        
        return None
    
from django.utils.deprecation import MiddlewareMixin
from .models import Store

class StoreViewMiddleware(MiddlewareMixin):
    """Middleware to track store views"""
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Check if this is a store detail view
        if view_func.__name__ == 'store_detail' and 'slug' in view_kwargs:
            try:
                store = Store.objects.get(slug=view_kwargs['slug'])
                # Use the track_view method if you implement session-based tracking
                store.increment_views()
            except Store.DoesNotExist:
                pass
        return None