from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files.storage import default_storage
from django.db import transaction
import os

try:
    import cloudinary.uploader
except Exception:
    cloudinary = None


class Command(BaseCommand):
    help = "Migrate existing Store.logo and Store.cover_image files from local MEDIA_ROOT to Cloudinary (when configured)."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show what would be uploaded without changing DB')
        parser.add_argument('--limit', type=int, default=0, help='Limit number of stores to process (0 = all)')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']

        if not cloudinary:
            self.stderr.write(self.style.ERROR('cloudinary.uploader not available. Install and configure cloudinary.'))
            return

        if not getattr(settings, 'CLOUDINARY_CLOUD_NAME', ''):
            self.stderr.write(self.style.ERROR('CLOUDINARY_CLOUD_NAME not set in settings; aborting.'))
            return

        from storefront.models import Store

        qs = Store.objects.exclude(logo='').exclude(logo__isnull=True) | Store.objects.exclude(cover_image='').exclude(cover_image__isnull=True)
        qs = qs.distinct().order_by('pk')
        if limit > 0:
            qs = qs[:limit]

        total = qs.count()
        self.stdout.write(f'Found {total} stores to inspect')

        for idx, store in enumerate(qs, start=1):
            self.stdout.write(f'[{idx}/{total}] Processing Store id={store.pk} name={store.name}')
            for field_name, folder in (('logo', 'baysoko/stores/logos'), ('cover_image', 'baysoko/stores/covers')):
                val = getattr(store, field_name)
                if not val:
                    continue

                # If the stored value already looks like a cloudinary URL/public id, skip
                try:
                    url = val.url
                except Exception:
                    url = str(val)

                if url and (url.startswith('http') and 'res.cloudinary.com' in url or (not url.startswith(settings.MEDIA_URL) and not url.startswith('/media/'))):
                    self.stdout.write(self.style.NOTICE(f'  {field_name}: already cloud-hosted (skipping)'))
                    continue

                # Attempt to find the local file path
                # val.name is usually the relative path inside MEDIA_ROOT
                rel_name = getattr(val, 'name', None) or str(val)
                local_path = os.path.join(settings.MEDIA_ROOT, rel_name.lstrip('/'))

                if not os.path.exists(local_path):
                    self.stdout.write(self.style.WARNING(f'  {field_name}: local file not found at {local_path} (skipping)'))
                    continue

                self.stdout.write(f'  {field_name}: will upload {local_path} -> Cloudinary folder={folder}')

                if dry_run:
                    continue

                # Upload to Cloudinary
                try:
                    res = cloudinary.uploader.upload(local_path, folder=folder)
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f'  {field_name}: upload failed: {e}'))
                    continue

                public_id = res.get('public_id')
                secure_url = res.get('secure_url')

                if not public_id:
                    self.stderr.write(self.style.ERROR(f'  {field_name}: no public_id returned; response: {res}'))
                    continue

                # Save the public_id into the field (CloudinaryField stores public_id)
                try:
                    with transaction.atomic():
                        setattr(store, field_name, public_id)
                        store.save()
                        self.stdout.write(self.style.SUCCESS(f'  {field_name}: uploaded and updated to Cloudinary public_id={public_id} url={secure_url}'))
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f'  {field_name}: failed to save model update: {e}'))

        self.stdout.write(self.style.SUCCESS('Done'))
