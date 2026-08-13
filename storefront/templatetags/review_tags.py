# Create storefront/templatetags/review_tags.py
from django import template

register = template.Library()

@register.filter
def review_type_badge(review_type):
    """Return badge HTML for review type"""
    if review_type == 'product':
        return '<span class="badge bg-info me-2">Product Review</span>'
    elif review_type == 'store':
        return '<span class="badge bg-primary me-2">Store Review</span>'
    return ''