from django import forms
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

class StoreForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = ['name', 'slug', 'description', 'is_premium', 'logo', 'cover_image']

    def clean_logo(self):
        logo = self.cleaned_data.get('logo')
        if logo:
            # Check if it's an image file
            if not hasattr(logo, 'content_type') or not logo.content_type.startswith('image/'):
                raise forms.ValidationError('Please upload a valid image file.')
            
            # Check file size (10MB limit)
            if logo.size > 10 * 1024 * 1024:  # 10MB
                raise forms.ValidationError('Image file is too large (>10MB)')
            
            # Additional image validation could go here
            try:
                from PIL import Image
                img = Image.open(logo)
                img.verify()  # Verify it's a valid image
                
                # Check dimensions
                if img.width > 4000 or img.height > 4000:
                    raise forms.ValidationError('Image dimensions are too large (max 4000x4000)')
                    
            except Exception as e:
                raise forms.ValidationError('Invalid image file. Please try another file.')
                
        return logo

    def clean_cover_image(self):
        cover_image = self.cleaned_data.get('cover_image')
        if cover_image:
            # Check if it's an image file
            if not hasattr(cover_image, 'content_type') or not cover_image.content_type.startswith('image/'):
                raise forms.ValidationError('Please upload a valid image file.')
            
            # Check file size (10MB limit)
            if cover_image.size > 10 * 1024 * 1024:  # 10MB
                raise forms.ValidationError('Image file is too large (>10MB)')
            
            # Additional image validation
            try:
                from PIL import Image
                img = Image.open(cover_image)
                img.verify()  # Verify it's a valid image
                
                # Check dimensions
                if img.width > 4000 or img.height > 4000:
                    raise forms.ValidationError('Image dimensions are too large (max 4000x4000)')
                    
            except Exception as e:
                raise forms.ValidationError('Invalid image file. Please try another file.')


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