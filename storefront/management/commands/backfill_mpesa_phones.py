from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from storefront.models import MpesaPayment
from storefront.mpesa import MpesaGateway


class Command(BaseCommand):
    help = 'Backfill/normalize MpesaPayment.phone_number into canonical 2547XXXXXXXX format. Dry-run by default.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Apply changes to DB instead of dry-run')
        parser.add_argument('--limit', type=int, default=0, help='Limit number of rows to process (0 = all)')

    def handle(self, *args, **options):
        apply_changes = options.get('apply')
        limit = options.get('limit') or None

        payments = MpesaPayment.objects.all().order_by('id')
        if limit:
            payments = payments[:limit]

        total = payments.count()
        self.stdout.write(f'Found {total} MpesaPayment rows to inspect')

        mg = MpesaGateway()
        to_update = []
        failures = []

        for p in payments:
            old = (p.phone_number or '').strip()
            try:
                new = mg._normalize_phone(old)
                if new != old:
                    to_update.append((p.id, old, new))
            except Exception as e:
                failures.append((p.id, old, str(e)))

        self.stdout.write(f'Will update {len(to_update)} rows; {len(failures)} failures')

        if failures:
            self.stdout.write('Sample failures:')
            for fid, val, err in failures[:10]:
                self.stdout.write(f'  id={fid} value={val!r} error={err}')

        if not apply_changes:
            self.stdout.write('Dry-run complete. Re-run with --apply to persist changes.')
            return

        # Apply updates transactionally
        with transaction.atomic():
            for _id, old, new in to_update:
                MpesaPayment.objects.filter(id=_id).update(phone_number=new, updated_at=timezone.now())

        self.stdout.write(f'Applied {len(to_update)} updates.')
