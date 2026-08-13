from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
import os

try:
    import cloudinary.uploader
except Exception:
    cloudinary = None


class Command(BaseCommand):
    help = "Migrate common media (users, stores) to Cloudinary when configured."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show what would be uploaded without changing DB')
        parser.add_argument('--limit', type=int, default=0, help='Limit number of items per model (0 = all)')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']

        if not cloudinary:
            self.stderr.write(self.style.ERROR('cloudinary.uploader not available. Install and configure cloudinary.'))
            return

        if not getattr(settings, 'CLOUDINARY_CLOUD_NAME', ''):
            self.stderr.write(self.style.ERROR('CLOUDINARY_CLOUD_NAME not set in settings; aborting.'))
            return

        # Process Users
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
        except Exception:
            User = None

        if User:
            qs = User.objects.exclude(profile_picture='').exclude(profile_picture__isnull=True)
            if limit > 0:
                qs = qs.order_by('pk')[:limit]
            total = qs.count()
            self.stdout.write(f'Found {total} users with profile pictures to inspect')
            for idx, user in enumerate(qs, start=1):
                self.stdout.write(f'[{idx}/{total}] User id={user.pk} username={user.username}')
                val = getattr(user, 'profile_picture', None)
                if not val:
                    continue
                try:
                    url = val.url
                except Exception:
                    url = str(val)

                # Skip if already cloud-hosted
                if url and 'res.cloudinary.com' in url:
                    self.stdout.write(self.style.NOTICE('  profile_picture: already cloud-hosted (skipping)'))
                    continue

                rel_name = getattr(val, 'name', None) or str(val)
                local_path = os.path.join(settings.MEDIA_ROOT, rel_name.lstrip('/'))
                if not os.path.exists(local_path):
                    self.stdout.write(self.style.WARNING(f'  profile_picture: local file not found at {local_path} (skipping)'))
                    continue

                folder = getattr(settings, 'CLOUDINARY_UPLOAD_FOLDER_PROFILES', 'baysoko/profiles')
                self.stdout.write(f'  profile_picture: will upload {local_path} -> Cloudinary folder={folder}')
                if dry_run:
                    continue

                try:
                    res = cloudinary.uploader.upload(local_path, folder=folder)
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f'  profile_picture: upload failed: {e}'))
                    continue

                public_id = res.get('public_id')
                secure_url = res.get('secure_url')
                if not public_id:
                    self.stderr.write(self.style.ERROR(f'  profile_picture: no public_id returned; response: {res}'))
                    continue

                try:
                    with transaction.atomic():
                        # If field is CloudinaryField, store public_id; otherwise store secure_url in profile_picture (best-effort)
                        field_obj = User._meta.get_field('profile_picture')
                        if field_obj.__class__.__name__ == 'CloudinaryField':
                            setattr(user, 'profile_picture', public_id)
                        else:
                            # For ImageField, store the secure url in a new attribute if available, else keep existing
                            setattr(user, 'profile_picture', secure_url)
                        user.save()
                        self.stdout.write(self.style.SUCCESS(f'  profile_picture: uploaded and updated to Cloudinary public_id={public_id} url={secure_url}'))
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f'  profile_picture: failed to save model update: {e}'))

        # Reuse existing storefront helper if available
        try:
            from storefront.management.commands.migrate_store_media import Command as StoreCommand
            self.stdout.write('Invoking storefront.migrate_store_media for stores...')
            store_cmd = StoreCommand()
            # Call its handle with dry_run and limit
            store_cmd.handle(dry_run=dry_run, limit=limit)
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Could not run storefront migration helper: {e}'))

        self.stdout.write(self.style.SUCCESS('Done'))
