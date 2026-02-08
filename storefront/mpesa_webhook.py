from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import timedelta, datetime
import json
from .models import MpesaPayment
import os
from django.utils.timezone import now as tz_now
import logging

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)
MPESA_LOG_PATH = os.path.join('logs', 'mpesa_callbacks.log')

logger = logging.getLogger(__name__)


def _extract_callback_metadata_items(stk_callback):
    items = stk_callback.get('CallbackMetadata', {}).get('Item', []) or []
    out = {}
    for it in items:
        name = it.get('Name') or it.get('name')
        value = it.get('Value') if 'Value' in it else it.get('value')
        if name:
            out[name] = value
    return out


@csrf_exempt
@require_http_methods(["POST"])
def mpesa_callback(request):
    """Handle M-Pesa payment callbacks for subscriptions and orders"""
    try:
        # Persistent debug log for incoming callbacks (raw JSON + timestamp)
        try:
            raw = request.body.decode('utf-8') if isinstance(request.body, (bytes, bytearray)) else str(request.body)
        except Exception:
            raw = '<unreadable body>'
        with open(MPESA_LOG_PATH, 'a', encoding='utf-8') as fh:
            fh.write(f"{tz_now().isoformat()}\t{request.META.get('REMOTE_ADDR', '-')}	{raw}\n")

        callback_data = json.loads(request.body)
        stk = callback_data.get('Body', {}).get('stkCallback', {})
        result_code = stk.get('ResultCode')
        checkout_request_id = stk.get('CheckoutRequestID')

        # Try subscription payments first
        try:
            payment = MpesaPayment.objects.select_related('subscription').get(
                checkout_request_id=checkout_request_id
            )

            # Idempotency: if already completed, ignore
            if payment.status == 'completed':
                logger.info(f"Ignoring duplicate callback for subscription payment {payment.id} (checkout={checkout_request_id})")
                return JsonResponse({'status': 'success', 'message': 'Already processed'})

            # Record raw response
            payment.raw_response = callback_data

            if result_code == 0:  # Successful payment
                payment.status = 'completed'
                payment.result_code = str(result_code)
                payment.result_description = 'Success'

                meta = _extract_callback_metadata_items(stk)
                receipt = meta.get('MpesaReceiptNumber') or meta.get('ReceiptNumber')
                amount = meta.get('Amount')
                if receipt:
                    payment.mpesa_receipt_number = receipt
                if amount:
                    try:
                        payment.amount = float(amount)
                    except Exception:
                        pass

                payment.save()

                # Reuse existing subscription activation flow
                from .subscription_service import SubscriptionService
                subscription = payment.subscription

                # Strict validation: ensure amounts match
                if float(payment.amount) != float(subscription.amount):
                    logger.error(f"Payment amount mismatch for subscription {subscription.id}: payment={payment.amount}, subscription={subscription.amount}")
                    return JsonResponse({'status': 'error', 'message': 'Payment amount does not match subscription amount'}, status=400)

                is_valid_payment, validation_message = SubscriptionService.validate_payment_for_activation(payment, subscription)
                if not is_valid_payment:
                    logger.error(f"Payment validation failed for subscription {subscription.id}: {validation_message}")
                    return JsonResponse({'status': 'error', 'message': f'Payment validation failed: {validation_message}'}, status=400)

                if subscription.status in ['canceled', 'past_due', 'trialing', 'unpaid']:
                    activation_success, activation_message = SubscriptionService.activate_subscription_safely(subscription, payment)
                    if not activation_success:
                        SubscriptionService.log_activation_attempt(subscription, 'webhook_payment_success', False, activation_message)
                        return JsonResponse({'status': 'error', 'message': f'Safe activation failed: {activation_message}'}, status=400)
                    SubscriptionService.log_activation_attempt(subscription, 'webhook_payment_success', True)
                    # send notifications if needed (kept minimal)
                    return JsonResponse({'status': 'success', 'message': 'Subscription activated successfully after payment validation'})

                # Pending plan change handling
                if subscription.metadata and subscription.metadata.get('change_requires_payment'):
                    pending_plan = subscription.metadata.get('pending_plan_change')
                    if pending_plan:
                        subscription.plan = pending_plan
                        subscription.amount = SubscriptionService.PLAN_DETAILS[pending_plan]['price']
                        subscription.metadata.update({
                            'plan_changed_at': timezone.now().isoformat(),
                            'old_plan': subscription.metadata.get('pending_old_plan', subscription.plan),
                            'new_plan': pending_plan,
                            'change_type': subscription.metadata.get('pending_change_type', 'upgrade'),
                            'activated_via_payment': True,
                            'payment_reference': checkout_request_id,
                        })
                        for key in ['pending_plan_change', 'pending_plan_change_at', 'pending_payment_amount', 'pending_old_plan', 'pending_old_amount', 'pending_change_type', 'change_requires_payment']:
                            subscription.metadata.pop(key, None)
                        subscription.save()
                        logger.info(f"Pending plan change applied for subscription {subscription.id}: {pending_plan}")
                        return JsonResponse({'status': 'success', 'message': f'Plan successfully changed to {pending_plan.capitalize()} after payment confirmation'})

                # Renewal: update billing cycle
                subscription.current_period_end = timezone.now() + timedelta(days=30)
                subscription.next_billing_date = timezone.now() + timedelta(days=30)
                subscription.metadata = subscription.metadata or {}
                subscription.metadata['last_payment_successful'] = timezone.now().isoformat()
                subscription.metadata['payment_reference'] = checkout_request_id
                subscription.save()

            else:
                # Failed subscription payment
                payment.status = 'failed'
                payment.result_code = str(result_code)
                payment.result_description = stk.get('ResultDesc', 'Payment failed')
                payment.save()

                subscription = payment.subscription
                # Keep subscription state unchanged on failed activation payments
                if subscription.status in ['canceled', 'past_due']:
                    metadata = subscription.metadata or {}
                    for k in ['pending_plan_change', 'pending_plan_change_at', 'pending_payment_amount', 'pending_change_description']:
                        metadata.pop(k, None)
                    subscription.metadata = metadata
                    subscription.save()
                elif subscription.status == 'trialing':
                    pass
                else:
                    if (subscription.current_period_end and (subscription.current_period_end - timezone.now()).days <= 3):
                        subscription.status = 'past_due'
                        subscription.save()

            return JsonResponse({'status': 'success', 'message': 'Callback processed successfully'})

        except MpesaPayment.DoesNotExist:
            # Not a subscription payment -- try order payment
            from listings.models import Payment as OrderPayment
            try:
                order_payment = OrderPayment.objects.select_related('order').get(mpesa_checkout_request_id=checkout_request_id)

                # Idempotency: if already completed, ignore
                if getattr(order_payment, 'status', None) == 'completed':
                    logger.info(f"Ignoring duplicate callback for order payment {order_payment.id} (checkout={checkout_request_id})")
                    return JsonResponse({'status': 'success', 'message': 'Already processed'})

                # Record raw callback if field exists
                try:
                    order_payment.mpesa_callback_data = callback_data
                except Exception:
                    pass

                if result_code == 0:
                    # successful order payment
                    meta = _extract_callback_metadata_items(stk)
                    receipt = meta.get('MpesaReceiptNumber') or meta.get('ReceiptNumber')
                    amount = meta.get('Amount')
                    if receipt:
                        order_payment.mpesa_receipt_number = receipt
                    if amount:
                        try:
                            order_payment.mpesa_result_code = str(result_code)
                            order_payment.mpesa_result_desc = 'Success'
                        except Exception:
                            pass

                    order_payment.status = 'completed'
                    order_payment.save()

                    # Mark payment as completed which will mark order as paid
                    try:
                        order_payment.mark_as_completed(transaction_id=receipt or f"MPESA-{checkout_request_id}")
                    except Exception:
                        order_payment.save()

                else:
                    # failed order payment
                    order_payment.status = 'failed'
                    order_payment.mpesa_result_code = str(result_code)
                    order_payment.mpesa_result_desc = stk.get('ResultDesc', 'Payment failed')
                    order_payment.save()

                return JsonResponse({'status': 'success', 'message': 'Order callback processed'})

            except OrderPayment.DoesNotExist:
                logger.error(f"No payment record found for CheckoutRequestID={checkout_request_id}")
                return JsonResponse({'status': 'error', 'message': 'Payment record not found'}, status=404)

    except Exception as e:
        # Log the error but return 200 to M-Pesa to avoid retries on malformed payloads
        logger.exception(f"Error processing M-Pesa callback: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)