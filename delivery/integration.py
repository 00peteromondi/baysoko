"""
Integration with Baysoko e-commerce platform
"""
import requests
import json
from django.conf import settings
from django.utils import timezone
from .models import DeliveryRequest
from listings.models import Order, Cart


def create_delivery_from_order(order):
    """
    Create a delivery request from an e-commerce order
    """
    try:
        # Check if delivery already exists (use order.id as the canonical order identifier)
        existing = DeliveryRequest.objects.filter(order_id=str(order.id)).first()
        if existing:
            return existing
        
        # Get shipping address (order stores address fields directly)
        shipping_address = order.shipping_address

        # Calculate package weight (best-effort): sum listing weight if numeric, otherwise default to 1.0
        package_weight = 0.0
        try:
            for item in order.order_items.all():
                w = getattr(item.listing, 'weight', None)
                try:
                    package_weight += float(w) * (item.quantity or 1)
                except Exception:
                    package_weight += 1.0 * (item.quantity or 1)
        except Exception:
            package_weight = 1.0
        
        # Create delivery request
        delivery = DeliveryRequest.objects.create(
            order_id=str(order.id),
            external_order_ref=f"ECOMM_{order.id}",
            status='pending',
            priority=2 if getattr(order, 'is_urgent', False) else 1,
            
            # Pickup information (use site/store defaults; Order has no store reference)
            pickup_name=getattr(settings, 'baysoko', {}).get('SITE_NAME', 'Baysoko'),
            pickup_address=getattr(settings, 'DEFAULT_PICKUP_ADDRESS', 'Main Store, HomaBay'),
            pickup_phone=getattr(settings, 'DEFAULT_PICKUP_PHONE', '+254700000000'),
            pickup_email=getattr(settings, 'DEFAULT_PICKUP_EMAIL', 'store@baysoko.com'),
            
            # Delivery information (customer)
            recipient_name=f"{order.first_name} {order.last_name}".strip() or order.user.get_full_name() or order.user.username,
            recipient_address=shipping_address or '',
            recipient_phone=order.phone_number or '',
            recipient_email=order.email or order.user.email,
            
            # Package details
            package_description=f"Order #{order.id} - {order.order_items.count()} items",
            package_weight=package_weight or 1.0,
            declared_value=order.total_price,
            requires_signature=True,
            
            # Financial details
            delivery_fee=0,
            total_amount=order.total_price,
            payment_status='paid' if order.status == 'paid' else 'pending',
            
            # Metadata
            metadata={
                'order_id': order.id,
                'user_id': getattr(getattr(order, 'user', None), 'id', None),
                'store_id': (getattr(order, 'store', None).id if getattr(order, 'store', None) else None),
                'created_from': 'ecommerce',
                'items': [
                    {
                        'name': item.listing.title,
                        'quantity': item.quantity,
                        'price': str(item.price)
                    }
                    for item in order.order_items.all()
                ]
            }
        )
        
        # Send notification
        from .utils import send_delivery_notification
        send_delivery_notification(
            delivery=delivery,
            notification_type='delivery_created_from_order',
            recipient=order.user
        )
        
        return delivery
        
    except Exception as e:
        # Log error
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to create delivery from order {order.id}: {str(e)}")
        return None


def update_order_from_delivery(delivery):
    """
    Update order status based on delivery status
    """
    try:
        # Find the order
        from listings.models import Order
        # delivery.order_id may be a string; handle possible 'ECOMM_<id>' external refs
        order = None
        order_id_val = str(delivery.order_id or '')
        if order_id_val.startswith('ECOMM_'):
            try:
                oid = int(order_id_val.split('_', 1)[1])
                order = Order.objects.filter(id=oid).first()
            except Exception:
                order = None
        else:
            try:
                oid = int(order_id_val)
                order = Order.objects.filter(id=oid).first()
            except Exception:
                order = None
        
        if not order:
            return False
        
        # Map delivery status to order status
        status_mapping = {
            'picked_up': 'processing',
            'in_transit': 'shipped',
            'out_for_delivery': 'out_for_delivery',
            'delivered': 'delivered',
            'failed': 'delivery_failed',
            'cancelled': 'cancelled',
        }
        
        if delivery.status in status_mapping:
            mapped = status_mapping[delivery.status]
            try:
                # Use the delivery-aware setter on Order so only delivery app can mark shipped/delivered
                if hasattr(order, 'set_delivery_status'):
                    order.set_delivery_status(mapped)
                else:
                    order.status = mapped
                    order.save()
            except Exception:
                # Fallback: set directly
                order.status = mapped
                order.save()

            # Update order tracking info
            if not order.tracking_number and getattr(delivery, 'tracking_number', None):
                order.tracking_number = delivery.tracking_number
                order.save()
        
        return True
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to update order from delivery {delivery.id}: {str(e)}")
        return False


