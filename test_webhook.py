import os
import requests
import json
import hashlib
import hmac
from datetime import datetime
from pathlib import Path

def test_webhook():
    """Test webhook integration"""
    webhook_url = "http://localhost:8000/api/delivery-webhook/"
    # Prefer environment variable so it matches Django settings in tests
    secret = os.environ.get('DELIVERY_WEBHOOK_SECRET')
    if not secret:
        # Fallback: parse the project's .env file if present
        env_path = Path(__file__).resolve().parents[0] / '.env'
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line.startswith('DELIVERY_WEBHOOK_SECRET'):
                    _, val = line.split('=', 1)
                    val = val.split('#', 1)[0].strip()
                    if (val.startswith("'") and val.endswith("'")) or (val.startswith('"') and val.endswith('"')):
                        val = val[1:-1]
                    secret = val
                    break
    if not secret:
        secret = 'your-test-secret'
    
    # Create test payload
    payload = {
        "event": "delivery_out_for_delivery",
        "order_id": 1,  # Use an existing order ID
        "tracking_number": "TEST123456",
        "timestamp": datetime.now().isoformat()
    }
    
    # Create the JSON string exactly as we'll send it, then sign that string
    payload_str = json.dumps(payload, separators=(',', ':'), ensure_ascii=False, sort_keys=True)
    signature = hmac.new(secret.encode('utf-8'), payload_str.encode('utf-8'), hashlib.sha256).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": signature
    }

    # Print payload and signature for debugging so it's easy to compare with server logs
    print('PAYLOAD_BODY:')
    print(payload_str)
    print('\nSENDING_SIGNATURE:')
    print(signature)

    # Send the exact string in the request body so signature matches
    response = requests.post(webhook_url, data=payload_str.encode('utf-8'), headers=headers)
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code == 200:
        print("✅ Webhook receiver working!")
    else:
        print("❌ Webhook test failed")

if __name__ == "__main__":
    test_webhook()