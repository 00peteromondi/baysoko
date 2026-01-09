from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

User = get_user_model()

class DeliveryConsumer(AsyncJsonWebsocketConsumer):
    """WebSocket consumer for order-level delivery updates.

    Clients subscribe to `ws/orders/<tracking_or_orderid>/`.
    We add them to a group named `order_<identifier>`.
    """
    async def connect(self):
        self.order_id = self.scope['url_route']['kwargs'].get('order_id')
        self.group_name = f"order_{self.order_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        try:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        except Exception:
            pass

    async def order_status_update(self, event):
        # event should contain 'status' and optional 'payload'
        await self.send_json({
            'type': 'order.status',
            'status': event.get('status'),
            'payload': event.get('payload', {})
        })


class UserDeliveryConsumer(AsyncJsonWebsocketConsumer):
    """WebSocket consumer for user-scoped delivery updates.

    Clients subscribe to `ws/users/<user_id>/` to receive delivery updates
    related to any of their orders.
    """
    async def connect(self):
        self.user_id = self.scope['url_route']['kwargs'].get('user_id')
        self.group_name = f"user_{self.user_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        try:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        except Exception:
            pass

    async def order_status_update(self, event):
        await self.send_json({
            'type': 'user.order.status',
            'status': event.get('status'),
            'payload': event.get('payload', {})
        })
