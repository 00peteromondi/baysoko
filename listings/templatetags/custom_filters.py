# listings/templatetags/custom_filters.py
from django import template

register = template.Library()

@register.filter
def get_category_name(categories, category_id):
    try:
        return categories.get(id=category_id).name
    except:
        return "Unknown Category"

@register.filter
def get_location_name(locations, location_value):
    for value, name in locations:
        if value == location_value:
            return name
    return "Unknown Location"


@register.filter
def get_item(value, key):
    """
    Safely get item from dictionary, list, or object
    """
    try:
        if isinstance(value, dict):
            return value.get(key, 0)
        elif hasattr(value, '__getitem__'):
            return value[key]
        elif hasattr(value, str(key)):
            return getattr(value, str(key), 0)
        return 0
    except (KeyError, IndexError, AttributeError, TypeError):
        return 0

@register.filter
def user_is_seller(order_items, user):
    """Check if user is seller of any item in order"""
    return order_items.filter(listing__seller=user).exists()

@register.filter
def mod(value, arg):
    """Returns the modulo of value and arg"""
    return value % arg

@register.filter
def sub(value, arg):
    """Subtract arg from value"""
    return value - arg

@register.filter
def mul(value, arg):
    """Multiply value by arg"""
    return value * arg

@register.filter
def div(value, arg):
    """Divide value by arg"""
    if arg == 0:
        return 0
    return value / arg

@register.filter
def abs_value(value):
    """Return absolute value"""
    return abs(value)