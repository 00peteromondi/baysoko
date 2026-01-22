# storefront/utils/subscription_utils.py
from django.conf import settings
from listings.models import Listing
from django.utils import timezone

def get_user_listing_limits(user, store=None):
    """
    Get user's listing limits and usage
    Returns: dict with limit info
    """
    FREE_LISTING_LIMIT = getattr(settings, 'STORE_FREE_LISTING_LIMIT', 5)
    
    # Count user's active listings (across all stores)
    if store:
        # For specific store
        user_listing_count = Listing.objects.filter(
            seller=user,
            store=store,
            is_active=True
        ).count()
    else:
        # Across all stores
        user_listing_count = Listing.objects.filter(
            seller=user,
            is_active=True
        ).count()
    
    # Check if user has premium access
    has_premium = False
    if store:
        has_premium = store.is_premium
    else:
        # Check if user has any premium store
        from storefront.models import Store
        has_premium = Store.objects.filter(
            owner=user,
            is_premium=True
        ).exists()
    
    limit_reached = user_listing_count >= FREE_LISTING_LIMIT and not has_premium
    remaining = max(FREE_LISTING_LIMIT - user_listing_count, 0)
    
    return {
        'current_count': user_listing_count,
        'free_limit': FREE_LISTING_LIMIT,
        'remaining_slots': remaining,
        'limit_reached': limit_reached,
        'has_premium': has_premium,
        'percentage_used': (user_listing_count / FREE_LISTING_LIMIT * 100) if FREE_LISTING_LIMIT > 0 else 0
    }

def check_listing_requires_upgrade(user, store=None):
    """
    Check if user needs to upgrade to create more listings
    Returns: tuple (requires_upgrade, limit_info)
    """
    limit_info = get_user_listing_limits(user, store)
    requires_upgrade = limit_info['limit_reached'] and not limit_info['has_premium']
    
    return requires_upgrade, limit_info