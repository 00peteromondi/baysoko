# storefront/templatetags/store_tags.py
from django import template
from storefront.models import Store

register = template.Library()

@register.simple_tag
def get_store_reviews(store, limit=5):
    """Get recent reviews for a store"""
    return store.reviews.all().order_by('-created_at')[:limit]

@register.filter
def rating_stars(rating):
    """Convert rating to star display"""
    stars = []
    for i in range(1, 6):
        if i <= rating:
            stars.append('full')
        else:
            stars.append('empty')
    return stars

@register.simple_tag(takes_context=True)
def user_can_review_store(context, store):
    """Check if user can review a store"""
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return False
    
    # User cannot review their own store
    if store.owner == request.user:
        return False
    
    # Check if user already reviewed
    return not store.reviews.filter(reviewer=request.user).exists()