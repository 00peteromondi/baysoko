from django.conf import settings
from django.db import models
from django.urls import reverse
from django.core.exceptions import ValidationError


class Store(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='stores')
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    # Optional logo and cover image for storefronts
    # Use CloudinaryField when Cloudinary is configured (keeps behavior consistent with ListingImage)
    if 'cloudinary' in __import__('django.conf').conf.settings.INSTALLED_APPS and hasattr(__import__('django.conf').conf.settings, 'CLOUDINARY_CLOUD_NAME') and __import__('django.conf').conf.settings.CLOUDINARY_CLOUD_NAME:
        from cloudinary.models import CloudinaryField
        logo = CloudinaryField('logo', folder='homabay_souq/stores/logos/', null=True, blank=True)
        cover_image = CloudinaryField('cover_image', folder='homabay_souq/stores/covers/', null=True, blank=True)
    else:
        logo = models.ImageField(upload_to='store_logos/', null=True, blank=True)
        cover_image = models.ImageField(upload_to='store_covers/', null=True, blank=True)
    description = models.TextField(blank=True)
    is_premium = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def get_logo_url(self):
        """Return the logo URL or None; templates can fall back to placeholder."""
        try:
            if self.logo and hasattr(self.logo, 'url'):
                return self.logo.url
        except Exception:
            pass
        return None

    def get_cover_image_url(self):
        try:
            if self.cover_image and hasattr(self.cover_image, 'url'):
                return self.cover_image.url
        except Exception:
            pass
        return None

    def get_absolute_url(self):
        return reverse('storefront:store_detail', kwargs={'slug': self.slug})

    def clean(self):
        """
        Enforce that a user may only create more than one Store if they have a premium subscription
        (i.e., at least one existing Store with is_premium=True or an active Subscription).
        This prevents users from bypassing listing limits by creating additional free stores.
        """
        # Only validate on create (no PK yet) or when owner is changing
        if not self.pk:
            # If the owner is not yet set (e.g., ModelForm validation before view assigns owner), skip here.
            # The view will assign owner on save, and save() calls full_clean() again so validation will run then.
            owner = getattr(self, 'owner', None)
            if owner is None:
                return

            # Count existing stores for owner
            existing = Store.objects.filter(owner=owner)
            if existing.exists():
                # If user already has stores, require that they have at least one premium store
                has_premium_store = existing.filter(is_premium=True).exists()
                # Also allow if there's an active subscription tied to any existing store
                has_active_subscription = Subscription.objects.filter(store__owner=owner, status='active').exists()
                if not (has_premium_store or has_active_subscription):
                    raise ValidationError("You must upgrade to Pro (subscribe) to create additional storefronts.")

    def save(self, *args, **kwargs):
        # Run full_clean to ensure model-level validation runs on save as well as via forms
        self.full_clean()
        return super().save(*args, **kwargs)


class Subscription(models.Model):
    STATUS = [
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('cancelled', 'Cancelled'),
        ('trialing', 'Trial Period'),
    ]
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.CharField(max_length=50, default='premium')
    status = models.CharField(max_length=20, choices=STATUS, default='trialing')
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    next_billing_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.store.name} - {self.plan} ({self.status})"

    def is_in_trial(self):
        """Check if subscription is in trial period"""
        if not self.trial_ends_at:
            return False
        from django.utils import timezone
        return self.status == 'trialing' and self.trial_ends_at > timezone.now()

    def is_active(self):
        """Check if subscription is active (including trial period)"""
        return self.status in ['active', 'trialing'] and not self.is_expired()

    def is_expired(self):
        """Check if subscription has expired"""
        if not self.expires_at:
            return False
        from django.utils import timezone
        return self.expires_at <= timezone.now()

    def cancel(self):
        """Cancel the subscription"""
        from django.utils import timezone
        self.status = 'cancelled'
        self.cancelled_at = timezone.now()
        self.save()


class MpesaPayment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='payments')
    checkout_request_id = models.CharField(max_length=100)
    merchant_request_id = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    result_code = models.CharField(max_length=10, null=True, blank=True)
    result_description = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['-transaction_date']

    def __str__(self):
        return f"Payment for {self.subscription.store.name} - {self.amount} - {self.status}"
