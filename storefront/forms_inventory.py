# storefront/forms_inventory.py
from django import forms
from .models import InventoryAlert, ProductVariant, StockMovement, InventoryAudit
from listings.models import Listing

class InventoryAlertForm(forms.ModelForm):
    class Meta:
        model = InventoryAlert
        fields = ['product', 'alert_type', 'threshold', 'notification_method', 'is_active']
        widgets = {
            'notification_method': forms.CheckboxSelectMultiple(choices=[
                ('email', 'Email'),
                ('sms', 'SMS'),
                ('dashboard', 'Dashboard Notification'),
                ('push', 'Push Notification'),
            ]),
        }
    
    def __init__(self, store, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Listing.objects.filter(store=store)
        self.fields['notification_method'].initial = ['email', 'dashboard']

class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = ['name', 'value', 'sku', 'price_adjustment', 'stock', 'weight', 'dimensions', 'is_active']
    
    def clean_sku(self):
        sku = self.cleaned_data.get('sku')
        if sku:
            if ProductVariant.objects.filter(sku=sku).exclude(pk=self.instance.pk if self.instance else None).exists():
                raise forms.ValidationError('SKU already exists')
        return sku

class StockAdjustmentForm(forms.ModelForm):
    adjustment_type = forms.ChoiceField(
        choices=[
            ('add', 'Add Stock'),
            ('remove', 'Remove Stock'),
            ('set', 'Set Exact Quantity')
        ],
        initial='add'
    )
    
    class Meta:
        model = StockMovement
        fields = ['product', 'variant', 'quantity', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, store, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Listing.objects.filter(store=store)
        self.fields['variant'].queryset = ProductVariant.objects.none()
        
        if 'product' in self.data:
            try:
                product_id = int(self.data.get('product'))
                self.fields['variant'].queryset = ProductVariant.objects.filter(listing_id=product_id)
            except (ValueError, TypeError):
                pass
        elif self.instance.pk:
            self.fields['variant'].queryset = self.instance.product.variants.all()

class InventoryAuditForm(forms.ModelForm):
    class Meta:
        model = InventoryAudit
        fields = ['audit_date', 'notes']
        widgets = {
            'audit_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'notes': forms.Textarea(attrs={'rows': 4}),
        }

class BulkStockUpdateForm(forms.Form):
    update_type = forms.ChoiceField(
        choices=[
            ('percentage', 'Percentage Change'),
            ('fixed', 'Fixed Amount'),
            ('set', 'Set Exact Price')
        ],
        initial='percentage'
    )
    value = forms.DecimalField(max_digits=10, decimal_places=2)
    apply_to = forms.ChoiceField(
        choices=[
            ('all', 'All Products'),
            ('category', 'Specific Category'),
            ('low_stock', 'Low Stock Items'),
            ('out_of_stock', 'Out of Stock Items')
        ],
        initial='all'
    )
    category = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Select Category"
    )
    
    def __init__(self, store, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from listings.models import Category
        self.fields['category'].queryset = Category.objects.filter(
            listing__store=store
        ).distinct()