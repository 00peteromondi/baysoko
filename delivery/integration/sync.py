"""
Order synchronization service
"""
import requests
import json
import logging
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from django.conf import settings

from ..models import DeliveryRequest, DeliveryPerson, DeliveryService, DeliveryZone
from .models import EcommercePlatform, OrderSyncLog, OrderMapping, OrderSyncRule
from ..utils import calculate_delivery_fee
from .mappers import map_order_to_delivery

logger = logging.getLogger(__name__)


class OrderSyncService:
    """Service for synchronizing orders from e-commerce platforms"""
    
    def __init__(self, platform):
        self.platform = platform
        self.api_client = self._create_api_client(platform)
        self.sync_log = None
    
    def _create_api_client(self, platform):
        """Create API client for the platform"""
        if platform.platform_type == 'homabay_souq':
            return HomaBaySouqClient(platform)
        elif platform.platform_type == 'shopify':
            return ShopifyClient(platform)
        elif platform.platform_type == 'woocommerce':
            return WooCommerceClient(platform)
        elif platform.platform_type == 'magento':
            return MagentoClient(platform)
        else:
            return GenericAPIClient(platform)
    
    def sync_orders(self, sync_type='scheduled', force=False):
        """Synchronize orders from platform"""
        try:
            # Create sync log
            self.sync_log = OrderSyncLog.objects.create(
                platform=self.platform,
                sync_type=sync_type,
                status='in_progress'
            )
            
            # Get orders from platform
            orders = self.api_client.fetch_orders(force=force)
            
            # Process each order
            synced_count = 0
            failed_count = 0
            
            for order_data in orders:
                try:
                    # Check if order should be synced
                    if not self._should_sync_order(order_data):
                        logger.info(f"Skipping order {order_data.get('order_id')}")
                        continue
                    
                    # Create or update delivery request
                    delivery_request = self._process_order(order_data)
                    
                    # Create order mapping
                    OrderMapping.objects.update_or_create(
                        platform=self.platform,
                        platform_order_id=order_data['id'],
                        defaults={
                            'platform_order_number': order_data.get('order_number', order_data['id']),
                            'delivery_request': delivery_request,
                            'raw_order_data': order_data
                        }
                    )
                    
                    synced_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to sync order {order_data.get('id')}: {str(e)}")
                    failed_count += 1
            
            # Update sync log
            self.sync_log.status = 'partial' if failed_count > 0 else 'success'
            self.sync_log.orders_synced = synced_count
            self.sync_log.orders_failed = failed_count
            self.sync_log.completed_at = timezone.now()
            self.sync_log.save()
            
            # Update platform last sync
            self.platform.last_sync = timezone.now()
            self.platform.save(update_fields=['last_sync'])
            
            logger.info(f"Sync completed: {synced_count} synced, {failed_count} failed")
            
            return {
                'success': True,
                'synced': synced_count,
                'failed': failed_count,
                'log_id': self.sync_log.id
            }
            
        except Exception as e:
            logger.error(f"Sync failed: {str(e)}")
            if self.sync_log:
                self.sync_log.status = 'failed'
                self.sync_log.error_message = str(e)
                self.sync_log.completed_at = timezone.now()
                self.sync_log.save()
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def _should_sync_order(self, order_data):
        """Check if order should be synced based on rules"""
        # Check if order already exists
        existing = OrderMapping.objects.filter(
            platform=self.platform,
            platform_order_id=order_data['id']
        ).exists()
        
        if existing:
            return False
        
        # Apply sync rules
        rules = OrderSyncRule.objects.filter(
            platform=self.platform,
            is_active=True
        ).order_by('priority')
        
        for rule in rules:
            if not rule.evaluate(order_data):
                return False
        
        return True
    
    def _process_order(self, order_data):
        """Process order and create delivery request"""
        with transaction.atomic():
            # Map order data to delivery request
            delivery_data = map_order_to_delivery(order_data, self.platform)
            
            # Generate tracking number
            tracking_number = f"DLV{timezone.now().strftime('%Y%m%d%H%M%S')}"
            
            # Calculate delivery fee
            delivery_fee = calculate_delivery_fee(
                weight=delivery_data.get('package_weight', 1.0),
                distance=None,
                service_type=delivery_data.get('delivery_service'),
                zone=delivery_data.get('delivery_zone')
            )
            
            # Create delivery request
            delivery_request = DeliveryRequest.objects.create(
                tracking_number=tracking_number,
                order_id=order_data.get('order_number', order_data['id']),
                external_order_ref=order_data['id'],
                status='pending',
                priority=2,
                
                # Pickup information
                pickup_name=delivery_data.get('pickup_name', 'Store'),
                pickup_address=delivery_data.get('pickup_address', ''),
                pickup_phone=delivery_data.get('pickup_phone', ''),
                pickup_email=delivery_data.get('pickup_email', ''),
                
                # Delivery information
                recipient_name=delivery_data['recipient_name'],
                recipient_address=delivery_data['recipient_address'],
                recipient_phone=delivery_data['recipient_phone'],
                recipient_email=delivery_data.get('recipient_email', ''),
                
                # Package details
                package_description=delivery_data['package_description'],
                package_weight=delivery_data.get('package_weight', 1.0),
                declared_value=delivery_data.get('declared_value', 0),
                is_fragile=delivery_data.get('is_fragile', False),
                requires_signature=delivery_data.get('requires_signature', True),
                
                # Financial details
                delivery_fee=delivery_fee,
                total_amount=delivery_fee,
                payment_status=delivery_data.get('payment_status', 'pending'),
                
                # Metadata
                metadata={
                    'platform': self.platform.name,
                    'platform_type': self.platform.platform_type,
                    'order_data': order_data,
                    'sync_timestamp': timezone.now().isoformat(),
                    'source': 'auto_sync'
                }
            )
            
            # Send notification
            from ..utils import send_delivery_notification
            send_delivery_notification(
                delivery=delivery_request,
                notification_type='delivery_created_from_order',
                recipient=None  # Will be sent to admin
            )
            
            return delivery_request


