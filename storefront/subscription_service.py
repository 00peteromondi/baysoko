# storefront/subscription_service.py (updated with strict trial enforcement)
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from django.contrib import messages
from django.shortcuts import redirect
import logging
from .models import Store, Subscription, MpesaPayment
from .mpesa import MpesaGateway
from .models_trial import UserTrial
from django.db import models

logger = logging.getLogger(__name__)

class SubscriptionService:
    """Centralized subscription management service with strict trial enforcement"""
    TRIAL_LIMIT_PER_USER = 1  # Only 1 trial per user
    
    PLAN_DETAILS = {
        'basic': {
            'name': 'Basic',
            'price': 999,
            'period': 'month',
            'features': [
                'Priority listing',
                'Basic analytics',
                'Store customization',
                'Verified badge',
                'Up to 50 products',
                '1 storefront',
                'Email support',
            ],
            'max_products': 50,
            'max_stores': 1,
        },
        'premium': {
            'name': 'Premium',
            'price': 1999,
            'period': 'month',
            'features': [
                'Everything in Basic',
                'Advanced analytics',
                'Bulk product upload',
                'Inventory management',
                'Product bundles',
                'Up to 200 products',
                '3 storefronts',
                'Priority support',
            ],
            'max_products': 200,
            'max_stores': 3,
        },
        'enterprise': {
            'name': 'Enterprise',
            'price': 4999,
            'period': 'month',
            'features': [
                'Everything in Premium',
                'Custom integrations',
                'API access',
                'Unlimited products',
                'Unlimited storefronts',
                'Custom domain',
                'Dedicated support',
                'White-label options',
            ],
            'max_products': None,  # Unlimited
            'max_stores': None,    # Unlimited
        }
    }
    
    @classmethod
    def get_user_eligibility(cls, user, store=None):
        """Check user's trial and subscription eligibility with strict enforcement"""
        # Check if user has EVER had ANY trial (regardless of status)
        ever_had_trial = Subscription.objects.filter(
            store__owner=user,
            trial_ends_at__isnull=False
        ).exists()
        
        # Check if user has ACTIVE trial (currently in trial period)
        active_trial = Subscription.objects.filter(
            store__owner=user,
            status='trialing',
            trial_ends_at__gt=timezone.now()
        ).exists()
        
        # Check if user has EXPIRED trial (trial ended in past)
        expired_trial = Subscription.objects.filter(
            store__owner=user,
            status='trialing',
            trial_ends_at__lt=timezone.now()
        ).exists()
        
        # Check if user has ACTIVE subscription
        active_subscription = None
        if store:
            active_subscription = Subscription.objects.filter(
                store=store,
                status='active'
            ).order_by('-created_at').first()
        else:
            # Check across all user stores
            active_subscription = Subscription.objects.filter(
                store__owner=user,
                status='active'
            ).order_by('-created_at').first()
        
        # User can ONLY start trial if they have NEVER had ANY trial before
        can_start_trial = not ever_had_trial
        
        # User can subscribe if they don't have an active subscription
        can_subscribe = not active_subscription or active_subscription.status != 'active'
        
        # Get trial usage count
        trial_count = Subscription.objects.filter(
            store__owner=user,
            trial_ends_at__isnull=False
        ).count()
        
        return {
            'ever_had_trial': ever_had_trial,
            'active_trial': active_trial,
            'expired_trial': expired_trial,
            'can_start_trial': can_start_trial,
            'can_subscribe': can_subscribe,
            'active_subscription': active_subscription,
            'trial_count': trial_count,
            'trial_limit': 1,  # Only 1 trial per user
        }
    
    @classmethod
    def start_trial(cls, store, plan, phone_number, user):
        """Start a 7-day free trial with strict validation"""
        # First, check eligibility
        eligibility = cls.get_user_eligibility(user)
        
        if not eligibility['can_start_trial']:
            if eligibility['trial_count'] >= 1:
                return False, "You have already used your one free trial. Each user is limited to one trial period."
            return False, "You are not eligible for a free trial."
        
        # Additional safety check: verify user hasn't had any trial
        user_trials = Subscription.objects.filter(
            store__owner=user,
            trial_ends_at__isnull=False
        ).count()
        
        if user_trials >= 1:
            return False, "Trial limit reached. You have already used your free trial."
        
        with transaction.atomic():
            # Create trial subscription
            subscription = Subscription.objects.create(
                store=store,
                plan=plan,
                status='trialing',
                amount=cls.PLAN_DETAILS[plan]['price'],
                trial_ends_at=timezone.now() + timedelta(days=7),
                started_at=timezone.now(),
                mpesa_phone=f"+254{phone_number}",
                metadata={
                    'trial_started': timezone.now().isoformat(),
                    'via_trial': True,
                    'user_id': user.id,
                    'is_first_trial': True,
                    'trial_number': 1,
                }
            )
            
            # Enable premium features for trial
            store.is_premium = True
            store.save()
            
            # Log trial start for audit
            logger.info(f"Trial started for user {user.id} on store {store.id}. Trial count: {user_trials + 1}")
            
            return True, subscription
    
    @classmethod
    def subscribe_immediately(cls, store, plan, phone_number):
        """Subscribe immediately without trial"""
        with transaction.atomic():
            # Check if store already has active subscription
            existing_active = Subscription.objects.filter(
                store=store,
                status='active'
            ).exists()
            
            if existing_active:
                return False, "Store already has an active subscription."
            
            # Create active subscription
            subscription = Subscription.objects.create(
                store=store,
                plan=plan,
                status='active',
                amount=cls.PLAN_DETAILS[plan]['price'],
                started_at=timezone.now(),
                current_period_end=timezone.now() + timedelta(days=30),
                mpesa_phone=f"+254{phone_number}",
                metadata={
                    'subscribed_at': timezone.now().isoformat(),
                    'skipped_trial': True,
                    'bypassed_trial': True,
                }
            )
            
            # Enable premium features
            store.is_premium = True
            store.save()
            
            return True, subscription
    
    @classmethod
    def enforce_trial_expiry(cls):
        """Strict enforcement of trial expiry - disables premium features immediately"""
        expired_trials = Subscription.objects.filter(
            status='trialing',
            trial_ends_at__lt=timezone.now(),
            store__is_premium=True
        ).select_related('store')
        
        for subscription in expired_trials:
            with transaction.atomic():
                # Mark trial as expired in metadata
                subscription.status = 'canceled'
                subscription.cancelled_at = timezone.now()
                subscription.metadata.update({
                    'trial_expired_at': timezone.now().isoformat(),
                    'auto_downgraded': True,
                })
                subscription.save()
                
                # IMMEDIATELY disable premium features
                subscription.store.is_premium = False
                subscription.store.save()
                
                logger.info(f"Trial expired and premium features disabled for store: {subscription.store.name}")
    
    @classmethod
    def enforce_subscription_expiry(cls):
        """Strict enforcement of subscription expiry"""
        expired_subs = Subscription.objects.filter(
            status='active',
            current_period_end__lt=timezone.now()
        ).select_related('store')
        
        for subscription in expired_subs:
            with transaction.atomic():
                subscription.status = 'past_due'
                subscription.metadata.update({
                    'subscription_expired_at': timezone.now().isoformat(),
                    'payment_required': True,
                })
                subscription.save()
                
                # IMMEDIATELY disable premium features for past-due subscriptions
                subscription.store.is_premium = False
                subscription.store.save()
                
                logger.info(f"Subscription expired for store: {subscription.store.name}")
    
    @classmethod
    def can_user_access_premium(cls, user, store):
        """Check if user can access premium features with strict validation"""
        # Check for active subscription
        active_sub = Subscription.objects.filter(
            store=store,
            status='active'
        ).first()
        
        if active_sub:
            return True
        
        # Check for active trial
        active_trial = Subscription.objects.filter(
            store=store,
            status='trialing',
            trial_ends_at__gt=timezone.now()
        ).first()
        
        if active_trial:
            return True
        
        return False
    
    @classmethod
    def validate_subscription_access(cls, user, store, feature_name):
        """Validate subscription access for specific features"""
        # Get current subscription
        subscription = Subscription.objects.filter(
            store=store
        ).order_by('-created_at').first()
        
        if not subscription:
            return False, "No subscription found"
        
        # Check if subscription is valid
        if subscription.status == 'active':
            return True, "Access granted"
        
        elif subscription.status == 'trialing':
            if subscription.trial_ends_at and timezone.now() < subscription.trial_ends_at:
                return True, "Access granted during trial"
            else:
                # Trial expired - immediate denial
                return False, "Trial period has ended. Please subscribe to continue."
        
        elif subscription.status in ['past_due', 'canceled']:
            return False, "Subscription is not active. Please renew to access premium features."
        
        return False, "Access denied"
    
    @classmethod
    def get_subscription_summary(cls, user):
        """Get comprehensive subscription summary for user"""
        user_stores = Store.objects.filter(owner=user)
        
        summary = {
            'total_stores': user_stores.count(),
            'premium_stores': 0,
            'trial_stores': 0,
            'active_subscriptions': 0,
            'expired_trials': 0,
            'total_revenue_potential': 0,
            'trial_usage': {},
        }
        
        for store in user_stores:
            subscription = Subscription.objects.filter(
                store=store
            ).order_by('-created_at').first()
            
            if subscription:
                if subscription.status == 'active':
                    summary['active_subscriptions'] += 1
                    summary['premium_stores'] += 1
                    summary['total_revenue_potential'] += subscription.amount
                
                elif subscription.status == 'trialing':
                    if subscription.trial_ends_at and timezone.now() < subscription.trial_ends_at:
                        summary['trial_stores'] += 1
                    else:
                        summary['expired_trials'] += 1
                
                # Track trial usage
                if subscription.trial_ends_at:
                    store_key = f"{store.name} ({store.slug})"
                    summary['trial_usage'][store_key] = {
                        'started': subscription.created_at,
                        'ended': subscription.trial_ends_at,
                        'status': subscription.status,
                    }
        
        return summary

    @classmethod
    def change_plan(cls, store, new_plan):
        """Change subscription plan with immediate effect"""
        subscription = Subscription.objects.filter(
            store=store,
            status__in=['active', 'trialing']
        ).order_by('-created_at').first()
        
        if not subscription:
            return False, "No active subscription found to change plan."
        
        with transaction.atomic():
            # Update plan details
            subscription.plan = new_plan
            subscription.amount = cls.PLAN_DETAILS[new_plan]['price']
            subscription.metadata.update({
                'plan_changed_at': timezone.now().isoformat(),
                'new_plan': new_plan,
            })
            subscription.save()
            
            logger.info(f"Subscription plan changed to {new_plan} for store: {store.name}")
            
            return True, subscription
            
    @classmethod
    def get_user_trial_status(cls, user):
        """Get detailed trial status for user"""
        from .models import Subscription
        
        # Get trial summary
        trial_summary = UserTrial.get_user_trial_summary(user)
        
        # Get all user subscriptions with trials
        trial_subscriptions = Subscription.objects.filter(
            store__owner=user,
            trial_ends_at__isnull=False
        ).order_by('-created_at')
        
        # Check if any trial is currently active
        active_trial = None
        for sub in trial_subscriptions:
            if sub.status == 'trialing' and sub.trial_ends_at and sub.trial_ends_at > timezone.now():
                active_trial = sub
                break
        
        # Calculate days until next eligible trial (if any)
        next_trial_eligible = None
        if trial_summary['total_trials'] > 0:
            last_trial = trial_subscriptions.first()
            if last_trial and last_trial.trial_ends_at:
                # User can only have one trial, so no next trial
                next_trial_eligible = None
        
        return {
            'summary': trial_summary,
            'active_trial': active_trial,
            'trial_subscriptions': list(trial_subscriptions.values(
                'id', 'plan', 'status', 'trial_ends_at', 'created_at', 'store__name'
            )),
            'next_trial_eligible': next_trial_eligible,
            'can_start_trial': trial_summary['remaining_trials'] > 0,
            'trial_limit': cls.TRIAL_LIMIT_PER_USER,
            'trial_count': trial_summary['total_trials'],
        }
    
    @classmethod
    def validate_trial_eligibility(cls, user):
        """Validate if user can start a trial"""
        trial_status = cls.get_user_trial_status(user)
        
        # Check if user has exceeded trial limit
        if trial_status['summary']['has_exceeded_limit']:
            return False, {
                'code': 'TRIAL_LIMIT_EXCEEDED',
                'message': f'You have already used your {cls.TRIAL_LIMIT_PER_USER} free trial(s).',
                'details': {
                    'trial_count': trial_status['trial_count'],
                    'trial_limit': cls.TRIAL_LIMIT_PER_USER,
                    'remaining': 0,
                }
            }
        
        # Check if user has an active trial
        if trial_status['active_trial']:
            return False, {
                'code': 'ACTIVE_TRIAL_EXISTS',
                'message': 'You already have an active trial.',
                'details': {
                    'trial_end_date': trial_status['active_trial'].trial_ends_at,
                    'store': trial_status['active_trial'].store.name,
                }
            }
        
        # Check if user has remaining trials
        if trial_status['summary']['remaining_trials'] <= 0:
            return False, {
                'code': 'NO_TRIALS_REMAINING',
                'message': 'No trials remaining.',
                'details': {
                    'trial_count': trial_status['trial_count'],
                    'trial_limit': cls.TRIAL_LIMIT_PER_USER,
                }
            }
        
        return True, {
            'code': 'ELIGIBLE',
            'message': 'User is eligible for trial.',
            'details': {
                'remaining_trials': trial_status['summary']['remaining_trials'],
                'trial_number': trial_status['trial_count'] + 1,
            }
        }
    
    @classmethod
    def start_trial_with_tracking(cls, store, plan, phone_number, user):
        """Start a trial with comprehensive tracking"""
        # Validate trial eligibility
        eligible, eligibility_data = cls.validate_trial_eligibility(user)
        
        if not eligible:
            return False, eligibility_data['message']
        
        with transaction.atomic():
            # Create subscription with trial
            subscription = Subscription.objects.create(
                store=store,
                plan=plan,
                status='trialing',
                amount=cls.PLAN_DETAILS[plan]['price'],
                trial_ends_at=timezone.now() + timedelta(days=7),
                started_at=timezone.now(),
                mpesa_phone=f"+254{phone_number}",
                trial_number=eligibility_data['details']['trial_number'],
                metadata={
                    'trial_started': timezone.now().isoformat(),
                    'via_trial': True,
                    'user_id': user.id,
                    'trial_number': eligibility_data['details']['trial_number'],
                    'trial_limit': cls.TRIAL_LIMIT_PER_USER,
                    'remaining_trials_before': eligibility_data['details']['remaining_trials'],
                }
            )
            
            # Enable premium features
            store.is_premium = True
            store.save()
            
            # Record trial in UserTrial model
            trial_record = UserTrial.record_trial_start(
                user=user,
                store=store,
                subscription=subscription
            )
            
            # Log trial start
            logger.info(
                f"Trial #{trial_record.trial_number} started for user {user.id} "
                f"on store {store.id}. Remaining trials: {eligibility_data['details']['remaining_trials'] - 1}"
            )
            
            return True, {
                'subscription': subscription,
                'trial_record': trial_record,
                'trial_number': trial_record.trial_number,
                'remaining_trials': eligibility_data['details']['remaining_trials'] - 1,
            }
    
    @classmethod
    def end_trial_with_tracking(cls, subscription, reason='ended'):
        """End a trial with comprehensive tracking"""
        with transaction.atomic():
            # Update subscription
            subscription.status = 'canceled'
            subscription.cancelled_at = timezone.now()
            subscription.metadata.update({
                'trial_ended_at': timezone.now().isoformat(),
                'trial_end_reason': reason,
                'auto_downgraded': True,
            })
            subscription.save()
            
            # Disable premium features
            subscription.store.is_premium = False
            subscription.store.save()
            
            # Record trial end
            trial_record = UserTrial.record_trial_end(subscription, reason)
            
            # Log trial end
            logger.info(
                f"Trial #{subscription.trial_number} ended for user {subscription.store.owner.id} "
                f"on store {subscription.store.id}. Reason: {reason}"
            )
            
            return True, {
                'subscription': subscription,
                'trial_record': trial_record,
            }
    
    @classmethod
    def convert_trial_to_paid(cls, subscription, phone_number):
        """Convert trial to paid subscription with tracking"""
        with transaction.atomic():
            # Record trial conversion
            trial_record = UserTrial.record_trial_end(subscription, 'converted')
            
            # Update subscription to active
            subscription.status = 'active'
            subscription.cancelled_at = None
            subscription.current_period_end = timezone.now() + timedelta(days=30)
            subscription.metadata.update({
                'trial_converted_at': timezone.now().isoformat(),
                'converted_from_trial': True,
                'trial_number': subscription.trial_number,
            })
            subscription.save()
            
            # Keep premium features enabled
            subscription.store.is_premium = True
            subscription.store.save()
            
            # Record conversion in trial
            if trial_record:
                trial_record.conversion_attempts += 1
                trial_record.save()
            
            # Log conversion
            logger.info(
                f"Trial #{subscription.trial_number} converted to paid for user {subscription.store.owner.id}"
            )
            
            return True, subscription
    
    @classmethod
    def get_trial_usage_analytics(cls, user=None):
        """Get trial usage analytics for admin or user"""
        from django.db.models import Count, Avg, Max, Min
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        if user:
            # User-specific analytics
            user_trials = UserTrial.objects.filter(user=user)
            
            analytics = {
                'user': {
                    'email': user.email,
                    'id': user.id,
                    'date_joined': user.date_joined,
                },
                'trial_summary': UserTrial.get_user_trial_summary(user),
                'conversion_rate': 0,
                'average_trial_days': 0,
                'preferred_plan': None,
            }
            
            if user_trials.exists():
                # Calculate conversion rate
                total_trials = user_trials.count()
                converted_trials = user_trials.filter(status='converted').count()
                analytics['conversion_rate'] = (converted_trials / total_trials) * 100 if total_trials > 0 else 0
                
                # Calculate average trial days
                ended_trials = user_trials.exclude(ended_at__isnull=True)
                if ended_trials.exists():
                    avg_days = ended_trials.aggregate(Avg('days_used'))['days_used__avg']
                    analytics['average_trial_days'] = round(avg_days, 1)
                
                # Find preferred plan
                from .models import Subscription
                subscriptions = Subscription.objects.filter(
                    store__owner=user,
                    trial_ends_at__isnull=False
                )
                if subscriptions.exists():
                    plan_counts = subscriptions.values('plan').annotate(count=Count('id')).order_by('-count')
                    if plan_counts:
                        analytics['preferred_plan'] = plan_counts[0]['plan']
            
            return analytics
        
        else:
            # Admin/global analytics
            total_users = User.objects.count()
            users_with_trials = User.objects.filter(trials__isnull=False).distinct().count()
            
            trial_stats = UserTrial.objects.aggregate(
                total_trials=Count('id'),
                active_trials=Count('id', filter=models.Q(status='active')),
                converted_trials=Count('id', filter=models.Q(status='converted')),
                avg_days_used=Avg('days_used'),
                max_trials_per_user=Max('trial_number'),
            )
            
            # Trial conversion rate
            conversion_rate = (trial_stats['converted_trials'] / trial_stats['total_trials'] * 100) if trial_stats['total_trials'] > 0 else 0
            
            # Users exceeding trial limit
            from django.db.models import Count
            users_exceeding_limit = User.objects.annotate(
                trial_count=Count('trials')
            ).filter(
                trial_count__gt=cls.TRIAL_LIMIT_PER_USER
            ).count()
            
            return {
                'total_users': total_users,
                'users_with_trials': users_with_trials,
                'users_without_trials': total_users - users_with_trials,
                'trial_stats': trial_stats,
                'conversion_rate': round(conversion_rate, 2),
                'users_exceeding_limit': users_exceeding_limit,
                'trial_limit': cls.TRIAL_LIMIT_PER_USER,
                'trial_abuse_risk': (users_exceeding_limit / total_users * 100) if total_users > 0 else 0,
            }
    
    @classmethod
    def enforce_trial_limits_daily(cls):
        """Daily cron job to enforce trial limits"""
        from .models import Subscription
        
        # Find users who might be trying to abuse trials
        from django.db.models import Count
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        # Get users with multiple trials across different stores
        potential_abusers = User.objects.annotate(
            trial_count=Count('stores__subscriptions', filter=models.Q(
                stores__subscriptions__trial_ends_at__isnull=False
            ))
        ).filter(
            trial_count__gt=cls.TRIAL_LIMIT_PER_USER
        )
        
        for user in potential_abusers:
            logger.warning(
                f"Potential trial abuse detected: User {user.id} has {user.trial_count} trials "
                f"(limit: {cls.TRIAL_LIMIT_PER_USER})"
            )
            
            # Flag user for review
            user.metadata = user.metadata or {}
            user.metadata.update({
                'trial_abuse_warning': {
                    'detected_at': timezone.now().isoformat(),
                    'trial_count': user.trial_count,
                    'limit': cls.TRIAL_LIMIT_PER_USER,
                    'action': 'flagged_for_review',
                }
            })
            user.save()

    @classmethod
    def change_plan(cls, subscription, new_plan):
        """Change subscription plan with immediate effect"""
        # Validate new plan
        if new_plan not in cls.PLAN_DETAILS:
            return False, "Invalid plan selected."
        
        # Check if subscription is in a state that allows plan changes
        if subscription.status not in ['active', 'trialing']:
            return False, "Only active or trialing subscriptions can change plan."
        
        with transaction.atomic():
            # Update plan details
            old_plan = subscription.plan
            subscription.plan = new_plan
            subscription.amount = cls.PLAN_DETAILS[new_plan]['price']
            subscription.metadata = subscription.metadata or {}
            subscription.metadata.update({
                'plan_changed_at': timezone.now().isoformat(),
                'old_plan': old_plan,
                'new_plan': new_plan,
            })
            subscription.save()
            
            logger.info(f"Subscription plan changed from {old_plan} to {new_plan} for store: {subscription.store.name}")
            
            return True, f"Plan successfully changed from {old_plan.capitalize()} to {new_plan.capitalize()}"