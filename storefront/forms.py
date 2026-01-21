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
        # Accept 'user' kwarg and remove it before calling parent
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Make logo and cover_image fields optional for editing
        if self.instance and self.instance.pk:
            self.fields['logo'].required = False
            self.fields['cover_image'].required = False
            
        # Initialize these attributes
        self.can_be_featured = False
        self.is_enterprise = False
        
        # Only check for existing stores (edit mode)
        if self.instance and self.instance.pk:
            # Check if store has active subscription or valid trial
            try:
                has_active = Subscription.objects.filter(
                    store=self.instance, 
                    status='active'
                ).exists()
                has_valid_trial = Subscription.objects.filter(
                    store=self.instance,
                    status='trialing',
                    trial_ends_at__gt=timezone.now()
                ).exists()
                
                self.can_be_featured = has_active or has_valid_trial
                
                if self.can_be_featured:
                    # Check if it's an enterprise subscription
                    self.is_enterprise = Subscription.objects.filter(
                        store=self.instance,
                        status='active',
                        plan='enterprise'
                    ).exists()
                    
                    # Add is_featured field for premium stores
                    self.fields['is_featured'] = forms.BooleanField(
                        required=False,
                        label='Featured Store',
                        help_text='Check to feature your store in listings',
                        widget=forms.CheckboxInput(attrs={
                            'class': 'form-check-input',
                            'disabled': self.is_enterprise
                        }),
                        initial=self.instance.is_featured,
                        disabled=self.is_enterprise
                    )
            except Exception as e:
                # If there's an error (e.g., subscription table doesn't exist yet), 
                # just don't add the featured field
                pass
    
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
        
        return cleaned_data
    
    def save(self, commit=True):
        # Get the unsaved store instance
        store = super().save(commit=False)
        
        # For new stores, ensure is_featured is False
        if not store.pk:
            store.is_featured = False
        else:
            # For existing stores, handle is_featured if the field exists
            if 'is_featured' in self.cleaned_data and hasattr(self, 'can_be_featured'):
                if not self.can_be_featured:
                    # Non-premium users can't set featured
                    store.is_featured = False
                elif hasattr(self, 'is_enterprise') and self.is_enterprise:
                    # Enterprise stores are always featured
                    store.is_featured = True
                else:
                    # Regular premium store - use the value from the form
                    store.is_featured = self.cleaned_data.get('is_featured', False)
        
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