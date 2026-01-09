"""
Signals for delivery automation
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import DeliveryRequest, DeliveryStatusHistory, DeliveryNotification
from .utils import send_delivery_notification


@receiver(post_save, sender=DeliveryRequest)
def create_initial_status_history(sender, instance, created, **kwargs):
    """Create initial status history when delivery is created"""
    if created:
        DeliveryStatusHistory.objects.create(
            delivery_request=instance,
            old_status='created',
            new_status=instance.status,
            notes='Delivery created'
        )


@receiver(pre_save, sender=DeliveryRequest)
def check_status_change(sender, instance, **kwargs):
    """Check if status has changed and trigger notifications"""
    if instance.pk:
        try:
            old_instance = DeliveryRequest.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                # Status has changed - notification will be sent via update_status method
                pass
        except DeliveryRequest.DoesNotExist:
            pass


@receiver(post_save, sender=DeliveryStatusHistory)
def notify_status_change(sender, instance, created, **kwargs):
    """Send notification when status changes"""
    if created:
        delivery = instance.delivery_request
        
        # Determine recipient
        recipient = None
        if isinstance(delivery.metadata, dict):
            user_id = delivery.metadata.get('user_id')
            if user_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                recipient = User.objects.filter(id=user_id).first()
        
        # Send notification
        if recipient:
            try:
                send_delivery_notification(
                    delivery=delivery,
                    notification_type='status_update',
                    recipient=recipient,
                    context={
                        'old_status': instance.old_status,
                        'new_status': instance.new_status,
                        'notes': instance.notes,
                    }
                )
            except Exception:
                pass

        # First, attempt to reflect this change back to the e-commerce Order model
        order = None
        user_id = None
        try:
            from listings.models import Order

            # Try using delivery.order_id if it maps to our Order id
            if getattr(delivery, 'order_id', None):
                oid = None
                try:
                    if isinstance(delivery.order_id, str) and delivery.order_id.startswith('ECOMM_'):
                        oid = int(delivery.order_id.split('_')[-1])
                    else:
                        oid = int(str(delivery.order_id))
                except Exception:
                    oid = None

                if oid:
                    order = Order.objects.filter(id=oid).first()

            # Fallback: try matching tracking number
            if not order and getattr(delivery, 'tracking_number', None):
                order = Order.objects.filter(tracking_number=delivery.tracking_number).first()

            # Another fallback: try matching delivery_request id stored on Order
            if not order:
                order = Order.objects.filter(delivery_request_id=getattr(delivery, 'id', None)).first()

            if order:
                # Update the order.delivery_status field so buyer views reflect change
                order.delivery_status = instance.new_status
                # Update delivered_at timestamp when delivered
                if instance.new_status == 'delivered':
                    from django.utils import timezone
                    order.delivered_at = getattr(order, 'delivered_at', None) or timezone.now()
                order.save(update_fields=['delivery_status', 'delivered_at'] if instance.new_status == 'delivered' else ['delivery_status'])
                if getattr(order, 'user', None):
                    user_id = order.user.id
        except Exception:
            # best-effort; don't fail status updates if order reflection isn't possible
            order = None
            user_id = None

        # Publish update to WebSocket groups so buyers see real-time updates (after DB updated)
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer

            channel_layer = get_channel_layer()

            payload = {
                'tracking_number': getattr(delivery, 'tracking_number', None),
                'old_status': instance.old_status,
                'new_status': instance.new_status,
                'notes': instance.notes,
                'timestamp': instance.created_at.isoformat()
            }

            # Send to order group (use tracking number or order id)
            if getattr(delivery, 'tracking_number', None):
                group = f"order_{delivery.tracking_number}"
                async_to_sync(channel_layer.group_send)(group, {
                    'type': 'order_status_update',
                    'status': instance.new_status,
                    'payload': payload,
                })

            # Also send to user group if available
            if user_id:
                async_to_sync(channel_layer.group_send)(f'user_{user_id}', {
                    'type': 'order_status_update',
                    'status': instance.new_status,
                    'payload': payload,
                })
        except Exception:
            # best effort; don't break status creation if websocket layer unavailable
            pass
        # (order reflection handled above)