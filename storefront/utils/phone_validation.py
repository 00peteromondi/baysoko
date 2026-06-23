# storefront/utils/phone_validation.py
import re

def validate_kenyan_phone_number(phone_number):
    """Validate and normalize Kenyan phone numbers"""
    if not phone_number:
        return False, "Phone number is required"
    
    phone = str(phone_number).strip()
    
    # Remove any non-digit characters except +
    phone = re.sub(r'[^\d\+]', '', phone)
    
    # Check if it's a valid Kenyan number
    # Valid formats: 0712345678, 712345678, +254712345678, 254712345678
    if phone.startswith('0') and len(phone) == 10:
        # Format: 0712345678
        return True, '+254' + phone[1:]
    elif phone.isdigit() and len(phone) == 9:
        # Format: 712345678
        return True, '+254' + phone
    elif phone.startswith('+254') and len(phone) == 13:
        # Format: +254712345678
        return True, phone
    elif phone.startswith('254') and len(phone) == 12:
        # Format: 254712345678
        return True, '+' + phone
    else:
        return False, "Invalid phone number format. Please use: 0712345678, 712345678, or +254712345678"