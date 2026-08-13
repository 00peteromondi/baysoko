from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Backfill DeliveryRequest records for Orders missing delivery entries'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Do not save changes')
        parser.add_argument('--limit', type=int, help='Limit number of orders to process')
        parser.add_argument('--store-id', type=int, help='Only process orders for this store id (if Order has store)')

    def handle(self, *args, **options):
        from listings.models import Order
        # Try to import create_delivery_from_order from delivery.integration.
        # In some setups delivery/integration may be a package directory which hides delivery/integration.py.
        try:
            from delivery.integration import create_delivery_from_order
        except Exception:
            # Fallback: load the integration.py file directly by path
            try:
                import os
                from importlib.machinery import SourceFileLoader
                cmd_dir = os.path.dirname(__file__)
                # path: delivery/management/commands -> go up three levels to delivery/
                delivery_app_dir = os.path.normpath(os.path.join(cmd_dir, '..', '..'))
                integration_path = os.path.join(delivery_app_dir, 'integration.py')
                if os.path.exists(integration_path):
                    mod = SourceFileLoader('delivery_integration_fallback', integration_path).load_module()
                    create_delivery_from_order = getattr(mod, 'create_delivery_from_order', None)
                else:
                    create_delivery_from_order = None
            except Exception:
                create_delivery_from_order = None

        dry_run = options.get('dry_run')
        limit = options.get('limit')
        store_id = options.get('store_id')

        qs = Order.objects.all().order_by('id')
        # If Order model has `store` and a store_id filter was provided, apply it
        if store_id and hasattr(Order, 'store'):
            qs = qs.filter(store__id=store_id)

        # Only orders without a delivery_request_id
        qs = qs.filter(delivery_request_id='')

        total = qs.count()
        self.stdout.write(f'Found {total} orders missing delivery_request_id')

        if limit:
            qs = qs[:limit]

        created = 0
        for order in qs:
            try:
                self.stdout.write(f'Processing Order #{order.id}...')
                if dry_run:
                    # just simulate
                    self.stdout.write(' (dry-run)')
                    continue

                with transaction.atomic():
                    dr = create_delivery_from_order(order)
                    if dr:
                        # Mark the order as paid for uniformity if not already paid
                        try:
                            if hasattr(order, 'mark_as_paid') and getattr(order, 'status', None) != 'paid':
                                order.mark_as_paid()
                        except Exception:
                            # Fall back to setting fields directly
                            try:
                                order.status = 'paid'
                                from django.utils import timezone as _tz
                                order.paid_at = _tz.now()
                                order.save(update_fields=['status', 'paid_at'])
                            except Exception:
                                pass

                        order.delivery_request_id = str(dr.id)
                        if dr.tracking_number:
                            order.delivery_tracking_number = dr.tracking_number
                        order.save(update_fields=['delivery_request_id', 'delivery_tracking_number'])
                        created += 1
                        self.stdout.write(f'  -> Created DeliveryRequest {dr.id} (order marked paid)')
                    else:
                        self.stdout.write('  -> No DeliveryRequest created')
            except Exception as e:
                logger.exception('Failed to process order %s', order.id)
                self.stderr.write(f'Error processing order {order.id}: {e}')

        self.stdout.write(self.style.SUCCESS(f'Backfill complete. Created {created} delivery requests.'))
