from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime
from storefront.models import WithdrawalRequest

class Command(BaseCommand):
    help = 'Process scheduled withdrawal requests (should run on Thursdays)'

    def handle(self, *args, **options):
        now = timezone.now()
        today_weekday = now.weekday()  # Monday=0 .. Sunday=6
        # Only process on Thursdays (3)
        if today_weekday != 3:
            self.stdout.write('Today is not Thursday; skipping processing')
            return

        pending = WithdrawalRequest.objects.filter(status='scheduled', scheduled_for__lte=now)
        self.stdout.write(f'Processing {pending.count()} withdrawals')
        for w in pending:
            ok = w.process()
            self.stdout.write(f'{w.id}: processed={ok} status={w.status}')
