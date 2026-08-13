import base64
import logging
import os
import time

import requests
from django.conf import settings
from requests.exceptions import RequestException, SSLError

from .phone import normalize_phone_number

logger = logging.getLogger(__name__)

BREVO_API_URL = 'https://api.brevo.com/v3/transactionalSMS/sms'
TWILIO_API_URL_TEMPLATE = 'https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json'


def _sms_attempts() -> int:
    try:
        return max(int(getattr(settings, 'SMS_MAX_ATTEMPTS', 3)), 1)
    except Exception:
        return 3


def _sms_backoff_base() -> float:
    try:
        return float(getattr(settings, 'SMS_BACKOFF_BASE', 1))
    except Exception:
        return 1.0


def _sms_enabled() -> bool:
    return bool(
        getattr(settings, 'ENABLE_SMS_NOTIFICATIONS', False)
        or getattr(settings, 'SMS_ENABLED', False)
        or getattr(settings, 'TWILIO_SMS_ENABLED', False)
        or getattr(settings, 'BREVO_SMS_ENABLED', False)
    )


def _preferred_provider() -> str:
    provider = (
        getattr(settings, 'SMS_PROVIDER', None)
        or os.environ.get('SMS_PROVIDER')
        or 'twilio'
    )
    return str(provider).strip().lower()


def _truncate_message(message: str) -> str:
    text = str(message or '').strip()
    if len(text) <= 1500:
        return text
    return text[:1497] + '...'


def _retry_post_json(url: str, json_payload: dict, headers: dict) -> tuple[bool, dict]:
    attempts = _sms_attempts()
    backoff_base = _sms_backoff_base()
    last_error = None

    for attempt in range(1, attempts + 1):
        try:
            response = requests.post(url, json=json_payload, headers=headers, timeout=12)
            if 200 <= response.status_code < 300:
                try:
                    return True, response.json()
                except Exception:
                    return True, {'raw': response.text}

            try:
                body = response.json()
            except Exception:
                body = {'raw': response.text}

            if 400 <= response.status_code < 500:
                return False, {'status_code': response.status_code, 'body': body}

            last_error = {'status_code': response.status_code, 'body': body}
        except SSLError as exc:
            last_error = {'error': f'SSL error: {exc}'}
        except RequestException as exc:
            last_error = {'error': str(exc)}

        if attempt < attempts:
            time.sleep(backoff_base * (2 ** (attempt - 1)))

    return False, last_error or {'error': 'unknown_error'}


def send_sms_twilio(to_number: str, message: str) -> dict:
    account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '') or os.environ.get('TWILIO_ACCOUNT_SID', '')
    auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '') or os.environ.get('TWILIO_AUTH_TOKEN', '')
    from_number = getattr(settings, 'TWILIO_FROM_NUMBER', '') or os.environ.get('TWILIO_FROM_NUMBER', '')
    messaging_service_sid = getattr(settings, 'TWILIO_MESSAGING_SERVICE_SID', '') or os.environ.get('TWILIO_MESSAGING_SERVICE_SID', '')

    if not account_sid or not auth_token or not (from_number or messaging_service_sid):
        logger.warning('Twilio SMS not configured; skipping SMS send')
        return {'success': False, 'error': 'twilio_not_configured'}

    normalized = normalize_phone_number(to_number)
    if not normalized:
        logger.warning('Unable to normalize phone number for Twilio: %s', to_number)
        return {'success': False, 'error': 'invalid_phone_number', 'original': to_number}

    payload = {
        'To': normalized,
        'Body': _truncate_message(message),
    }
    if messaging_service_sid:
        payload['MessagingServiceSid'] = messaging_service_sid
    else:
        payload['From'] = from_number

    url = TWILIO_API_URL_TEMPLATE.format(account_sid=account_sid)
    auth_value = base64.b64encode(f'{account_sid}:{auth_token}'.encode()).decode()
    headers = {
        'Authorization': f'Basic {auth_value}',
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    attempts = _sms_attempts()
    backoff_base = _sms_backoff_base()
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.post(url, data=payload, headers=headers, timeout=12)
            if 200 <= response.status_code < 300:
                try:
                    data = response.json()
                except Exception:
                    data = {'raw': response.text}
                logger.info('Twilio SMS sent to %s: sid=%s', normalized, data.get('sid'))
                return {'success': True, 'response': data}

            try:
                body = response.json()
            except Exception:
                body = {'raw': response.text}

            logger.warning('Twilio SMS failed with status %s: %s', response.status_code, body)
            if 400 <= response.status_code < 500:
                return {'success': False, 'status_code': response.status_code, 'body': body}
            last_error = {'status_code': response.status_code, 'body': body}
        except SSLError as exc:
            last_error = {'error': f'SSL error: {exc}'}
        except RequestException as exc:
            last_error = {'error': str(exc)}

        if attempt < attempts:
            time.sleep(backoff_base * (2 ** (attempt - 1)))

    logger.error('Twilio SMS failed after retries: %s', last_error)
    return {'success': False, **(last_error or {'error': 'unknown_error'})}


def send_sms_brevo(to_number: str, message: str) -> dict:
    """
    Backward-compatible wrapper.

    Existing callers still import `send_sms_brevo`, but the project now prefers
    Twilio for SMS delivery. This wrapper delegates to the configured provider,
    using Brevo only when explicitly selected or as a fallback.
    """
    return send_sms(to_number, message)


def _send_sms_brevo_direct(to_number: str, message: str) -> dict:
    api_key = getattr(settings, 'BREVO_API_KEY', os.environ.get('BREVO_API_KEY', ''))
    sender = getattr(settings, 'BREVO_SMS_SENDER', os.environ.get('BREVO_SMS_SENDER', 'Baysoko'))

    if not api_key:
        logger.warning('BREVO_API_KEY not configured; skipping Brevo SMS send')
        return {'success': False, 'error': 'brevo_api_key_not_configured'}

    normalized = normalize_phone_number(to_number)
    if not normalized:
        logger.warning('Unable to normalize phone number for Brevo: %s', to_number)
        return {'success': False, 'error': 'invalid_phone_number', 'original': to_number}

    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'api-key': api_key,
    }
    payload = {
        'sender': sender,
        'content': _truncate_message(message),
        'recipient': normalized,
        'recipients': [{'msisdn': normalized}],
    }

    ok, result = _retry_post_json(BREVO_API_URL, payload, headers)
    if ok:
        logger.info('Brevo SMS sent to %s', normalized)
        return {'success': True, 'response': result}

    logger.error('Brevo SMS failed for %s: %s', normalized, result)
    return {'success': False, **result}


def send_sms(to_number: str, message: str) -> dict:
    if not _sms_enabled():
        logger.info('SMS sending skipped because SMS is disabled in settings')
        return {'success': False, 'error': 'sms_disabled'}

    provider = _preferred_provider()

    if provider == 'twilio':
        result = send_sms_twilio(to_number, message)
        if result.get('success'):
            return result
        if getattr(settings, 'BREVO_SMS_ENABLED', False):
            logger.warning('Twilio SMS failed; attempting Brevo SMS fallback')
            return _send_sms_brevo_direct(to_number, message)
        return result

    if provider == 'brevo':
        result = _send_sms_brevo_direct(to_number, message)
        if result.get('success'):
            return result
        if getattr(settings, 'TWILIO_SMS_ENABLED', False):
            logger.warning('Brevo SMS failed; attempting Twilio fallback')
            return send_sms_twilio(to_number, message)
        return result

    logger.warning('Unknown SMS provider %s; defaulting to Twilio', provider)
    return send_sms_twilio(to_number, message)
