from .models import Notification

def notifications_context(request):
    """Context processor to add notification data to all templates"""
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(
            recipient=request.user, 
            is_read=False
        ).count()
        
        recent_notifications = Notification.objects.filter(
            recipient=request.user
        ).select_related('sender')[:5]
        
        return {
            'unread_notifications_count': unread_count,
            'recent_notifications': recent_notifications,
        }
    
    return {
        'unread_notifications_count': 0,
        'recent_notifications': [],
    }