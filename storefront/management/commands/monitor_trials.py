# storefront/management/commands/monitor_trials.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Count
from django.contrib.auth import get_user_model
from storefront.subscription_service import SubscriptionService
from storefront.models_trial import UserTrial
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Monitor trial usage and enforce limits'
    
    def handle(self, *args, **options):
        self.stdout.write('Starting trial monitoring...')
        
        # 1. End expired trials
        SubscriptionService.enforce_trial_expiry()
        
        # 2. Check for trial abuse
        SubscriptionService.enforce_trial_limits_daily()
        
        # 3. Update trial usage stats
        self.update_trial_stats()
        
        # 4. Flag potential abuse cases
        self.flag_potential_abuse()
        
        self.stdout.write(self.style.SUCCESS('Trial monitoring completed'))
    
    def update_trial_stats(self):
        """Update trial usage statistics"""
        User = get_user_model()
        
        # Get users with multiple trials
        users_with_multiple_trials = User.objects.annotate(
            trial_count=Count('trials')
        ).filter(
            trial_count__gt=1
        ).count()
        
        # Get conversion rate
        total_trials = UserTrial.objects.count()
        converted_trials = UserTrial.objects.filter(status='converted').count()
        conversion_rate = (converted_trials / total_trials * 100) if total_trials > 0 else 0
        
        logger.info(
            f"Trial Stats: {total_trials} total trials, "
            f"{converted_trials} converted ({conversion_rate:.1f}%), "
            f"{users_with_multiple_trials} users with multiple trials"
        )
    
    def flag_potential_abuse(self):
        """Flag potential trial abuse"""
        User = get_user_model()
        
        # Find users creating new accounts for trials
        suspicious_users = User.objects.filter(
            date_joined__gte=timezone.now() - timedelta(days=30)
        ).annotate(
            trial_count=Count('trials')
        ).filter(
            trial_count__gte=1
        ).order_by('date_joined')
        
        for user in suspicious_users[:10]:  # Top 10 suspicious
            # Check if user has any paid subscriptions
            has_paid = user.stores.filter(
                subscriptions__status='active',
                subscriptions__trial_ends_at__isnull=True
            ).exists()
            
            if not has_paid:
                logger.warning(
                    f"Suspicious user detected: {user.email} "
                    f"joined {user.date_joined.strftime('%Y-%m-%d')}, "
                    f"has {user.trial_count} trial(s), no paid subscriptions"
                )