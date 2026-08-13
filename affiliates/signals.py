from decimal import Decimal, ROUND_HALF_UP
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model

from listings.models import Order
from storefront.models import Store, MpesaPayment
from .models import AffiliateProfile, AffiliateCommission, AffiliateSubscriptionCommission, AffiliateAttribution


def _is_seller(user):
    try:
        return Store.objects.filter(owner=user).exists()
    except Exception:
        return False


@receiver(pre_save, sender=AffiliateProfile)
def _affiliate_profile_presave(sender, instance, **kwargs):
    instance.ensure_code()


@receiver(post_save, sender=get_user_model())
def _ensure_affiliate_profile(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        AffiliateProfile.objects.get_or_create(user=instance)
    except Exception:
        return


@receiver(post_save, sender=Order)
def _affiliate_commission_on_paid(sender, instance, created, **kwargs):
    try:
        if instance.status != 'paid':
            return
        if AffiliateCommission.objects.filter(order=instance).exists():
            return

        attribution = AffiliateAttribution.objects.filter(user=instance.user).select_related('affiliate').first()
        if not attribution or not attribution.affiliate or not attribution.affiliate.is_active:
            return
        # Avoid self-referral
        if attribution.affiliate.user_id == instance.user_id:
            return
        # Buyer-only order referral: both affiliate and referred must be non-sellers
        if _is_seller(attribution.affiliate.user) or _is_seller(instance.user):
            return

        rate = getattr(attribution.affiliate, 'default_rate', None)
        if rate is None:
            rate = getattr(settings, 'AFFILIATE_DEFAULT_RATE', 0.05)
        total = instance.total_price
        try:
            amount = (total * Decimal(rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except Exception:
            amount = total * rate

        AffiliateCommission.objects.create(
            affiliate=attribution.affiliate,
            order=instance,
            amount=amount,
            rate=rate,
            status='pending',
        )
    except Exception:
        return


@receiver(post_save, sender=MpesaPayment)
def _affiliate_subscription_commission_on_paid(sender, instance, created, **kwargs):
    try:
        if instance.status != 'completed':
            return
        subscription = instance.subscription
        if not subscription or subscription.plan == 'free':
            return
        referred_user = getattr(subscription.store, 'owner', None)
        if not referred_user:
            return

        attribution = AffiliateAttribution.objects.filter(user=referred_user).select_related('affiliate').first()
        if not attribution or not attribution.affiliate or not attribution.affiliate.is_active:
            return
        if attribution.affiliate.user_id == referred_user.id:
            return

        is_affiliate_seller = _is_seller(attribution.affiliate.user)
        is_referred_seller = _is_seller(referred_user)

        # Seller affiliates: commission on paid subscriptions for referred sellers
        if is_affiliate_seller and is_referred_seller:
            if AffiliateSubscriptionCommission.objects.filter(payment=instance).exists():
                return
            rate = getattr(settings, 'AFFILIATE_SUBSCRIPTION_RATE', Decimal('0.05'))
            amount = (Decimal(instance.amount) * Decimal(rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            AffiliateSubscriptionCommission.objects.create(
                affiliate=attribution.affiliate,
                subscription=subscription,
                payment=instance,
                referred_user=referred_user,
                commission_type='subscription',
                amount=amount,
                rate=rate,
                status='pending',
                note='Seller referral subscription commission'
            )
            return

        # Buyer affiliates: bonus after 3 consecutive paid subscription payments by referred user
        if (not is_affiliate_seller) and is_referred_seller:
            latest_three = list(MpesaPayment.objects.filter(
                subscription__store__owner=referred_user,
                status='completed'
            ).exclude(subscription__plan='free').order_by('-created_at')[:3])
            if len(latest_three) < 3:
                return
            # Ensure this payment is the latest and is the 3rd consecutive paid
            if latest_three[0].id != instance.id:
                return
            if AffiliateSubscriptionCommission.objects.filter(
                affiliate=attribution.affiliate,
                referred_user=referred_user,
                commission_type='bonus'
            ).exists():
                return
            bonus_rate = getattr(settings, 'AFFILIATE_BONUS_RATE', Decimal('0.02'))
            amount = (Decimal(instance.amount) * Decimal(bonus_rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            AffiliateSubscriptionCommission.objects.create(
                affiliate=attribution.affiliate,
                subscription=subscription,
                payment=instance,
                referred_user=referred_user,
                commission_type='bonus',
                amount=amount,
                rate=bonus_rate,
                status='pending',
                note='Buyer referral bonus after 3 consecutive paid subscriptions'
            )
    except Exception:
        return
