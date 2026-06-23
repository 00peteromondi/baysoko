from django.conf import settings
import requests
import base64
from datetime import datetime
import json
import re
import logging
import time

logger = logging.getLogger(__name__)


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
            if response.status_code != 200:
                # Log response for debugging (do not log secret values)
                try:
                    body = response.json()
                except Exception:
                    body = response.text
                logger.error("MPESA token request failed: status=%s body=%s", response.status_code, body)
                raise Exception(f"Failed to get access token: status={response.status_code} body={body}")

            data = response.json()
            return data.get("access_token")
        except Exception as e:
            logger.exception("Error obtaining MPESA access token")
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

        # Prepare payload
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

        # Build headers lazily to avoid failing token retrieval from stopping retry logic
        try:
            token = self.get_token()
        except Exception as e:
            logger.exception('Failed to obtain MPESA token before STK push')
            raise

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # Retry policy: respect configured env vars if present
        max_retries = getattr(__import__('django.conf').conf.settings, 'MPESA_MAX_RETRIES', None) or getattr(__import__('os'), 'environ', {}).get('MPESA_MAX_RETRIES')
        try:
            max_retries = int(max_retries) if max_retries is not None else 3
        except Exception:
            max_retries = 3

        retry_interval = getattr(__import__('django.conf').conf.settings, 'MPESA_RETRY_INTERVAL', None) or getattr(__import__('os'), 'environ', {}).get('MPESA_RETRY_INTERVAL')
        try:
            retry_interval = int(retry_interval) if retry_interval is not None else 2
        except Exception:
            retry_interval = 2

        timeout = getattr(__import__('django.conf').conf.settings, 'MPESA_REQUEST_TIMEOUT', None) or 10
        attempt = 0
        last_exc = None
        while attempt <= max_retries:
            attempt += 1
            try:
                logger.debug('Initiating STK push attempt %s to %s for phone=%s amount=%s', attempt, api_url, phone_normalized, amount)
                resp = requests.post(api_url, json=payload, headers=headers, timeout=timeout)
                logger.debug('STK push response status=%s', getattr(resp, 'status_code', None))
                if 200 <= resp.status_code < 300:
                    try:
                        return resp.json()
                    except Exception:
                        return {'status_code': resp.status_code, 'text': resp.text}

                # For client errors, do not retry
                if 400 <= resp.status_code < 500:
                    try:
                        err = resp.json()
                    except Exception:
                        err = resp.text
                    error_msg = f"STK push failed with status {resp.status_code}: {err}"
                    logger.warning(error_msg)
                    raise Exception(error_msg)

                # For server errors (5xx), raise and retry
                try:
                    err = resp.json()
                except Exception:
                    err = resp.text
                logger.warning('STK push server error (attempt %s): status=%s body=%s', attempt, resp.status_code, err)
                last_exc = Exception(f"STK push failed with status {resp.status_code}: {err}")

            except requests.exceptions.Timeout as e:
                logger.warning('STK push attempt %s timed out: %s', attempt, e)
                last_exc = e
            except requests.exceptions.SSLError as e:
                logger.exception('STK push SSL error on attempt %s', attempt)
                last_exc = e
                break
            except requests.exceptions.RequestException as e:
                logger.warning('STK push request exception on attempt %s: %s', attempt, e)
                last_exc = e

            # If we have exhausted attempts, break
            if attempt > max_retries:
                break

            # Backoff before next retry
            sleep_for = retry_interval * attempt
            logger.debug('Waiting %s seconds before next STK push attempt', sleep_for)
            time.sleep(sleep_for)

        # After retries exhausted
        if last_exc:
            raise Exception(f"STK push failed after {attempt} attempts: {str(last_exc)}")
        raise Exception('STK push failed: unknown error')

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