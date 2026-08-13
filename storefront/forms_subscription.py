# storefront/forms_subscription.py
from django import forms
from django.core.validators import RegexValidator

class SubscriptionPlanForm(forms.Form):
    PLAN_CHOICES = (
        ('basic', 'Basic - KSh 999/month'),
        ('premium', 'Premium - KSh 1,999/month'),
        ('enterprise', 'Enterprise - KSh 4,999/month'),
    )
    
    plan = forms.ChoiceField(
        choices=PLAN_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'plan-radio'}),
        initial='premium'
    )

class PhoneNumberForm(forms.Form):
    phone_regex = RegexValidator(
        regex=r'^[0-9]{9}$',
        message="Phone number must be 9 digits without +254 (e.g., 712345678)"
    )
    
    phone_number = forms.CharField(
        max_length=9,
        validators=[phone_regex],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '712345678',
            'pattern': '[0-9]{9}',
        }),
        help_text="Enter your M-Pesa registered phone number (without +254)"
    )
    
    terms = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="I agree to start a 7-day free trial. After trial, I'll be charged monthly. I can cancel anytime."
    )