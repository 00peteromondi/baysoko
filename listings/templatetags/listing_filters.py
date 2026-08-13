from django import template
from django.db.models import Sum

register = template.Library()

@register.filter
def filter_listing_seller(order_items, user):
    """Filter order items by the current user as seller."""
    if not user or not user.is_authenticated:
        return order_items.none()
    return order_items.filter(listing__seller=user)

@register.filter
def sum_total(order_items):
    """Calculate the total price for a list of order items."""
    if not order_items:
        return 0
    return sum(item.get_total_price() for item in order_items)

@register.filter
def filter_shipped(order_items, shipped_status):
    """Filter order items by shipped status."""
    if shipped_status:
        return order_items.filter(shipped=True)
    else:
        return order_items.filter(shipped=False)

@register.filter
def map_attr(items, attr_name):
    """Get a list of attributes from a list of items."""
    if not items:
        return []
    
    attrs = []
    for item in items:
        try:
            obj = item
            for attr in attr_name.split('.'):
                obj = getattr(obj, attr)
            attrs.append(obj)
        except AttributeError:
            continue
    return attrs

@register.filter
def unique(items):
    """Return a list of unique items, preserving order."""
    if not items:
        return []
    
    seen = set()
    unique_items = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique_items.append(item)
    return unique_items