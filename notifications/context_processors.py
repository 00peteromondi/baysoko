from django.contrib.auth.models import AnonymousUser
from .models import Notification

def notifications_context(request):
    """Context processor to add unread notification count to all templates"""
    try:
        if request.user.is_authenticated and hasattr(request.user, 'id'):
            unread_count = Notification.objects.filter(
                recipient=request.user, 
                is_read=False
            ).count()
            return {'unread_notifications_count': unread_count}
    except Exception as e:
        # If Notification model doesn't exist yet (during migrations)
        print(f"Error in notifications context processor: {e}")
        return {'unread_notifications_count': 0}
    
    return {'unread_notifications_count': 0}