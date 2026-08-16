from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Count

from listings.models import Order


class Command(BaseCommand):
    help = (
        "Find orders with zero items and a zero total — the artifact of a "
        "since-fixed bug where a duplicate/re-submitted checkout could "
        "create an empty order. Reports them by default; pass --delete to "
        "actually remove them (their Payment/Escrow records are removed "
        "automatically via cascade)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete',
            action='store_true',
            help='Delete the broken orders found. Without this flag, only reports them.',
        )

    def handle(self, *args, **options):
        broken = (
            Order.objects.annotate(item_count=Count('order_items'))
            .filter(item_count=0, total_price__in=[0, Decimal('0.00')])
        )

        count = broken.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS('No broken (0-item, 0-total) orders found.'))
            return

        self.stdout.write(self.style.WARNING(f'Found {count} broken order(s):'))
        for order in broken.order_by('-created_at')[:200]:
            self.stdout.write(
                f'  Order #{order.id} — user={order.user_id} — status={order.status} — '
                f'created={order.created_at:%Y-%m-%d %H:%M}'
            )
        if count > 200:
            self.stdout.write(f'  ... and {count - 200} more')

        if options['delete']:
            deleted_count, _ = broken.delete()
            self.stdout.write(self.style.SUCCESS(f'Deleted {count} broken order(s).'))
        else:
            self.stdout.write(self.style.NOTICE('Dry run only — re-run with --delete to remove these.'))