def sync_delivery_with_external_system(delivery):
    """
    Sync delivery with external delivery system if configured
    """
    if not settings.DELIVERY_SYSTEM_URL:
        return None
    
    try:
        # Prepare data for external system
        payload = {
            'tracking_number': delivery.tracking_number,
            'order_id': delivery.order_id,
            'status': delivery.status,
            'pickup': {
                'name': delivery.pickup_name,
                'address': delivery.pickup_address,
                'phone': delivery.pickup_phone,
            },
            'delivery': {
                'name': delivery.recipient_name,
                'address': delivery.recipient_address,
                'phone': delivery.recipient_phone,
            },
            'package': {
                'description': delivery.package_description,
                'weight': str(delivery.package_weight),
                'value': str(delivery.declared_value),
            }
        }
        
        # Send to external system: include both Authorization Bearer and X-API-Key
        headers = {
            'Content-Type': 'application/json'
        }

        # Prefer separate config keys when available
        system_key = getattr(settings, 'DELIVERY_SYSTEM_API_KEY', None)
        webhook_key = getattr(settings, 'DELIVERY_WEBHOOK_KEY', None)
        if system_key:
            headers['Authorization'] = f'Bearer {system_key}'
        # Ensure X-API-Key is present for receivers expecting that header
        headers['X-API-Key'] = webhook_key or system_key or ''

        response = requests.post(
            f"{settings.DELIVERY_SYSTEM_URL}/api/deliveries/",
            json=payload,
            headers=headers,
            timeout=10
        )
        
        if response.status_code in (200, 201):
            data = response.json()
            delivery.metadata['external_system_id'] = data.get('id')
            delivery.save()
            return data
        
        return None
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to sync delivery {delivery.id}: {str(e)}")
        return None


def get_available_delivery_services():
    """
    Get available delivery services for checkout
    """
    from .models import DeliveryService, DeliveryZone
    
    services = DeliveryService.objects.filter(is_active=True)
    
    result = []
    for service in services:
        result.append({
            'id': service.id,
            'name': service.name,
            'type': service.service_type,
            'description': service.description,
            'base_price': str(service.base_price),
            'estimated_days': f"{service.estimated_days_min}-{service.estimated_days_max}",
            'zones': [
                {
                    'id': zone.id,
                    'name': zone.name,
                    'fee': str(zone.delivery_fee),
                }
                for zone in DeliveryZone.objects.filter(is_active=True)
            ]
        })
    
    return result


def calculate_shipping_cost(address, cart_items, service_type='standard'):
    """
    Calculate shipping cost for cart items to address
    """
    try:
        from .models import DeliveryZone, DeliveryService
        from .utils import calculate_delivery_fee
        
        # Find delivery zone
        zone = None
        # In production, you would geocode the address here
        # For now, use default zone
        zone = DeliveryZone.objects.filter(is_active=True).first()
        
        # Get delivery service
        service = DeliveryService.objects.filter(
            service_type=service_type,
            is_active=True
        ).first()
        
        # Calculate total weight
        total_weight = sum(
            item.product.weight * item.quantity 
            for item in cart_items if hasattr(item.product, 'weight')
        ) or 1.0
        
        # Calculate fee
        fee = calculate_delivery_fee(
            weight=total_weight,
            service_type=service,
            zone=zone
        )
        
        return fee
        
    except Exception as e:
        # Return default fee
        return 200  # Default KES 200