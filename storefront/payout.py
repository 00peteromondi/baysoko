from django.conf import settings
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def payout_to_phone(phone, amount, reference=None):
    """Attempt to payout to seller phone number.

    This is a light wrapper. In sandbox or when `MPESA_SIMULATE_PAYOUTS` is True
    it simulates success. Integrate your payouts provider here for real transfers.
    Returns (success: bool, provider_ref_or_error: str)
    """
    try:
        simulate = getattr(settings, 'MPESA_SIMULATE_PAYOUTS', True)
        if simulate:
            ref = f"SIMPAYOUT-{int(datetime.utcnow().timestamp())}"
            logger.info(f"Simulated payout to {phone} amount={amount} ref={ref}")
            return True, ref

        # TODO: integrate actual M-Pesa B2C/Bulk API here using your MpesaGateway
        # Example: mpesa = MpesaGateway(); mpesa.disburse(...)
        raise NotImplementedError('Real payout integration not implemented')
    except Exception as e:
        logger.exception('Payout failed')
        return False, str(e)
