import logging
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import Count
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import Message
from django.db import connection

logger = logging.getLogger(__name__)
User = get_user_model()


def get_unread_count_for_user(user_id):
    try:
        return Message.objects.filter(
            conversation__participants__id=user_id
        ).exclude(sender_id=user_id).filter(is_read=False).count()
    except Exception as e:
        logger.exception(f"Error computing unread count for {user_id}: {e}")
        return 0


def broadcast_unread_sync(user_id):
    """Sync helper: compute unread count and broadcast to user's group."""
    try:
        count = get_unread_count_for_user(user_id)
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'user_{user_id}',
            {
                'type': 'chat_unread',
                'unread_count': count,
            }
        )
    except Exception as e:
        logger.exception(f"Failed to broadcast unread count for {user_id}: {e}")


async def broadcast_unread_async(user_id):
    """Async helper for use from consumers: compute unread count and send group message."""
    try:
        # compute count using ORM in async-safe way
        from django.db import close_old_connections
        close_old_connections()
        count = await __aget_unread_count(user_id)
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f'user_{user_id}',
            {
                'type': 'chat_unread',
                'unread_count': count,
            }
        )
    except Exception:
        logger.exception(f"Failed to broadcast unread count async for {user_id}")


async def __aget_unread_count(user_id):
    # perform the queryset in thread pool
    from asgiref.sync import sync_to_async
    return await sync_to_async(get_unread_count_for_user)(user_id)
