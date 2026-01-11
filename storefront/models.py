from django.conf import settings
from django.db import models
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.db.models import Sum, Avg
from django.utils import timezone
from datetime import timedelta

class Store(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='stores')
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    
    # Optional logo and cover image for storefronts
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
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    location = models.CharField(max_length=255, blank=True)
    policies = models.TextField(blank=True, help_text="Store policies, return policy, etc.")

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
    
    def get_sales_count(self):
        """Return total sales count for all listings in this store."""
        from listings.models import OrderItem
        
        # Get the sum of quantities from all order items for this store's listings
        total_quantity = OrderItem.objects.filter(
            listing__store=self
        ).aggregate(
            total_quantity=Sum('quantity')
        )['total_quantity']
        
        return total_quantity or 0
    
    def get_rating(self):
        """
        Return combined average rating for:
        1. Product reviews for all listings in this store
        2. Direct store reviews (if StoreReview model exists)
        """
        from listings.models import Review
        from django.db.models import Avg, Q
        
        all_ratings = []
        
        # Get product reviews for all listings in this store
        product_reviews = Review.objects.filter(listing__store=self)
        if product_reviews.exists():
            product_avg = product_reviews.aggregate(avg_rating=Avg('rating'))['avg_rating']
            if product_avg:
                all_ratings.append(product_avg)
        
        # Get direct store reviews if StoreReview model exists
        try:
            # Check if StoreReview model exists in current app
            from .models import StoreReview
            store_reviews = StoreReview.objects.filter(store=self)
            if store_reviews.exists():
                store_avg = store_reviews.aggregate(avg_rating=Avg('rating'))['avg_rating']
                if store_avg:
                    all_ratings.append(store_avg)
        except (ImportError, AttributeError):
            # StoreReview model not defined yet, skip
            pass
        
        # Calculate weighted average if we have both types of reviews
        if not all_ratings:
            return 0
        
        # Simple average of all ratings
        combined_avg = sum(all_ratings) / len(all_ratings)
        return round(combined_avg, 1)

    def get_review_count(self):
        """Get total number of reviews (product reviews + store reviews)."""
        from listings.models import Review
        total = 0
        
        # Count product reviews
        total += Review.objects.filter(listing__store=self).count()
        
        # Count direct store reviews if StoreReview model exists
        try:
            from .models import StoreReview
            total += StoreReview.objects.filter(store=self).count()
        except (ImportError, AttributeError):
            # StoreReview model not defined yet, skip
            pass
        
        return total
    

    def has_user_reviewed(self, user):
        """Check if user has reviewed this store (either via products or directly)."""
        if not user.is_authenticated:
            return False
        
        from listings.models import Review
        
        # Check if user has reviewed any product in this store
        # FIXED: Changed 'reviewer' to 'user' to match the Review model field
        has_product_review = Review.objects.filter(
            listing__store=self,
            user=user  # Changed from reviewer=user to user=user
        ).exists()
        
        if has_product_review:
            return True
        
        # Check if user has directly reviewed the store
        try:
            from .models import StoreReview
            return StoreReview.objects.filter(store=self, reviewer=user).exists()
        except (ImportError, AttributeError):
            # StoreReview model not defined yet
            return False


    def get_all_reviews(self):
        """Get all reviews for this store (both product and direct store reviews)"""
        from listings.models import Review
        
        all_reviews = []
        
        # Get product reviews for this store's listings
        product_reviews = Review.objects.filter(listing__store=self).select_related(
            'user', 'listing'
        ).order_by('-created_at')
        
        # Get direct store reviews
        try:
            store_reviews = self.reviews.all().select_related('reviewer').order_by('-created_at')
        except (ImportError, AttributeError):
            store_reviews = []
        
        # Combine and sort by date
        for review in product_reviews:
            all_reviews.append({
                'type': 'product',
                'id': review.id,
                'reviewer': review.user,
                'rating': review.rating,
                'comment': review.comment,
                'created_at': review.created_at,
                'listing': review.listing,
                'helpful_count': 0,  # Product reviews don't have helpful count
            })
        
        for review in store_reviews:
            all_reviews.append({
                'type': 'store',
                'id': review.id,
                'reviewer': review.reviewer,
                'rating': review.rating,
                'comment': review.comment,
                'created_at': review.created_at,
                'listing': None,
                'helpful_count': review.helpful_count,
            })
        
        # Sort by created_at, newest first
        all_reviews.sort(key=lambda x: x['created_at'], reverse=True)
        
        return all_reviews

    def get_all_reviews_paginated(self, page=1, per_page=10):
        """Get paginated reviews"""
        all_reviews = self.get_all_reviews()
        
        # Simple pagination for list
        from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
        
        paginator = Paginator(all_reviews, per_page)
        
        try:
            reviews_page = paginator.page(page)
        except PageNotAnInteger:
            reviews_page = paginator.page(1)
        except EmptyPage:
            reviews_page = paginator.page(paginator.num_pages)
        
        return reviews_page
    
    def get_average_store_rating(self):
        """Get average rating from direct store reviews only."""
        try:
            from .models import StoreReview
            store_reviews = StoreReview.objects.filter(store=self)
            if store_reviews.exists():
                return store_reviews.aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0
        except (ImportError, AttributeError):
            pass
        return 0
    
    def get_product_reviews(self):
        """Get product reviews for this store's listings."""
        from listings.models import Review
        return Review.objects.filter(listing__store=self).select_related('user', 'listing').order_by('-created_at')
        
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


