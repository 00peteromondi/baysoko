# storefront/middleware/trial_limit.py
from django.utils.deprecation import MiddlewareMixin
from storefront.subscription_service import SubscriptionService

class TrialLimitMiddleware(MiddlewareMixin):
    """Middleware to enforce trial limits"""
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Only check authenticated users
        if not request.user.is_authenticated:
            return None
        
        # Only check subscription-related views
        view_name = view_func.__name__
        subscription_views = [
            'subscription_plan_select',
            'start_trial',
            'subscription_payment_options',
        ]
        
        if view_name in subscription_views:
            # Check trial limit
            trial_status = SubscriptionService.get_user_trial_status(request.user)
            
            if trial_status['summary']['has_exceeded_limit']:
                from django.contrib import messages
                from django.shortcuts import redirect
                
                messages.error(
                    request,
                    f"❌ Trial Limit Exceeded: You have already used {trial_status['trial_count']} "
                    f"out of {trial_status['trial_limit']} allowed trials."
                )
                
                # Redirect to appropriate page
                if 'slug' in view_kwargs:
                    return redirect('storefront:subscription_manage', slug=view_kwargs['slug'])
                else:
                    return redirect('storefront:seller_dashboard')
        
        return None