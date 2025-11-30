from django.conf import settings
import requests
import base64
from datetime import datetime
import json
import re


class MpesaGateway:
    """
    Handles M-Pesa payment integration
    """
    def __init__(self):
        self.consumer_key = settings.MPESA_CONSUMER_KEY
        self.consumer_secret = settings.MPESA_CONSUMER_SECRET
        self.business_shortcode = settings.MPESA_BUSINESS_SHORTCODE
        self.passkey = settings.MPESA_PASSKEY
        self.callback_url = settings.MPESA_CALLBACK_URL
        self.env = settings.MPESA_ENVIRONMENT

    def get_token(self):
        """Get OAuth token for API calls"""
        if self.env == "sandbox":
            api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
        else:
            api_url = "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"

        auth = base64.b64encode(f"{self.consumer_key}:{self.consumer_secret}".encode()).decode()
        headers = {"Authorization": f"Basic {auth}"}

        try:
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()  # Raises an HTTPError for bad responses
            return response.json()["access_token"]
        except Exception as e:
            raise Exception(f"Failed to get access token: {str(e)}")

    def initiate_stk_push(self, phone, amount, account_reference):
        """
        Initiate STK Push payment
        """
        if self.env == "sandbox":
            api_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
        else:
            api_url = "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"

        # Normalize phone number to format required by M-Pesa: 2547XXXXXXXX
        phone_normalized = self._normalize_phone(phone)

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password = base64.b64encode(
            f"{self.business_shortcode}{self.passkey}{timestamp}".encode()
        ).decode()

        headers = {
            "Authorization": f"Bearer {self.get_token()}",
            "Content-Type": "application/json",
        }

        payload = {
            "BusinessShortCode": self.business_shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": phone_normalized,
            "PartyB": self.business_shortcode,
            "PhoneNumber": phone_normalized,
            "CallBackURL": self.callback_url,
            "AccountReference": account_reference,
            "TransactionDesc": "Store Premium Subscription"
        }

        try:
            response = requests.post(api_url, json=payload, headers=headers)
            if response.status_code != 200:
                # Try to include useful details from the response body
                error_msg = f"STK push failed with status {response.status_code}"
                try:
                    error_detail = response.json()
                    # Safely extract known fields
                    err = error_detail.get('errorMessage') or error_detail.get('error') or json.dumps(error_detail)
                    error_msg += f": {err}"
                except Exception:
                    error_msg += f": {response.text}"
                raise Exception(error_msg)
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"STK push failed: {str(e)}")
        except Exception as e:
            raise Exception(f"STK push failed: {str(e)}")

    def _normalize_phone(self, phone):
        """Normalize and validate phone numbers into the format required by M-Pesa.

        Accepted inputs: '07XXXXXXXX', '7XXXXXXXX', '+2547XXXXXXXX', '2547XXXXXXXX'
        Output: '2547XXXXXXXX' (12 digits)
        Raises ValueError for invalid formats.
        """
        if phone is None:
            raise ValueError("Phone number is required")

        s = str(phone).strip()
        # Remove common separators
        s = re.sub(r"[^0-9+]", "", s)

        # Remove leading + if present
        if s.startswith('+'):
            s = s[1:]

        # If starts with 0 and has 10 digits (e.g., 07xxxxxxxx), convert to 2547xxxxxxx
        if s.startswith('0') and len(s) == 10:
            s = '254' + s[1:]
        # If starts with 7 and has 9 digits (e.g., 7xxxxxxxx), convert to 2547xxxxxxx
        elif s.startswith('7') and len(s) == 9:
            s = '254' + s
        # If starts with 254 and has 12 digits, assume valid
        elif s.startswith('254') and len(s) == 12:
            pass
        else:
            # Last resort: if numeric and 12 digits, accept
            if s.isdigit() and len(s) == 12:
                pass
            else:
                raise ValueError(
                    "Invalid phone number format. Provide 07..., 7..., +254..., or 254... (example: 254712345678)"
                )

        # Final sanity check
        if not (s.isdigit() and len(s) == 12 and s.startswith('254')):
            raise ValueError("Normalized phone number must be 12 digits starting with '254'")

        return s

    def verify_transaction(self, checkout_request_id):
        """
        Verify transaction status using checkout request ID
        """
        if self.env == "sandbox":
            api_url = "https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query"
        else:
            api_url = "https://api.safaricom.co.ke/mpesa/stkpushquery/v1/query"

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password = base64.b64encode(
            f"{self.business_shortcode}{self.passkey}{timestamp}".encode()
        ).decode()

        headers = {
            "Authorization": f"Bearer {self.get_token()}",
            "Content-Type": "application/json",
        }

        payload = {
            "BusinessShortCode": self.business_shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id
        }

        try:
            response = requests.post(api_url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"Transaction verification failed: {str(e)}")