"""
WebSocket consumers for real-time notifications.

This module provides WebSocket consumers for push-based notification delivery.
Replaces polling with server-sent push for better performance and UX.
"""

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
import json
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for real-time user notifications.
    
    Clients connect to: ws/notifications/
    
    Features:
    - Pushes new notifications as they're created
    - Allows marking notifications as read via WebSocket
    - Supports notification dismissal
    - Maintains group-based broadcast for efficient delivery
    - Graceful fallback to polling if WebSocket disconnects
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        try:
            # Get authenticated user
            user = self.scope.get('user')
            
            if user is None or isinstance(user, AnonymousUser):
                await self.close(code=4001, reason='Unauthorized')
                return
            
            self.user_id = user.id
            self.user = user
            self.group_name = f"notifications_user_{self.user_id}"
            self.is_connected = True
            
            # Add this connection to the user's notification group
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            
            await self.accept()
            
            logger.info(f"Notification WebSocket connected for user {self.user_id}")
            
            # Send initial unread count
            unread_count = await self.get_unread_count()
            await self.send_json({
                'type': 'connection_established',
                'unread_count': unread_count,
                'timestamp': await self.get_current_timestamp()
            })
            
        except Exception as e:
            logger.error(f"Error in notification consumer connect: {str(e)}")
            await self.close(code=4000)
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        try:
            if hasattr(self, 'group_name'):
                await self.channel_layer.group_discard(
                    self.group_name,
                    self.channel_name
                )
            
            self.is_connected = False
            logger.info(f"Notification WebSocket disconnected for user {self.user_id}, code: {close_code}")
            
        except Exception as e:
            logger.error(f"Error in notification consumer disconnect: {str(e)}")
    
    async def receive_json(self, content):
        """
        Handle incoming WebSocket messages.
        
        Supports:
        - mark_read: Mark a notification as read
        - mark_all_read: Mark all notifications as read
        - delete: Delete a notification
        - heartbeat: Keep connection alive (client ping)
        """
        try:
            action = content.get('action')
            
            if action == 'mark_read':
                notification_id = content.get('notification_id')
                result = await self.mark_notification_read(notification_id)
                await self.send_json({
                    'type': 'mark_read_response',
                    'notification_id': notification_id,
                    'success': result,
                    'unread_count': await self.get_unread_count()
                })
            
            elif action == 'mark_all_read':
                await self.mark_all_read()
                await self.send_json({
                    'type': 'mark_all_read_response',
                    'success': True,
                    'unread_count': 0
                })
            
            elif action == 'delete':
                notification_id = content.get('notification_id')
                result = await self.delete_notification(notification_id)
                await self.send_json({
                    'type': 'delete_response',
                    'notification_id': notification_id,
                    'success': result
                })
            
            elif action == 'heartbeat':
                # Keep connection alive
                await self.send_json({
                    'type': 'heartbeat_ack',
                    'timestamp': await self.get_current_timestamp()
                })
            
            else:
                await self.send_json({
                    'type': 'error',
                    'message': f'Unknown action: {action}'
                })
        
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {str(e)}")
            await self.send_json({
                'type': 'error',
                'message': 'Error processing request'
            })
    
    # ==================== Broadcast Handlers ====================
    # These methods are called when group messages are sent to this consumer
    
    async def notification_created(self, event):
        """
        Broadcast handler for new notifications.
        
        Called by channel_layer.group_send() with type='notification.created'
        """
        try:
            notification_data = event.get('notification')
            
            await self.send_json({
                'type': 'notification_created',
                'notification': notification_data,
                'timestamp': await self.get_current_timestamp()
            })
        except Exception as e:
            logger.error(f"Error sending notification_created: {str(e)}")
    
    async def notification_marked_read(self, event):
        """Broadcast handler for notification read status update."""
        try:
            await self.send_json({
                'type': 'notification_marked_read',
                'notification_id': event.get('notification_id'),
                'timestamp': await self.get_current_timestamp()
            })
        except Exception as e:
            logger.error(f"Error sending notification_marked_read: {str(e)}")
    
    async def bulk_marked_read(self, event):
        """Broadcast handler for bulk read status updates."""
        try:
            await self.send_json({
                'type': 'bulk_marked_read',
                'timestamp': await self.get_current_timestamp()
            })
        except Exception as e:
            logger.error(f"Error sending bulk_marked_read: {str(e)}")
    
    async def notification_deleted(self, event):
        """Broadcast handler for notification deletion."""
        try:
            await self.send_json({
                'type': 'notification_deleted',
                'notification_id': event.get('notification_id'),
                'timestamp': await self.get_current_timestamp()
            })
        except Exception as e:
            logger.error(f"Error sending notification_deleted: {str(e)}")

    async def listing_created(self, event):
        """Broadcast handler for new listing events."""
        try:
            listing = event.get('listing')
            await self.send_json({
                'type': 'listing_created',
                'listing': listing,
                'timestamp': await self.get_current_timestamp()
            })
        except Exception as e:
            logger.error(f"Error sending listing_created: {str(e)}")

    async def listing_liked(self, event):
        """Broadcast handler for listing favorite/like updates."""
        try:
            listing = event.get('listing')
            await self.send_json({
                'type': 'listing_liked',
                'listing': listing,
                'timestamp': await self.get_current_timestamp()
            })
        except Exception as e:
            logger.error(f"Error sending listing_liked: {str(e)}")

    async def cart_updated(self, event):
        """Broadcast handler for cart updates for the connected user."""
        try:
            cart = event.get('cart')
            await self.send_json({
                'type': 'cart_updated',
                'cart': cart,
                'timestamp': await self.get_current_timestamp()
            })
        except Exception as e:
            logger.error(f"Error sending cart_updated: {str(e)}")
    
    # ==================== Database Sync Methods ====================
    
    @database_sync_to_async
    def get_unread_count(self):
        """Get count of unread notifications for the user."""
        try:
            from .models import Notification
            return Notification.objects.filter(
                recipient=self.user,
                is_read=False
            ).count()
        except Exception as e:
            logger.error(f"Error getting unread count: {str(e)}")
            return 0
    
    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """Mark a specific notification as read."""
        try:
            from .models import Notification
            notification = Notification.objects.filter(
                id=notification_id,
                recipient=self.user
            ).first()
            
            if notification and not notification.is_read:
                notification.mark_as_read()
                return True
            return False
        except Exception as e:
            logger.error(f"Error marking notification read: {str(e)}")
            return False
    
    @database_sync_to_async
    def mark_all_read(self):
        """Mark all notifications as read."""
        try:
            from .models import Notification
            Notification.objects.filter(
                recipient=self.user,
                is_read=False
            ).update(is_read=True)
            return True
        except Exception as e:
            logger.error(f"Error marking all read: {str(e)}")
            return False
    
    @database_sync_to_async
    def delete_notification(self, notification_id):
        """Delete a specific notification."""
        try:
            from .models import Notification
            notification = Notification.objects.filter(
                id=notification_id,
                recipient=self.user
            ).first()
            
            if notification:
                notification.delete()
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting notification: {str(e)}")
            return False
    
    @staticmethod
    @database_sync_to_async
    def get_current_timestamp():
        """Get current timestamp."""
        from django.utils import timezone
        return timezone.now().isoformat()
