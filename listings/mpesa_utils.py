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
    def __init__(self):
        self.consumer_key = getattr(settings, 'MPESA_CONSUMER_KEY', '')
        self.consumer_secret = getattr(settings, 'MPESA_CONSUMER_SECRET', '')
        self.business_shortcode = getattr(settings, 'MPESA_BUSINESS_SHORTCODE', '174379')
        self.passkey = getattr(settings, 'MPESA_PASSKEY', '')
        self.callback_url = getattr(settings, 'MPESA_CALLBACK_URL', '')
        self.environment = getattr(settings, 'MPESA_ENVIRONMENT', 'sandbox')
        
        # Check if we have valid credentials
        self.has_valid_credentials = all([
            self.consumer_key,
            self.consumer_secret, 
            self.passkey
        ])
        
        if self.environment == 'sandbox':
            self.base_url = 'https://sandbox.safaricom.co.ke'
        else:
            self.base_url = 'https://api.safaricom.co.ke'
    
    def get_access_token(self):
        """Get OAuth access token from Safaricom API"""
        if not self.has_valid_credentials:
            logger.warning("M-Pesa credentials not configured. Using simulation mode.")
            return "simulation_token"
        
        try:
            url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
            auth_string = f"{self.consumer_key}:{self.consumer_secret}"
            encoded_auth = base64.b64encode(auth_string.encode()).decode()
            
            headers = {
                'Authorization': f'Basic {encoded_auth}',
                'Cache-Control': 'no-cache'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                access_token = data.get('access_token')
                if access_token:
                    logger.info("Successfully obtained M-Pesa access token")
                    return access_token
                else:
                    logger.error("No access token in response")
                    return None
            else:
                logger.error(f"M-Pesa API Error {response.status_code}: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting M-Pesa access token: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting access token: {str(e)}")
            return None
    
    def generate_password(self, timestamp):
        """Generate Lipa Na M-Pesa Online Password"""
        data_to_encode = f"{self.business_shortcode}{self.passkey}{timestamp}"
        encoded_string = base64.b64encode(data_to_encode.encode()).decode()
        return encoded_string
    
    def stk_push(self, phone_number, amount, account_reference, transaction_desc):
        """Initiate STK Push to customer"""
        # If no valid credentials, simulate success for development
        if not self.has_valid_credentials:
            logger.info("Simulating M-Pesa STK Push (no valid credentials)")
            return self._simulate_stk_push()
        
        try:
            access_token = self.get_access_token()
            if not access_token:
                return {
                    'success': False, 
                    'error': 'Could not authenticate with M-Pesa API. Please check your credentials.'
                }
            
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password = self.generate_password(timestamp)
            
            url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
            
            payload = {
                "BusinessShortCode": self.business_shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": int(amount),
                "PartyA": self.format_phone_number(phone_number),
                "PartyB": self.business_shortcode,
                "PhoneNumber": self.format_phone_number(phone_number),
                "CallBackURL": self.callback_url,
                "AccountReference": account_reference,
                "TransactionDesc": transaction_desc
            }
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            logger.info(f"Sending STK Push request: {payload}")
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response_data = response.json()
            
            logger.info(f"STK Push response: {response_data}")
            
            if response.status_code == 200:
                if response_data.get('ResponseCode') == '0':
                    return {
                        'success': True,
                        'checkout_request_id': response_data.get('CheckoutRequestID'),
                        'merchant_request_id': response_data.get('MerchantRequestID'),
                        'response_description': response_data.get('ResponseDescription')
                    }
                else:
                    error_msg = response_data.get('ResponseDescription', 'Unknown error from M-Pesa')
                    logger.error(f"M-Pesa STK Push failed: {error_msg}")
                    return {
                        'success': False,
                        'error': error_msg
                    }
            else:
                error_msg = f"HTTP {response.status_code}: {response_data.get('errorMessage', 'Unknown error')}"
                logger.error(f"M-Pesa API error: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
                
        except requests.exceptions.Timeout:
            error_msg = "M-Pesa API request timed out"
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error: {str(e)}"
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}
    
    def _simulate_stk_push(self):
        """Simulate successful STK push for development"""
        import time
        timestamp = int(time.time())
        return {
            'success': True,
            'checkout_request_id': f'ws_CO_{timestamp}',
            'merchant_request_id': f'MARQ-{timestamp}',
            'response_description': 'Success. Request accepted for processing [SIMULATION]'
        }
    
    def format_phone_number(self, phone_number):
        """Format phone number to 2547XXXXXXXX format"""
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
    
    def check_transaction_status(self, checkout_request_id):
        """Check status of a transaction"""
        if not self.has_valid_credentials:
            # In simulation, return pending status
            return {
                'success': True,
                'result_code': '0',
                'result_desc': 'The service request has been accepted successfully [SIMULATION]'
            }
        
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
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response_data = response.json()
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'result_code': response_data.get('ResultCode'),
                    'result_desc': response_data.get('ResultDesc'),
                    'response_data': response_data
                }
            else:
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}: {response_data.get('errorMessage', 'Unknown error')}"
                }
                
        except Exception as e:
            logger.error(f"Transaction status check error: {str(e)}")
            return {'success': False, 'error': str(e)}

# Create a singleton instance
mpesa_gateway = MpesaGateway()