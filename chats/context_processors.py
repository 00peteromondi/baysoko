from .models import Message


def messages_context(request):
    """Context processor to add unread messages count to all templates"""
    if request.user.is_authenticated:
        unread_count = Message.objects.filter(
            conversation__participants=request.user
        ).exclude(
            sender=request.user
        ).filter(
            is_read=False
        ).count()
        return {
            'unread_messages_count': unread_count
        }
    return {'unread_messages_count': 0}