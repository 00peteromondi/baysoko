from django import forms
from allauth.socialaccount.forms import SignupForm
from .models import User
import logging

logger = logging.getLogger(__name__)

class CustomSocialSignupForm(SignupForm):
    first_name = forms.CharField(max_length=30, required=False, label='First Name')
    last_name = forms.CharField(max_length=30, required=False, label='Last Name')
    phone_number = forms.CharField(max_length=15, required=False, label='Phone Number')
    location = forms.CharField(max_length=100, required=True, label='Location', 
                              help_text="Your specific area in Homabay, e.g., Ndhiwa, Rodi Kopany")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Pre-fill data from social account if available
        if self.sociallogin:
            extra_data = self.sociallogin.account.extra_data
            provider = self.sociallogin.account.provider
            
            logger.info(f"Social login from {provider} with data: {extra_data}")
            
            if provider == 'google':
                self._populate_from_google(extra_data)
            elif provider == 'facebook':
                self._populate_from_facebook(extra_data)
            else:
                self._populate_generic(extra_data)

    def _populate_from_google(self, extra_data):
        """Populate form fields from Google OAuth data"""
        if extra_data:
            # Google provides given_name and family_name
            self.fields['first_name'].initial = extra_data.get('given_name', '')
            self.fields['last_name'].initial = extra_data.get('family_name', '')
            
            # Get email from extra_data or from the email field
            if 'email' in extra_data:
                self.fields['email'].initial = extra_data.get('email', '')

    def _populate_from_facebook(self, extra_data):
        """Populate form fields from Facebook OAuth data"""
        if extra_data:
            # Facebook provides first_name and last_name
            self.fields['first_name'].initial = extra_data.get('first_name', '')
            self.fields['last_name'].initial = extra_data.get('last_name', '')
            
            # Facebook might have name field as full name
            if 'name' in extra_data and not extra_data.get('first_name'):
                name_parts = extra_data.get('name', '').split(' ', 1)
                if len(name_parts) > 0:
                    self.fields['first_name'].initial = name_parts[0]
                if len(name_parts) > 1:
                    self.fields['last_name'].initial = name_parts[1]

    def _populate_generic(self, extra_data):
        """Generic population for other providers"""
        if extra_data:
            if 'given_name' in extra_data:
                self.fields['first_name'].initial = extra_data.get('given_name')
            if 'family_name' in extra_data:
                self.fields['last_name'].initial = extra_data.get('family_name')
            elif 'name' in extra_data:
                name_parts = extra_data.get('name', '').split(' ', 1)
                if len(name_parts) > 0:
                    self.fields['first_name'].initial = name_parts[0]
                if len(name_parts) > 1:
                    self.fields['last_name'].initial = name_parts[1]

    def save(self, request):
        user = super().save(request)
        
        # Update additional fields
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.phone_number = self.cleaned_data.get('phone_number', '')
        user.location = self.cleaned_data.get('location', 'Homabay')
        user.save()
        
        return user