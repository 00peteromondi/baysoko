# storefront/forms_bundles.py
from django import forms
from .models_bundles import ProductBundle, BundleItem, BundleRule, UpsellProduct, ProductTemplate
from listings.models import Listing, Category
from django.utils import timezone

class ProductBundleForm(forms.ModelForm):
    """Form for creating/editing product bundles"""
    class Meta:
        model = ProductBundle
        fields = [
            'name', 'description', 'bundle_price', 'sku', 'stock',
            'track_inventory', 'image', 'display_order', 'featured',
            'is_active', 'start_date', 'end_date'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
    
    def __init__(self, store, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.store = store
        
        # Auto-generate SKU if empty
        if not self.instance.sku:
            self.initial['sku'] = f"BUNDLE-{store.id}-{timezone.now().strftime('%Y%m%d')}"
    
    def clean_bundle_price(self):
        price = self.cleaned_data.get('bundle_price')
        if price and price <= 0:
            raise forms.ValidationError("Bundle price must be greater than 0")
        return price
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            self.add_error('end_date', "End date must be after start date")
        
        return cleaned_data

class BundleItemForm(forms.ModelForm):
    """Form for adding items to a bundle"""
    class Meta:
        model = BundleItem
        fields = ['product', 'quantity', 'is_required', 'can_substitute', 'notes', 'display_order']
    
    def __init__(self, bundle, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bundle = bundle
        
        # Only show products from the same store
        self.fields['product'].queryset = Listing.objects.filter(
            store=bundle.store,
            is_active=True
        ).exclude(
            id__in=bundle.items.values_list('product_id', flat=True)
        )
    
    def clean_product(self):
        product = self.cleaned_data.get('product')
        if product and BundleItem.objects.filter(bundle=self.bundle, product=product).exists():
            raise forms.ValidationError("This product is already in the bundle")
        return product

class BundleRuleForm(forms.ModelForm):
    """Form for creating bundle rules"""
    class Meta:
        model = BundleRule
        fields = [
            'name', 'rule_type', 'conditions', 'discount_type',
            'discount_value', 'free_product', 'free_quantity',
            'start_date', 'end_date', 'priority',
            'is_active', 'apply_automatically'
        ]
        widgets = {
            'conditions': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': '{"categories": [1,2], "min_price": 1000, "min_quantity": 2}'
            }),
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
    
    def __init__(self, store, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.store = store
        self.fields['free_product'].queryset = Listing.objects.filter(store=store)
    
    def clean(self):
        cleaned_data = super().clean()
        discount_type = cleaned_data.get('discount_type')
        discount_value = cleaned_data.get('discount_value')
        free_product = cleaned_data.get('free_product')
        
        if discount_type in ['percentage', 'fixed'] and not discount_value:
            self.add_error('discount_value', 'Discount value is required for this discount type')
        
        if discount_type == 'percentage' and discount_value:
            if discount_value < 0 or discount_value > 100:
                self.add_error('discount_value', 'Percentage must be between 0 and 100')
        
        if discount_type == 'free_item' and not free_product:
            self.add_error('free_product', 'Free product is required for free item discount')
        
        return cleaned_data

class UpsellProductForm(forms.ModelForm):
    """Form for creating upsell products"""
    class Meta:
        model = UpsellProduct
        fields = [
            'base_product', 'upsell_product', 'discount_type',
            'discount_value', 'combo_price', 'message',
            'display_order', 'is_active'
        ]
    
    def __init__(self, store, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.store = store
        
        self.fields['base_product'].queryset = Listing.objects.filter(
            store=store,
            is_active=True
        )
        self.fields['upsell_product'].queryset = Listing.objects.filter(
            store=store,
            is_active=True
        )
    
    def clean(self):
        cleaned_data = super().clean()
        discount_type = cleaned_data.get('discount_type')
        discount_value = cleaned_data.get('discount_value')
        combo_price = cleaned_data.get('combo_price')
        
        if discount_type == 'combo' and not combo_price:
            self.add_error('combo_price', 'Combo price is required for combo discount')
        
        if discount_type in ['percentage', 'fixed'] and not discount_value:
            self.add_error('discount_value', 'Discount value is required for this discount type')
        
        if discount_type == 'percentage' and discount_value:
            if discount_value < 0 or discount_value > 100:
                self.add_error('discount_value', 'Percentage must be between 0 and 100')
        
        # Check that base and upsell products are different
        base_product = cleaned_data.get('base_product')
        upsell_product = cleaned_data.get('upsell_product')
        
        if base_product and upsell_product and base_product.id == upsell_product.id:
            self.add_error('upsell_product', 'Upsell product must be different from base product')
        
        return cleaned_data

class ProductTemplateForm(forms.ModelForm):
    """Form for creating product templates"""
    class Meta:
        model = ProductTemplate
        fields = [
            'name', 'category', 'title_template', 'description_template',
            'price', 'stock', 'condition', 'location', 'delivery_option',
            'default_tags', 'attributes', 'is_active'
        ]
        widgets = {
            'description_template': forms.Textarea(attrs={'rows': 4}),
            'default_tags': forms.TextInput(attrs={
                'placeholder': 'tag1, tag2, tag3'
            }),
            'attributes': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': '{"color": "red", "size": "large"}'
            }),
        }
    
    def __init__(self, store, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.store = store
        self.user = user
        
        self.fields['category'].queryset = Category.objects.filter(
            listing__store=store
        ).distinct()
    
    def clean_default_tags(self):
        tags = self.cleaned_data.get('default_tags', '')
        if isinstance(tags, str):
            return [tag.strip() for tag in tags.split(',') if tag.strip()]
        return tags
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.store = self.store
        instance.created_by = self.user
        
        if commit:
            instance.save()
        
        return instance

class QuickProductForm(forms.Form):
    """Form for quick product creation from template"""
    template = forms.ModelChoiceField(
        queryset=ProductTemplate.objects.none(),
        empty_label="Select Template"
    )
    
    # Dynamic fields will be added via JavaScript based on template
    title = forms.CharField(max_length=200, required=False)
    price = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    stock = forms.IntegerField(required=False, initial=0)
    
    def __init__(self, store, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.store = store
        
        self.fields['template'].queryset = ProductTemplate.objects.filter(
            store=store,
            is_active=True
        )
    
    def clean(self):
        cleaned_data = super().clean()
        template = cleaned_data.get('template')
        
        if template:
            # Validate required fields based on template
            if not cleaned_data.get('title'):
                if '{' in template.title_template:
                    # Template has variables, need custom title
                    self.add_error('title', 'Custom title is required for this template')
            
            if not cleaned_data.get('price') and not template.price:
                self.add_error('price', 'Price is required')
        
        return cleaned_data