#!/usr/bin/env python
"""
Emergency database configuration override
"""
import os
import django
from django.conf import settings

# Force PostgreSQL configuration
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'homabay_souq.settings')

# Hardcoded configuration for Render
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'baysoko2',
        'USER': 'baysoko2_user',
        'PASSWORD': 'Da8a4VMjdk7X0QOuJtBxtZs3Q4ym7VzG',
        'HOST': 'dpg-d5gd8m7pm1nc73e44la0-a',
        'PORT': '5432',
        'CONN_MAX_AGE': 600,
    }
}

print("🚨 USING EMERGENCY DATABASE CONFIGURATION")