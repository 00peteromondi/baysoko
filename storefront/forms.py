from django import forms
from .models import Store
from listings.forms import ListingForm
from .mpesa import MpesaGateway


class UpgradeForm(forms.Form):
    phone_number = forms.CharField(max_length=32, required=True, label='Phone Number')

    def clean_phone_number(self):
        val = self.cleaned_data.get('phone_number')
        try:
            # Use the gateway normalizer to validate and canonicalize
            norm = MpesaGateway._normalize_phone(None, val)
            return norm
        except Exception as e:
            raise forms.ValidationError(str(e))


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