class StoreReview(models.Model):
    """Review model for stores"""
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='store_reviews')
    rating = models.PositiveIntegerField(
        choices=[(1, '1'), (2, '2'), (3, '3'), (4, '4'), (5, '5')],
        default=5
    )
    comment = models.TextField(max_length=1000)
    helpful_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['store', 'reviewer']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.reviewer.username} - {self.store.name} - {self.rating}★"
    
    def mark_helpful(self, user):
        """Mark review as helpful by a user"""
        if not ReviewHelpful.objects.filter(review=self, user=user).exists():
            ReviewHelpful.objects.create(review=self, user=user)
            self.helpful_count += 1
            self.save()
            return True
        return False


class ReviewHelpful(models.Model):
    """Track which reviews users found helpful"""
    review = models.ForeignKey(StoreReview, on_delete=models.CASCADE, related_name='helpful_votes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['review', 'user']


class Subscription(models.Model):
    """Store subscription model - Enhanced"""
    SUBSCRIPTION_STATUS = (
        ('trialing', 'Trialing'),
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('canceled', 'Canceled'),
        ('unpaid', 'Unpaid'),
    )
    
    PLAN_CHOICES = (
        ('basic', 'Basic - KSh 999/month'),
        ('premium', 'Premium - KSh 1,999/month'),
        ('enterprise', 'Enterprise - KSh 4,999/month'),
    )
    
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='basic')
    status = models.CharField(max_length=20, choices=SUBSCRIPTION_STATUS, default='trialing')
    
    # Billing details
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=999.00)
    currency = models.CharField(max_length=3, default='KES')
    
    # Dates
    started_at = models.DateTimeField(auto_now_add=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    
    # Payment method
    mpesa_phone = models.CharField(max_length=15, null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.store.name} - {self.get_plan_display()} ({self.status})"
    
    def is_active(self):
        """Check if subscription is currently active"""
        now = timezone.now()
        if self.status in ['active', 'trialing']:
            if self.trial_ends_at and now > self.trial_ends_at:
                return self.status == 'active'
            return True
        return False
    
    @property
    def expires_at(self):
        """Property to get expiration date for admin display"""
        if self.status == 'trialing' and self.trial_ends_at:
            return self.trial_ends_at
        elif self.current_period_end:
            return self.current_period_end
        elif self.trial_ends_at:
            return self.trial_ends_at
        return None
    
    def cancel(self):
        """Cancel subscription"""
        self.status = 'canceled'
        self.canceled_at = timezone.now()
        self.save()
        
        # Update store premium status
        if self.store.is_premium:
            # Check if store has any other active subscriptions
            active_subs = Subscription.objects.filter(
                store=self.store,
                status__in=['active', 'trialing']
            ).exclude(id=self.id)
            
            if not active_subs.exists():
                self.store.is_premium = False
                self.store.save()
    
    def renew(self, payment=None):
        """Renew subscription after payment"""
        self.status = 'active'
        self.current_period_end = timezone.now() + timezone.timedelta(days=30)
        
        if payment:
            self.mpesa_phone = payment.phone_number
        
        self.save()
        
        # Ensure store is marked as premium
        if not self.store.is_premium:
            self.store.is_premium = True
            self.store.save()


class MpesaPayment(models.Model):
    """M-Pesa payment records"""
    PAYMENT_STATUS = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    )
    
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='payments')
    
    # M-Pesa details
    checkout_request_id = models.CharField(max_length=100, unique=True)
    merchant_request_id = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Transaction details
    mpesa_receipt_number = models.CharField(max_length=50, null=True, blank=True)
    transaction_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    
    # Metadata
    result_code = models.CharField(max_length=10, null=True, blank=True)
    result_description = models.TextField(null=True, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"MPesa Payment - {self.phone_number} - KSh {self.amount} - {self.status}"
    
    def is_successful(self):
        """Check if payment was successful"""
        return self.status == 'completed'


