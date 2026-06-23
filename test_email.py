#!/usr/bin/env python
"""
Test script to verify email functionality
"""
import os
import sys
import django

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(__file__))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'baysoko.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings

def test_email():
    print("🧪 Testing Email Configuration")
    print("=" * 50)
    print(f"DEBUG: {settings.DEBUG}")
    print(f"EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
    print(f"EMAIL_HOST: {settings.EMAIL_HOST}")
    print(f"EMAIL_PORT: {settings.EMAIL_PORT}")
    print(f"EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
    print(f"EMAIL_HOST_USER: {'SET' if settings.EMAIL_HOST_USER else 'NOT SET'}")
    print(f"EMAIL_HOST_PASSWORD: {'SET' if settings.EMAIL_HOST_PASSWORD else 'NOT SET'}")
    print(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
    print()

    try:
        print("📤 Sending test email...")
        result = send_mail(
            subject='Baysoko Email Test',
            message='This is a test email to verify email functionality.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=['test@example.com'],  # Change this to your email for testing
            fail_silently=False
        )
        print(f"✅ Email sent successfully! Result: {result}")
        print("📋 Check your Django console output (if using console backend) or email inbox (if using SMTP backend)")
    except Exception as e:
        print(f"❌ Email failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_email()