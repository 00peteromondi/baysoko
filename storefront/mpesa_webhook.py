from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import timedelta
import json
from .models import MpesaPayment
import os
from django.utils.timezone import now as tz_now

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)
MPESA_LOG_PATH = os.path.join('logs', 'mpesa_callbacks.log')

@csrf_exempt
@require_http_methods(["POST"])
def mpesa_callback(request):
    """Handle M-Pesa payment callbacks"""
    try:
        # Persistent debug log for incoming callbacks (raw JSON + timestamp)
        try:
            raw = request.body.decode('utf-8') if isinstance(request.body, (bytes, bytearray)) else str(request.body)
        except Exception:
            raw = '<unreadable body>'
        with open(MPESA_LOG_PATH, 'a', encoding='utf-8') as fh:
            fh.write(f"{tz_now().isoformat()}\t{request.META.get('REMOTE_ADDR', '-')}\t{raw}\n")

        # Parse the callback data
        callback_data = json.loads(request.body)
        result_code = callback_data.get('Body', {}).get('stkCallback', {}).get('ResultCode')
        checkout_request_id = callback_data.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID')
        
        # Find the corresponding payment
        payment = MpesaPayment.objects.select_related('subscription').get(
            checkout_request_id=checkout_request_id
        )
        
        if result_code == 0:  # Successful payment
            # Update payment status
            payment.status = 'completed'
            payment.result_code = str(result_code)
            payment.result_description = 'Success'
            payment.save()
            
            # Update subscription
            subscription = payment.subscription
            subscription.status = 'active'
            # Set next billing date (1 month from trial end or now if trial ended)
            if subscription.trial_ends_at and subscription.trial_ends_at > timezone.now():
                subscription.next_billing_date = subscription.trial_ends_at + timedelta(days=30)
            else:
                subscription.next_billing_date = timezone.now() + timedelta(days=30)
            subscription.save()
            
            # Ensure store is marked as premium
            store = subscription.store
            store.is_premium = True
            store.save()
            
        else:  # Failed payment
            # Update payment status
            payment.status = 'failed'
            payment.result_code = str(result_code)
            payment.result_description = callback_data.get('Body', {}).get('stkCallback', {}).get('ResultDesc', 'Payment failed')
            payment.save()
            
            # If this was the first payment (during trial), we might want to handle differently
            subscription = payment.subscription
            if subscription.status == 'trialing':
                # Keep trial active but mark that initial payment failed
                # This allows user to try payment again during trial period
                pass
            else:
                # For regular renewal payments, mark subscription as past_due
                subscription.status = 'past_due'
                subscription.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Callback processed successfully'
        })
        
    except Exception as e:
        # Log the error but return success to M-Pesa (as required by their API)
        print(f"Error processing M-Pesa callback: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)