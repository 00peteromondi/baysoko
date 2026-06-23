"""
Webhook processors for handling real-time order updates
"""
import json
import hashlib
import hmac
import logging
from datetime import datetime
from django.utils import timezone
from django.db import transaction

from .models import WebhookEvent, EcommercePlatform, OrderMapping
from ..models import DeliveryRequest
from .mappers import map_order_to_delivery, create_delivery_from_order

logger = logging.getLogger(__name__)


def verify_webhook_signature(platform, signature, payload):
    """Verify webhook signature for security"""
    if not platform.webhook_secret:
        return True  # No secret configured, accept all
    
    # Different platforms have different verification methods
    if platform.platform_type == 'shopify':
        # Shopify uses HMAC-SHA256
        computed_signature = hmac.new(
            platform.webhook_secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(computed_signature, signature)
    
    elif platform.platform_type == 'woocommerce':
        # WooCommerce uses X-WC-Webhook-Signature
        # Implementation depends on WooCommerce version
        return True  # Implement proper verification
    
    elif platform.platform_type == 'baysoko':
        # Custom verification for Baysoko
        expected_signature = hashlib.sha256(
            f"{platform.webhook_secret}{payload}".encode('utf-8')
        ).hexdigest()
        return signature == expected_signature
    
    return True  # Default to accepting


def process_webhook_event(webhook_event):
    """Process incoming webhook event"""
    try:
        webhook_event.status = 'processing'
        webhook_event.save(update_fields=['status'])
        
        payload = webhook_event.payload
        event_type = webhook_event.event_type
        
        # Process based on event type
        if event_type == 'order_created':
            result = process_order_created(webhook_event.platform, payload)
        
        elif event_type == 'order_updated':
            result = process_order_updated(webhook_event.platform, payload)
        
        elif event_type == 'order_cancelled':
            result = process_order_cancelled(webhook_event.platform, payload)
        
        elif event_type == 'order_paid':
            result = process_order_paid(webhook_event.platform, payload)
        
        elif event_type == 'order_shipped':
            result = process_order_shipped(webhook_event.platform, payload)
        
        elif event_type == 'order_delivered':
            result = process_order_delivered(webhook_event.platform, payload)
        
        else:
            result = {'success': True, 'message': 'Event type not processed'}
        
        # Update webhook event status
        webhook_event.status = 'processed'
        webhook_event.processed_at = timezone.now()
        webhook_event.save(update_fields=['status', 'processed_at'])
        
        logger.info(f"Webhook processed: {webhook_event.id} - {event_type}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to process webhook {webhook_event.id}: {str(e)}")
        webhook_event.status = 'failed'
        webhook_event.error_message = str(e)
        webhook_event.processed_at = timezone.now()
        webhook_event.save(update_fields=['status', 'error_message', 'processed_at'])
        
        return {'success': False, 'error': str(e)}


def process_order_created(platform, payload):
    """Process order created webhook"""
    try:
        with transaction.atomic():
            # Extract order data from payload
            order_data = extract_order_data(platform, payload)
            
            # Check if order already exists
            existing_mapping = OrderMapping.objects.filter(
                platform=platform,
                platform_order_id=order_data['id']
            ).first()
            
            if existing_mapping:
                # Update existing delivery request
                delivery = existing_mapping.delivery_request
                update_delivery_from_order(delivery, order_data)
                return {'success': True, 'action': 'updated', 'delivery_id': delivery.id}
            else:
                # Create new delivery request
                delivery = create_delivery_from_order(order_data, platform)
                return {'success': True, 'action': 'created', 'delivery_id': delivery.id}
                
    except Exception as e:
        logger.error(f"Failed to process order created: {str(e)}")
        raise


def process_order_updated(platform, payload):
    """Process order updated webhook"""
    try:
        order_data = extract_order_data(platform, payload)
        
        # Find existing order mapping
        mapping = OrderMapping.objects.filter(
            platform=platform,
            platform_order_id=order_data['id']
        ).first()
        
        if not mapping:
            # Order doesn't exist, create it
            return process_order_created(platform, payload)
        
        # Update delivery request based on order changes
        delivery = mapping.delivery_request
        
        # Update order mapping with new data
        mapping.raw_order_data = order_data
        mapping.save(update_fields=['raw_order_data'])
        
        # Update delivery status based on order status
        order_status = order_data.get('status')
        if order_status in ['cancelled', 'refunded']:
            delivery.status = 'cancelled'
            delivery.save(update_fields=['status'])
        
        elif order_status == 'shipped':
            if delivery.status != 'delivered':
                delivery.status = 'in_transit'
                delivery.save(update_fields=['status'])
        
        elif order_status == 'delivered':
            delivery.status = 'delivered'
            delivery.actual_delivery_time = timezone.now()
            delivery.save(update_fields=['status', 'actual_delivery_time'])
        
        return {'success': True, 'action': 'updated', 'delivery_id': delivery.id}
        
    except Exception as e:
        logger.error(f"Failed to process order updated: {str(e)}")
        raise


def process_order_cancelled(platform, payload):
    """Process order cancelled webhook"""
    try:
        order_id = extract_order_id(platform, payload)
        
        # Find delivery request
        mapping = OrderMapping.objects.filter(
            platform=platform,
            platform_order_id=order_id
        ).first()
        
        if mapping and mapping.delivery_request:
            delivery = mapping.delivery_request
            
            # Only cancel if not already delivered
            if delivery.status not in ['delivered', 'cancelled']:
                delivery.status = 'cancelled'
                delivery.save(update_fields=['status'])
                
                # Log the cancellation
                from ..models import DeliveryStatusHistory
                DeliveryStatusHistory.objects.create(
                    delivery_request=delivery,
                    old_status=delivery.status,
                    new_status='cancelled',
                    notes='Order cancelled in e-commerce platform'
                )
        
        return {'success': True, 'action': 'cancelled'}
        
    except Exception as e:
        logger.error(f"Failed to process order cancelled: {str(e)}")
        raise


def process_order_paid(platform, payload):
    """Process order paid webhook"""
    try:
        order_id = extract_order_id(platform, payload)
        
        # Find delivery request
        mapping = OrderMapping.objects.filter(
            platform=platform,
            platform_order_id=order_id
        ).first()
        
        if mapping and mapping.delivery_request:
            delivery = mapping.delivery_request
            
            # Update payment status
            delivery.payment_status = 'paid'
            delivery.save(update_fields=['payment_status'])
            
            # If order was pending due to payment, mark as accepted
            if delivery.status == 'pending':
                delivery.status = 'accepted'
                delivery.save(update_fields=['status'])
        
        return {'success': True, 'action': 'payment_updated'}
        
    except Exception as e:
        logger.error(f"Failed to process order paid: {str(e)}")
        raise


def process_order_shipped(platform, payload):
    """Process order shipped webhook"""
    try:
        order_id = extract_order_id(platform, payload)
        
        # Find delivery request
        mapping = OrderMapping.objects.filter(
            platform=platform,
            platform_order_id=order_id
        ).first()
        
        if mapping and mapping.delivery_request:
            delivery = mapping.delivery_request
            
            # Update delivery status to in_transit
            if delivery.status not in ['delivered', 'cancelled']:
                delivery.status = 'in_transit'
                delivery.save(update_fields=['status'])
        
        return {'success': True, 'action': 'shipped'}
        
    except Exception as e:
        logger.error(f"Failed to process order shipped: {str(e)}")
        raise


def process_order_delivered(platform, payload):
    """Process order delivered webhook (from e-commerce platform)"""
    try:
        order_id = extract_order_id(platform, payload)
        
        # Find delivery request
        mapping = OrderMapping.objects.filter(
            platform=platform,
            platform_order_id=order_id
        ).first()
        
        if mapping and mapping.delivery_request:
            delivery = mapping.delivery_request
            
            # Mark as delivered in delivery system
            delivery.status = 'delivered'
            delivery.actual_delivery_time = timezone.now()
            delivery.save(update_fields=['status', 'actual_delivery_time'])
        
        return {'success': True, 'action': 'delivered'}
        
    except Exception as e:
        logger.error(f"Failed to process order delivered: {str(e)}")
        raise


def extract_order_data(platform, payload):
    """Extract order data from webhook payload based on platform"""
    if platform.platform_type == 'baysoko':
        # Baysoko webhook format
        return payload.get('data', {})
    
    elif platform.platform_type == 'shopify':
        # Shopify webhook format
        return {
            'id': str(payload.get('id')),
            'order_number': payload.get('order_number'),
            'name': payload.get('name'),
            'financial_status': payload.get('financial_status'),
            'fulfillment_status': payload.get('fulfillment_status'),
            'total_price': float(payload.get('total_price', 0)),
            'currency': payload.get('currency'),
            'created_at': payload.get('created_at'),
            'customer': payload.get('customer', {}),
            'shipping_address': payload.get('shipping_address', {}),
            'line_items': payload.get('line_items', []),
        }
    
    elif platform.platform_type == 'woocommerce':
        # WooCommerce webhook format
        return {
            'id': str(payload.get('id')),
            'order_number': payload.get('number'),
            'status': payload.get('status'),
            'total': float(payload.get('total', 0)),
            'currency': payload.get('currency'),
            'date_created': payload.get('date_created'),
            'customer_id': payload.get('customer_id'),
            'billing': payload.get('billing', {}),
            'shipping': payload.get('shipping', {}),
            'line_items': payload.get('line_items', []),
        }
    
    else:
        # Generic format
        return payload


def extract_order_id(platform, payload):
    """Extract order ID from payload"""
    if platform.platform_type == 'baysoko':
        return str(payload.get('data', {}).get('id', ''))
    
    elif platform.platform_type == 'shopify':
        return str(payload.get('id', ''))
    
    elif platform.platform_type == 'woocommerce':
        return str(payload.get('id', ''))
    
    else:
        return str(payload.get('id', payload.get('order_id', '')))


def update_delivery_from_order(delivery, order_data):
    """Update existing delivery request from order data"""
    # Map order data to delivery format
    delivery_data = map_order_to_delivery(order_data, delivery.metadata.get('platform', 'generic'))
    
    # Update fields that might have changed
    delivery.recipient_name = delivery_data['recipient_name']
    delivery.recipient_address = delivery_data['recipient_address']
    delivery.recipient_phone = delivery_data['recipient_phone']
    delivery.package_description = delivery_data['package_description']
    delivery.package_weight = delivery_data['package_weight']
    delivery.declared_value = delivery_data['declared_value']
    
    # Update metadata
    if 'metadata' in delivery_data:
        delivery.metadata.update(delivery_data['metadata'])
    
    delivery.save()
    
    return delivery