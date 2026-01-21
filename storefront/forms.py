from django import forms
from django.db import models
from .models import Store
from listings.forms import ListingForm
from .mpesa import MpesaGateway


# REPLACE the entire UpgradeForm section (from line 79) with this SINGLE, CORRECTED UpgradeForm:

class UpgradeForm(forms.Form):
    """Form for upgrading to premium - Enhanced"""
    phone_number = forms.CharField(
        max_length=12,  # Changed from 10 to 12 to accommodate +254 prefix
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': '07XXXXXXXX or 7XXXXXXXX',
            'pattern': '^[0-9]{9,12}$'
        })
    )
    
    # Remove the hidden plan field if you're using session storage
    # plan = forms.ChoiceField(
    #     choices=Subscription.PLAN_CHOICES,
    #     widget=forms.HiddenInput(),
    #     required=False,
    #     initial='basic'
    # )
    
    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number', '')
        
        if not phone:
            raise forms.ValidationError('Phone number is required')
        
        # Remove any non-digit characters
        phone = ''.join(filter(str.isdigit, phone))
        
        # Handle various Kenyan phone formats
        if phone.startswith('0') and len(phone) == 10:  # 07XXXXXXXX
            phone = '254' + phone[1:]  # Convert to 2547XXXXXXXX
        elif phone.startswith('7') and len(phone) == 9:  # 7XXXXXXXX
            phone = '254' + phone  # Convert to 2547XXXXXXXX
        elif phone.startswith('254') and len(phone) == 12:  # 2547XXXXXXXX
            pass  # Already correct
        else:
            raise forms.ValidationError(
                'Please enter a valid Kenyan phone number format: '
                '07XXXXXXXX, 7XXXXXXXX, or 2547XXXXXXXX'
            )
        
        # Final validation - must be 12 digits starting with 254
        if len(phone) != 12 or not phone.startswith('254'):
            raise forms.ValidationError('Invalid phone number format')
        
        return f"+{phone}"  # Return with + prefix
    
    def clean(self):
        cleaned_data = super().clean()
        # You can add additional validation here if needed
        return cleaned_data

from django import forms
from .models import Store, Subscription
from django.utils import timezone

from django import forms
from .models import Store, Subscription
from django.utils import timezone
from django.core.exceptions import ValidationError

class StoreForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = ['name', 'slug', 'description', 'logo', 'cover_image']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Make logo and cover_image fields optional for editing
        if self.instance and self.instance.pk:
            self.fields['logo'].required = False
            self.fields['cover_image'].required = False
            
        # For existing stores (edit mode), no featured option - it's set automatically
        # Remove all is_featured field logic
    
    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        if slug:
            # Check if slug is unique (excluding current store)
            qs = Store.objects.filter(slug=slug)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("This store URL is already taken. Please choose a different one.")
        return slug
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Ensure store owner can't change owner through form
        if self.instance and self.instance.pk and 'owner' in cleaned_data:
            del cleaned_data['owner']
        
        # is_featured is now set automatically based on subscription, no manual setting
        
        return cleaned_data
    
    def save(self, commit=True):
        # Get the unsaved store instance
        store = super().save(commit=False)
        
        # Only update logo/cover if new files are provided in cleaned_data
        # This ensures existing files are preserved when not updating
        if 'logo' in self.cleaned_data and self.cleaned_data['logo'] is not None:
            # If logo is explicitly set to None (via clear), it will be None
            # If it's a new file, it will be set
            # If it's the existing file (from initial data), it stays as is
            pass
        # No else needed - if logo not in cleaned_data or is None and we didn't clear, keep existing
        
        if 'cover_image' in self.cleaned_data and self.cleaned_data['cover_image'] is not None:
            pass
        
        # Set is_featured automatically based on subscription
        store.is_featured = self._get_featured_status(store)
        
        if commit:
            store.save()
            self.save_m2m()
        
        return store
    
    def _get_featured_status(self, store):
        """Determine if store should be featured based on active subscription"""
        from .models import Subscription
        from django.utils import timezone
        
        # Check for active premium or enterprise subscription
        active_premium_subscription = Subscription.objects.filter(
            store=store,
            status__in=['active', 'trialing'],
            plan__in=['premium', 'enterprise']
        ).filter(
            # For trialing, ensure trial hasn't expired
            ~models.Q(status='trialing', trial_ends_at__lt=timezone.now())
        ).exists()
        
        return active_premium_subscription

# Reuse ListingForm for creating/editing storefront "products" (listings)
class ProductForm(ListingForm):
    pass

# storefront/forms.py - Add to existing forms

from django import forms
from .models import StoreReview, Subscription
from django.core.validators import MinValueValidator, MaxValueValidator


class StoreReviewForm(forms.ModelForm):
    class Meta:
        model = StoreReview
        fields = ['rating', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={
                'rows': 5,
                'placeholder': 'Share your experience with this store...',
                'class': 'form-control'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['comment'].required = True
        self.fields['rating'].required = True

class SubscriptionPlanForm(forms.Form):
    """Form for selecting subscription plan"""
    PLAN_CHOICES = (
        ('basic', 'Basic - KSh 999/month'),
        ('premium', 'Premium - KSh 1,999/month'),
        ('enterprise', 'Enterprise - KSh 4,999/month'),
    )
    
    plan = forms.ChoiceField(
        choices=PLAN_CHOICES,
        widget=forms.RadioSelect,
        initial='basic'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['plan'].label = "Select Plan"



class CancelSubscriptionForm(forms.Form):
    """Form for cancelling subscription"""
    reason = forms.ChoiceField(
        choices=[
            ('too_expensive', 'Too expensive'),
            ('missing_features', 'Missing features'),
            ('not_using', 'Not using it enough'),
            ('poor_experience', 'Poor experience'),
            ('other', 'Other')
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    feedback = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': 'Optional feedback...'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['reason'].label = "Reason for cancelling"
        self.fields['feedback'].label = "Additional feedback"