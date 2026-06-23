# storefront/models_trial.py
from django.db import models
from django.conf import settings
from django.utils import timezone

class UserTrial(models.Model):
    """Track trial usage per user"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='trials'
    )
    store = models.ForeignKey(
        'storefront.Store',
        on_delete=models.CASCADE,
        related_name='trials'
    )
    subscription = models.ForeignKey(
        'storefront.Subscription',
        on_delete=models.CASCADE,
        related_name='trial_records'
    )
    
    # Trial details
    trial_number = models.PositiveIntegerField(default=1)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('ended', 'Ended'),
            ('canceled', 'Canceled'),
            ('converted', 'Converted to Paid'),
        ],
        default='active'
    )
    
    # Usage metrics
    days_used = models.PositiveIntegerField(default=0)
    features_accessed = models.JSONField(default=list, blank=True)
    conversion_attempts = models.PositiveIntegerField(default=0)
    
    # Audit trail
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-started_at']
        unique_together = ['user', 'trial_number']
        verbose_name = 'User Trial'
        verbose_name_plural = 'User Trials'
    
    def __str__(self):
        return f"{self.user.email} - Trial #{self.trial_number} ({self.status})"
    
    @property
    def is_active(self):
        """Check if trial is currently active"""
        if not self.ended_at:
            return True
        return timezone.now() < self.ended_at
    
    @property
    def days_remaining(self):
        """Calculate days remaining in trial"""
        if not self.ended_at:
            return 0
        remaining = (self.ended_at - timezone.now()).days
        return max(0, remaining)
    
    @property
    def progress_percentage(self):
        """Calculate trial progress percentage"""
        if not self.ended_at:
            return 0
        
        total_days = (self.ended_at - self.started_at).days
        days_used = (timezone.now() - self.started_at).days
        
        if total_days == 0:
            return 100
        
        progress = (days_used / total_days) * 100
        return min(100, progress)
    
    @classmethod
    def get_user_trial_summary(cls, user):
        """Get comprehensive trial summary for user"""
        trials = cls.objects.filter(user=user)
        
        if not trials.exists():
            return {
                'total_trials': 0,
                'active_trials': 0,
                'used_trials': 0,
                'trial_limit': settings.TRIAL_LIMIT_PER_USER,
                'remaining_trials': settings.TRIAL_LIMIT_PER_USER,
                'has_exceeded_limit': False,
                'trial_history': [],
            }
        
        active_trials = trials.filter(status='active', ended_at__gt=timezone.now())
        used_trials = trials.exclude(status='active')
        
        summary = {
            'total_trials': trials.count(),
            'active_trials': active_trials.count(),
            'used_trials': used_trials.count(),
            'trial_limit': settings.TRIAL_LIMIT_PER_USER,
            'remaining_trials': max(0, settings.TRIAL_LIMIT_PER_USER - trials.count()),
            'has_exceeded_limit': trials.count() >= settings.TRIAL_LIMIT_PER_USER,
            'trial_history': list(trials.values(
                'trial_number', 'status', 'started_at', 'ended_at', 
                'days_used', 'store__name'
            )),
        }
        
        return summary
    
    @classmethod
    def record_trial_start(cls, user, store, subscription):
        """Record when a user starts a trial"""
        # Get next trial number
        last_trial = cls.objects.filter(user=user).order_by('-trial_number').first()
        trial_number = last_trial.trial_number + 1 if last_trial else 1
        
        # Create trial record
        trial = cls.objects.create(
            user=user,
            store=store,
            subscription=subscription,
            trial_number=trial_number,
            started_at=timezone.now(),
            ended_at=subscription.trial_ends_at,
            status='active',
            features_accessed=['initial_access']
        )
        
        return trial
    
    @classmethod
    def record_trial_end(cls, subscription, reason='ended'):
        """Record when a trial ends"""
        try:
            trial = cls.objects.get(subscription=subscription, status='active')
            trial.ended_at = timezone.now()
            trial.status = reason
            trial.days_used = (trial.ended_at - trial.started_at).days
            
            # Calculate actual days used
            if subscription.trial_ends_at:
                actual_days = min(
                    (timezone.now() - trial.started_at).days,
                    (subscription.trial_ends_at - trial.started_at).days
                )
                trial.days_used = max(0, actual_days)
            
            trial.save()
            return trial
        except cls.DoesNotExist:
            return None
    
    @classmethod
    def record_feature_access(cls, user, feature_name):
        """Record when a user accesses a premium feature during trial"""
        active_trials = cls.objects.filter(
            user=user,
            status='active',
            ended_at__gt=timezone.now()
        )
        
        for trial in active_trials:
            if feature_name not in trial.features_accessed:
                trial.features_accessed.append(feature_name)
                trial.save()