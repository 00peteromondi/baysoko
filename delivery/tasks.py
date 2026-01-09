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
