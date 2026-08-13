from django import forms
from .models import NotificationPreference

class NotificationPreferenceForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = [
            'email_messages', 'email_orders', 'email_reviews', 'email_promotional',
            'push_messages', 'push_orders', 'push_reviews', 'push_system',
            'digest_frequency'
        ]
        widgets = {
            'digest_frequency': forms.RadioSelect(choices=[
                ('instant', 'Instant - Notify me immediately'),
                ('daily', 'Daily Digest - Once per day'),
                ('weekly', 'Weekly Digest - Once per week'),
            ])
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add CSS classes to checkboxes
        for field_name in self.fields:
            if isinstance(self.fields[field_name].widget, forms.CheckboxInput):
                self.fields[field_name].widget.attrs['class'] = 'form-check-input'