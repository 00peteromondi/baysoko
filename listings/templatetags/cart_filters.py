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
    
