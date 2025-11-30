# listings/forms.py
from django import forms
from .models import Listing, Category, Review, Payment

class ListingForm(forms.ModelForm):
    # Remove the multiple images field from here for now
    # We'll handle multiple images in the view
    class Meta:
        model = Listing
        fields = ['title', 'description', 'price', 'category', 'store', 'location', 'image', 'condition', 'delivery_option', 'stock']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Enter a catchy title for your item'}),
            'price': forms.NumberInput(attrs={'min': '0', 'step': '0.01', 'placeholder': '0.00'}),
            'stock': forms.NumberInput(attrs={'min': '1', 'step': '1', 'placeholder': '1'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe your item in detail...'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'location': forms.Select(attrs={'class': 'form-select'}),
            'condition': forms.Select(attrs={'class': 'form-select'}),
            'delivery_option': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            # Cloudinary handles file validation, but you can add custom validation
            if hasattr(image, 'size') and image.size > 10 * 1024 * 1024:  # 10MB limit
                raise forms.ValidationError("Image file too large ( > 10MB )")
        return image

    def __init__(self, *args, **kwargs):
        # Accept an optional 'user' kwarg to limit the store choices
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Lazy-import Store to avoid circular imports
        try:
            from storefront.models import Store
        except Exception:
            Store = None

        # Add a store field as a ModelChoice limited to the current user's stores
        if Store:
            # Make the store field required when the user has at least one store.
            user_stores_qs = Store.objects.none()
            if user and user.is_authenticated:
                user_stores_qs = Store.objects.filter(owner=user)

            self.fields['store'] = forms.ModelChoiceField(
                queryset=user_stores_qs,
                required=(user_stores_qs.exists()),
                label='Store',
                help_text='Select which store/business this listing belongs to'
            )

class CheckoutForm(forms.Form):
    shipping_address = forms.CharField(
        max_length=200,
        widget=forms.Textarea(attrs={'rows': 3}),
        help_text="Where should we deliver your items?"
    )
    phone_number = forms.CharField(
        max_length=15,
        help_text="Your phone number for delivery updates"
    )
    
    first_name = forms.CharField(max_length=30,
        help_text="Your first name"

    )
    last_name = forms.CharField(max_length=30,
        help_text="Your last name"
    )
    email = forms.EmailField(
        help_text="Your email address"
    )
    city = forms.CharField(max_length=50,
        help_text="Your city"
    )
    postal_code = forms.CharField(max_length=20,
        help_text="Your postal code"
    )

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 4}),
        }