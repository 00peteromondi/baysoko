# storefront/management/commands/check_subscriptions.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from storefront.subscription_service import SubscriptionService
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Check and update subscription statuses'

    def handle(self, *args, **options):
        self.stdout.write('Checking subscription statuses...')
        
        # Check for expired trials
        SubscriptionService.check_trial_expiry()
        
        # Check for expired subscriptions
        SubscriptionService.check_subscription_expiry()
        
        self.stdout.write(self.style.SUCCESS('Successfully checked subscriptions'))