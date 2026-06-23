"""
Signal handlers for notifications app.

These signals handle WebSocket broadcasting whenever notifications are created or modified.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.exceptions import ObjectDoesNotExist
import logging

from .models import Notification

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Notification)
def broadcast_notification_on_create(sender, instance, created, **kwargs):
    """
    Signal handler that broadcasts a notification via WebSocket when it's created.
    
    This enables real-time push notifications to connected WebSocket clients,
    while the notification is still stored in the database for polling fallback.
    """
    if not created:
        # Only broadcast when the notification is first created, not on updates
        return
    
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        
        channel_layer = get_channel_layer()
        group_name = f"notifications_user_{instance.recipient_id}"
        
        # Prepare notification data
        notification_data = {
            'id': instance.id,
            'title': instance.title,
            'message': instance.message,
            'type': instance.notification_type,
            'is_read': instance.is_read,
            'time_since': instance.time_since,
            'action_url': instance.action_url,
            'action_text': instance.action_text,
            'created_at': instance.created_at.isoformat(),
            'sender': instance.sender.username if instance.sender else None,
        }
        
        # Send via WebSocket group
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'notification.created',
                'notification': notification_data
            }
        )
        
        logger.debug(f"Notification {instance.id} broadcasted to {group_name}")
    
    except Exception as e:
        # Log but don't raise - notification is still in DB
        logger.warning(f"Failed to broadcast notification via WebSocket: {str(e)}")


@receiver(post_save, sender=Notification)
def broadcast_notification_read_status(sender, instance, created, update_fields, **kwargs):
    """
    Signal handler that broadcasts when a notification's read status changes.
    """
    if created:
        # Skip on creation - handled by broadcast_notification_on_create
        return
    
    if update_fields and 'is_read' not in update_fields:
        # Only handle updates to is_read field
        return
    
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        
        channel_layer = get_channel_layer()
        group_name = f"notifications_user_{instance.recipient_id}"
        
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'notification.marked_read',
                'notification_id': instance.id
            }
        )
        
        logger.debug(f"Notification read status broadcasted for {instance.id}")
    
    except Exception as e:
        logger.warning(f"Failed to broadcast notification read status: {str(e)}")


@receiver(post_delete, sender=Notification)
def broadcast_notification_deleted(sender, instance, **kwargs):
    """
    Signal handler that broadcasts when a notification is deleted.
    """
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        
        channel_layer = get_channel_layer()
        group_name = f"notifications_user_{instance.recipient_id}"
        
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'notification.deleted',
                'notification_id': instance.id
            }
        )
        
        logger.debug(f"Notification deletion broadcasted for {instance.id}")
    
    except Exception as e:
        logger.warning(f"Failed to broadcast notification deletion: {str(e)}")
