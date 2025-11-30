from django import forms
from allauth.socialaccount.forms import SignupForm
from .models import User

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