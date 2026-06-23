"""
Webhook signals for order events in Baysoko
"""
import json
import hashlib
import hmac
import requests
import logging
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


def send_order_webhook(order, event_type):
    """Send webhook notification to delivery system about order event"""
    if not settings.DELIVERY_SYSTEM_ENABLED:
        return None

    # When running the Django test runner, avoid making external HTTP calls.
    # Create a lightweight WebhookLog entry and return success so tests are
    # deterministic and quiet.
    if getattr(settings, 'RUNNING_TESTS', False):
        try:
            from .models import WebhookLog
            WebhookLog.objects.create(
                order=order,
                event_type=event_type,
                payload={
                    'test_stub': True,
                    'order_id': order.id,
                },
                response_status=200,
                response_body='[test stubbed]',
                success=True
            )
        except Exception:
            pass
        return True
    
    try:
        # Prepare webhook payload
        payload = {
            'event': event_type,
            'timestamp': timezone.now().isoformat(),
            'data': _prepare_order_data(order)
        }
        
        # Create signature over deterministic JSON bytes
        payload_str = json.dumps(payload, separators=(',', ':'), ensure_ascii=False, sort_keys=True)
        signature = hmac.new(
            getattr(settings, 'DELIVERY_WEBHOOK_KEY', '').encode('utf-8'),
            payload_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # Headers (include Authorization if delivery system expects API key)
        headers = {
            'Content-Type': 'application/json',
            'X-Webhook-Signature': signature,
            'X-Event-Type': event_type,
            'X-Platform-Name': settings.ECOMMERCE_PLATFORM_NAME,
            'X-Webhook-Secret': getattr(settings, 'DELIVERY_WEBHOOK_KEY', ''),
        }
        if getattr(settings, 'DELIVERY_SYSTEM_API_KEY', ''):
            headers['Authorization'] = f"Bearer {settings.DELIVERY_SYSTEM_API_KEY}"
        
        # Create webhook log
        from .models import WebhookLog
        webhook_log = WebhookLog.objects.create(
            order=order,
            event_type=event_type,
            payload=payload,
            success=False
        )
        
        # Send webhook
        # Send deterministic payload bytes so signature matches exactly
        response = requests.post(
            settings.ECOMMERCE_WEBHOOK_URL,
            data=payload_str.encode('utf-8'),
            headers=headers,
            timeout=5
        )
        
        # Update webhook log
        webhook_log.response_status = response.status_code
        webhook_log.response_body = response.text[:1000]  # Limit response size
        webhook_log.success = response.status_code == 200
        
        if response.status_code == 200:
            logger.info(f"Webhook sent for order {order.id} - {event_type}")
            webhook_log.save()
            return True
        else:
            logger.error(f"Webhook failed for order {order.id}: {response.status_code} - {response.text}")
            webhook_log.error_message = f"HTTP {response.status_code}: {response.text}"
            webhook_log.save()
            return False
    
    except Exception as e:
        logger.error(f"Failed to send webhook for order {order.id}: {str(e)}")
        
        # Log error
        if 'webhook_log' in locals():
            webhook_log.error_message = str(e)
            webhook_log.save()
        
        return False

def _prepare_order_data(order):
    """Prepare order data for webhook"""
    # Convert order to dictionary
    order_data = {
        'id': order.id,
        'order_number': str(order.id),
        'status': order.status,
        'payment_status': (order.payment.status if hasattr(order, 'payment') and order.payment else ('completed' if order.status == 'paid' else 'pending')),
        'total_amount': str(order.total_price),
        'shipping_cost': '0',
        'currency': 'KES',
        'created_at': order.created_at.isoformat() if order.created_at else None,
        'updated_at': order.updated_at.isoformat() if order.updated_at else None,
        'metadata': {},
    }
    
    # Add user/customer info
    if order.user:
        order_data['customer'] = {
            'id': order.user.id,
            'name': order.user.get_full_name(),
            'email': order.user.email,
            'phone': getattr(order.user, 'phone', ''),
        }
    
    # Add shipping address (Order stores shipping address as text fields)
    order_data['shipping_address'] = {
        'address_text': order.shipping_address or '',
        'city': order.city or '',
        'postal_code': order.postal_code or '',
        'phone': order.phone_number or '',
    }
    
    # Add store/seller info if available on order
    if hasattr(order, 'store') and order.store:
        store = order.store
        order_data['store'] = {
            'id': store.id,
            'name': store.name,
            'address': getattr(store, 'address', '') or '',
            'phone': getattr(store, 'phone', '') or '',
            'email': getattr(store, 'email', '') or '',
        }
    
    # Add order items from OrderItem relation
    items = []
    for item in getattr(order, 'order_items', order.items).all():
        try:
            name = item.listing.title
        except Exception:
            name = getattr(item, 'product', None) and getattr(item.product, 'name', 'Unknown Product') or 'Unknown Product'

        item_data = {
            'name': name,
            'quantity': item.quantity,
            'price': str(item.price),
            'total': str(item.price * item.quantity),
        }

        # Add listing/product details if available
        if hasattr(item, 'listing') and item.listing:
            item_data['product'] = {
                'id': item.listing.id,
                'weight': str(getattr(item.listing, 'weight', 0.5)),
                'is_fragile': getattr(item.listing, 'is_fragile', False) if hasattr(item.listing, 'is_fragile') else False,
                'dimensions': getattr(item.listing, 'dimensions', {}),
            }

        items.append(item_data)

    order_data['items'] = items
    
    return order_data


def _create_webhook_signature(payload):
    """Create HMAC signature for webhook security"""
    payload_str = json.dumps(payload, sort_keys=True)
    secret = getattr(settings, 'DELIVERY_WEBHOOK_KEY', '').encode('utf-8')
    
    signature = hmac.new(
        secret,
        payload_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature


# Signal handlers for Order model
@receiver(post_save, sender='listings.Order')
def handle_order_created(sender, instance, created, **kwargs):
    """Handle order creation"""
    if created:
        send_order_webhook(instance, 'order_created')
        # Also create a DeliveryRequest internally so delivery app can manage shipment
        # During tests, skip creating DeliveryRequests to avoid external dependencies
        from django.conf import settings as _settings
        if not getattr(_settings, 'RUNNING_TESTS', False):
            try:
                try:
                    from delivery.integration import create_delivery_from_order
                except Exception:
                    create_delivery_from_order = None

                if not create_delivery_from_order:
                    # Fallback: load delivery/integration.py directly from project root
                    try:
                        import os
                        from importlib.machinery import SourceFileLoader
                        project_root = os.path.dirname(os.path.dirname(__file__))
                        integration_path = os.path.join(project_root, 'delivery', 'integration.py')
                        if os.path.exists(integration_path):
                            mod = SourceFileLoader('delivery_integration_fallback', integration_path).load_module()
                            create_delivery_from_order = getattr(mod, 'create_delivery_from_order', None)
                    except Exception:
                        create_delivery_from_order = None

                if create_delivery_from_order:
                    dr = create_delivery_from_order(instance)
                    if dr:
                        try:
                            instance.delivery_request_id = str(dr.id)
                            if dr.tracking_number:
                                instance.delivery_tracking_number = dr.tracking_number
                            instance.save(update_fields=['delivery_request_id', 'delivery_tracking_number'])
                        except Exception:
                            # non-fatal
                            pass
            except Exception:
                # delivery integration may not be available
                pass
    else:
        # Order was updated
        send_order_webhook(instance, 'order_updated')


# You can add more specific signal handlers for different events
@receiver(post_save, sender='listings.Order')
def handle_order_status_change(sender, instance, **kwargs):
    """Handle specific status changes"""
    # Use the `_original_status` attribute if available (set in Order.save)
    prev = getattr(instance, '_original_status', None)
    new = instance.status

    # If order just moved to 'paid', ensure a DeliveryRequest exists
    if prev != 'paid' and new == 'paid':
        try:
            from delivery.integration import create_delivery_from_order
            if create_delivery_from_order:
                dr = create_delivery_from_order(instance)
                if dr:
                    try:
                        instance.delivery_request_id = str(dr.id)
                        if dr.tracking_number:
                            instance.delivery_tracking_number = dr.tracking_number
                        instance.save(update_fields=['delivery_request_id', 'delivery_tracking_number'])
                    except Exception:
                        # non-fatal
                        pass
        except Exception:
            # best-effort: don't raise
            pass

    # If order moved to 'delivered', update the corresponding DeliveryRequest status
    if prev != 'delivered' and new == 'delivered':
        try:
            from delivery.models import DeliveryRequest
            # prefer explicit delivery_request_id, fall back to matching order_id
            dr = None
            if instance.delivery_request_id:
                dr = DeliveryRequest.objects.filter(id=instance.delivery_request_id).first()
            if not dr:
                dr = DeliveryRequest.objects.filter(order_id=str(instance.id)).first()

            if dr:
                try:
                    dr.update_status('delivered', notes='Marked delivered in ecommerce')
                except Exception:
                    # fallback: set fields directly
                    dr.status = 'delivered'
                    try:
                        from django.utils import timezone
                        dr.completed_at = timezone.now()
                    except Exception:
                        pass
                    dr.save()
        except Exception:
            pass


# Signal for payment updates
@receiver(post_save, sender='listings.Payment')
def handle_payment_update(sender, instance, created, **kwargs):
    """Handle payment updates"""
    if instance.order and instance.status == 'completed':
        send_order_webhook(instance.order, 'order_paid')
        # Also ensure a DeliveryRequest is created when payment completes
        try:
            from delivery.integration import create_delivery_from_order
            if create_delivery_from_order:
                dr = create_delivery_from_order(instance.order)
                if dr:
                    try:
                        instance.order.delivery_request_id = str(dr.id)
                        if dr.tracking_number:
                            instance.order.delivery_tracking_number = dr.tracking_number
                        instance.order.save(update_fields=['delivery_request_id', 'delivery_tracking_number'])
                    except Exception:
                        pass
        except Exception:
            pass