# listings/templatetags/custom_filters.py
from django import template
import json

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

@register.filter(name='get_item')
def get_item(dictionary, key):
    """Get an item from a dictionary using a key."""
    if not dictionary:
        return None
    # Try to convert key to string (since cart_items keys are strings)
    key_str = str(key)
    return dictionary.get(key_str)

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

@register.filter
def prettify_json(value):
    """Pretty-print JSON data for display"""
    if not value:
        return ""
    
    try:
        # If it's already a dict/list, convert to JSON string
        if isinstance(value, (dict, list)):
            json_str = json.dumps(value, indent=2, default=str)
        else:
            # If it's a string, try to parse and re-format
            json_str = json.dumps(json.loads(str(value)), indent=2, default=str)
        return json_str
    except (json.JSONDecodeError, TypeError, ValueError):
        # If it's not valid JSON, just return as-is
        return str(value)