"""
Django management command for scheduled order synchronization
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import logging

from delivery.integration.models import EcommercePlatform
from delivery.integration.sync import OrderSyncService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Synchronize orders from e-commerce platforms'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--platform',
            type=str,
            help='Platform ID or name to sync (default: all active platforms)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force sync even if recently synced'
        )
        parser.add_argument(
            '--sync-type',
            type=str,
            default='scheduled',
            choices=['scheduled', 'manual', 'webhook'],
            help='Type of sync operation'
        )
    
    def handle(self, *args, **options):
        platform_filter = options['platform']
        force = options['force']
        sync_type = options['sync_type']
        
        # Get platforms to sync
        if platform_filter:
            try:
                if platform_filter.isdigit():
                    platforms = EcommercePlatform.objects.filter(
                        id=int(platform_filter),
                        is_active=True,
                        sync_enabled=True
                    )
                else:
                    platforms = EcommercePlatform.objects.filter(
                        name__icontains=platform_filter,
                        is_active=True,
                        sync_enabled=True
                    )
            except Exception as e:
                self.stderr.write(f"Error finding platform: {str(e)}")
                return
        else:
            platforms = EcommercePlatform.objects.filter(
                is_active=True,
                sync_enabled=True
            )
        
        if not platforms.exists():
            self.stdout.write("No active platforms to sync")
            return
        
        self.stdout.write(f"Starting sync for {platforms.count()} platform(s)")
        
        # Sync each platform
        for platform in platforms:
            try:
                # Check if platform needs sync
                if not force and platform.last_sync:
                    time_since_sync = timezone.now() - platform.last_sync
                    if time_since_sync < timedelta(minutes=platform.sync_interval):
                        self.stdout.write(
                            f"Skipping {platform.name}: "
                            f"last sync was {time_since_sync.seconds // 60} minutes ago"
                        )
                        continue
                
                self.stdout.write(f"Syncing {platform.name}...")
                
                # Create sync service
                service = OrderSyncService(platform)
                result = service.sync_orders(sync_type=sync_type, force=force)
                
                if result['success']:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ {platform.name}: {result['synced']} orders synced, "
                            f"{result['failed']} failed"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f"✗ {platform.name}: {result.get('error', 'Unknown error')}"
                        )
                    )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ {platform.name}: {str(e)}")
                )
                logger.error(f"Failed to sync platform {platform.name}: {str(e)}")
        
        self.stdout.write(self.style.SUCCESS("Sync completed"))