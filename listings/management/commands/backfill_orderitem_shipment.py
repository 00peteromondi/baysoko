from django.core.management.base import BaseCommand
from listings.models import Order, OrderItem
from django.db import transaction

class Command(BaseCommand):
    help = 'Backfill per-item shipment state for old orders and update order status.'

    def handle(self, *args, **options):
        updated_orders = 0
        with transaction.atomic():
            for order in Order.objects.all():
                items = order.order_items.all()
                # Set shipped=False for all items if not set
                for item in items:
                    if item.shipped is None:
                        item.shipped = False
                        item.save()
                # Update order status if all shipped
                if items and all(item.shipped for item in items):
                    if order.status not in ['delivered', 'cancelled', 'disputed']:
                        order.status = 'shipped'
                        order.save()
                        updated_orders += 1
                elif any(item.shipped for item in items):
                    if order.status not in ['delivered', 'cancelled', 'disputed']:
                        order.status = 'partially_shipped'
                        order.save()
                        updated_orders += 1
        self.stdout.write(self.style.SUCCESS(f'Backfill complete. Updated {updated_orders} orders.'))
