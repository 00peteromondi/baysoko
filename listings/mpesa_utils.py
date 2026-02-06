# listings/mpesa_utils.py
import requests
import base64
from datetime import datetime
import json
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class MpesaGateway:
    """
    Unified M-Pesa Gateway for both sandbox and production environments.
    Automatically detects environment from settings and routes requests accordingly.
    Supports automatic retries and fallback to simulation mode if credentials missing.
    """
    
    def __init__(self):
        self.consumer_key = getattr(settings, 'MPESA_CONSUMER_KEY', '')
        self.consumer_secret = getattr(settings, 'MPESA_CONSUMER_SECRET', '')
        self.business_shortcode = getattr(settings, 'MPESA_BUSINESS_SHORTCODE', '174379')
        self.passkey = getattr(settings, 'MPESA_PASSKEY', '')
        self.callback_url = getattr(settings, 'MPESA_CALLBACK_URL', '')
        self.environment = getattr(settings, 'MPESA_ENVIRONMENT', 'sandbox').lower()
        self.max_retries = getattr(settings, 'MPESA_MAX_RETRIES', 3)
        
        # Validate environment setting
        if self.environment not in ['sandbox', 'production']:
            logger.warning(f"Invalid MPESA_ENVIRONMENT '{self.environment}', defaulting to 'sandbox'")
            self.environment = 'sandbox'
        
        # Check if we have valid credentials
        self.has_valid_credentials = all([
            self.consumer_key,
            self.consumer_secret, 
            self.passkey,
            self.callback_url
        ])
        
        # Set base URLs based on environment
        if self.environment == 'sandbox':
            self.base_url = 'https://sandbox.safaricom.co.ke'
            self.oauth_url = 'https://sandbox.safaricom.co.ke/oauth/v1/generate'
        else:  # production
            self.base_url = 'https://api.safaricom.co.ke'
            self.oauth_url = 'https://api.safaricom.co.ke/oauth/v1/generate'
        
        logger.info(f"M-Pesa Gateway initialized: environment={self.environment}, credentials={'configured' if self.has_valid_credentials else 'MISSING'}")
    
    def _normalize_phone(self, phone_number):
        """Normalize phone number to 2547XXXXXXXX format"""
        # Remove any non-digit characters
        cleaned = ''.join(filter(str.isdigit, str(phone_number)))
        
        # Handle different formats
        if cleaned.startswith('0'):
            return '254' + cleaned[1:]
        elif cleaned.startswith('254'):
            return cleaned
        elif cleaned.startswith('+254'):
            return cleaned[1:]
        elif len(cleaned) == 9:
            return '254' + cleaned
        else:
            # Assume it's already in correct format
            return cleaned
    
    def get_access_token(self):
        """Get OAuth access token from Safaricom API with retry logic"""
        if not self.has_valid_credentials:
            logger.warning(f"M-Pesa credentials not configured. Running in simulation mode for {self.environment}.")
            return "simulation_token"
        
        for attempt in range(self.max_retries):
            try:
                auth_string = f"{self.consumer_key}:{self.consumer_secret}"
                encoded_auth = base64.b64encode(auth_string.encode()).decode()
                
                headers = {
                    'Authorization': f'Basic {encoded_auth}',
                    'Cache-Control': 'no-cache'
                }
                # Debug: log request metadata (non-sensitive)
                logger.debug(f"[MPESA DEBUG] Token request prepared: url={self.oauth_url}, method=GET, auth_header_present={'Authorization' in headers}, consumer_key_set={bool(self.consumer_key)}, consumer_secret_set={bool(self.consumer_secret)}")
                
                response = requests.get(
                    self.oauth_url,
                    headers=headers,
                    timeout=30,
                    verify=True
                )
                
                if response.status_code == 200:
                    data = response.json()
                    access_token = data.get('access_token')
                    if access_token:
                        logger.info(f"[{self.environment.upper()}] Successfully obtained M-Pesa access token (attempt {attempt + 1})")
                        return access_token
                    else:
                        logger.error(f"[{self.environment.upper()}] No access token in response: {data}")
                        if attempt < self.max_retries - 1:
                            logger.info(f"Retrying token acquisition... (attempt {attempt + 2}/{self.max_retries})")
                            continue
                        return None
                else:
                    logger.error(f"[{self.environment.upper()}] M-Pesa API Error {response.status_code}: {response.text}")
                    if attempt < self.max_retries - 1:
                        logger.info(f"Retrying token acquisition... (attempt {attempt + 2}/{self.max_retries})")
                        continue
                    return None
                    
            except requests.exceptions.Timeout:
                logger.error(f"[{self.environment.upper()}] Token request timeout (attempt {attempt + 1})")
                if attempt < self.max_retries - 1:
                    continue
                return None
            except requests.exceptions.RequestException as e:
                logger.error(f"[{self.environment.upper()}] Network error getting token: {str(e)} (attempt {attempt + 1})")
                if attempt < self.max_retries - 1:
                    continue
                return None
            except Exception as e:
                logger.error(f"[{self.environment.upper()}] Unexpected error getting access token: {str(e)} (attempt {attempt + 1})")
                if attempt < self.max_retries - 1:
                    continue
                return None
        
        logger.error(f"[{self.environment.upper()}] Failed to get access token after {self.max_retries} attempts")
        return None
    
    def generate_password(self, timestamp):
        """Generate Lipa Na M-Pesa Online Password"""
        data_to_encode = f"{self.business_shortcode}{self.passkey}{timestamp}"
        encoded_string = base64.b64encode(data_to_encode.encode()).decode()
        return encoded_string
    
    def initiate_stk_push(self, phone, amount, account_reference, transaction_desc="Payment"):
        """
        Initiate STK Push to customer.
        Works for both sandbox and production based on settings.
        Returns dict with success status and checkout details.
        """
        # Normalize phone number
        phone_number = self._normalize_phone(phone)
        
        # If no valid credentials, simulate success for development
        if not self.has_valid_credentials:
            logger.info(f"[{self.environment.upper()}] Simulating M-Pesa STK Push (no valid credentials)")
            return self._simulate_stk_push(phone_number, amount)
        
        for attempt in range(self.max_retries):
            try:
                access_token = self.get_access_token()
                if not access_token:
                    error_msg = 'Could not authenticate with M-Pesa API. Please check your credentials.'
                    logger.error(f"[{self.environment.upper()}] {error_msg}")
                    return {'success': False, 'error': error_msg}
                
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                password = self.generate_password(timestamp)
                
                url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
                
                payload = {
                    "BusinessShortCode": self.business_shortcode,
                    "Password": password,
                    "Timestamp": timestamp,
                    "TransactionType": "CustomerPayBillOnline",
                    "Amount": int(amount),
                    "PartyA": phone_number,
                    "PartyB": self.business_shortcode,
                    "PhoneNumber": phone_number,
                    "CallBackURL": self.callback_url,
                    "AccountReference": str(account_reference)[:12],  # Max 12 chars
                    "TransactionDesc": str(transaction_desc)[:13]  # Max 13 chars
                }
                
                headers = {
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json'
                }
                
                logger.info(f"[{self.environment.upper()}] Sending STK Push request for {phone_number} (KSh {amount}) (attempt {attempt + 1})")
                
                response = requests.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=30,
                    verify=True
                )
                response_data = response.json()
                
                logger.info(f"[{self.environment.upper()}] STK Push response: {response_data}")
                
                if response.status_code == 200:
                    if response_data.get('ResponseCode') == '0':
                        logger.info(f"[{self.environment.upper()}] STK Push initiated successfully for {phone_number}")
                        return {
                            'success': True,
                            'checkout_request_id': response_data.get('CheckoutRequestID'),
                            'merchant_request_id': response_data.get('MerchantRequestID'),
                            'response_code': response_data.get('ResponseCode'),
                            'response_description': response_data.get('ResponseDescription'),
                            'environment': self.environment
                        }
                    else:
                        error_msg = response_data.get('ResponseDescription', 'Unknown error from M-Pesa')
                        logger.error(f"[{self.environment.upper()}] M-Pesa STK Push failed: {error_msg}")
                        if attempt < self.max_retries - 1:
                            logger.info(f"Retrying STK push... (attempt {attempt + 2}/{self.max_retries})")
                            continue
                        return {'success': False, 'error': error_msg}
                else:
                    error_msg = f"HTTP {response.status_code}: {response_data.get('errorMessage', 'Unknown error')}"
                    logger.error(f"[{self.environment.upper()}] M-Pesa API error: {error_msg}")
                    if attempt < self.max_retries - 1:
                        logger.info(f"Retrying STK push... (attempt {attempt + 2}/{self.max_retries})")
                        continue
                    return {'success': False, 'error': error_msg}
                    
            except requests.exceptions.Timeout:
                error_msg = "M-Pesa API request timed out"
                logger.error(f"[{self.environment.upper()}] {error_msg} (attempt {attempt + 1})")
                if attempt < self.max_retries - 1:
                    continue
                return {'success': False, 'error': error_msg}
            except requests.exceptions.RequestException as e:
                error_msg = f"Network error: {str(e)}"
                logger.error(f"[{self.environment.upper()}] {error_msg} (attempt {attempt + 1})")
                if attempt < self.max_retries - 1:
                    continue
                return {'success': False, 'error': error_msg}
            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                logger.error(f"[{self.environment.upper()}] {error_msg} (attempt {attempt + 1})")
                if attempt < self.max_retries - 1:
                    continue
                return {'success': False, 'error': error_msg}
        
        return {'success': False, 'error': f'Failed to initiate STK push after {self.max_retries} attempts'}
    
    def _simulate_stk_push(self, phone_number, amount):
        """Simulate successful STK push for development"""
        import time
        timestamp = int(time.time())
        logger.info(f"[SIMULATION] STK Push simulation: {phone_number} - KSh {amount}")
        return {
            'success': True,
            'checkout_request_id': f'ws_CO_{timestamp}_{int(amount)}',
            'merchant_request_id': f'MARQ-{timestamp}',
            'response_code': '0',
            'response_description': 'Success. Request accepted for processing [SIMULATION]',
            'environment': self.environment
        }
    
    def format_phone_number(self, phone_number):
        """Format phone number to 2547XXXXXXXX format (backward compatibility)"""
        return self._normalize_phone(phone_number)
    
    def check_transaction_status(self, checkout_request_id):
        """Check status of a transaction with retry logic"""
        if not self.has_valid_credentials:
            # In simulation, return pending status
            logger.info(f"[SIMULATION] Checking transaction status for {checkout_request_id}")
            return {
                'success': True,
                'result_code': '0',
                'result_desc': 'The service request has been accepted successfully [SIMULATION]',
                'checkout_request_id': checkout_request_id
            }
        
        for attempt in range(self.max_retries):
            try:
                access_token = self.get_access_token()
                if not access_token:
                    return {'success': False, 'error': 'Could not get access token'}
                
                url = f"{self.base_url}/mpesa/stkpushquery/v1/query"
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                password = self.generate_password(timestamp)
                
                payload = {
                    "BusinessShortCode": self.business_shortcode,
                    "Password": password,
                    "Timestamp": timestamp,
                    "CheckoutRequestID": checkout_request_id
                }
                
                headers = {
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json'
                }
                
                logger.info(f"[{self.environment.upper()}] Checking transaction status for {checkout_request_id} (attempt {attempt + 1})")
                
                response = requests.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=30,
                    verify=True
                )
                response_data = response.json()
                
                if response.status_code == 200:
                    logger.info(f"[{self.environment.upper()}] Status query response: {response_data}")
                    return {
                        'success': True,
                        'result_code': response_data.get('ResultCode'),
                        'result_desc': response_data.get('ResultDesc'),
                        'response_data': response_data,
                        'checkout_request_id': checkout_request_id
                    }
                else:
                    error_msg = f"HTTP {response.status_code}: {response_data.get('errorMessage', 'Unknown error')}"
                    logger.error(f"[{self.environment.upper()}] Status check error: {error_msg} (attempt {attempt + 1})")
                    if attempt < self.max_retries - 1:
                        logger.info(f"Retrying status check... (attempt {attempt + 2}/{self.max_retries})")
                        continue
                    return {'success': False, 'error': error_msg}
                    
            except requests.exceptions.Timeout:
                logger.error(f"[{self.environment.upper()}] Status check timeout (attempt {attempt + 1})")
                if attempt < self.max_retries - 1:
                    continue
            except requests.exceptions.RequestException as e:
                logger.error(f"[{self.environment.upper()}] Network error in status check: {str(e)} (attempt {attempt + 1})")
                if attempt < self.max_retries - 1:
                    continue
            except Exception as e:
                logger.error(f"[{self.environment.upper()}] Unexpected error in status check: {str(e)} (attempt {attempt + 1})")
                if attempt < self.max_retries - 1:
                    continue
        
        return {'success': False, 'error': f'Failed to check status after {self.max_retries} attempts'}
    
    # Backward compatibility alias
    def stk_push(self, phone_number, amount, account_reference, transaction_desc="Payment"):
        """Backward compatibility wrapper for initiate_stk_push"""
        return self.initiate_stk_push(phone_number, amount, account_reference, transaction_desc)

# Create a singleton instance
mpesa_gateway = MpesaGateway()
# Create a singleton instance
mpesa_gateway = MpesaGateway()