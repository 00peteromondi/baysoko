"""
Data mappers for converting e-commerce orders to delivery requests
"""
from django.utils import timezone
from datetime import datetime


def map_order_to_delivery(order_data, platform):
    """Map e-commerce order data to delivery request format"""
    
    # Extract common data
    platform_type = platform.platform_type
    
    if platform_type == 'baysoko':
        return _map_baysoko_order(order_data)
    elif platform_type == 'shopify':
        return _map_shopify_order(order_data)
    elif platform_type == 'woocommerce':
        return _map_woocommerce_order(order_data)
    elif platform_type == 'magento':
        return _map_magento_order(order_data)
    else:
        return _map_generic_order(order_data)


def _map_baysoko_order(order_data):
    """Map Baysoko order to delivery request"""
    shipping = order_data.get('shipping_address', {})
    customer = order_data.get('customer', {})
    store = order_data.get('store', {})
    items = order_data.get('items', [])
    
    # Calculate package weight (sum of items)
    package_weight = sum(
        item.get('product', {}).get('weight', 0) * item.get('quantity', 1)
        for item in items
    ) or 1.0  # Default 1kg if no weight
    
    # Build package description
    item_names = [item.get('product', {}).get('name', 'Item') for item in items[:3]]
    package_description = f"Order #{order_data.get('order_number')} - {', '.join(item_names)}"
    if len(items) > 3:
        package_description += f" and {len(items) - 3} more items"
    
    return {
        'order_id': order_data.get('order_number'),
        'platform_order_id': order_data.get('id'),
        
        # Pickup information (from store/seller)
        'pickup_name': store.get('name', 'Baysoko Store'),
        'pickup_address': store.get('address', ''),
        'pickup_phone': store.get('phone', ''),
        'pickup_email': store.get('email', ''),
        
        # Delivery information (customer)
        'recipient_name': shipping.get('full_name', customer.get('name')),
        'recipient_address': _format_address(shipping),
        'recipient_phone': shipping.get('phone', customer.get('phone')),
        'recipient_email': customer.get('email', ''),
        
        # Package details
        'package_description': package_description,
        'package_weight': package_weight,
        'declared_value': float(order_data.get('total_amount', 0)),
        'is_fragile': any(item.get('product', {}).get('is_fragile', False) for item in items),
        'requires_signature': True,
        
        # Payment status
        'payment_status': order_data.get('payment_status', 'pending'),
        
        # Additional metadata
        'metadata': {
            'order_status': order_data.get('status'),
            'items_count': len(items),
            'platform': 'baysoko',
            'order_created': order_data.get('created_at'),
        }
    }


def _map_shopify_order(order_data):
    """Map Shopify order to delivery request"""
    shipping = order_data.get('shipping_address', {})
    customer = order_data.get('customer', {})
    items = order_data.get('items', [])
    
    # Calculate total weight
    total_weight = sum(item.get('weight', 0) for item in items) / 1000  # Convert grams to kg
    package_weight = total_weight if total_weight > 0 else 1.0
    
    # Build package description
    item_names = [item.get('name') for item in items[:3]]
    package_description = f"Shopify Order #{order_data.get('order_number')} - {', '.join(item_names)}"
    
    return {
        'order_id': order_data.get('order_number'),
        'platform_order_id': order_data.get('id'),
        
        # Pickup information (default warehouse/store)
        'pickup_name': 'Warehouse',
        'pickup_address': 'Default Warehouse Address',
        'pickup_phone': '',
        'pickup_email': '',
        
        # Delivery information
        'recipient_name': shipping.get('full_name', customer.get('name')),
        'recipient_address': _format_address(shipping),
        'recipient_phone': shipping.get('phone', ''),
        'recipient_email': customer.get('email', ''),
        
        # Package details
        'package_description': package_description,
        'package_weight': package_weight,
        'declared_value': float(order_data.get('total_price', 0)),
        'is_fragile': False,  # Could be determined from item tags
        'requires_signature': order_data.get('financial_status') == 'paid',
        
        # Payment status
        'payment_status': 'paid' if order_data.get('financial_status') == 'paid' else 'pending',
        
        # Additional metadata
        'metadata': {
            'shopify_order_name': order_data.get('name'),
            'fulfillment_status': order_data.get('fulfillment_status'),
            'items_count': len(items),
            'platform': 'shopify',
        }
    }


def _map_woocommerce_order(order_data):
    """Map WooCommerce order to delivery request"""
    shipping = order_data.get('shipping_address', {})
    billing = order_data.get('customer', {})
    items = order_data.get('items', [])
    
    # Package description
    item_names = [item.get('name') for item in items[:3]]
    package_description = f"WooCommerce Order #{order_data.get('order_number')} - {', '.join(item_names)}"
    
    return {
        'order_id': order_data.get('order_number'),
        'platform_order_id': order_data.get('id'),
        
        # Pickup information
        'pickup_name': 'Store',
        'pickup_address': 'Store Address',
        'pickup_phone': '',
        'pickup_email': '',
        
        # Delivery information
        'recipient_name': shipping.get('full_name', billing.get('name')),
        'recipient_address': _format_address(shipping),
        'recipient_phone': shipping.get('phone', billing.get('phone')),
        'recipient_email': billing.get('email', ''),
        
        # Package details
        'package_description': package_description,
        'package_weight': 1.0,  # Default weight
        'declared_value': float(order_data.get('total', 0)),
        'is_fragile': False,
        'requires_signature': order_data.get('status') == 'completed',
        
        # Payment status
        'payment_status': 'paid' if order_data.get('status') == 'completed' else 'pending',
        
        # Additional metadata
        'metadata': {
            'woocommerce_status': order_data.get('status'),
            'payment_method': order_data.get('metadata', {}).get('payment_method'),
            'items_count': len(items),
            'platform': 'woocommerce',
        }
    }


