# In your context_processors.py
from .models import Cart
from chats.models import Message

def cart_item_count(request):
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
        return {'cart_item_count': cart.items.count()}
    return {'cart_item_count': 0}


# Add this context processor to get cart counts globally
def cart_context(request):
    """Context processor to add cart item count to all templates"""
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
        return {
            'cart_item_count': cart.items.count()
        }
    return {'cart_item_count': 0}

