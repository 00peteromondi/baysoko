# storefront/utils/subscription_states.py
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache

class SubscriptionStateManager:
    """Manage subscription states and eligibility"""
    
    @classmethod
    def get_user_subscription_state(cls, user, store=None):
        """Get comprehensive subscription state for user/store"""
        from ..models import Subscription, Store
        
        state = {
            'has_active_subscription': False,
            'has_valid_trial': False,
            'has_expired_trial': False,
            'has_cancelled_subscription': False,
            'has_past_due': False,
            'can_start_trial': False,
            'can_subscribe': True,
            'can_change_plan': False,
            'needs_renewal': False,
            'current_plan': None,
            'subscription': None,
            'store': store,
        }
        
        # If store is provided, check subscription for that store
        if store:
            subscription = Subscription.objects.filter(
                store=store
            ).order_by('-created_at').first()
            
            if subscription:
                return cls._analyze_subscription(subscription, state)
        
        # Otherwise, check all stores owned by user
        user_stores = user.stores.all()
        active_subscriptions = []
        
        for user_store in user_stores:
            subscription = Subscription.objects.filter(
                store=user_store
            ).order_by('-created_at').first()
            
            if subscription:
                sub_state = cls._analyze_subscription(subscription, state.copy())
                
                if sub_state['has_active_subscription'] or sub_state['has_valid_trial']:
                    active_subscriptions.append(sub_state)
                
                # Track if user has ever had a trial
                if subscription.status == 'trialing' and subscription.trial_ends_at:
                    if timezone.now() > subscription.trial_ends_at:
                        state['has_expired_trial'] = True
        
        # If user has active subscriptions on any store
        if active_subscriptions:
            # Get the most recent active subscription
            latest_sub = active_subscriptions[0]
            state.update(latest_sub)
            
            # User can only start trial if they've never had one
            state['can_start_trial'] = not state['has_expired_trial']
        else:
            # User has no active subscriptions
            state['can_start_trial'] = not state['has_expired_trial']
            state['can_subscribe'] = True
        
        return state
    
    @classmethod
    def _analyze_subscription(cls, subscription, state):
        """Analyze a single subscription"""
        state['subscription'] = subscription
        state['current_plan'] = subscription.plan
        
        now = timezone.now()
        
        # Prefer Subscription.is_active() which treats valid trials as active
        try:
            is_active = subscription.is_active()
        except Exception:
            is_active = subscription.status == 'active'

        if is_active:
            # Active includes valid trials per model logic
            state['has_active_subscription'] = True
            state['can_change_plan'] = True
            state['can_start_trial'] = False

            if subscription.status == 'trialing' and subscription.trial_ends_at and now < subscription.trial_ends_at:
                state['has_valid_trial'] = True

        elif subscription.status == 'trialing':
            # Expired trial
            state['has_expired_trial'] = True
            state['needs_renewal'] = True
            state['can_start_trial'] = False

        elif subscription.status == 'past_due':
            state['has_past_due'] = True
            state['needs_renewal'] = True
            state['can_start_trial'] = False

        elif subscription.status == 'canceled':
            state['has_cancelled_subscription'] = True
            state['needs_renewal'] = True
            state['can_start_trial'] = False
        
        # User cannot start trial if they've ever had one that ended
        if state['has_expired_trial']:
            state['can_start_trial'] = False
        
        return state
    
    @classmethod
    def can_user_start_trial(cls, user):
        """Check if user is eligible for a new trial"""
        from ..models import Subscription
        
        # Check if user has ever had a trial that ended
        expired_trials = Subscription.objects.filter(
            store__owner=user,
            status='trialing',
            trial_ends_at__lt=timezone.now()
        ).exists()
        
        # Check if user has an active trial
        active_trials = Subscription.objects.filter(
            store__owner=user,
            status='trialing',
            trial_ends_at__gt=timezone.now()
        ).exists()
        
        # User can start trial if they've never had an expired trial and don't have active trial
        return not expired_trials and not active_trials
    
    @classmethod
    def get_subscription_action_required(cls, subscription):
        """Get the required action for a subscription"""
        if not subscription:
            return 'subscribe'
        
        now = timezone.now()
        
        try:
            if subscription.is_active():
                return 'manage'
        except Exception:
            if subscription.status == 'active':
                return 'manage'

        if subscription.status == 'trialing':
            if subscription.trial_ends_at and now < subscription.trial_ends_at:
                # Still in trial
                days_left = (subscription.trial_ends_at - now).days
                if days_left <= 2:
                    return 'trial_ending'
                return 'in_trial'
            else:
                return 'trial_expired'
        
        elif subscription.status == 'past_due':
            return 'past_due'
        
        elif subscription.status == 'canceled':
            return 'renew'
        
        return 'subscribe'