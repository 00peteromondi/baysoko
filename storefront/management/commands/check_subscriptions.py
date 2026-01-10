# storefront/management/commands/check_subscriptions.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from storefront.models import Subscription
from django.core.mail import send_mail
from django.conf import settings

class Command(BaseCommand):
    help = 'Check subscription statuses and send notifications'
    
    def handle(self, *args, **options):
        now = timezone.now()
        
        # Check for subscriptions ending soon (within 3 days)
        ending_soon = Subscription.objects.filter(
            status='active',
            current_period_end__isnull=False,
            current_period_end__lte=now + timezone.timedelta(days=3),
            current_period_end__gt=now
        )
        
        for subscription in ending_soon:
            # Send reminder email
            self.send_reminder_email(subscription)
            self.stdout.write(
                self.style.WARNING(
                    f'Reminder sent for subscription {subscription.id} '
                    f'ending on {subscription.current_period_end}'
                )
            )
        
        # Check for expired subscriptions
        expired = Subscription.objects.filter(
            status='active',
            current_period_end__isnull=False,
            current_period_end__lte=now
        )
        
        for subscription in expired:
            subscription.status = 'past_due'
            subscription.save()
            
            # Send expiration email
            self.send_expiration_email(subscription)
            self.stdout.write(
                self.style.ERROR(
                    f'Subscription {subscription.id} expired and marked as past due'
                )
            )
        
        self.stdout.write(self.style.SUCCESS('Subscription check completed'))
    
    def send_reminder_email(self, subscription):
        """Send subscription renewal reminder"""
        subject = f'Subscription Renewal Reminder - {subscription.store.name}'
        message = f"""
        Hello {subscription.store.owner.get_full_name() or subscription.store.owner.username},
        
        Your {subscription.get_plan_display()} subscription for {subscription.store.name} 
        will expire on {subscription.current_period_end.strftime('%B %d, %Y')}.
        
        Please renew your subscription to continue enjoying premium features.
        
        Renew now: {settings.SITE_URL}/dashboard/store/{subscription.store.slug}/subscription/renew/
        
        Thank you for using Baysoko!
        """
        
        send_mail(
            subject=subject,
            message=message.strip(),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[subscription.store.owner.email],
            fail_silently=True,
        )
    
    def send_expiration_email(self, subscription):
        """Send subscription expired notification"""
        subject = f'Subscription Expired - {subscription.store.name}'
        message = f"""
        Hello {subscription.store.owner.get_full_name() or subscription.store.owner.username},
        
        Your {subscription.get_plan_display()} subscription for {subscription.store.name} 
        has expired. Your store will lose premium features if not renewed.
        
        Please renew your subscription to restore premium features.
        
        Renew now: {settings.SITE_URL}/dashboard/store/{subscription.store.slug}/subscription/renew/
        
        Thank you for using Baysoko!
        """
        
        send_mail(
            subject=subject,
            message=message.strip(),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[subscription.store.owner.email],
            fail_silently=True,
        )