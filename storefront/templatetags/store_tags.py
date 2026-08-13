# storefront/templatetags/store_tags.py
from django import template
from storefront.models import Store

register = template.Library()

@register.simple_tag
def get_store_reviews(store, limit=5):
    """Get recent reviews for a store"""
    return store.reviews.all().order_by('-created_at')[:limit]


@register.simple_tag
def get_listing_reviews(listing, limit=5):
    """Get recent reviews for a listing (product)"""
    try:
        from listings.models import Review
        return Review.objects.filter(review_type='listing', listing=listing).order_by('-created_at')[:limit]
    except Exception:
        return []

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


@register.simple_tag(takes_context=True)
def user_can_review_listing(context, listing):
    """Check if the current user can review a listing/product."""
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return False

    # User cannot review their own listing
    if listing.seller == request.user:
        return False

    # Check if user already reviewed this listing
    try:
        return not listing.reviews.filter(user=request.user).exists()
    except Exception:
        return False