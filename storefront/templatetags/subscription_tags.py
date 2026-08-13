# storefront/templatetags/subscription_tags.py
from django import template
from django.utils import timezone

register = template.Library()

@register.filter
def has_feature(store, feature_name):
    """Check if store has access to specific feature"""
    from ..models import Subscription
    
    if not store or not hasattr(store, 'owner'):
        return False
    
    subscription = Subscription.objects.filter(
        store=store
    ).order_by('-created_at').first()
    
    if not subscription:
        return False
    
    # Check if subscription is active
    if not subscription.is_active():
        return False
    
    # Check trial expiration
    if subscription.status == 'trialing' and subscription.trial_ends_at:
        if timezone.now() > subscription.trial_ends_at:
            return False
    
    # Feature mapping by plan
    features = {
        'basic': {
            'multiple_stores': False,
            'advanced_analytics': False,
            'bulk_operations': False,
            'inventory_management': False,
            'product_bundles': False,
            'featured_placement': True,
            'unlimited_listings': False,
            'custom_domain': False,
            'api_access': False,
        },
        'premium': {
            'multiple_stores': True,
            'advanced_analytics': True,
            'bulk_operations': True,
            'inventory_management': True,
            'product_bundles': True,
            'featured_placement': True,
            'unlimited_listings': True,
            'custom_domain': False,
            'api_access': False,
        },
        'enterprise': {
            'multiple_stores': True,
            'advanced_analytics': True,
            'bulk_operations': True,
            'inventory_management': True,
            'product_bundles': True,
            'featured_placement': True,
            'unlimited_listings': True,
            'custom_domain': True,
            'api_access': True,
        }
    }
    
    plan_features = features.get(subscription.plan, {})
    return plan_features.get(feature_name, False)

@register.simple_tag
def get_subscription_status(store):
    """Get subscription status for a store"""
    from ..models import Subscription
    
    subscription = Subscription.objects.filter(
        store=store
    ).order_by('-created_at').first()
    
    if not subscription:
        return 'no_subscription'
    
    if subscription.status == 'trialing':
        if subscription.trial_ends_at and timezone.now() > subscription.trial_ends_at:
            return 'trial_expired'
        return 'trialing'
    
    return subscription.status

@register.filter
def can_create_store(user):
    """Check if user can create additional stores"""
    from ..models import Store, Subscription
    
    stores = Store.objects.filter(owner=user)
    
    # First store is free
    if not stores.exists():
        return True
    
    # Check if any store has active subscription
    for store in stores:
        subscription = Subscription.objects.filter(
            store=store
        ).order_by('-created_at').first()
        
        if subscription and subscription.is_active():
            # Check trial expiration
            if subscription.status == 'trialing' and subscription.trial_ends_at:
                if timezone.now() > subscription.trial_ends_at:
                    continue
            return True
    
    return False

@register.filter
def get_plan_display_name(plan):
    """Get display name for plan"""
    plan_names = {
        'basic': 'Basic',
        'premium': 'Premium',
        'enterprise': 'Enterprise',
    }
    return plan_names.get(plan, 'Free')

@register.filter
def can_access_feature(subscription, feature_name):
    """Check if subscription can access specific feature"""
    if not subscription or not subscription.is_active():
        return False
    
    # Feature matrix by plan
    features = {
        'basic': [
            'featured_placement',
            'basic_analytics',
            'store_customization',
            'up_to_5_stores',
            'up_to_50_products',
        ],
        'premium': [
            'featured_placement',
            'advanced_analytics',
            'bulk_operations',
            'inventory_management',
            'product_bundles',
            'multiple_stores',
            'up_to_200_products',
        ],
        'enterprise': [
            'featured_placement',
            'advanced_analytics',
            'bulk_operations',
            'inventory_management',
            'product_bundles',
            'multiple_stores',
            'unlimited_products',
            'api_access',
            'custom_domain',
            'priority_support',
        ]
    }
    
    plan_features = features.get(subscription.plan, [])
    return feature_name in plan_features


@register.filter
def split(value, delimiter):
    """Split a string by delimiter"""
    if not value:
        return []
    return value.split(delimiter)

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary"""
    if not dictionary:
        return None
    return dictionary.get(key)