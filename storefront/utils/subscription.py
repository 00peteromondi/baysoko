# storefront/utils/subscription.py
from datetime import datetime
from django.utils import timezone
from django.core.cache import cache
from storefront.models import Subscription


def get_store_subscription(store):
    """Get active subscription for store with caching"""
    cache_key = f"store_subscription_{store.id}"
    subscription = cache.get(cache_key)
    
    if not subscription:
        subscription = Subscription.get_store_subscription(store)
        cache.set(cache_key, subscription, 300)  # Cache for 5 minutes
    
    return subscription

def can_access_feature(store, feature_name):
    """Check if store can access a specific feature"""
    subscription = get_store_subscription(store)
    
    if not subscription:
        return False
    
    return subscription.can_access_feature(feature_name)

def enforce_subscription_limits(store, action):
    """Enforce subscription limits for specific actions"""
    subscription = get_store_subscription(store)
    
    if not subscription or not subscription.is_active():
        return False, "Active subscription required"
    
    # Plan-based limits
    limits = {
        'basic': {
            'max_products': 50,
            'max_stores': 1,
            'max_employees': 1,
        },
        'premium': {
            'max_products': 200,
            'max_stores': 3,
            'max_employees': 3,
        },
        'enterprise': {
            'max_products': float('inf'),
            'max_stores': float('inf'),
            'max_employees': float('inf'),
        }
    }
    
    plan_limits = limits.get(subscription.plan, {})
    
    # Check specific action limits
    if action == 'create_product':
        current_count = store.listings.count()
        if current_count >= plan_limits.get('max_products', 5):
            return False, f"Product limit reached for {subscription.plan} plan"
    
    elif action == 'create_store':
        current_count = store.owner.stores.count()
        if current_count >= plan_limits.get('max_stores', 1):
            return False, f"Store limit reached for {subscription.plan} plan"
    
    return True, "Allowed"