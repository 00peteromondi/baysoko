# users/forms.py (updated)

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
import re
from .models import User

from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _

class CustomUserCreationForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'input-modern', 'placeholder': 'Create a strong password', 'autocomplete': 'new-password'}),
        help_text='Password must be at least 8 characters with letters and numbers.'
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={'class': 'input-modern', 'placeholder': 'Confirm your password', 'autocomplete': 'new-password'})
    )
    terms = forms.BooleanField(
        required=True,
        error_messages={'required': 'You must agree to the Terms of Service and Privacy Policy.'}
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'phone_number', 'location')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'input-modern', 'placeholder': 'Choose a username'}),
            'email': forms.EmailInput(attrs={'class': 'input-modern', 'placeholder': 'your.email@example.com'}),
            'first_name': forms.TextInput(attrs={'class': 'input-modern', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'input-modern', 'placeholder': 'Last name'}),
            'phone_number': forms.TextInput(attrs={'class': 'input-modern', 'placeholder': '+254 712 345 678'}),
            'location': forms.TextInput(attrs={'class': 'input-modern', 'placeholder': 'Your area in Homabay'}),
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
            'first_name': {'required': 'First name is required.', 'max_length': 'First name is too long.'},
            'last_name': {'required': 'Last name is required.', 'max_length': 'Last name is too long.'},
            'phone_number': {'required': 'Phone number is required.', 'max_length': 'Phone number is too long.'},
            'location': {'required': 'Location is required.', 'max_length': 'Location is too long.'},
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
        if email:
            email = email.lower().strip()
            if User.objects.filter(email__iexact=email).exists():
                raise ValidationError("This email is already registered.")
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            username = username.strip()
            if User.objects.filter(username__iexact=username).exists():
                raise ValidationError("This username is already taken.")
            if len(username) < 3:
                raise ValidationError("Username must be at least 3 characters.")
            if not re.match(r'^[\w.@+-]+$', username):
                raise ValidationError("Username can only contain letters, numbers, and @/./+/-/_ characters.")
        return username

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            phone_number = phone_number.strip()
            leading_plus = phone_number.startswith('+')
            digits = re.sub(r'[^0-9]', '', phone_number)
            phone_number = f"+{digits}" if leading_plus else digits
            if not re.match(r'^\+?[0-9]+$', phone_number):
                raise ValidationError("Please enter a valid phone number.")
            if User.objects.filter(phone_number=phone_number).exists():
                raise ValidationError("This phone number is already registered.")
        else:
            phone_number = None
        return phone_number

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', "Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        user.is_active = True   # User can log in but middleware will enforce email verification
        phone = self.cleaned_data.get('phone_number')
        user.phone_number = phone if phone else None
        if commit:
            user.save()
        return user

class EmailVerificationForm(forms.Form):
    code = forms.CharField(
        max_length=7,
        min_length=7,
        widget=forms.TextInput(attrs={
            'class': 'verification-input',
            'placeholder': '• • • • • • •',
            'autocomplete': 'off',
            'inputmode': 'numeric',
            'pattern': '[0-9]*'
        })
    )
    
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


class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        max_length=254,
        widget=forms.TextInput(attrs={'autofocus': True, 'class': 'input-modern'}),
        label=_('Email or Username')
    )

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        if username and password:
            user_qs = User.objects.none()
            if '@' in username:
                user_qs = User.objects.filter(email__iexact=username)
            if not user_qs.exists():
                user_qs = User.objects.filter(username__iexact=username)

            if user_qs.exists():
                user_obj = user_qs.first()
                user = authenticate(self.request, username=user_obj.username, password=password)
            else:
                user = authenticate(self.request, username=username, password=password)

            if user is None:
                raise forms.ValidationError(self.error_messages['invalid_login'], code='invalid_login')
            else:
                self.confirm_login_allowed(user)
                self.user_cache = user
        return self.cleaned_data