# Create a new file: notifications/middleware.py
from django.utils.deprecation import MiddlewareMixin
from .models import Notification

class NotificationsMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.user.is_authenticated:
            try:
                unread_count = Notification.objects.filter(
                    recipient=request.user, 
                    is_read=False
                ).count()
                request.unread_notifications_count = unread_count
            except:
                request.unread_notifications_count = 0
        else:
            request.unread_notifications_count = 0
        return None
    
    def process_template_response(self, request, response):
        if hasattr(response, 'context_data'):
            if response.context_data is None:
                response.context_data = {}
            response.context_data['unread_notifications_count'] = getattr(
                request, 'unread_notifications_count', 0
            )
        return response