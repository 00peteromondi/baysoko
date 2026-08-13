from django import template
from listings.models import Cart, CartItem

register = template.Library()

@register.filter
def in_cart(listing, user):
    """
    Check if a listing is in the user's cart.
    Returns the CartItem if found, None otherwise.
    Usage: {% with cart_item=product|in_cart:request.user %}{{ cart_item.quantity }}{% endwith %}
    """
    if not user or not user.is_authenticated:
        return None

    try:
        # Get or create the user's cart
        cart, created = Cart.objects.get_or_create(user=user)
        # Try to get the cart item for this listing
        cart_item = CartItem.objects.filter(cart=cart, listing=listing).first()
        return cart_item
    except Exception:
        # Return None if anything goes wrong
        return None

@register.filter
def isinstance(obj, class_name):
    """
    Check if an object is an instance of a class given its name as a string.
    Usage: {% if some_object|isinstance:"DesiredClassName" %} ... {% endif %}
    """
    return obj.__class__.__name__ == class_name
