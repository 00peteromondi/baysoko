from django.core.management.base import BaseCommand
from django.conf import settings
import os

try:
    import cloudinary.uploader
except Exception:
    cloudinary = None


class Command(BaseCommand):
    help = "Upload files from MEDIA_ROOT subfolders to Cloudinary using the same relative public_id (no DB access)."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show what would be uploaded')
        parser.add_argument('--dirs', type=str, default='profile_pics,chat_attachments,cover_photos',
                            help='Comma-separated media subfolders to upload (relative to MEDIA_ROOT)')
        parser.add_argument('--limit', type=int, default=0, help='Limit number of files uploaded per run (0 = all)')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        dirs = [d.strip() for d in options['dirs'].split(',') if d.strip()]
        limit = options['limit']

        if not cloudinary:
            self.stderr.write(self.style.ERROR('cloudinary.uploader not available. Install and configure cloudinary.'))
            return

        media_root = getattr(settings, 'MEDIA_ROOT', None)
        if not media_root:
            self.stderr.write(self.style.ERROR('MEDIA_ROOT not configured; cannot proceed.'))
            return

        files_to_process = []
        for sub in dirs:
            base = os.path.join(media_root, sub)
            if not os.path.exists(base):
                self.stdout.write(self.style.WARNING(f'Skipping missing folder: {base}'))
                continue
            for root, _, files in os.walk(base):
                for fn in files:
                    # ignore hidden files
                    if fn.startswith('.'):
                        continue
                    full = os.path.join(root, fn)
                    rel = os.path.relpath(full, media_root).replace('\\', '/')
                    files_to_process.append((full, rel))

        total = len(files_to_process)
        if limit > 0:
            files_to_process = files_to_process[:limit]

        self.stdout.write(f'Found {total} files across {len(dirs)} folders; processing {len(files_to_process)}')

        for idx, (full, rel) in enumerate(files_to_process, start=1):
            self.stdout.write(f'[{idx}/{len(files_to_process)}] {rel}')
            if dry_run:
                continue
            try:
                # Upload preserving the relative path as public_id so existing URLs keep working
                public_id = rel.lstrip('/')
                # determine resource type by extension
                ext = os.path.splitext(full)[1].lower()
                rtype = 'image' if ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp') else 'auto'
                res = cloudinary.uploader.upload(full, public_id=public_id, resource_type=rtype, overwrite=False)
                pid = res.get('public_id')
                url = res.get('secure_url')
                self.stdout.write(self.style.SUCCESS(f'  uploaded -> public_id={pid} url={url}'))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'  upload failed: {e}'))

        self.stdout.write(self.style.SUCCESS('Done'))
