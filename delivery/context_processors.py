from .models import DeliveryNotification


def delivery_user_context(request):
    """Expose seller/delivery flags and unread notification count to templates.

    - `is_seller`: True if user owns at least one Store (set by middleware too)
    - `is_delivery_person`: True if user has a delivery_person relation
    - `unread_notifications_count`: number of unread DeliveryNotification for user
    """
    user = getattr(request, 'user', None)
    is_seller = getattr(request, 'is_seller', False) if user and getattr(user, 'is_authenticated', False) else False
    is_delivery_person = getattr(request, 'is_delivery_person', False) if user and getattr(user, 'is_authenticated', False) else False
    unread_notifications_count = 0
    try:
        if user and getattr(user, 'is_authenticated', False):
            unread_notifications_count = DeliveryNotification.objects.filter(user=user, is_read=False).count()
    except Exception:
        unread_notifications_count = 0

    return {
        'is_seller': is_seller,
        'is_delivery_person': is_delivery_person,
        'unread_notifications_count': unread_notifications_count,
    }