# API Clients for different platforms
class HomaBaySouqClient:
    """Client for HomaBay Souq platform"""
    
    def __init__(self, platform):
        self.platform = platform
        self.base_url = platform.base_url.rstrip('/')
        self.api_key = platform.api_key
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    def fetch_orders(self, force=False):
        """Fetch orders from HomaBay Souq"""
        try:
            # Calculate date range (last 24 hours or since last sync)
            if force or not self.platform.last_sync:
                from_date = timezone.now() - timedelta(days=1)
            else:
                from_date = self.platform.last_sync - timedelta(minutes=5)
            
            # API endpoint for orders
            url = f"{self.base_url}/api/orders/"
            
            params = {
                'status': 'paid,processing,shipped',
                'date_from': from_date.isoformat(),
                'date_to': timezone.now().isoformat(),
                'limit': 100
            }
            
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            
            orders = response.json().get('results', [])
            
            # Format orders for processing
            formatted_orders = []
            for order in orders:
                formatted_orders.append(self._format_order(order))
            
            return formatted_orders
            
        except Exception as e:
            logger.error(f"Failed to fetch orders from HomaBay Souq: {str(e)}")
            raise
    
    def _format_order(self, order):
        """Format order data for delivery system"""
        return {
            'id': str(order.get('id')),
            'order_number': order.get('order_number'),
            'status': order.get('status'),
            'payment_status': order.get('payment_status'),
            'total_amount': float(order.get('total_amount', 0)),
            'shipping_cost': float(order.get('shipping_cost', 0)),
            'currency': order.get('currency', 'KES'),
            'created_at': order.get('created_at'),
            'updated_at': order.get('updated_at'),
            
            # Customer information
            'customer': {
                'id': order.get('user', {}).get('id'),
                'name': order.get('shipping_address', {}).get('full_name'),
                'email': order.get('user', {}).get('email'),
                'phone': order.get('shipping_address', {}).get('phone'),
            },
            
            # Shipping address
            'shipping_address': {
                'full_name': order.get('shipping_address', {}).get('full_name'),
                'address_line1': order.get('shipping_address', {}).get('address_line1'),
                'address_line2': order.get('shipping_address', {}).get('address_line2'),
                'city': order.get('shipping_address', {}).get('city'),
                'state': order.get('shipping_address', {}).get('state'),
                'postal_code': order.get('shipping_address', {}).get('postal_code'),
                'country': order.get('shipping_address', {}).get('country'),
                'phone': order.get('shipping_address', {}).get('phone'),
            },
            
            # Store/seller information
            'store': {
                'id': order.get('store', {}).get('id'),
                'name': order.get('store', {}).get('name'),
                'address': order.get('store', {}).get('address'),
                'phone': order.get('store', {}).get('phone'),
                'email': order.get('store', {}).get('email'),
            },
            
            # Items
            'items': order.get('items', []),
            
            # Additional metadata
            'metadata': order.get('metadata', {})
        }


