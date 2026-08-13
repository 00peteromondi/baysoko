from django.core.mail import mail_admins
from django.conf import settings
import logging

logger = logging.getLogger('storefront.payment')


def send_admin_alert(subject: str, message: str):
    """Send alert to site admins (ADMINS in settings).

    Uses mail_admins which respects ADMINS setting and email backend.
    Falls back to logging if ADMINS is not configured.
    """
    try:
        if getattr(settings, 'ADMINS', None):
            mail_admins(subject, message, fail_silently=False)
            logger.info(f"Sent admin alert: {subject}")
        else:
            # No ADMINS configured — log as critical
            logger.critical(f"ADMIN ALERT (no ADMINS configured): {subject} - {message}")
    except Exception as e:
        logger.exception(f"Failed to send admin alert: {e}")
