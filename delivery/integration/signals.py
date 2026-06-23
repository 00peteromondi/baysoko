"""
Signals for integrating with Baysoko e-commerce platform
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.conf import settings
import logging

from ..models import DeliveryRequest
from .models import OrderMapping, EcommercePlatform
from .sync import create_delivery_from_order

logger = logging.getLogger(__name__)


@receiver(post_save, sender='listings.Order')
def create_delivery_on_order_creation(sender, instance, created, **kwargs):
    """
    Signal handler to automatically create delivery request when order is created
    in Baysoko e-commerce platform
    """
    if not created:
        return
    
    try:
        # Check if auto-sync is enabled
        if not getattr(settings, 'DELIVERY_AUTO_SYNC_ENABLED', True):
            return
        
        # Get or create Baysoko platform
        platform, _ = EcommercePlatform.objects.get_or_create(
            platform_type='baysoko',
            defaults={
                'name': 'Baysoko',
                'base_url': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
                'api_key': '',
                'is_active': True,
                'sync_enabled': True
            }
        )
        
        # Convert order instance to dictionary
        order_data = _order_to_dict(instance)
        
        # Create delivery request
        delivery = create_delivery_from_order(order_data, platform)
        
        logger.info(f"Created delivery {delivery.tracking_number} for order {instance.order_number}")
        
    except Exception as e:
        logger.error(f"Failed to create delivery for order {instance.id}: {str(e)}")


@receiver(post_save, sender='listings.Order')
def update_delivery_on_order_status_change(sender, instance, **kwargs):
    """
    Update delivery status when order status changes
    """
    try:
        # Find delivery request for this order
        mapping = OrderMapping.objects.filter(
            platform__platform_type='baysoko',
            platform_order_id=str(instance.id)
        ).first()
        
        if not mapping or not mapping.delivery_request:
            return
        
        delivery = mapping.delivery_request
        
        # Map order status to delivery status
        status_mapping = {
            'processing': 'accepted',
            'shipped': 'in_transit',
            'out_for_delivery': 'out_for_delivery',
            'delivered': 'delivered',
            'cancelled': 'cancelled',
            'refunded': 'cancelled',
        }
        
        new_status = status_mapping.get(instance.status)
        
        if new_status and new_status != delivery.status:
            delivery.update_status(new_status, f"Order status changed to {instance.status}")
            
            logger.info(f"Updated delivery {delivery.tracking_number} to {new_status}")
        
    except Exception as e:
        logger.error(f"Failed to update delivery for order {instance.id}: {str(e)}")


@receiver(post_save, sender=DeliveryRequest)
def update_order_on_delivery_status_change(sender, instance, **kwargs):
    """
    Update order status in e-commerce platform when delivery status changes
    (Optional: for two-way sync)
    """
    if not getattr(settings, 'DELIVERY_UPDATE_ORDER_STATUS', False):
        return
    
    try:
        # Find order mapping
        mapping = getattr(instance, 'order_mapping', None)
        if not mapping or mapping.platform.platform_type != 'baysoko':
            return
        
        # Map delivery status to order status
        status_mapping = {
            'accepted': 'processing',
            'assigned': 'processing',
            'picked_up': 'shipped',
            'in_transit': 'shipped',
            'out_for_delivery': 'out_for_delivery',
            'delivered': 'delivered',
            'failed': 'delivery_failed',
            'cancelled': 'cancelled',
        }
        
        order_status = status_mapping.get(instance.status)
        
        if order_status:
            # Update order in e-commerce platform
            # This would require API call to update order status
            # For now, we'll log it
            logger.info(
                f"Delivery {instance.tracking_number} status changed to {instance.status}, "
                f"order should be updated to {order_status}"
            )
        
    except Exception as e:
        logger.error(f"Failed to update order for delivery {instance.id}: {str(e)}")


def _order_to_dict(order_instance):
    """Convert Order model instance to dictionary"""
    from django.core.serializers.json import DjangoJSONEncoder
    import json
    
    # Basic order data
    order_data = {
        'id': str(order_instance.id),
        'order_number': order_instance.order_number,
        'status': order_instance.status,
        'payment_status': order_instance.payment_status,
        'total_amount': float(order_instance.total_amount),
        'shipping_cost': float(order_instance.shipping_cost) if order_instance.shipping_cost else 0,
        'currency': 'KES',
        'created_at': order_instance.created_at.isoformat() if order_instance.created_at else None,
        'updated_at': order_instance.updated_at.isoformat() if order_instance.updated_at else None,
    }
    
    # Customer information
    if order_instance.user:
        order_data['customer'] = {
            'id': order_instance.user.id,
            'name': order_instance.user.get_full_name(),
            'email': order_instance.user.email,
        }
    
    # Shipping address
    if hasattr(order_instance, 'shipping_address') and order_instance.shipping_address:
        shipping = order_instance.shipping_address
        order_data['shipping_address'] = {
            'full_name': shipping.full_name,
            'address_line1': shipping.address_line1,
            'address_line2': shipping.address_line2 or '',
            'city': shipping.city,
            'state': shipping.state,
            'postal_code': shipping.postal_code,
            'country': shipping.country,
            'phone': shipping.phone,
        }
    
    # Store/seller information
    if hasattr(order_instance, 'store') and order_instance.store:
        store = order_instance.store
        order_data['store'] = {
            'id': store.id,
            'name': store.name,
            'address': store.address or '',
            'phone': store.phone or '',
            'email': store.email or '',
        }
    
    # Order items
    if hasattr(order_instance, 'items'):
        items = []
        for item in order_instance.items.all():
            item_data = {
                'name': item.product.name if item.product else 'Unknown Product',
                'quantity': item.quantity,
                'price': float(item.price),
                'total': float(item.price * item.quantity),
            }
            
            if item.product:
                item_data['product'] = {
                    'weight': float(item.product.weight) if hasattr(item.product, 'weight') else 0.5,
                    'is_fragile': getattr(item.product, 'is_fragile', False),
                }
            
            items.append(item_data)
        
        order_data['items'] = items
    
    return order_data