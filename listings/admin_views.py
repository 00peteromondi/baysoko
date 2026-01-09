"""
Admin views for webhook configuration
"""
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.conf import settings
import requests


@user_passes_test(lambda u: u.is_staff)
def configure_webhooks(request):
    """Webhook configuration page"""
    
    if request.method == 'POST':
        # Test webhook connection
        test_result = test_webhook_connection()
        
        if test_result['success']:
            messages.success(request, 'Webhook connection test successful!')
        else:
            messages.error(request, f'Webhook test failed: {test_result.get("error", "Unknown error")}')
        
        return redirect('admin:configure_webhooks')
    
    context = {
        'webhook_enabled': settings.DELIVERY_SYSTEM_ENABLED,
        'webhook_url': settings.ECOMMERCE_WEBHOOK_URL,
        'delivery_system_url': settings.DELIVERY_SYSTEM_URL,
    }
    
    return render(request, 'admin/webhook_config.html', context)


def test_webhook_connection():
    """Test webhook connection to delivery system"""
    try:
        # Prepare test payload
        test_payload = {
            'event': 'test',
            'timestamp': '2024-01-01T10:00:00Z',
            'data': {
                'test': True,
                'message': 'Test webhook from HomaBay Souq'
            }
        }
        
        # Create signature
        import json
        import hashlib
        import hmac
        
        payload_str = json.dumps(test_payload, sort_keys=True)
        secret = settings.DELIVERY_WEBHOOK_SECRET.encode('utf-8')
        
        signature = hmac.new(
            secret,
            payload_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Headers
        headers = {
            'Content-Type': 'application/json',
            'X-Webhook-Signature': signature,
            'X-Event-Type': 'test',
            'X-Platform-Name': settings.ECOMMERCE_PLATFORM_NAME,
        }
        
        # Send test request
        response = requests.post(
            settings.ECOMMERCE_WEBHOOK_URL,
            json=test_payload,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return {'success': True, 'response': response.json()}
        else:
            return {'success': False, 'error': f'HTTP {response.status_code}: {response.text}'}
    
    except Exception as e:
        return {'success': False, 'error': str(e)}


@user_passes_test(lambda u: u.is_staff)
def sync_all_orders(request):
    """Manually sync all orders to delivery system"""
    try:
        from listings.models import Order
        from listings.webhooks import send_order_webhook
        
        orders = Order.objects.all()
        synced = 0
        
        for order in orders:
            send_order_webhook(order, 'order_created')
            synced += 1
        
        messages.success(request, f'Successfully queued {synced} orders for sync')
    
    except Exception as e:
        messages.error(request, f'Sync failed: {str(e)}')
    
    return redirect('admin:configure_webhooks')