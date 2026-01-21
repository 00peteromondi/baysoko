# cart_filters.py
from django import template

register = template.Library()

@register.filter
def in_cart(listing, user):
    if not user.is_authenticated:
        return None
    try:
        cart = user.cart
        cart_item = cart.items.filter(listing=listing).first()
        return cart_item
    except Exception:
        return None
    

@register.filter(name='get_item')
def get_item(dictionary, key):
    """Get an item from a dictionary using a key."""
    if not dictionary:
        return None
    # Try to convert key to string (since cart_items keys are strings)
    key_str = str(key)
    return dictionary.get(key_str)
    
