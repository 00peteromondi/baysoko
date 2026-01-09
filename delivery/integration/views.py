"""
Webhook views for e-commerce integration
"""
import json
import logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_GET
from django.utils.decorators import method_decorator
from django.views import View
from django.conf import settings

from .models import EcommercePlatform, WebhookEvent
from .processors import verify_webhook_signature, process_webhook_event
from . import tasks as integration_tasks

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def platform_webhook(request, platform_id=None):
    """Generic webhook endpoint for all platforms"""
    try:
        # Get platform from URL or headers
        if platform_id:
            platform = EcommercePlatform.objects.get(id=platform_id, is_active=True)
        else:
            # Try to get platform from headers
            platform_name = request.headers.get('X-Platform-Name')
            if not platform_name:
                return JsonResponse({'error': 'Platform not specified'}, status=400)
            
            platform = EcommercePlatform.objects.get(
                name=platform_name,
                is_active=True
            )
        
        # Verify webhook signature
        signature = request.headers.get('X-Webhook-Signature', '')
        payload = request.body.decode('utf-8')
        
        if not verify_webhook_signature(platform, signature, payload):
            return JsonResponse({'error': 'Invalid signature'}, status=401)
        
        # Parse payload
        try:
            payload_data = json.loads(payload)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        # Get event type
        event_type = request.headers.get('X-Event-Type', 'order_updated')
        
        # Create webhook event record
        webhook_event = WebhookEvent.objects.create(
            platform=platform,
            event_type=event_type,
            payload=payload_data,
            headers=dict(request.headers)
        )
        
        # Process webhook asynchronously (or synchronously)
        # For production, use Celery or similar
        result = process_webhook_event(webhook_event)
        
        if result.get('success'):
            return JsonResponse({'status': 'success', 'event_id': webhook_event.id})
        else:
            return JsonResponse({'status': 'error', 'error': result.get('error')}, status=500)
        
    except EcommercePlatform.DoesNotExist:
        return JsonResponse({'error': 'Platform not found or inactive'}, status=404)
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@csrf_exempt
@require_POST
def homabay_souq_webhook(request):
    """Webhook endpoint specifically for HomaBay Souq"""
    try:
        # Get HomaBay Souq platform
        platform = EcommercePlatform.objects.get(
            platform_type='homabay_souq',
            is_active=True
        )
        
        # Verify webhook secret
        secret = request.headers.get('X-Webhook-Secret')
        if secret != platform.webhook_secret:
            return JsonResponse({'error': 'Invalid secret'}, status=401)
        
        # Parse payload
        payload = json.loads(request.body.decode('utf-8'))
        
        # Determine event type
        event_type = payload.get('event', 'order_updated')
        
        # Create webhook event
        webhook_event = WebhookEvent.objects.create(
            platform=platform,
            event_type=event_type,
            payload=payload,
            headers=dict(request.headers)
        )
        
        # Process immediately
        result = process_webhook_event(webhook_event)
        
        return JsonResponse({
            'status': 'success' if result.get('success') else 'error',
            'event_id': webhook_event.id,
            'message': result.get('message', '')
        })
        
    except EcommercePlatform.DoesNotExist:
        return JsonResponse({'error': 'HomaBay Souq platform not configured'}, status=404)
    except Exception as e:
        logger.error(f"HomaBay Souq webhook error: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@csrf_exempt
@require_POST
def shopify_webhook(request):
    """Webhook endpoint for Shopify"""
    try:
        # Shopify sends shop domain in headers
        shop_domain = request.headers.get('X-Shopify-Shop-Domain')
        if not shop_domain:
            return JsonResponse({'error': 'Shop domain not specified'}, status=400)
        
        # Find platform by domain
        platform = EcommercePlatform.objects.get(
            platform_type='shopify',
            base_url__contains=shop_domain,
            is_active=True
        )
        
        # Verify webhook signature
        signature = request.headers.get('X-Shopify-Hmac-SHA256', '')
        payload = request.body.decode('utf-8')
        
        if not verify_webhook_signature(platform, signature, payload):
            return JsonResponse({'error': 'Invalid signature'}, status=401)
        
        # Parse payload and determine event type from topic header
        payload_data = json.loads(payload)
        topic = request.headers.get('X-Shopify-Topic', 'orders/updated')
        
        # Map Shopify topic to our event type
        event_type_map = {
            'orders/create': 'order_created',
            'orders/updated': 'order_updated',
            'orders/cancelled': 'order_cancelled',
            'orders/paid': 'order_paid',
            'orders/fulfilled': 'order_shipped',
        }
        
        event_type = event_type_map.get(topic, 'order_updated')
        
        # Create webhook event
        webhook_event = WebhookEvent.objects.create(
            platform=platform,
            event_type=event_type,
            payload=payload_data,
            headers=dict(request.headers)
        )
        
        # Process asynchronously (in production, use Celery)
        result = process_webhook_event(webhook_event)
        
        return JsonResponse({
            'status': 'success' if result.get('success') else 'error',
            'event_id': webhook_event.id
        })
        
    except EcommercePlatform.DoesNotExist:
        return JsonResponse({'error': 'Shopify platform not found'}, status=404)
    except Exception as e:
        logger.error(f"Shopify webhook error: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@csrf_exempt
@require_POST
def woocommerce_webhook(request):
    """Webhook endpoint for WooCommerce"""
    try:
        # WooCommerce sends webhook ID in headers
        webhook_id = request.headers.get('X-WC-Webhook-ID')
        if not webhook_id:
            return JsonResponse({'error': 'Webhook ID not specified'}, status=400)
        
        # Find platform by webhook ID (you might need to store this)
        platform = EcommercePlatform.objects.get(
            platform_type='woocommerce',
            webhook_secret=webhook_id,  # Or store webhook ID separately
            is_active=True
        )
        
        # Parse payload
        payload = json.loads(request.body.decode('utf-8'))
        
        # Determine event from action in payload
        action = payload.get('action', 'updated')
        event_type_map = {
            'created': 'order_created',
            'updated': 'order_updated',
            'deleted': 'order_cancelled',
            'restored': 'order_updated',
        }
        
        event_type = event_type_map.get(action, 'order_updated')
        
        # Create webhook event
        webhook_event = WebhookEvent.objects.create(
            platform=platform,
            event_type=event_type,
            payload=payload,
            headers=dict(request.headers)
        )
        
        # Process webhook
        result = process_webhook_event(webhook_event)
        
        return JsonResponse({
            'status': 'success' if result.get('success') else 'error',
            'event_id': webhook_event.id
        })
        
    except EcommercePlatform.DoesNotExist:
        return JsonResponse({'error': 'WooCommerce platform not found'}, status=404)
    except Exception as e:
        logger.error(f"WooCommerce webhook error: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


class WebhookTestView(View):
    """View for testing webhooks"""
    
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def post(self, request):
        """Test webhook endpoint"""
        try:
            # Create test webhook payload
            test_payload = {
                'event': 'order_created',
                'data': {
                    'id': 'test_' + str(request.user.id),
                    'order_number': f"TEST{request.user.id}",
                    'status': 'paid',
                    'payment_status': 'paid',
                    'total_amount': 1000.00,
                    'shipping_cost': 200.00,
                    'currency': 'KES',
                    'created_at': '2024-01-01T10:00:00Z',
                    'customer': {
                        'id': request.user.id,
                        'name': request.user.get_full_name(),
                        'email': request.user.email,
                        'phone': '0712345678'
                    },
                    'shipping_address': {
                        'full_name': request.user.get_full_name(),
                        'address_line1': '123 Test Street',
                        'city': 'Homabay',
                        'state': 'Homabay County',
                        'postal_code': '40300',
                        'country': 'Kenya',
                        'phone': '0712345678'
                    },
                    'store': {
                        'name': 'Test Store',
                        'address': '456 Store Street, Homabay',
                        'phone': '0700123456',
                        'email': 'store@example.com'
                    },
                    'items': [
                        {
                            'name': 'Test Product',
                            'quantity': 2,
                            'price': 500.00,
                            'product': {
                                'weight': 0.5,
                                'is_fragile': False
                            }
                        }
                    ]
                }
            }
            
            # Process test webhook
            from .models import EcommercePlatform
            platform, _ = EcommercePlatform.objects.get_or_create(
                platform_type='homabay_souq',
                defaults={
                    'name': 'Test Platform',
                    'base_url': settings.SITE_URL,
                    'is_active': True
                }
            )
            
            from .processors import process_order_created
            result = process_order_created(platform, test_payload)
            
            return JsonResponse({
                'success': True,
                'message': 'Test webhook processed',
                'result': result
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@require_GET
def sync_platforms(request):
    """Trigger synchronization for all active platforms (async via Celery)."""
    try:
        # If Celery is configured, run asynchronously; otherwise call synchronously
        try:
            integration_tasks.sync_all_platforms.delay()
        except Exception:
            # Fallback: call directly
            integration_tasks.sync_all_platforms()

        return JsonResponse({'status': 'sync_started'})
    except Exception as e:
        logger.error(f"Error starting platforms sync: {e}")
        return JsonResponse({'error': 'Could not start sync'}, status=500)


@require_GET
def sync_platform(request, platform_id):
    """Trigger synchronization for a specific platform."""
    try:
        try:
            integration_tasks.sync_platform.delay(platform_id)
        except Exception:
            integration_tasks.sync_platform(platform_id)

        return JsonResponse({'status': 'sync_started', 'platform_id': platform_id})
    except Exception as e:
        logger.error(f"Error starting sync for platform {platform_id}: {e}")
        return JsonResponse({'error': 'Could not start sync for platform'}, status=500)


@require_GET
def get_order_delivery(request, order_id):
    """Return delivery request status for a given order id.

    Tries to find a `DeliveryRequest` by `order_id` or `external_order_ref`.
    """
    try:
        from delivery.models import DeliveryRequest

        # Try direct match first
        try:
            dr = DeliveryRequest.objects.get(order_id=str(order_id))
        except DeliveryRequest.DoesNotExist:
            dr = DeliveryRequest.objects.filter(external_order_ref=str(order_id)).first()

        if not dr:
            return JsonResponse({'error': 'DeliveryRequest not found'}, status=404)

        data = {
            'tracking_number': dr.tracking_number,
            'status': dr.status,
            'delivery_person': dr.delivery_person.user.get_full_name() if dr.delivery_person else None,
            'estimated_delivery_time': dr.estimated_delivery_time.isoformat() if dr.estimated_delivery_time else None,
            'updated_at': dr.updated_at.isoformat() if dr.updated_at else None,
        }

        return JsonResponse({'success': True, 'delivery': data})
    except Exception as e:
        logger.exception(f"Error fetching delivery for order {order_id}: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)