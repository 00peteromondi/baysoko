import requests
import json
from django.conf import settings
from django.core.cache import cache
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

TOKEN_CACHE_KEY = 'glovo_access_token'
TOKEN_TTL = 60 * 14  # 14 minutes to be safe


def get_glovo_access_token():
    """Obtain Glovo access token using client credentials and cache it."""
    token = cache.get(TOKEN_CACHE_KEY)
    if token:
        return token

    client_id = getattr(settings, 'GLOVO_CLIENT_ID', None)
    client_secret = getattr(settings, 'GLOVO_CLIENT_SECRET', None)
    if not client_id or not client_secret:
        raise RuntimeError('Glovo credentials not configured')

    url = getattr(settings, 'GLOVO_TOKEN_URL', 'https://glovo.partner.deliveryhero.io/v2/oauth/token')
    payload = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret
    }
    headers = {'Content-Type': 'application/json'}
    resp = requests.post(url, json=payload, headers=headers, timeout=10)
    if resp.status_code != 200:
        logger.error('Failed to get Glovo token: %s', resp.text)
        raise RuntimeError('Failed to obtain Glovo token')
    data = resp.json()
    token = data.get('access_token')
    expires_in = data.get('expires_in', TOKEN_TTL)
    cache.set(TOKEN_CACHE_KEY, token, timeout=min(TOKEN_TTL, int(expires_in) - 30 if expires_in else TOKEN_TTL))
    return token


def update_glovo_order_status(chain_id, vendor_id, order_id, status):
    """Update an order status in Glovo partner API."""
    token = get_glovo_access_token()
    url = f"https://glovo.partner.deliveryhero.io/v2/chains/{chain_id}/vendors/{vendor_id}/orders/{order_id}"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    payload = {'status': status}
    resp = requests.put(url, json=payload, headers=headers, timeout=10)
    if resp.status_code not in (200, 204):
        logger.error('Glovo update failed %s: %s', resp.status_code, resp.text)
        return False, resp.text
    return True, resp.text


def create_glovo_order(chain_id, vendor_id, order_payload):
    """Create a Glovo order for vendor via partner API.
    `order_payload` must follow Glovo's spec.
    """
    token = get_glovo_access_token()
    url = f"https://glovo.partner.deliveryhero.io/v2/chains/{chain_id}/vendors/{vendor_id}/orders"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    resp = requests.post(url, json=order_payload, headers=headers, timeout=10)
    if resp.status_code not in (200, 201):
        logger.error('Glovo create order failed %s: %s', resp.status_code, resp.text)
        return False, resp.text
    return True, resp.json()
