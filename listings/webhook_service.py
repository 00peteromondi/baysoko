"""
Lightweight webhook service that integrates with existing order flow
"""
import json
import hmac
import hashlib
import requests
import logging
import os
from django.conf import settings
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)


class DeliveryWebhookService:
    """Service to send order events to delivery system"""
    
    def __init__(self):
        # Prefer delivery integration settings that exist in project settings
        self.enabled = getattr(settings, 'DELIVERY_SYSTEM_ENABLED', getattr(settings, 'WEBHOOKS_ENABLED', False))
        # Use explicit e-commerce webhook URL if configured, otherwise delivery system URL
        self.webhook_url = getattr(settings, 'ECOMMERCE_WEBHOOK_URL', getattr(settings, 'DELIVERY_SYSTEM_URL', ''))
        # Secret for signing outgoing webhooks — prefer DELIVERY_WEBHOOK_SECRET
        self.secret = os.environ.get('DELIVERY_WEBHOOK_SECRET', getattr(settings, 'DELIVERY_WEBHOOK_SECRET', getattr(settings, 'WEBHOOK_SECRET_KEY', '')))
    
    def send_order_event(self, order, event_type):
        

        """Send order event to delivery system"""
        if not self.enabled or not self.webhook_url:
            logger.debug("Webhooks disabled or no URL configured")
            return False
        
        try:
            payload = self._prepare_payload(order, event_type)
            # Serialize payload deterministically to bytes and sign those bytes
            # Serialize deterministically (sorted keys) and sign those bytes
            payload_str = json.dumps(payload, separators=(',', ':'), ensure_ascii=False, sort_keys=True)
            signature = hmac.new(self.secret.encode('utf-8'), payload_str.encode('utf-8'), hashlib.sha256).hexdigest()

            headers = {
                'Content-Type': 'application/json',
                'X-Webhook-Signature': signature,
                'X-Event-Type': event_type,
                'X-Platform': 'HomaBay Souq'
            }

            response = requests.post(
                self.webhook_url,
                data=payload_str.encode('utf-8'),
                headers=headers,
                timeout=5
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"Webhook sent for order #{order.id} - {event_type}")
                
                # Update order with tracking if provided
                if event_type == 'order_shipped':
                    self._update_order_from_response(order, response.json())
                
                return True
            elif response.status_code in [302, 403, 500]:
                logger.error(f"Webhook failed for order #{order.id}: {response.status_code} - {response.text}")
                return False
            else:
                logger.error(f"Webhook failed for order #{order.id}: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Webhook error for order #{order.id}: {str(e)}")
            return False
    
    def _prepare_payload(self, order, event_type):
        """Prepare payload using existing order data"""
        payload = {
            'event': event_type,
            'timestamp': timezone.now().isoformat(),
            'order_id': order.id,
            'customer': {
                'name': f"{order.first_name} {order.last_name}".strip(),
                'email': order.email,
                'phone': order.phone_number,
            },
            'delivery_address': {
                'address': order.shipping_address,
                'city': order.city,
                'postal_code': order.postal_code,
            },
            'total_amount': float(order.total_price),
            'items': []
        }
        
        # Add items
        for item in order.order_items.all():
            payload['items'].append({
                'title': item.listing.title,
                'quantity': item.quantity,
                'price': float(item.price),
                'seller': item.listing.seller.username if item.listing.seller else 'Unknown',
            })
        
        return payload
    
    def _create_signature(self, payload):
        """Create HMAC signature for security"""
        payload_str = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
        return hmac.new(self.secret.encode('utf-8'), payload_str.encode('utf-8'), hashlib.sha256).hexdigest()
    
    def _update_order_from_response(self, order, response_data):
        """Update order with tracking info from delivery system"""
        if response_data.get('tracking_number'):
            order.tracking_number = response_data['tracking_number']
            order.save(update_fields=['tracking_number'])
            logger.info(f"Updated order #{order.id} with tracking: {response_data['tracking_number']}")


# Global instance for easy access
webhook_service = DeliveryWebhookService()