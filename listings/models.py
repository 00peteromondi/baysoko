# listings/models.py
import os
from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.db.models import Avg
from cloudinary.models import CloudinaryField

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


User = get_user_model()

class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, default='bi-grid', help_text="Bootstrap icon class name")
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    is_featured = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['order', 'name']

class ListingImage(models.Model):
    listing = models.ForeignKey('Listing', on_delete=models.CASCADE, related_name='images')
    
    # Cloudinary field for images
    if 'cloudinary' in settings.INSTALLED_APPS and hasattr(settings, 'CLOUDINARY_CLOUD_NAME') and settings.CLOUDINARY_CLOUD_NAME:
        image = CloudinaryField(
            'image',
            folder='homabay_souq/listings/gallery/',
            null=True,
            blank=True
        )
    else:
        image = models.ImageField(
            upload_to='listing_images/gallery/',
            null=True,
            blank=True
        )
    
    caption = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"Image for {self.listing.title}"

    def get_image_url(self):
        """Safe method to get image URL"""
        if self.image:
            try:
                return self.image.url
            except Exception as e:
                if hasattr(self.image, 'url'):
                    return self.image.url
        return '/static/images/listing_placeholder.svg'
    
    
class Listing(models.Model):
    HOMABAY_LOCATIONS = [
        ('HB_Town', 'Homa Bay Town'),
        ('Kendu_Bay', 'Kendu Bay'),
        ('Rodi_Kopany', 'Rodi Kopany'),
        ('Mbita', 'Mbita'),
        ('Oyugis', 'Oyugis'),
        ('Rangwe', 'Rangwe'),
        ('Ndhiwa', 'Ndhiwa'),
        ('Suba', 'Suba'),
    ]

    CONDITION_CHOICES = [
        ('new', 'New'),
        ('used', 'Used'),
        ('refurbished', 'Refurbished'),
    ]

    DELIVERY_OPTIONS = [
        ('pickup', 'Pickup'),
        ('delivery', 'Delivery'),
        ('shipping', 'Shipping'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    location = models.CharField(max_length=50, choices=HOMABAY_LOCATIONS)
    
    # Image field with Cloudinary fallback
    if 'cloudinary' in settings.INSTALLED_APPS and hasattr(settings, 'CLOUDINARY_CLOUD_NAME') and settings.CLOUDINARY_CLOUD_NAME:
        image = CloudinaryField(
            'image',
            folder='homabay_souq/listings/',
            null=True,
            blank=True
        )
    else:
        image = models.ImageField(
            upload_to='listing_images/',
            null=True,
            blank=True
        )
    
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='used')
    delivery_option = models.CharField(max_length=20, choices=DELIVERY_OPTIONS, default='pickup')
    stock = models.PositiveIntegerField(default=1)
    is_sold = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    favorited_by = models.ManyToManyField(User, related_name='favorited_listings', blank=True)
    
    # Product specifications
    brand = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)
    dimensions = models.CharField(max_length=100, blank=True, help_text="e.g., 10x5x3 inches")
    weight = models.CharField(max_length=50, blank=True, help_text="e.g., 2.5 kg")
    color = models.CharField(max_length=50, blank=True)
    material = models.CharField(max_length=100, blank=True)
    
    # SEO and sharing
    meta_description = models.TextField(blank=True)
    slug = models.SlugField(unique=True, blank=True)
    # Optional explicit link to a Store (storefront.Store). Nullable to remain backward compatible.
    store = models.ForeignKey('storefront.Store', on_delete=models.SET_NULL, null=True, blank=True, related_name='listings')
    
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='listings', null=True)
    
    # Price history (we'll track this via a separate model)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    views = models.PositiveIntegerField(default=0)  # For trending
    discount_price = models.DecimalField(  # For flash sales
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('listing-detail', kwargs={'pk': self.pk})

    def get_condition_display(self):
        return dict(self.CONDITION_CHOICES).get(self.condition, 'Unknown')

    def get_delivery_option_display(self):
        return dict(self.DELIVERY_OPTIONS).get(self.delivery_option, 'Unknown')

    @property
    def average_rating(self):
        if self.reviews.count() > 0:
            return self.reviews.aggregate(Avg('rating'))['rating__avg']
        return 0
    
    def get_image_url(self):
        """Safe method to get image URL that works with both Cloudinary and local storage"""
        if self.image:
            try:
                return self.image.url
            except Exception as e:
                if hasattr(self.image, 'url'):
                    return self.image.url
        return '/static/images/listing_placeholder.svg'
    
    
    @property
    def price_trend(self):
        """Simple price trend indicator"""
        if self.original_price and self.original_price > self.price:
            return 'down'
        elif self.original_price and self.original_price < self.price:
            return 'up'
        return 'stable'
    
    def save(self, *args, **kwargs):
        # Set original price on first save
        if not self.pk and not self.original_price:
            self.original_price = self.price
        
        # Ensure the directory exists before saving
        if self.image:
            import os
            os.makedirs(os.path.join(settings.MEDIA_ROOT, 'listing_images'), exist_ok=True)
        
        # Generate slug if not provided
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.title)
            # Ensure uniqueness
            original_slug = self.slug
            counter = 1
            while Listing.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        
        super().save(*args, **kwargs)

