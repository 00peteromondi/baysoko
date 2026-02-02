# storefront/utils/subscription_utils.py
from django.conf import settings
from listings.models import Listing
from django.utils import timezone
from django.db import transaction



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


def enforce_expired_trials_for_user(user):
    """Cancel expired trials without payment and lock stores/listings except the first.

    This function is safe to call at request-time for authenticated users; it
    performs a quick query for subscriptions that have expired and processes
    them. It's idempotent.
    """
    from storefront.models import Subscription, Store, MpesaPayment
    from django.utils import timezone
    from listings.models import Listing

    now = timezone.now()
    expired_trials = Subscription.objects.filter(
        store__owner=user,
        status='trialing',
        trial_ends_at__lte=now
    )

    if not expired_trials.exists():
        return 0

    processed = 0
    for subscription in expired_trials.select_related('store'):
        # If a completed payment exists, convert to active
        has_payment = MpesaPayment.objects.filter(
            subscription=subscription,
            status='completed'
        ).exists()

        if has_payment:
            subscription.status = 'active'
            subscription.next_billing_date = now + timezone.timedelta(days=30)
            subscription.save()
            processed += 1
            continue

        # No payment: cancel and lock stores except the first
        with transaction.atomic():
            subscription.status = 'cancelled'
            subscription.save()

            owner = subscription.store.owner
            owner_stores = Store.objects.filter(owner=owner).order_by('created_at')
            first = owner_stores.first()

            for s in owner_stores:
                if first and s.id == first.id:
                    s.is_premium = False
                    s.is_active = True
                    s.save()
                    continue
                s.is_premium = False
                s.is_active = False
                s.save()
                Listing.objects.filter(store=s).update(is_active=False)

        processed += 1

    return processed