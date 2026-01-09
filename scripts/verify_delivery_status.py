#!/usr/bin/env python
"""Quick script to verify the delivery-status API for a test order.

Usage:
  python scripts/verify_delivery_status.py [TRACKING_NUMBER]

If TRACKING_NUMBER is omitted the script will try to find any order with a tracking_number.
This script sets HTTP_HOST='localhost' and follows redirects to avoid DisallowedHost/301 issues seen in test client runs.
"""
import os
import sys
import json
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'homabay_souq.settings')
# Ensure project root is in sys.path when script is run directly
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import django
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from listings.models import Order

User = get_user_model()

def main():
    tracking = sys.argv[1] if len(sys.argv) > 1 else None

    # Find an order
    order = None
    if tracking:
        order = Order.objects.filter(tracking_number=tracking).first()
    else:
        order = Order.objects.filter(tracking_number__isnull=False).first()

    if not order:
        print('No order found with a tracking number.')
        sys.exit(1)

    print(f'Using order id={order.id} tracking={order.tracking_number} delivery_status={order.delivery_status}')

    # Ensure a user owns the order (use existing or create a temp user)
    user = order.user
    if not user:
        # pick any user or create testbuyer
        user = User.objects.filter(is_active=True).first()
        if not user:
            user = User.objects.create_user('verify_buyer', 'verify@example.com', 'verify123')
        order.user = user
        order.save()

    # Use Django test client to make a request authenticated as the user
    client = Client()
    # set host to localhost
    logged = client.force_login(user) if hasattr(client, 'force_login') else client.login(username=user.username, password='')
    # perform GET and follow redirects
    url = f'/api/orders/{order.tracking_number}/delivery-status/'
    print('Requesting', url)
    resp = client.get(url, HTTP_HOST='localhost', follow=True)

    print('HTTP status:', resp.status_code)
    content_type = resp.headers.get('Content-Type') if hasattr(resp, 'headers') else resp['Content-Type'] if 'Content-Type' in resp else None
    print('Content-Type:', content_type)

    body = resp.content.decode('utf-8')
    # Try to parse JSON
    try:
        data = json.loads(body)
        print('JSON response:')
        print(json.dumps(data, indent=2))
    except Exception:
        print('Non-JSON response body:')
        print(body[:1000])

if __name__ == '__main__':
    main()