class ShopifyClient:
    """Client for Shopify platform"""
    
    def __init__(self, platform):
        self.platform = platform
        self.base_url = platform.base_url.rstrip('/')
        self.api_key = platform.api_key
        self.api_secret = platform.api_secret
        self.headers = {
            'X-Shopify-Access-Token': self.api_key,
            'Content-Type': 'application/json'
        }
    
    def fetch_orders(self, force=False):
        """Fetch orders from Shopify"""
        try:
            # Shopify API endpoint
            url = f"{self.base_url}/admin/api/2023-07/orders.json"
            
            # Build query parameters
            params = {
                'status': 'open',
                'limit': 50
            }
            
            if not force and self.platform.last_sync:
                # Get orders updated since last sync
                updated_at_min = self.platform.last_sync.isoformat()
                params['updated_at_min'] = updated_at_min
            
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            
            orders = response.json().get('orders', [])
            
            # Format orders
            formatted_orders = []
            for order in orders:
                formatted_orders.append(self._format_order(order))
            
            return formatted_orders
            
        except Exception as e:
            logger.error(f"Failed to fetch orders from Shopify: {str(e)}")
            raise
    
    def _format_order(self, order):
        """Format Shopify order"""
        shipping_address = order.get('shipping_address', {})
        billing_address = order.get('billing_address', {})
        
        return {
            'id': str(order.get('id')),
            'order_number': order.get('order_number'),
            'name': order.get('name'),
            'financial_status': order.get('financial_status'),
            'fulfillment_status': order.get('fulfillment_status'),
            'total_price': float(order.get('total_price', 0)),
            'currency': order.get('currency'),
            'created_at': order.get('created_at'),
            'updated_at': order.get('updated_at'),
            
            'customer': {
                'id': order.get('customer', {}).get('id'),
                'name': f"{shipping_address.get('first_name', '')} {shipping_address.get('last_name', '')}".strip(),
                'email': order.get('customer', {}).get('email'),
                'phone': shipping_address.get('phone') or billing_address.get('phone'),
            },
            
            'shipping_address': {
                'full_name': f"{shipping_address.get('first_name', '')} {shipping_address.get('last_name', '')}".strip(),
                'address_line1': shipping_address.get('address1', ''),
                'address_line2': shipping_address.get('address2', ''),
                'city': shipping_address.get('city', ''),
                'state': shipping_address.get('province', ''),
                'postal_code': shipping_address.get('zip', ''),
                'country': shipping_address.get('country', ''),
                'phone': shipping_address.get('phone', ''),
            },
            
            'items': [
                {
                    'name': item.get('name'),
                    'quantity': item.get('quantity'),
                    'price': float(item.get('price', 0)),
                    'weight': item.get('grams', 0) / 1000,  # Convert grams to kg
                }
                for item in order.get('line_items', [])
            ],
            
            'metadata': {
                'shopify_order_id': order.get('id'),
                'shopify_order_name': order.get('name'),
                'note': order.get('note', ''),
            }
        }


