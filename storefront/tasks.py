from celery import shared_task
from django.utils import timezone
from .models import WithdrawalRequest


@shared_task
def process_scheduled_withdrawals():
    """Celery task to process scheduled withdrawals. Typically run once daily.

    It is safe to run daily; WithdrawalRequest.schedule() schedules for Thursday and
    requests will only be processed when their `scheduled_for` is due.
    """
    now = timezone.now()
    # Process only those scheduled for now or earlier
    scheduled = WithdrawalRequest.objects.filter(status='scheduled', scheduled_for__lte=now)
    results = []
    for w in scheduled:
        ok = w.process()
        results.append({'id': w.id, 'ok': ok, 'status': w.status})
    return results
# storefront/tasks.py
from celery import shared_task
from django.utils import timezone
from django.template.loader import render_to_string
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

try:
    from baysoko.utils.email_helpers import render_and_send
except Exception:
    render_and_send = None

try:
    from notifications.utils import NotificationService
except Exception:
    NotificationService = None

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
    
    # Send trial expiration reminders (2 days and 1 day before)
    for days_before in (2, 1):
        reminder_date = timezone.now() + timedelta(days=days_before)
        expiring_trials = Subscription.objects.filter(
            status='trialing',
            trial_ends_at__lte=reminder_date,
            trial_ends_at__gt=timezone.now()
        )
        for subscription in expiring_trials:
            send_trial_expiration_reminder.delay(subscription.id, days_before)
    
    return f"Processed {len(expired_trials)} expired trials, {len(expiring_trials)} reminders sent"

@shared_task
def send_trial_expired_notification(subscription_id):
    """Send notification when trial expires"""
    from .models import Subscription
    from notifications.utils import create_notification
    
    try:
        subscription = Subscription.objects.get(id=subscription_id)
        store = subscription.store
        user = store.owner
        
        # Send internal notification
        create_notification(
            recipient=user,
            notification_type='system',
            title='Trial Period Ended',
            message=f'Your {subscription.get_plan_display()} trial for {store.name} has ended. Upgrade to a paid plan to keep premium features active.',
            related_object_id=subscription.id,
            related_content_type='subscription',
            action_url=f'/dashboard/store/{store.slug}/subscription/plans/',
            action_text='Choose Plan'
        )
        
        subject = f"Your {subscription.get_plan_display()} Trial Has Ended - {store.name}"

        context = {
            'store': store,
            'subscription': subscription,
            'plan_name': subscription.get_plan_display(),
            'user': user,
        }

        # Prefer centralized sender
        recipients = [e for e in [getattr(user, 'email', None)] if e]
        if render_and_send and recipients:
            try:
                render_and_send('storefront/emails/trial_expired.html', 'storefront/emails/trial_expired.txt', context, subject, recipients)
            except Exception:
                logger.exception('Failed to send trial expired email via centralized sender')
        else:
            # Fallback to simple rendering + send_mail if necessary
            try:
                html_message = render_to_string('storefront/emails/trial_expired.html', context)
                text_message = render_to_string('storefront/emails/trial_expired.txt', context)
                from django.core.mail import send_mail
                send_mail(subject=subject, message=text_message, from_email='noreply@baysoko.com', recipient_list=[user.email], html_message=html_message, fail_silently=True)
            except Exception:
                logger.exception('Fallback trial expired email send failed')
        # Send SMS notification where possible
        try:
            if NotificationService:
                phone = getattr(user, 'phone_number', None) or getattr(store, 'phone', None)
                if phone:
                    NotificationService().send_sms(phone, f"Your {subscription.get_plan_display()} trial for {store.name} has ended. Reactivate to regain premium features.")
        except Exception:
            logger.exception('Failed to send trial expired SMS')
        
    except Exception as e:
        logger.error(f"Error sending trial expired notification: {str(e)}")

