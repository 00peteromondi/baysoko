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
            
            # STRICT PAYMENT VALIDATION: Only proceed if payment amount matches subscription amount
            subscription = payment.subscription
            if payment.amount != subscription.amount:
                print(f"Payment amount mismatch for subscription {subscription.id}: payment={payment.amount}, subscription={subscription.amount}")
                return JsonResponse({
                    'status': 'error',
                    'message': 'Payment amount does not match subscription amount'
                }, status=400)
            
            # Additional validation: Check if this payment is legitimate
            from .subscription_service import SubscriptionService
            is_valid_payment, validation_message = SubscriptionService.validate_payment_for_activation(payment, subscription)
            
            if not is_valid_payment:
                print(f"Payment validation failed for subscription {subscription.id}: {validation_message}")
                return JsonResponse({
                    'status': 'error',
                    'message': f'Payment validation failed: {validation_message}'
                }, status=400)
            
            # Check if this payment was for activation (subscription not yet active)
            if subscription.status in ['canceled', 'past_due', 'trialing', 'unpaid']:
                # Use the safe activation method - this is the ONLY way to activate subscriptions
                activation_success, activation_message = SubscriptionService.activate_subscription_safely(subscription, payment)
                
                if not activation_success:
                    print(f"Safe activation failed for subscription {subscription.id}: {activation_message}")
                    SubscriptionService.log_activation_attempt(subscription, 'webhook_payment_success', False, activation_message)
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Safe activation failed: {activation_message}'
                    }, status=400)
                
                SubscriptionService.log_activation_attempt(subscription, 'webhook_payment_success', True)
                return JsonResponse({
                    'status': 'success',
                    'message': 'Subscription activated successfully after payment validation'
                })
                
            # Check for pending plan changes that require payment
            elif subscription.metadata and subscription.metadata.get('change_requires_payment'):
                # Apply pending plan change after successful payment
                pending_plan = subscription.metadata.get('pending_plan_change')
                if pending_plan:
                    old_plan = subscription.metadata.get('pending_old_plan', subscription.plan)
                    old_amount = subscription.metadata.get('pending_old_amount', subscription.amount)
                    
                    # Apply the plan change
                    subscription.plan = pending_plan
                    subscription.amount = SubscriptionService.PLAN_DETAILS[pending_plan]['price']
                    subscription.metadata.update({
                        'plan_changed_at': timezone.now().isoformat(),
                        'old_plan': old_plan,
                        'new_plan': pending_plan,
                        'change_type': subscription.metadata.get('pending_change_type', 'upgrade'),
                        'activated_via_payment': True,
                        'payment_reference': checkout_request_id,
                    })
                    
                    # Clear pending change metadata
                    pending_keys = [
                        'pending_plan_change', 'pending_plan_change_at', 'pending_payment_amount',
                        'pending_old_plan', 'pending_old_amount', 'pending_change_type', 'change_requires_payment'
                    ]
                    for key in pending_keys:
                        subscription.metadata.pop(key, None)
                    
                    subscription.save()
                    
                    logger.info(f"Pending plan change applied for subscription {subscription.id}: {old_plan} -> {pending_plan}")
                    return JsonResponse({
                        'status': 'success',
                        'message': f'Plan successfully changed to {pending_plan.capitalize()} after payment confirmation'
                    })
            
            else:
                # This was a payment for an already active subscription (renewal/upgrade)
                # Just update the billing cycle
                subscription.current_period_end = timezone.now() + timedelta(days=30)
                subscription.next_billing_date = timezone.now() + timedelta(days=30)
                subscription.metadata = subscription.metadata or {}
                subscription.metadata['last_payment_successful'] = timezone.now().isoformat()
                subscription.metadata['payment_reference'] = checkout_request_id
                subscription.save()
            
        else:  # Failed payment
            # Update payment status
            payment.status = 'failed'
            payment.result_code = str(result_code)
            payment.result_description = callback_data.get('Body', {}).get('stkCallback', {}).get('ResultDesc', 'Payment failed')
            payment.save()
            
            # Handle failed payment based on subscription state
            subscription = payment.subscription
            
            # If subscription was being activated (was canceled/past_due/trialing), keep it in that state
            # DO NOT activate subscriptions on failed payments
            if subscription.status in ['canceled', 'past_due']:
                # Remove any pending plan changes on failed payment
                metadata = subscription.metadata or {}
                if 'pending_plan_change' in metadata:
                    metadata.pop('pending_plan_change', None)
                    metadata.pop('pending_plan_change_at', None)
                    metadata.pop('pending_payment_amount', None)
                    metadata.pop('pending_change_description', None)
                    subscription.metadata = metadata
                    subscription.save()
                # Subscription remains inactive - user needs to try payment again
                pass
            elif subscription.status == 'trialing':
                # Trial remains active - user can try payment again during trial
                pass
            else:
                # For active subscriptions, mark as past_due if this was a renewal payment
                # Check if payment was near billing date
                if (subscription.current_period_end and 
                    (subscription.current_period_end - timezone.now()).days <= 3):
                    subscription.status = 'past_due'
                    subscription.save()
            
            # Log failed payment
            print(f"Payment failed for subscription {subscription.id}: {payment.result_description}")
        
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