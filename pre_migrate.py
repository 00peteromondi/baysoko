#!/usr/bin/env python
"""
Script to run before migrations to ensure proper environment setup
"""
import os
import sys

# Set minimal environment for migrations
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'homabay_souq.settings')

# If no SECRET_KEY is set, generate one for migrations only
if not os.environ.get('SECRET_KEY'):
    from django.core.management.utils import get_random_secret_key
    os.environ['SECRET_KEY'] = get_random_secret_key()
    print("⚠️  Generated temporary SECRET_KEY for migrations")

print("✅ Environment ready for migrations")