class PriceHistory(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='price_history')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    date_changed = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Price Histories"
        ordering = ['-date_changed']

class Favorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='favorites'
    )
    listing = models.ForeignKey(
        'Listing', 
        on_delete=models.CASCADE, 
        related_name='favorites'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'listing')
        ordering = ['-created_at']

class Activity(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='activities'
    )
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} - {self.action} at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

class RecentlyViewed(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'listing')
        ordering = ['-viewed_at']

class FAQ(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='faqs')
    question = models.CharField(max_length=255)
    answer = models.TextField()
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['order', 'id']
    

class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart ({self.user.username})"

    def get_total_price(self):
        return sum(item.get_total_price() for item in self.items.all())

    @property
    def total_items(self):
        return self.items.count()


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items'
    )
    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE
    )
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('cart', 'listing')

    def __str__(self):
        return f"{self.quantity} x {self.listing.title}"

    def get_total_price(self):
        return self.quantity * self.listing.price


class Order(models.Model):
    ORDER_STATUS = [
        ('pending', 'Pending Payment'),
        ('paid', 'Paid'),
        ('partially_shipped', 'Partially Shipped'),
        ('confirmed', 'Confirmed'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('disputed', 'Disputed'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders'
    )
    items = models.ManyToManyField(Listing, through='OrderItem')
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=ORDER_STATUS, default='pending')
    
    # Add shipping and contact information fields
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    shipping_address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)

    tracking_number = models.CharField(max_length=100, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    # Delivery system integration
    delivery_request_id = models.CharField(max_length=100, blank=True)
    driver_assigned = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Order #{self.id} - {self.user.username}"

    def mark_as_paid(self):
        self.status = 'paid'
        self.paid_at = timezone.now()
        self.save()
        
        # Update stock for each item in the order
        for order_item in self.order_items.all():
            listing = order_item.listing
            # Only update stock if it's greater than 0
            if listing.stock >= order_item.quantity:
                listing.stock -= order_item.quantity
                # Mark as sold only if stock reaches 0
                if listing.stock == 0:
                    listing.is_sold = True
                listing.save()
            else:
                # This shouldn't happen if validation is proper, but handle just in case
                listing.stock = 0
                listing.is_sold = True
                listing.save()

        
    def can_be_shipped(self):
        """Check if order can be shipped"""
        return self.status == 'paid'
    
    def can_confirm_delivery(self):
        """Check if delivery can be confirmed"""
        return self.status == 'shipped'


                
                
class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_items')
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    added_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    # Per-item shipment state (important for multi-seller orders)
    shipped = models.BooleanField(default=False)
    shipped_at = models.DateTimeField(null=True, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.quantity} x {self.listing.title}"

    def get_total_price(self):
        return self.quantity * self.price




class Payment(models.Model):
    PAYMENT_METHODS = [
        ('mpesa', 'M-Pesa'),
        ('bank_transfer', 'Bank Transfer'),
        ('cash', 'Cash on Delivery'),
    ]

    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('initiated', 'M-Pesa Initiated'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='payment'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='mpesa')
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    transaction_id = models.CharField(max_length=100, blank=True)
    mpesa_phone_number = models.CharField(max_length=15, blank=True)
    mpesa_checkout_request_id = models.CharField(max_length=100, blank=True)
    mpesa_merchant_request_id = models.CharField(max_length=100, blank=True)
    mpesa_result_code = models.IntegerField(null=True, blank=True)
    mpesa_result_desc = models.TextField(blank=True)
    mpesa_callback_data = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Add these for real escrow
    is_held_in_escrow = models.BooleanField(default=True)
    actual_release_date = models.DateTimeField(null=True, blank=True)
    seller_payout_reference = models.CharField(max_length=100, blank=True)
    
    def hold_in_escrow(self):
        """Actually move funds to escrow account"""
        # Implementation depends on your payment processor
        # This would typically involve:
        # 1. Capturing payment but not settling to seller
        # 2. Moving to a separate escrow account
        # 3. Setting up automatic release after X days or manual release
        pass
    
    def release_to_seller(self):
        """Actually transfer funds from escrow to seller"""
        # Implementation depends on your payment processor
        # This would typically involve:
        # 1. Releasing from escrow account to seller's balance
        # 2. Creating a payout transaction
        # 3. Updating accounting records
        pass

    def __str__(self):
        return f"Payment for Order #{self.order.id}"

    def mark_as_completed(self, transaction_id):
        self.status = 'completed'
        self.transaction_id = transaction_id
        self.completed_at = timezone.now()
        self.save()
        
        # Mark order as paid
        self.order.mark_as_paid()

    
    def initiate_mpesa_payment(self, phone_number):
        """Initiate M-Pesa STK push with proper error handling"""
        from .mpesa_utils import mpesa_gateway
        
        result = mpesa_gateway.stk_push(
            phone_number=phone_number,
            amount=self.amount,
            account_reference=f"ORDER{self.order.id}",
            transaction_desc=f"Payment for order #{self.order.id}"
        )
        
        if result['success']:
            self.status = 'initiated'
            self.method = 'mpesa'
            self.mpesa_phone_number = phone_number
            self.mpesa_checkout_request_id = result['checkout_request_id']
            self.mpesa_merchant_request_id = result['merchant_request_id']
            self.save()
            
            # For simulation mode, auto-complete after delay
            if not mpesa_gateway.has_valid_credentials:
                self._simulate_payment_completion()
            
            return True, result['response_description']
        else:
            self.status = 'failed'
            self.save()
            return False, result['error']

    def _simulate_payment_completion(self):
        """Simulate payment completion for development"""
        import threading
        import time
        
        import logging
        logger = logging.getLogger(__name__)

        def complete_payment():
            time.sleep(10)  # Wait 10 seconds to simulate payment processing
            try:
                # Refresh the payment object
                payment = Payment.objects.get(id=self.id)
                if payment.status == 'initiated':  # Only complete if still initiated
                    payment.mark_as_completed(f"MPESA{int(time.time())}")
                    logger.info(f"Simulated payment completion for order #{payment.order.id}")
            except Payment.DoesNotExist:
                logger.error("Payment no longer exists for simulation")
            except Exception as e:
                logger.error(f"Error in payment simulation: {str(e)}")
        
        thread = threading.Thread(target=complete_payment)
        thread.daemon = True
        thread.start()

class Escrow(models.Model):
    ESCROW_STATUS = [
        ('held', 'Funds Held'),
        ('released', 'Funds Released to Seller'),
        ('refunded', 'Funds Refunded to Buyer'),
        ('disputed', 'Disputed'),
    ]

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='escrow'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=ESCROW_STATUS, default='held')
    created_at = models.DateTimeField(auto_now_add=True)
    released_at = models.DateTimeField(null=True, blank=True)
    auto_release_date = models.DateTimeField(null=True, blank=True)
    dispute_resolved_at = models.DateTimeField(null=True, blank=True)

    def schedule_auto_release(self, days=7):
        """Automatically release funds after X days if no dispute"""
        from django.utils import timezone
        from datetime import timedelta
        
        self.auto_release_date = timezone.now() + timedelta(days=days)
        self.save()
    
    def check_auto_release(self):
        """Check if escrow should be automatically released"""
        if (self.auto_release_date and 
            timezone.now() >= self.auto_release_date and
            self.status == 'held'):
            self.release_funds()
            return True
        return False

    def __str__(self):
        return f"Escrow for Order #{self.order.id}"

    def release_funds(self):
        self.status = 'released'
        self.released_at = timezone.now()
        self.save()
        
        # In a real implementation, you would transfer funds to seller here
        # For now, we'll just update the status
        
        # Create activity log
        Activity.objects.create(
            user=self.order.user,
            action=f"Escrow released for Order #{self.order.id}"
        )

    def refund_funds(self):
        self.status = 'refunded'
        self.released_at = timezone.now()
        self.save()
        
        # In a real implementation, you would refund funds to buyer here
        
        # Create activity log
        Activity.objects.create(
            user=self.order.user,
            action=f"Escrow refunded for Order #{self.order.id}"
        )

class Review(models.Model):
    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('listing', 'user')
        ordering = ['-created_at']

    def __str__(self):
        return f"Review by {self.user.username} for {self.listing.title}"