def _map_magento_order(order_data):
    """Map Magento order to delivery request"""
    # Implementation for Magento
    return _map_generic_order(order_data)


def _map_generic_order(order_data):
    """Map generic order data to delivery request"""
    shipping = order_data.get('shipping_address', {})
    customer = order_data.get('customer', {})
    
    return {
        'order_id': order_data.get('order_number', order_data.get('id')),
        'platform_order_id': order_data.get('id'),
        
        # Pickup information
        'pickup_name': 'Warehouse',
        'pickup_address': 'Default Address',
        'pickup_phone': '',
        'pickup_email': '',
        
        # Delivery information
        'recipient_name': shipping.get('full_name', customer.get('name', 'Customer')),
        'recipient_address': _format_address(shipping),
        'recipient_phone': shipping.get('phone', customer.get('phone', '')),
        'recipient_email': customer.get('email', ''),
        
        # Package details
        'package_description': f"Order #{order_data.get('order_number', order_data.get('id'))}",
        'package_weight': 1.0,
        'declared_value': float(order_data.get('total_amount', 0)),
        'is_fragile': False,
        'requires_signature': True,
        
        # Payment status
        'payment_status': order_data.get('payment_status', 'pending'),
        
        # Additional metadata
        'metadata': {
            'platform': 'generic',
            'source_data': order_data,
        }
    }


def _format_address(address_data):
    """Format address from dictionary to string"""
    parts = []
    
    if address_data.get('full_name'):
        parts.append(address_data['full_name'])
    
    if address_data.get('address_line1'):
        parts.append(address_data['address_line1'])
    
    if address_data.get('address_line2'):
        parts.append(address_data['address_line2'])
    
    city_state = []
    if address_data.get('city'):
        city_state.append(address_data['city'])
    
    if address_data.get('state'):
        city_state.append(address_data['state'])
    
    if city_state:
        parts.append(', '.join(city_state))
    
    if address_data.get('postal_code'):
        parts.append(address_data['postal_code'])
    
    if address_data.get('country'):
        parts.append(address_data['country'])
    
    return '\n'.join(parts)


def create_delivery_from_order(order_data, platform=None):
    """Create delivery request from order data (compatible with existing code)"""
    from .models import EcommercePlatform
    from ..models import DeliveryRequest
    from ..utils import calculate_delivery_fee
    
    # If platform not provided, try to find or create default
    if not platform:
        platform, _ = EcommercePlatform.objects.get_or_create(
            platform_type='baysoko',
            defaults={
                'name': 'Baysoko',
                'base_url': settings.SITE_URL,
                'api_key': '',
                'is_active': True
            }
        )
    
    # Map order data
    delivery_data = map_order_to_delivery(order_data, platform)
    
    # Generate tracking number
    from django.utils import timezone
    import uuid
    tracking_number = f"DLV{timezone.now().strftime('%Y%m%d%H%M%S')}"
    
    # Calculate delivery fee
    delivery_fee = calculate_delivery_fee(
        weight=delivery_data.get('package_weight', 1.0),
        distance=None,
        service_type=None,
        zone=None
    )
    
    # Create delivery request
    delivery_request = DeliveryRequest.objects.create(
        tracking_number=tracking_number,
        order_id=delivery_data['order_id'],
        external_order_ref=delivery_data['platform_order_id'],
        status='pending',
        priority=2,
        
        # Pickup information
        pickup_name=delivery_data['pickup_name'],
        pickup_address=delivery_data['pickup_address'],
        pickup_phone=delivery_data.get('pickup_phone', ''),
        pickup_email=delivery_data.get('pickup_email', ''),
        
        # Delivery information
        recipient_name=delivery_data['recipient_name'],
        recipient_address=delivery_data['recipient_address'],
        recipient_phone=delivery_data['recipient_phone'],
        recipient_email=delivery_data.get('recipient_email', ''),
        
        # Package details
        package_description=delivery_data['package_description'],
        package_weight=delivery_data['package_weight'],
        declared_value=delivery_data['declared_value'],
        is_fragile=delivery_data.get('is_fragile', False),
        requires_signature=delivery_data.get('requires_signature', True),
        
        # Financial details
        delivery_fee=delivery_fee,
        total_amount=delivery_fee,
        payment_status=delivery_data.get('payment_status', 'pending'),
        
        # Metadata
        metadata=delivery_data.get('metadata', {})
    )
    
    # Create order mapping
    from .models import OrderMapping
    OrderMapping.objects.create(
        platform=platform,
        platform_order_id=delivery_data['platform_order_id'],
        platform_order_number=delivery_data['order_id'],
        delivery_request=delivery_request,
        raw_order_data=order_data
    )
    
    return delivery_request