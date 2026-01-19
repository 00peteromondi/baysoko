# storefront/tasks.py
from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

@shared_task
def check_trial_expirations():
    """Check and handle expired trials"""
    from .models import Subscription, Store
    
    # Find subscriptions with expired trials
    expired_trials = Subscription.objects.filter(
        status='trialing',
        trial_ends_at__lt=timezone.now()
    )
    
    for subscription in expired_trials:
        try:
            # Downgrade subscription
            subscription.status = 'canceled'
            subscription.save()
            
            # Remove premium features from store
            store = subscription.store
            store.is_premium = False
            store.is_featured = False
            store.save()
            
            # Send expiration notification
            send_trial_expired_notification.delay(subscription.id)
            
            logger.info(f"Trial expired for store: {store.name}")
            
        except Exception as e:
            logger.error(f"Error handling expired trial for subscription {subscription.id}: {str(e)}")
    
    # Send trial expiration reminders (2 days before)
    reminder_date = timezone.now() + timedelta(days=2)
    expiring_trials = Subscription.objects.filter(
        status='trialing',
        trial_ends_at__lte=reminder_date,
        trial_ends_at__gt=timezone.now()
    )
    
    for subscription in expiring_trials:
        send_trial_expiration_reminder.delay(subscription.id)
    
    return f"Processed {len(expired_trials)} expired trials, {len(expiring_trials)} reminders sent"

@shared_task
def send_trial_expired_notification(subscription_id):
    """Send notification when trial expires"""
    from .models import Subscription
    
    try:
        subscription = Subscription.objects.get(id=subscription_id)
        store = subscription.store
        user = store.owner
        
        subject = f"Your {subscription.get_plan_display()} Trial Has Ended - {store.name}"
        
        context = {
            'store': store,
            'subscription': subscription,
            'plan_name': subscription.get_plan_display(),
            'user': user,
        }
        
        html_message = render_to_string('storefront/emails/trial_expired.html', context)
        text_message = render_to_string('storefront/emails/trial_expired.txt', context)
        
        send_mail(
            subject=subject,
            message=text_message,
            from_email='noreply@baysoko.com',
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=True,
        )
        
    except Exception as e:
        logger.error(f"Error sending trial expired notification: {str(e)}")

@shared_task
def send_trial_expiration_reminder(subscription_id):
    """Send reminder 2 days before trial expires"""
    from .models import Subscription
    
    try:
        subscription = Subscription.objects.get(id=subscription_id)
        store = subscription.store
        user = store.owner
        
        remaining_days = (subscription.trial_ends_at - timezone.now()).days
        
        subject = f"Your Trial Ends in {remaining_days} Days - {store.name}"
        
        context = {
            'store': store,
            'subscription': subscription,
            'remaining_days': remaining_days,
            'plan_name': subscription.get_plan_display(),
            'user': user,
        }
        
        html_message = render_to_string('storefront/emails/trial_reminder.html', context)
        text_message = render_to_string('storefront/emails/trial_reminder.txt', context)
        
        send_mail(
            subject=subject,
            message=text_message,
            from_email='noreply@baysoko.com',
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=True,
        )
        
    except Exception as e:
        logger.error(f"Error sending trial expiration reminder: {str(e)}")