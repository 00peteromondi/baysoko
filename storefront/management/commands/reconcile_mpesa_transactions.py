from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Reconcile pending M-Pesa STK transactions by querying Safaricom API'

    def add_arguments(self, parser):
        parser.add_argument('--minutes', type=int, default=2, help='Consider payments older than this many minutes')

    def handle(self, *args, **options):
        minutes = options.get('minutes', 2)
        from storefront.mpesa_webhook import logger as webhook_logger
        from listings.mpesa_utils import mpesa_gateway

        cutoff = timezone.now() - timedelta(minutes=minutes)

        # Reconcile subscription payments
        from storefront.models import MpesaPayment
        subs = MpesaPayment.objects.filter(status='pending', created_at__lte=cutoff)
        self.stdout.write(f"Reconciling {subs.count()} subscription payments...")
        for p in subs:
            try:
                checkout = p.checkout_request_id
                res = mpesa_gateway.check_transaction_status(checkout)
                if not res.get('success'):
                    self.stdout.write(f"No status for {checkout}: {res.get('error')}")
                    continue
                result_code = res.get('result_code')
                if str(result_code) in ['0', ''] or int(result_code) == 0:
                    p.status = 'completed'
                    p.result_code = str(result_code)
                    p.result_description = res.get('result_desc')
                    p.raw_response = res.get('response_data') or p.raw_response
                    p.save()
                    self.stdout.write(f"Marked subscription payment {p.id} completed")
                else:
                    p.status = 'failed'
                    p.result_code = str(result_code)
                    p.result_description = res.get('result_desc')
                    p.raw_response = res.get('response_data') or p.raw_response
                    p.save()
                    self.stdout.write(f"Marked subscription payment {p.id} failed: {result_code}")
            except Exception as e:
                webhook_logger.exception(f"Error reconciling subscription payment {p.id}: {e}")

        # Reconcile order payments
        from listings.models import Payment as OrderPayment
        orders = OrderPayment.objects.filter(status='initiated', mpesa_checkout_request_id__isnull=False, created_at__lte=cutoff)
        self.stdout.write(f"Reconciling {orders.count()} order payments...")
        for op in orders:
            try:
                checkout = op.mpesa_checkout_request_id
                res = mpesa_gateway.check_transaction_status(checkout)
                if not res.get('success'):
                    self.stdout.write(f"No status for {checkout}: {res.get('error')}")
                    continue
                result_code = res.get('result_code')
                if str(result_code) in ['0', ''] or int(result_code) == 0:
                    # extract receipt if available
                    resp = res.get('response_data') or {}
                    items = (resp.get('Body', {}).get('stkCallback', {}).get('CallbackMetadata', {}).get('Item', []))
                    receipt = None
                    for it in items:
                        if it.get('Name') in ('MpesaReceiptNumber', 'ReceiptNumber'):
                            receipt = it.get('Value')
                    op.status = 'completed'
                    op.mpesa_result_code = str(result_code)
                    op.mpesa_result_desc = res.get('result_desc')
                    op.mpesa_callback_data = resp
                    op.save()
                    try:
                        op.mark_as_completed(transaction_id=receipt or f"MPESA-{checkout}")
                    except Exception:
                        op.save()
                    self.stdout.write(f"Marked order payment {op.id} completed")
                else:
                    op.status = 'failed'
                    op.mpesa_result_code = str(result_code)
                    op.mpesa_result_desc = res.get('result_desc')
                    op.mpesa_callback_data = res.get('response_data')
                    op.save()
                    self.stdout.write(f"Marked order payment {op.id} failed: {result_code}")
            except Exception as e:
                webhook_logger.exception(f"Error reconciling order payment {op.id}: {e}")

        self.stdout.write("Reconciliation complete.")
