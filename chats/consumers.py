import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import Conversation, Message

User = get_user_model()
logger = logging.getLogger(__name__)

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            await self.close()
            return

        # Group for this specific user
        self.user_group_name = f"user_{self.user.id}"
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)
        await self.accept()
        logger.info(f"WebSocket connected for user {self.user.id}")

    async def disconnect(self, close_code):
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(self.user_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            event_type = data.get('type')
            if event_type == 'typing.start':
                await self.handle_typing_start(data)
            elif event_type == 'typing.stop':
                await self.handle_typing_stop(data)
            elif event_type == 'mark_read':
                await self.handle_mark_read(data)
            # Optionally handle sending messages via WebSocket
            # elif event_type == 'send_message':
            #     await self.handle_send_message(data)
        except Exception as e:
            logger.error(f"Error in WebSocket receive: {e}")

    async def handle_typing_start(self, data):
        conversation_id = data.get('conversation_id')
        if not conversation_id:
            return
        # Verify user is participant
        participant_ids = await self.get_conversation_participants(conversation_id)
        if self.user.id not in participant_ids:
            return
        # Send to other participants only
        for pid in participant_ids:
            if pid != self.user.id:
                await self.channel_layer.group_send(
                    f"user_{pid}",
                    {
                        'type': 'typing_notification',
                        'conversation_id': conversation_id,
                        'user_id': self.user.id,
                        'user_name': self.user.get_full_name() or self.user.username,
                        'typing': True,
                    }
                )

    async def handle_typing_stop(self, data):
        conversation_id = data.get('conversation_id')
        if not conversation_id:
            return
        participant_ids = await self.get_conversation_participants(conversation_id)
        if self.user.id not in participant_ids:
            return
        for pid in participant_ids:
            if pid != self.user.id:
                await self.channel_layer.group_send(
                    f"user_{pid}",
                    {
                        'type': 'typing_notification',
                        'conversation_id': conversation_id,
                        'user_id': self.user.id,
                        'typing': False,
                    }
                )

    async def handle_mark_read(self, data):
        conversation_id = data.get('conversation_id')
        message_ids = data.get('message_ids', [])
        if not conversation_id or not message_ids:
            return
        # Mark messages as read (update DB)
        await self.mark_messages_read(conversation_id, message_ids)
        # Notify sender(s) that messages have been read
        # For simplicity, we'll broadcast to other participants that specific messages were read
        participant_ids = await self.get_conversation_participants(conversation_id)
        for pid in participant_ids:
            if pid != self.user.id:
                await self.channel_layer.group_send(
                    f"user_{pid}",
                    {
                        'type': 'read_receipt',
                        'conversation_id': conversation_id,
                        'message_ids': message_ids,
                        'read_by': self.user.id,
                    }
                )
        # After marking read, update unread counts for all participants
        try:
            from .utils import broadcast_unread_async
            for pid in participant_ids:
                await broadcast_unread_async(pid)
        except Exception:
            logger.exception('Failed to broadcast unread counts after mark_read')

    # Handler for messages sent from server to client
    async def chat_message(self, event):
        """Send a new message to the WebSocket client."""
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'message': event['message']
        }))

    async def typing_notification(self, event):
        """Send typing indicator update."""
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'conversation_id': event['conversation_id'],
            'user_id': event['user_id'],
            'user_name': event.get('user_name'),
            'typing': event['typing']
        }))

    async def read_receipt(self, event):
        """Notify that messages have been read."""
        await self.send(text_data=json.dumps({
            'type': 'messages_read',
            'conversation_id': event['conversation_id'],
            'message_ids': event['message_ids'],
            'read_by': event['read_by']
        }))

    async def message_updated(self, event):
        """Notify that a message was edited or deleted."""
        await self.send(text_data=json.dumps({
            'type': 'message_update',
            'conversation_id': event['conversation_id'],
            'message_id': event['message_id'],
            'action': event['action'],      # 'edit', 'delete', 'pin'
            'data': event.get('data', {})
        }))

    # Database helpers
    @database_sync_to_async
    def get_conversation_participants(self, conversation_id):
        try:
            conv = Conversation.objects.get(id=conversation_id)
            return list(conv.participants.values_list('id', flat=True))
        except Conversation.DoesNotExist:
            return []

    @database_sync_to_async
    def mark_messages_read(self, conversation_id, message_ids):
        # Only mark messages not sent by current user
        Message.objects.filter(
            id__in=message_ids,
            conversation_id=conversation_id
        ).exclude(
            sender=self.user
        ).update(is_read=True, read_at=timezone.now())