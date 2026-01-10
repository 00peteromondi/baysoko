# storefront/context_processors.py
from .models import Store, Subscription

def store_context(request):
    """Add store-related context to all templates"""
    context = {}
    
    if request.user.is_authenticated:
        # Get user's stores
        user_stores = Store.objects.filter(owner=request.user)
        
        # Get active subscriptions
        active_subscriptions = Subscription.objects.filter(
            store__owner=request.user,
            status__in=['active', 'trialing']
        )
        
        # Check if user has premium store
        has_premium_store = user_stores.filter(is_premium=True).exists()
        
        context.update({
            'user_stores': user_stores,
            'active_subscriptions': active_subscriptions,
            'has_premium_store': has_premium_store,
            'total_user_stores': user_stores.count(),
        })
    
    return context