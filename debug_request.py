import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'baysoko.settings')
import sys

django.setup()
from django.test import Client
from django.urls import reverse

c = Client()
resp = c.get(reverse('storefront:seller_analytics'))
print('status:', resp.status_code)
print('location header:', resp.get('Location'))
print('headers:', dict(resp.items()))
print('content:', resp.content[:2000])
