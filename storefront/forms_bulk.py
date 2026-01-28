# storefront/forms_bulk.py
from django import forms
from django.core.validators import FileExtensionValidator
from .models_bulk import BatchJob, ExportJob, ImportTemplate
from listings.models import Category

class BulkProductUpdateForm(forms.Form):
    """Form for bulk updating products"""
    ACTION_CHOICES = [
        ('update_price', 'Update Prices'),
        ('update_stock', 'Update Stock'),
        ('update_status', 'Update Status'),
        ('update_category', 'Update Category'),
        ('add_tags', 'Add Tags'),
        ('remove_tags', 'Remove Tags'),
    ]
    
    UPDATE_METHOD_CHOICES = [
        ('percentage', 'Percentage Change'),
        ('fixed', 'Fixed Amount'),
        ('set', 'Set Exact Value'),
    ]
    
    action = forms.ChoiceField(choices=ACTION_CHOICES, widget=forms.RadioSelect)
    products = forms.MultipleChoiceField(
        widget=forms.SelectMultiple(attrs={'class': 'select2-multiple', 'style': 'width: 100%'}),
        required=False
    )
    
    # Price update fields
    price_update_method = forms.ChoiceField(
        choices=UPDATE_METHOD_CHOICES,
        required=False,
        widget=forms.RadioSelect
    )
    price_value = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        min_value=0,
        help_text="Percentage (e.g., 10 for 10% increase), Fixed amount, or Exact price"
    )
    
    # Stock update fields
    stock_update_method = forms.ChoiceField(
        choices=UPDATE_METHOD_CHOICES,
        required=False,
        widget=forms.RadioSelect
    )
    stock_value = forms.IntegerField(
        required=False,
        min_value=0,
        help_text="Positive to add, negative to remove, or exact quantity"
    )
    
    # Status update fields
    new_status = forms.ChoiceField(
        choices=[('active', 'Active'), ('inactive', 'Inactive'), ('draft', 'Draft')],
        required=False
    )
    
    # Category update fields
    new_category = forms.ModelChoiceField(
        queryset=Category.objects.none(),
        required=False,
        empty_label="Select Category"
    )
    
    # Tag fields
    tags_to_add = forms.CharField(
        required=False,
        help_text="Comma-separated tags to add"
    )
    tags_to_remove = forms.CharField(
        required=False,
        help_text="Comma-separated tags to remove"
    )
    
    # Filter criteria
    apply_to_all = forms.BooleanField(
        initial=False,
        required=False,
        help_text="Apply to all products in store"
    )
    filter_category = forms.ModelChoiceField(
        queryset=Category.objects.none(),
        required=False,
        empty_label="All Categories"
    )
    filter_stock_status = forms.ChoiceField(
        choices=[
            ('', 'All'),
            ('in_stock', 'In Stock'),
            ('low_stock', 'Low Stock'),
            ('out_of_stock', 'Out of Stock')
        ],
        required=False
    )
    filter_price_min = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        min_value=0
    )
    filter_price_max = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        min_value=0
    )
    
    def __init__(self, store, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.store = store
        
        # Set product choices
        products = store.listings.filter(is_active=True).values_list('id', 'title')
        self.fields['products'].choices = [(str(p[0]), p[1]) for p in products]
        
        # Set category querysets
        self.fields['new_category'].queryset = Category.objects.filter(
            listing__store=store
        ).distinct()
        self.fields['filter_category'].queryset = Category.objects.filter(
            listing__store=store
        ).distinct()
        
        # Initialize with store's products if no specific products selected
        if not self.data.get('products'):
            product_ids = store.listings.filter(is_active=True).values_list('id', flat=True)[:100]
            self.fields['products'].initial = [str(pid) for pid in product_ids]
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        
        # Validate based on action
        if action == 'update_price':
            if not cleaned_data.get('price_value'):
                self.add_error('price_value', 'Price value is required')
            if not cleaned_data.get('price_update_method'):
                self.add_error('price_update_method', 'Update method is required')
        
        elif action == 'update_stock':
            if cleaned_data.get('stock_value') is None:
                self.add_error('stock_value', 'Stock value is required')
            if not cleaned_data.get('stock_update_method'):
                self.add_error('stock_update_method', 'Update method is required')
        
        elif action == 'update_status':
            if not cleaned_data.get('new_status'):
                self.add_error('new_status', 'New status is required')
        
        elif action == 'update_category':
            if not cleaned_data.get('new_category'):
                self.add_error('new_category', 'New category is required')
        
        elif action == 'add_tags':
            if not cleaned_data.get('tags_to_add'):
                self.add_error('tags_to_add', 'Tags to add are required')
        
        elif action == 'remove_tags':
            if not cleaned_data.get('tags_to_remove'):
                self.add_error('tags_to_remove', 'Tags to remove are required')
        
        # Validate price range
        price_min = cleaned_data.get('filter_price_min')
        price_max = cleaned_data.get('filter_price_max')
        if price_min and price_max and price_min > price_max:
            self.add_error('filter_price_max', 'Maximum price must be greater than minimum price')
        
        return cleaned_data


class ExportSettingsForm(forms.Form):
    """Form for configuring export settings"""
    FORMAT_CHOICES = [
        ('csv', 'CSV (Comma Separated Values)'),
        ('excel', 'Excel (.xlsx)'),
        ('json', 'JSON'),
        ('pdf', 'PDF Report'),
    ]
    
    export_type = forms.ChoiceField(
        choices=[
            ('products', 'Products'),
            ('inventory', 'Inventory with Stock'),
            ('customers', 'Customers'),
            ('orders', 'Orders'),
            ('analytics', 'Analytics Data'),
        ]
    )
    format = forms.ChoiceField(choices=FORMAT_CHOICES, widget=forms.RadioSelect)
    
    # Date range
    date_range = forms.ChoiceField(
        choices=[
            ('today', 'Today'),
            ('yesterday', 'Yesterday'),
            ('this_week', 'This Week'),
            ('last_week', 'Last Week'),
            ('this_month', 'This Month'),
            ('last_month', 'Last Month'),
            ('custom', 'Custom Range'),
        ],
        initial='this_month'
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    # Filters
    include_inactive = forms.BooleanField(required=False, initial=False)
    include_out_of_stock = forms.BooleanField(required=False, initial=True)
    
    # Columns selection (will be populated dynamically via JavaScript)
    selected_columns = forms.MultipleChoiceField(
        required=False,
        widget=forms.CheckboxSelectMultiple
    )
    
    def __init__(self, store, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.store = store
        
        # Set column choices based on export type
        product_columns = [
            ('id', 'Product ID'),
            ('title', 'Title'),
            ('sku', 'SKU'),
            ('description', 'Description'),
            ('price', 'Price'),
            ('stock', 'Stock'),
            ('category', 'Category'),
            ('condition', 'Condition'),
            ('location', 'Location'),
            ('created_at', 'Created Date'),
            ('is_active', 'Status'),
        ]
        
        self.fields['selected_columns'].choices = product_columns
    
    def clean(self):
        cleaned_data = super().clean()
        date_range = cleaned_data.get('date_range')
        
        if date_range == 'custom':
            start_date = cleaned_data.get('start_date')
            end_date = cleaned_data.get('end_date')
            
            if not start_date or not end_date:
                self.add_error('start_date', 'Both start and end dates are required for custom range')
                self.add_error('end_date', 'Both start and end dates are required for custom range')
            elif start_date > end_date:
                self.add_error('end_date', 'End date must be after start date')
        
        return cleaned_data

class TemplateForm(forms.ModelForm):
    """Form for creating/editing import templates"""
    class Meta:
        model = ImportTemplate
        fields = ['name', 'template_type', 'description', 'file', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, store, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.store = store
        self.fields['file'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        template_type = cleaned_data.get('template_type')
        
        # Validate template file
        file = cleaned_data.get('file')
        if not file and not self.instance.file:
            self.add_error('file', 'Template file is required')
        
        # Check for duplicate template names
        name = cleaned_data.get('name')
        if name:
            qs = ImportTemplate.objects.filter(
                store=self.store,
                name=name,
                template_type=template_type
            )
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            
            if qs.exists():
                self.add_error('name', f'A template with this name already exists for {template_type}')
        
        return cleaned_data


class BulkImportForm(forms.ModelForm):
    """Form for bulk importing data"""

    template_type = forms.ChoiceField(
        label="Data Type",
        choices=[
            ('products', 'Products'),
            ('inventory', 'Inventory Updates'),
            ('customers', 'Customer Data'),
        ],
        initial='products',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    update_existing = forms.BooleanField(
        label="Update existing records",
        required=False,
        initial=True,
        help_text="Update records that already exist",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    create_new = forms.BooleanField(
        label="Create new records",
        required=False,
        initial=True,
        help_text="Create new records for data that doesn't exist",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    skip_errors = forms.BooleanField(
        label="Skip errors and continue",
        required=False,
        initial=False,
        help_text="Continue processing even if some rows have errors",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = BatchJob
        fields = ['file']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.csv,.xlsx,.xls'
            })
        }

    def __init__(self, store, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.store = store
        # Set template queryset to store's templates
        self.fields['template'] = forms.ModelChoiceField(
            label="Use Template (Optional)",
            queryset=ImportTemplate.objects.filter(store=store, is_active=True),
            required=False,
            empty_label="Select a template...",
            widget=forms.Select(attrs={'class': 'form-control'})
        )