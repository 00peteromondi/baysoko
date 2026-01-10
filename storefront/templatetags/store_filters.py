# storefront/templatetags/store_filters.py
from django import template
from storefront.models import StoreReview
from listings.models import Review


register = template.Library()

@register.filter
def mul(value, arg):
    """Multiply the value by the argument"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        try:
            return value * arg
        except Exception:
            return 0

@register.filter
def div(value, arg):
    """Divide the value by the argument"""
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter
def multiply_percentage(value, arg):
    """Multiply value by arg and format as percentage"""
    try:
        result = float(value) * float(arg)
        return f"{result:.1f}"
    except (ValueError, TypeError):
        return "0"
    

@register.filter
def user_can_review_store(store, user):
    """Check if user can review a store"""
    if not user.is_authenticated:
        return False
    
    # Check if user owns the store
    if store.owner == user:
        return False
    
    # Check if user already reviewed the store directly
    if StoreReview.objects.filter(store=store, reviewer=user).exists():
        return False
    
    # Check if user has reviewed any product in this store
    if Review.objects.filter(listing__store=store, user=user).exists():
        # User has reviewed a product, so they've already reviewed the store indirectly
        return False
    
    return True