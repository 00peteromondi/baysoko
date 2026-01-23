# chats/middleware.py
from django.utils import timezone
from .models import UserOnlineStatus

class OnlineStatusMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Update online status for authenticated users
        if request.user.is_authenticated:
            try:
                status, created = UserOnlineStatus.objects.get_or_create(user=request.user)
                status.last_active = timezone.now()
                
                # User is considered online if active in last 3 minutes
                if (timezone.now() - status.last_active).seconds < 180:
                    status.is_online = True
                    status.last_seen = timezone.now()
                
                status.save(update_fields=['is_online', 'last_active', 'last_seen'])
            except Exception as e:
                pass
        
        return response