class WooCommerceClient:
    """Client for WooCommerce platform"""
    
    def __init__(self, platform):
        self.platform = platform
        self.base_url = platform.base_url.rstrip('/')
        self.api_key = platform.api_key
        self.api_secret = platform.api_secret
        self.auth = (self.api_key, self.api_secret)
    
    def fetch_orders(self, force=False):
        """Fetch orders from WooCommerce"""
        try:
            # WooCommerce API endpoint
            url = f"{self.base_url}/wp-json/wc/v3/orders"
            
            params = {
                'status': 'processing,completed',
                'per_page': 50,
                'orderby': 'date',
                'order': 'desc'
            }
            
            if not force and self.platform.last_sync:
                # Convert datetime to WordPress format
                after_date = self.platform.last_sync.strftime('%Y-%m-%dT%H:%M:%S')
                params['after'] = after_date
            
            response = requests.get(url, auth=self.auth, params=params, timeout=30)
            response.raise_for_status()
            
            orders = response.json()
            
            # Format orders
            formatted_orders = []
            for order in orders:
                formatted_orders.append(self._format_order(order))
            
            return formatted_orders
            
        except Exception as e:
            logger.error(f"Failed to fetch orders from WooCommerce: {str(e)}")
            raise
    
    def _format_order(self, order):
        """Format WooCommerce order"""
        shipping = order.get('shipping', {})
        billing = order.get('billing', {})
        
        return {
            'id': str(order.get('id')),
            'order_number': order.get('number'),
            'status': order.get('status'),
            'total': float(order.get('total', 0)),
            'currency': order.get('currency'),
            'date_created': order.get('date_created'),
            'date_modified': order.get('date_modified'),
            
            'customer': {
                'id': order.get('customer_id'),
                'name': f"{billing.get('first_name', '')} {billing.get('last_name', '')}".strip(),
                'email': billing.get('email'),
                'phone': billing.get('phone'),
            },
            
            'shipping_address': {
                'full_name': f"{shipping.get('first_name', '')} {shipping.get('last_name', '')}".strip(),
                'address_line1': shipping.get('address_1', ''),
                'address_line2': shipping.get('address_2', ''),
                'city': shipping.get('city', ''),
                'state': shipping.get('state', ''),
                'postal_code': shipping.get('postcode', ''),
                'country': shipping.get('country', ''),
                'phone': shipping.get('phone', billing.get('phone')),
            },
            
            'items': [
                {
                    'name': item.get('name'),
                    'quantity': item.get('quantity'),
                    'price': float(item.get('price', 0)),
                    'total': float(item.get('total', 0)),
                }
                for item in order.get('line_items', [])
            ],
            
            'metadata': {
                'woocommerce_order_id': order.get('id'),
                'payment_method': order.get('payment_method'),
                'payment_method_title': order.get('payment_method_title'),
            }
        }


class GenericAPIClient:
    """Generic API client for custom platforms"""
    
    def __init__(self, platform):
        self.platform = platform
        self.base_url = platform.base_url.rstrip('/')
        self.api_key = platform.api_key
        self.api_secret = platform.api_secret
    
    def fetch_orders(self, force=False):
        """Fetch orders from generic API"""
        try:
            # Generic API endpoint - can be configured
            url = f"{self.base_url}/api/orders"
            
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            params = {}
            if not force and self.platform.last_sync:
                params['since'] = self.platform.last_sync.isoformat()
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            
            orders = response.json()
            
            # Format orders (assuming standard format)
            formatted_orders = []
            for order in orders:
                formatted_orders.append(self._format_order(order))
            
            return formatted_orders
            
        except Exception as e:
            logger.error(f"Failed to fetch orders from generic API: {str(e)}")
            raise
    
    def _format_order(self, order):
        """Format generic order data"""
        # This can be customized per platform
        return {
            'id': str(order.get('id', order.get('order_id'))),
            'order_number': order.get('order_number', order.get('id')),
            'status': order.get('status', 'pending'),
            'payment_status': order.get('payment_status', 'pending'),
            'total_amount': float(order.get('total_amount', 0)),
            'currency': order.get('currency', 'KES'),
            'created_at': order.get('created_at', timezone.now().isoformat()),
            
            'customer': order.get('customer', {}),
            'shipping_address': order.get('shipping_address', {}),
            'items': order.get('items', []),
            'metadata': order.get('metadata', {})
        }


def sync_orders_from_platform(platform):
    """Helper function to sync orders from a platform"""
    service = OrderSyncService(platform)
    return service.sync_orders()


def evaluate_sync_rule(rule, order_data):
    """Evaluate if order matches sync rule"""
    rule_type = rule.rule_type
    condition = rule.condition
    
    if rule_type == 'status_filter':
        allowed_statuses = condition.get('allowed_statuses', [])
        order_status = order_data.get('status')
        return order_status in allowed_statuses if allowed_statuses else True
    
    elif rule_type == 'payment_filter':
        require_payment = condition.get('require_payment', True)
        if not require_payment:
            return True
        
        payment_status = order_data.get('payment_status')
        return payment_status in ['paid', 'completed']
    
    elif rule_type == 'date_filter':
        days_back = condition.get('days_back', 7)
        created_at = order_data.get('created_at')
        
        if not created_at:
            return True
        
        try:
            order_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            cutoff_date = timezone.now() - timedelta(days=days_back)
            return order_date >= cutoff_date
        except:
            return True
    
    elif rule_type == 'value_filter':
        min_value = condition.get('min_value', 0)
        order_value = float(order_data.get('total_amount', 0))
        return order_value >= min_value
    
    elif rule_type == 'customer_filter':
        # Implement customer filtering logic
        return True
    
    return True