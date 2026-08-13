import re
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def normalize_phone_number(number: str, default_region: str | None = None) -> str:
    """Normalize a phone number to E.164-style string when possible.

    Strategy:
    - If `phonenumbers` library is available, use it to parse and format to E.164.
    - Otherwise, apply a simple heuristic:
      * strip everything except digits and leading +
      * if number already starts with +, return it
      * if a `PHONE_DEFAULT_COUNTRY_CODE` is configured in settings (e.g. '+254'),
        use it to prefix numbers that don't start with +
      * otherwise prefix with '+' as a last resort

    Returns the normalized number (possibly unchanged) or an empty string on bad input.
    """
    if not number:
        return ''

    raw = str(number).strip()

    # Try using python-phonenumbers if installed
    try:
        import phonenumbers
        region = default_region or getattr(settings, 'PHONE_DEFAULT_REGION', None)
        if region:
            parsed = phonenumbers.parse(raw, region)
        else:
            parsed = phonenumbers.parse(raw, None)

        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        else:
            logger.debug('phonenumbers parsed but number not valid: %s', raw)
    except Exception as e:
        # phonenumbers may not be installed or parsing failed — fall back
        logger.debug('phonenumbers not usable or parse failed: %s', e)

    # Fallback heuristic
    # Keep leading + if present, otherwise strip non-digits
    s = raw
    if s.startswith('+'):
        s = '+' + re.sub(r'[^\d]', '', s[1:])
        return s

    s = re.sub(r'[^\d]', '', s)
    if not s:
        return ''

    # If user configured a default country code like '+254', use it
    default_cc = (getattr(settings, 'PHONE_DEFAULT_COUNTRY_CODE', '') or '').strip()
    if not default_cc:
        # Try to infer a sensible default from the Django TIME_ZONE setting (common mappings)
        tz = (getattr(settings, 'TIME_ZONE', '') or '').lower()
        mapping = {
            'nairobi': '+254',    # Kenya
            'accra': '+233',      # Ghana
            'lagos': '+234',      # Nigeria
            'johannesburg': '+27',# South Africa
            'london': '+44',      # UK
            'kolkata': '+91',     # India
            'dubai': '+971',      # UAE
        }
        for key, cc in mapping.items():
            if key in tz:
                default_cc = cc
                logger.debug('Inferred default country code %s from TIME_ZONE %s', cc, tz)
                break

    if default_cc:
        if s.startswith('0'):
            # remove leading zero and attach country code
            return default_cc + s[1:]
        return default_cc + s

    # Last-resort: prefix with + (best-effort)
    return '+' + s
