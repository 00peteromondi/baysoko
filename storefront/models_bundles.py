# storefront/models_bundles.py
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
import uuid
from django.utils import timezone
from django.conf import settings
from listings.models import ListingImage

class ProductBundle(models.Model):
    """Product bundles/kits"""
    store = models.ForeignKey('Store', on_delete=models.CASCADE, related_name='bundles')
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField(blank=True)
    
    # Pricing
    base_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Auto-calculated if left empty"
    )
    bundle_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    discount_percentage = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Discount percentage compared to buying items separately"
    )
    
    # Inventory
    sku = models.CharField(max_length=100, unique=True, blank=True)
    stock = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    track_inventory = models.BooleanField(default=True)
    
    # Display
    image = models.ImageField(upload_to='bundles/', null=True, blank=True)
    display_order = models.IntegerField(default=0)
    featured = models.BooleanField(default=False)
    
    # Status
    is_active = models.BooleanField(default=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['display_order', '-created_at']
        indexes = [
            models.Index(fields=['store', 'is_active']),
            models.Index(fields=['slug']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            
            while ProductBundle.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            self.slug = slug
        
        # Calculate base price if not set
        if not self.base_price:
            self.base_price = self.calculate_base_price()
        
        # Calculate discount percentage
        if self.base_price and self.bundle_price:
            self.discount_percentage = int(
                ((self.base_price - self.bundle_price) / self.base_price) * 100
            )
        
        super().save(*args, **kwargs)
    
    def calculate_base_price(self):
        """Calculate total price of bundle items"""
        total = 0
        for item in self.items.all():
            if item.product:
                total += item.product.price * item.quantity
        return total
    
    @property
    def savings(self):
        """Calculate savings amount"""
        if self.base_price:
            return self.base_price - self.bundle_price
        return 0
    
    @property
    def is_available(self):
        """Check if bundle is available for purchase"""
        if not self.is_active:
            return False
        
        now = timezone.now()
        if self.start_date and self.start_date > now:
            return False
        if self.end_date and self.end_date < now:
            return False
        
        if self.track_inventory and self.stock <= 0:
            return False
        
        # Check if all bundle items are available
        for item in self.items.all():
            if not item.product or not item.product.is_active:
                return False
            if item.product.stock < item.quantity:
                return False
        
        return True
    
    @property
    def image_url(self):
        """Get bundle image URL"""
        if self.image and hasattr(self.image, 'url'):
            return self.image.url
        
        # Use first product image as fallback
        first_item = self.items.first()
        if first_item and first_item.product:
            return first_item.product.get_image_url()
        
        return None

class BundleItem(models.Model):
    """Items in a product bundle"""
    bundle = models.ForeignKey(ProductBundle, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('listings.Listing', on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    is_required = models.BooleanField(default=True, help_text="Required item in bundle")
    can_substitute = models.BooleanField(default=False, help_text="Allow substitution with similar products")
    substitute_options = models.ManyToManyField(
        'listings.Listing',
        related_name='substitute_for',
        blank=True,
        help_text="Alternative products if main is unavailable"
    )
    notes = models.CharField(max_length=200, blank=True)
    display_order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['display_order', 'id']
        unique_together = ['bundle', 'product']
    
    def __str__(self):
        return f"{self.quantity}x {self.product.title} in {self.bundle.name}"
    
    @property
    def item_price(self):
        """Price for this item in the bundle"""
        if self.product:
            return self.product.price * self.quantity
        return 0

class BundleRule(models.Model):
    """Rules for bundle creation and pricing"""
    store = models.ForeignKey('Store', on_delete=models.CASCADE, related_name='bundle_rules')
    name = models.CharField(max_length=200)
    rule_type = models.CharField(max_length=20, choices=[
        ('category', 'Category Based'),
        ('price', 'Price Based'),
        ('quantity', 'Quantity Based'),
        ('seasonal', 'Seasonal'),
    ])
    
    # Conditions
    conditions = models.JSONField(default=dict)  # e.g., {"categories": [1,2], "min_price": 1000}
    
    # Actions
    discount_type = models.CharField(max_length=20, choices=[
        ('percentage', 'Percentage Off'),
        ('fixed', 'Fixed Amount Off'),
        ('free_item', 'Free Item'),
    ])
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    free_product = models.ForeignKey(
        'listings.Listing',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='free_in_bundles'
    )
    free_quantity = models.IntegerField(default=1)
    
    # Validity
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    priority = models.IntegerField(default=0, help_text="Higher priority rules apply first")
    
    # Status
    is_active = models.BooleanField(default=True)
    apply_automatically = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-priority', '-created_at']
    
    def __str__(self):
        return self.name
    
    def check_conditions(self, products):
        """Check if rule conditions are met for given products"""
        # Implement condition checking logic
        pass

class UpsellProduct(models.Model):
    """Upsell/cross-sell products"""
    base_product = models.ForeignKey(
        'listings.Listing',
        on_delete=models.CASCADE,
        related_name='upsell_offers'
    )
    upsell_product = models.ForeignKey(
        'listings.Listing',
        on_delete=models.CASCADE,
        related_name='upsell_for'
    )
    discount_type = models.CharField(max_length=20, choices=[
        ('percentage', 'Percentage Off'),
        ('fixed', 'Fixed Amount Off'),
        ('combo', 'Combo Price'),
    ])
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    combo_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    message = models.CharField(max_length=200, blank=True)
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['display_order', '-created_at']
        unique_together = ['base_product', 'upsell_product']
    
    def __str__(self):
        return f"{self.base_product.title} → {self.upsell_product.title}"
    
    @property
    def final_price(self):
        """Calculate final price for upsell product"""
        if self.discount_type == 'percentage':
            return self.upsell_product.price * (1 - self.discount_value / 100)
        elif self.discount_type == 'fixed':
            return max(0, self.upsell_product.price - self.discount_value)
        elif self.discount_type == 'combo' and self.combo_price:
            return self.combo_price
        return self.upsell_product.price

class ProductTemplate(models.Model):
    """Templates for quick product creation"""
    store = models.ForeignKey('Store', on_delete=models.CASCADE, related_name='product_templates')
    name = models.CharField(max_length=200)
    category = models.ForeignKey('listings.Category', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Template fields
    title_template = models.CharField(max_length=200, help_text="Use {category}, {brand}, {color} etc.")
    description_template = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock = models.IntegerField(default=0)
    
    # Default attributes
    condition = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=20, blank=True)
    delivery_option = models.CharField(max_length=20, blank=True)
    
    # Images
    default_images = models.ManyToManyField(
        'listings.ListingImage',
        blank=True,
        related_name='templates'
    )
    
    # Tags and attributes
    default_tags = models.JSONField(default=list, blank=True)
    attributes = models.JSONField(default=dict, blank=True)  # Custom attributes
    
    usage_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-usage_count', '-created_at']
    
    def __str__(self):
        return self.name
    
    def create_product(self, **kwargs):
        """Create a product from template"""
        from listings.models import Listing
        
        # Prepare data
        data = {
            'store': self.store,
            'category': self.category,
            'title': self.title_template.format(**kwargs),
            'description': self.description_template.format(**kwargs) if self.description_template else '',
            'price': kwargs.get('price', self.price) or 0,
            'stock': kwargs.get('stock', self.stock),
            'condition': kwargs.get('condition', self.condition),
            'location': kwargs.get('location', self.location),
            'delivery_option': kwargs.get('delivery_option', self.delivery_option),
            'tags': kwargs.get('tags', self.default_tags),
            'seller': self.created_by,
            'is_active': True,
        }
        
        # Create product
        product = Listing.objects.create(**data)
        
        # Copy images
        for image in self.default_images.all():
            # Create a copy of the image
            new_image = ListingImage.objects.create(
                listing=product,
                image=image.image
            )
        
        # Update usage count
        self.usage_count += 1
        self.save()
        
        return product