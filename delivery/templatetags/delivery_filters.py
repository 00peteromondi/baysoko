"""
Custom template filters for delivery app
"""
from django import template
from django.template.defaultfilters import floatformat

register = template.Library()


@register.filter
def multiply(value, arg):
    """Multiply the value by the argument"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def divide(value, arg):
    """Divide the value by the argument"""
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0


@register.filter
def subtract(value, arg):
    """Subtract the argument from the value"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return value


@register.filter
def add(value, arg):
    """Add the argument to the value"""
    try:
        return float(value) + float(arg)
    except (ValueError, TypeError):
        return value


@register.filter
def percentage(value, total):
    """Calculate percentage"""
    try:
        if total == 0:
            return 0
        return (float(value) / float(total)) * 100
    except (ValueError, TypeError, ZeroDivisionError):
        return 0


@register.filter
def to_currency(value):
    """Format value as currency"""
    try:
        return f"KES {float(value):,.2f}"
    except (ValueError, TypeError):
        return f"KES 0.00"


@register.filter
def format_duration(value):
    """Format duration in seconds to hours/minutes"""
    try:
        total_seconds = float(value)
        if total_seconds < 60:
            return f"{total_seconds:.0f}s"
        elif total_seconds < 3600:
            minutes = total_seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = total_seconds / 3600
            return f"{hours:.1f}h"
    except (ValueError, TypeError):
        return "0s"


@register.filter
def get_item(dictionary, key):
    """Get item from dictionary"""
    try:
        return dictionary.get(key)
    except (AttributeError, KeyError):
        return None


@register.filter
def status_class(status):
    """Get CSS class for status"""
    status_classes = {
        'pending': 'status-pending',
        'accepted': 'status-accepted',
        'assigned': 'status-assigned',
        'picked_up': 'status-picked_up',
        'in_transit': 'status-in_transit',
        'out_for_delivery': 'status-out_for_delivery',
        'delivered': 'status-delivered',
        'failed': 'status-failed',
        'cancelled': 'status-cancelled',
        'returned': 'status-returned',
    }
    return status_classes.get(status, 'status-pending')


@register.filter
def driver_status_class(status):
    """Get CSS class for driver status"""
    status_classes = {
        'available': 'status-available',
        'busy': 'status-busy',
        'offline': 'status-offline',
        'on_break': 'status-on_break',
    }
    return status_classes.get(status, 'status-offline')

@register.filter
def user_display(user):
    """Safely get user display name"""
    if user and hasattr(user, 'get_full_name'):
        full_name = user.get_full_name()
        if full_name:
            return full_name
        return user.username if hasattr(user, 'username') else str(user)
    return "System"