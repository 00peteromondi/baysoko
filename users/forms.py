# users/forms.py - Updated with better validation
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
import re
from .models import User

class CustomUserCreationForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'input-modern',
            'placeholder': 'Create a strong password',
            'autocomplete': 'new-password'
        }),
        help_text='Password must be at least 8 characters with letters and numbers.'
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'input-modern',
            'placeholder': 'Confirm your password',
            'autocomplete': 'new-password'
        })
    )
    terms = forms.BooleanField(
        required=True,
        error_messages={'required': 'You must agree to the Terms of Service and Privacy Policy.'}
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'phone_number', 'location')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'input-modern',
                'placeholder': 'Choose a username'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'input-modern',
                'placeholder': 'your.email@example.com'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'input-modern',
                'placeholder': 'First name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'input-modern',
                'placeholder': 'Last name'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'input-modern',
                'placeholder': '+254 712 345 678'
            }),
            'location': forms.TextInput(attrs={
                'class': 'input-modern',
                'placeholder': 'Your area in Homabay'
            }),
        }
        error_messages = {
            'username': {
                'required': 'Username is required.',
                'unique': 'This username is already taken.',
                'max_length': 'Username is too long.',
            },
            'email': {
                'required': 'Email address is required.',
                'unique': 'This email is already registered.',
                'invalid': 'Please enter a valid email address.',
            },
            'first_name': {
                'required': 'First name is required.',
                'max_length': 'First name is too long.',
            },
            'last_name': {
                'required': 'Last name is required.',
                'max_length': 'Last name is too long.',
            },
            'location': {
                'required': 'Location is required.',
                'max_length': 'Location is too long.',
            },
        }

    def clean_password1(self):
        password1 = self.cleaned_data.get('password1')
        if len(password1) < 8:
            raise ValidationError("Password must be at least 8 characters long.")
        if not re.search(r'\d', password1):
            raise ValidationError("Password must contain at least one digit.")
        if not re.search(r'[a-zA-Z]', password1):
            raise ValidationError("Password must contain at least one letter.")
        return password1

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:  # Check if email is not None or empty
            # Normalize the email
            email = email.lower().strip()
            
            # Check if user exists (case-insensitive)
            if User.objects.filter(email__iexact=email).exists():
                raise ValidationError("This email is already registered.")
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            # Remove whitespace and normalize
            username = username.strip()
            
            # Check if username exists (case-insensitive)
            if User.objects.filter(username__iexact=username).exists():
                raise ValidationError("This username is already taken.")
            
            # Check length after trimming
            if len(username) < 3:
                raise ValidationError("Username must be at least 3 characters.")
                
            # Optional: Add username format validation
            if not re.match(r'^[\w.@+-]+$', username):
                raise ValidationError("Username can only contain letters, numbers, and @/./+/-/_ characters.")
        
        return username

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            # Basic phone number validation
            phone_number = phone_number.strip()
            if not re.match(r'^\+?[\d\s\-\(\)]+$', phone_number):
                raise ValidationError("Please enter a valid phone number.")
        return phone_number

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        # Only validate if both fields are present
        if password1 and password2:
            if password1 != password2:
                self.add_error('password2', "Passwords do not match.")
        
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user
    
class CustomUserChangeForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            'first_name', 
            'last_name', 
            'username', 
            'email', 
            'phone_number', 
            'bio', 
            'profile_picture',
            'cover_photo',
            'show_contact_info'
        ]
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'maxlength': 500}),
            'profile_picture': forms.FileInput(attrs={'accept': 'image/*'}),
            'cover_photo': forms.FileInput(attrs={'accept': 'image/*'}),
        }

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('This username is already taken.')
        return username
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('This email is already registered.')
        return email