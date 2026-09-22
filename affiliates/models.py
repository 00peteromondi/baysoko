from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.crypto import get_random_string


class AffiliateProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='affiliate_profile')
    code = models.CharField(max_length=32, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    default_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.05)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Affiliate {self.user.username}"

    def ensure_code(self):
        if self.code:
            return
        base = (self.user.username or '').strip().lower().replace(' ', '')
        base = base[:10] if base else 'aff'
        self.code = f"{base}-{get_random_string(6)}"

    def get_referral_link(self):
        """The single canonical way to build this affiliate's shareable
        link — used by the dashboard and the AI assistant, so both always
        agree on the format. Always returns a full absolute URL, even if
        SITE_URL somehow ends up unset, since a relative path is useless
        once shared outside the site (WhatsApp, social posts, etc.)."""
        from django.conf import settings as dj_settings
        query_param = getattr(dj_settings, 'AFFILIATE_QUERY_PARAM', 'aid')
        link_base = (getattr(dj_settings, 'SITE_URL', '') or '').rstrip('/')
        if not link_base:
            link_base = 'https://baysoko.up.railway.app'
        return f"{link_base}/?{query_param}={self.code}"


class AffiliateClick(models.Model):
    affiliate = models.ForeignKey(AffiliateProfile, on_delete=models.CASCADE, related_name='clicks')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    session_key = models.CharField(max_length=40, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    path = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class AffiliateAttribution(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='affiliate_attribution')
    affiliate = models.ForeignKey(AffiliateProfile, on_delete=models.CASCADE, related_name='attributions')
    first_touch_at = models.DateTimeField(default=timezone.now)
    last_touch_at = models.DateTimeField(default=timezone.now)
    source = models.CharField(max_length=50, default='link')

    class Meta:
        ordering = ['-last_touch_at']


class AffiliateCommission(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('canceled', 'Canceled'),
    ]

    affiliate = models.ForeignKey(AffiliateProfile, on_delete=models.CASCADE, related_name='commissions')
    order = models.OneToOneField('listings.Order', on_delete=models.CASCADE, related_name='affiliate_commission')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    rate = models.DecimalField(max_digits=5, decimal_places=4)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']


class AffiliateSubscriptionCommission(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('canceled', 'Canceled'),
    ]
    TYPE_CHOICES = [
        ('subscription', 'Subscription'),
        ('bonus', 'Bonus'),
    ]

    affiliate = models.ForeignKey(AffiliateProfile, on_delete=models.CASCADE, related_name='subscription_commissions')
    subscription = models.ForeignKey('storefront.Subscription', on_delete=models.CASCADE, related_name='affiliate_commissions')
    payment = models.OneToOneField('storefront.MpesaPayment', on_delete=models.SET_NULL, null=True, blank=True, related_name='affiliate_subscription_commission')
    referred_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='affiliate_subscription_referrals')
    commission_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='subscription')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    rate = models.DecimalField(max_digits=5, decimal_places=4)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']


class AffiliatePayout(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('canceled', 'Canceled'),
    ]

    affiliate = models.ForeignKey(AffiliateProfile, on_delete=models.CASCADE, related_name='payouts')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reference = models.CharField(max_length=64, blank=True)
    notes = models.TextField(blank=True)
    phone = models.CharField(max_length=15, blank=True)
    mpesa_reference = models.CharField(max_length=100, blank=True)
    mpesa_status = models.CharField(max_length=20, blank=True)
    mpesa_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payout {self.id} - {self.affiliate.user.username}"