@shared_task
def send_trial_expiration_reminder(subscription_id, days_before=2):
    """Send reminder `days_before` before trial expires"""
    from .models import Subscription
    from notifications.utils import create_notification

    try:
        subscription = Subscription.objects.get(id=subscription_id)
        store = subscription.store
        user = store.owner

        remaining_days = (subscription.trial_ends_at - timezone.now()).days

        # Send internal notification
        create_notification(
            recipient=user,
            notification_type='system',
            title='Trial Ending Soon',
            message=f'Your {subscription.get_plan_display()} trial for {store.name} ends in {remaining_days} days. Upgrade to keep premium features.',
            related_object_id=subscription.id,
            related_content_type='subscription',
            action_url=f'/dashboard/store/{store.slug}/subscription/plans/',
            action_text='Upgrade Plan'
        )

        subject = f"Your Trial Ends in {remaining_days} Days - {store.name}"

        context = {
            'store': store,
            'subscription': subscription,
            'remaining_days': remaining_days,
            'plan_name': subscription.get_plan_display(),
            'user': user,
        }

        recipients = [e for e in [getattr(user, 'email', None)] if e]
        if render_and_send and recipients:
            try:
                render_and_send('storefront/emails/trial_reminder.html', 'storefront/emails/trial_reminder.txt', context, subject, recipients)
            except Exception:
                logger.exception('Failed to send trial reminder via centralized sender')
        else:
            try:
                html_message = render_to_string('storefront/emails/trial_reminder.html', context)
                text_message = render_to_string('storefront/emails/trial_reminder.txt', context)
                from django.core.mail import send_mail
                send_mail(subject=subject, message=text_message, from_email='noreply@baysoko.com', recipient_list=[user.email], html_message=html_message, fail_silently=True)
            except Exception:
                logger.exception('Fallback trial reminder email send failed')

        # Send SMS where possible
        try:
            if NotificationService:
                phone = getattr(user, 'phone_number', None) or getattr(store, 'phone', None)
                if phone:
                    NotificationService().send_sms(phone, f"Reminder: your {subscription.get_plan_display()} trial for {store.name} ends in {remaining_days} days. Upgrade to keep premium features.")
        except Exception:
            logger.exception('Failed to send trial reminder SMS')

    except Exception as e:
        logger.error(f"Error sending trial expiration reminder: {str(e)}")


    @shared_task
    def check_active_subscription_expirations():
        """Find active subscriptions whose period ended and mark them canceled so
        the existing subscription post_save signal sends emails and in-app notifications.
        This should be scheduled to run once daily via Celery beat.
        """
        from .models import Subscription
        from django.utils import timezone

        now = timezone.now()
        expired = Subscription.objects.filter(status='active', current_period_end__lt=now)
        count = 0
        for sub in expired:
            try:
                sub.status = 'canceled'
                sub.save()
                logger.info('Marked subscription %s for store %s as canceled (period ended)', sub.id, getattr(sub.store, 'name', 'unknown'))
                count += 1
            except Exception:
                logger.exception('Failed to mark expired subscription %s', sub.id)
        return {'expired_marked': count}


    @shared_task
    def send_weekly_reactivation_reminders():
        """Send weekly reminders to users with canceled subscriptions to reactivate.

        This runs weekly via Celery beat. It will respect a metadata flag
        `last_reactivation_reminder` on the Subscription to avoid duplicate weekly messages.
        """
        from .models import Subscription
        from notifications.utils import create_notification
        from django.utils import timezone

        now = timezone.now()
        seven_days_ago = now - timedelta(days=7)

        candidates = Subscription.objects.filter(status='canceled')
        sent = 0
        for sub in candidates:
            try:
                meta = sub.metadata or {}
                last = meta.get('last_reactivation_reminder')
                if last:
                    try:
                        last_dt = timezone.datetime.fromisoformat(last)
                        last_dt = timezone.make_aware(last_dt) if last_dt.tzinfo is None else last_dt
                    except Exception:
                        last_dt = None
                else:
                    last_dt = None

                # Send if never sent or older than 7 days
                if not last_dt or last_dt <= seven_days_ago:
                    user = sub.store.owner
                    # send in-app
                    create_notification(
                        recipient=user,
                        notification_type='system',
                        title='Reactivate Your Subscription',
                        message=f'Your subscription for {sub.store.name} ended. Reactivate now to regain premium features.',
                        related_object_id=sub.id,
                        related_content_type='subscription',
                        action_url=f'/dashboard/store/{sub.store.slug}/subscription/plans/',
                        action_text='Reactivate'
                    )

                    # send email
                    subject = f'Reactivate your subscription for {sub.store.name}'
                    ctx = {'user': user, 'store': sub.store, 'subscription': sub}
                    try:
                        if render_and_send and getattr(user, 'email', None):
                            render_and_send('storefront/emails/reactivation_reminder.html', 'storefront/emails/reactivation_reminder.txt', ctx, subject, [user.email])
                        else:
                            html_message = render_to_string('storefront/emails/reactivation_reminder.html', ctx)
                            text_message = render_to_string('storefront/emails/reactivation_reminder.txt', ctx)
                            from django.core.mail import send_mail
                            send_mail(subject=subject, message=text_message, from_email='noreply@baysoko.com', recipient_list=[user.email], html_message=html_message, fail_silently=True)
                    except Exception:
                        logger.exception('Failed to send reactivation reminder email')

                    # send sms
                    try:
                        if NotificationService:
                            phone = getattr(user, 'phone_number', None)
                            if phone:
                                NotificationService().send_sms(phone, f"Your subscription for {sub.store.name} ended. Reactivate now to regain premium features.")
                    except Exception:
                        logger.exception('Failed to send reactivation reminder SMS')

                    # update metadata
                    meta['last_reactivation_reminder'] = timezone.now().isoformat()
                    Subscription.objects.filter(pk=sub.pk).update(metadata=meta)
                    sent += 1
            except Exception:
                logger.exception('Failed sending weekly reactivation reminder for subscription %s', sub.id)

        return {'weekly_reactivation_reminders_sent': sent}