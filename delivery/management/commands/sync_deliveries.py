"""
Management command to sync deliveries with e-commerce orders
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from delivery.integration import create_delivery_from_order
from listings.models import Order


class Command(BaseCommand):
    help = 'Sync e-commerce orders with delivery system'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days to look back for orders'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually creating deliveries'
        )
    
    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        start_date = timezone.now() - timezone.timedelta(days=days)
        
        orders = Order.objects.filter(
            created_at__gte=start_date,
            delivery_request_id__isnull=True
        ).exclude(status__in=['cancelled', 'failed'])
        
        self.stdout.write(f"Found {orders.count()} orders without delivery requests")
        
        created_count = 0
        for order in orders:
            if dry_run:
                self.stdout.write(f"[DRY RUN] Would create delivery for order #{order.id}")
            else:
                delivery = create_delivery_from_order(order)
                if delivery:
                    created_count += 1
                    self.stdout.write(f"Created delivery #{delivery.tracking_number} for order #{order.id}")
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created {created_count} delivery requests"
            )
        )