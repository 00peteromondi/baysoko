"""Background tasks for delivery sync.

This module defines a `sync_with_external_system` task. If Celery is
available it exposes a `shared_task`; otherwise the module provides a
callable function that runs synchronously so callers can use a uniform API.
"""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

try:
    from celery import shared_task
    has_celery = True
except Exception:
    has_celery = False


def _sync(delivery_id):
    try:
        from .models import DeliveryRequest
        from . import integration
        delivery = DeliveryRequest.objects.filter(id=delivery_id).first()
        if not delivery:
            return None
        # Call integration sync (best-effort)
        return integration.sync_delivery_with_external_system(delivery)
    except Exception:
        logger.exception('Failed to sync delivery %s with external system', delivery_id)
        return None


if has_celery:
    @shared_task
    def sync_with_external_system(delivery_id):
        return _sync(delivery_id)
else:
    def sync_with_external_system(delivery_id):
        return _sync(delivery_id)


if has_celery:
    @shared_task
    def process_scheduled_escrow_releases():
        from django.utils import timezone
        import logging
        logger = logging.getLogger(__name__)
        try:
            from listings.models import Payment
            now = timezone.now()
            payments = Payment.objects.filter(is_held_in_escrow=True, actual_release_date__lte=now)
            processed = 0
            for p in payments:
                try:
                    p.release_to_seller()
                    processed += 1
                except Exception as e:
                    logger.exception('Error releasing payment %s: %s', p.id, e)
            logger.info('Processed %s scheduled escrow releases', processed)
            return {'processed': processed}
        except Exception as e:
            logger.exception('Error in process_scheduled_escrow_releases: %s', e)
            return {'error': str(e)}

    @shared_task
    def weekly_payouts():
        from django.utils import timezone
        import logging
        logger = logging.getLogger(__name__)
        try:
            from listings.models import Payment
            now = timezone.now()
            payments = Payment.objects.filter(is_held_in_escrow=False, actual_release_date__isnull=False)
            processed = 0
            for p in payments:
                try:
                    if not p.seller_payout_reference:
                        p.seller_payout_reference = f"PAYOUT-{p.order.id}-{int(now.timestamp())}"
                        p.save()
                    processed += 1
                except Exception as e:
                    logger.exception('Error processing payout for payment %s: %s', p.id, e)
            logger.info('Weekly payouts processed placeholder for %s payments', processed)
            return {'processed': processed}
        except Exception as e:
            logger.exception('Error in weekly_payouts: %s', e)
            return {'error': str(e)}
