#!/usr/bin/env python
import os
import sys

# Run from project root: .venv\Scripts\python.exe scripts\set_homabay_secret.py

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'baysoko.settings')

import django
django.setup()

from delivery.integration.models import EcommercePlatform

TEST_SECRET = "Lr4J9pR2sX8vY7qW1tZ5uM3nB6cV0dG8h"

def set_secret():
    try:
        platform = EcommercePlatform.objects.get(platform_type='baysoko')
    except EcommercePlatform.DoesNotExist:
        try:
            platform = EcommercePlatform.objects.get(name__icontains='homabay')
        except EcommercePlatform.DoesNotExist:
            print('No HomaBay platform record found. Aborting.')
            return 1

    platform.webhook_secret = TEST_SECRET
    platform.save(update_fields=['webhook_secret'])
    print(f"Updated platform id={platform.id} name={platform.name} webhook_secret set")
    return 0

if __name__ == '__main__':
    sys.exit(set_secret())
