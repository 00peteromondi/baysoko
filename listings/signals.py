from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings
import logging

from .models import Listing, Review

logger = logging.getLogger(__name__)

try:
    from baysoko.utils.email_helpers import render_and_send
except Exception:
    render_and_send = None


@receiver(post_save, sender=Listing)
def listing_post_save(sender, instance, created, **kwargs):
    """
    Send comprehensive notifications when a listing is created or updated.
    Handles in-app notifications, emails, and SMS.
    """
    try:
        # Import here to avoid circular imports
        from notifications.utils import notify_listing_saved

        recipient = getattr(instance, 'seller', None) or getattr(instance, 'owner', None)
        if not recipient:
            # Nothing to notify
            return

        # This now sends in-app notification, email, and SMS based on user preferences
        notify_listing_saved(recipient, instance, created=created)
        logger.info(f"Sent notifications for listing {instance.pk} (created={created})")
    except Exception as e:
        logger.exception('Failed to send listing notifications: %s', e)

@receiver(post_delete, sender=Listing)
def listing_deleted(sender, instance, **kwargs):
    try:
        if not render_and_send:
            return
        ctx = {'listing': instance, 'user': instance.seller, 'site_url': getattr(settings, 'SITE_URL', '')}
        subject = f'Your listing "{instance.title}" was deleted'
        render_and_send('emails/listing_deleted.html', 'emails/listing_deleted.txt', ctx, subject, [instance.seller.email])
    except Exception:
        logger.exception('Error sending listing deleted email')


@receiver(post_save, sender=Review)
def review_created(sender, instance, created, **kwargs):
    # Only notify on new reviews
    if not created:
        return
    try:
        if not render_and_send:
            return
        # Notify relevant parties depending on review type
        if instance.review_type == 'listing' and instance.listing:
            seller = instance.listing.seller
            if seller and seller.email:
                subject = f'New review for your listing "{instance.listing.title}"'
                ctx = {'review': instance, 'listing': instance.listing, 'user': seller, 'site_url': getattr(settings, 'SITE_URL', '')}
                render_and_send('emails/listing_reviewed.html', 'emails/listing_reviewed.txt', ctx, subject, [seller.email])
        elif instance.review_type == 'seller' and instance.seller:
            seller = instance.seller
            if seller and seller.email:
                subject = f'New review for your seller profile'
                ctx = {'review': instance, 'user': seller, 'site_url': getattr(settings, 'SITE_URL', '')}
                render_and_send('emails/store_reviewed.html', 'emails/store_reviewed.txt', ctx, subject, [seller.email])
    except Exception:
        logger.exception('Error sending review notification')
# listings/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Cart

User = get_user_model()

@receiver(post_save, sender=User)
def create_user_cart(sender, instance, created, **kwargs):
    if created:
        Cart.objects.create(user=instance)

"""
Automated webhook triggers using Django signals
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order, Payment
from .webhook_service import webhook_service

@receiver(post_save, sender=Order)
def trigger_order_webhook(sender, instance, created, **kwargs):
    """
    Automatically send webhook when order status changes
    """
    if created:
        # New order created
        webhook_service.send_order_event(instance, 'order_created')
    else:
        # Order updated - check status changes
        try:
            # Get original state if available
            if hasattr(instance, '_original_status'):
                original_status = instance._original_status
                new_status = instance.status
                
                if original_status != new_status:
                    if new_status == 'paid':
                        webhook_service.send_order_event(instance, 'order_paid')
                    elif new_status == 'shipped':
                        webhook_service.send_order_event(instance, 'order_shipped')
                    elif new_status == 'delivered':
                        webhook_service.send_order_event(instance, 'order_delivered')
        except:
            pass


@receiver(post_save, sender=Order)
def notify_sellers_on_order(sender, instance, created, **kwargs):
    """Email each seller when an order containing their listings is created."""
    if not created:
        return
    if not render_and_send:
        return
    try:
        items = list(instance.order_items.select_related('listing', 'listing__store', 'listing__seller'))
        if not items:
            return
        seller_map = {}
        for item in items:
            listing = item.listing
            seller = None
            if getattr(listing, 'store', None) and getattr(listing.store, 'owner', None):
                seller = listing.store.owner
            elif getattr(listing, 'seller', None):
                seller = listing.seller
            if not seller or not getattr(seller, 'email', None):
                continue
            seller_map.setdefault(seller, []).append(item)

        for seller, seller_items in seller_map.items():
            seller_total = sum([it.get_total_price() for it in seller_items])
            ctx = {
                'order': instance,
                'buyer': instance.user,
                'seller': seller,
                'order_items': seller_items,
                'seller_total': seller_total,
                'site_url': getattr(settings, 'SITE_URL', ''),
            }
            subject = f'New order #{instance.id} for your listings'
            render_and_send('emails/new_order_seller.html', 'emails/new_order_seller.txt', ctx, subject, [seller.email])
    except Exception:
        logger.exception('Error sending seller new order email')

@receiver(post_save, sender=Payment)
def trigger_payment_webhook(sender, instance, created, **kwargs):
    """
    Send webhook when payment is completed
    """
    if instance.status == 'completed' and instance.order:
        webhook_service.send_order_event(instance.order, 'order_paid')
