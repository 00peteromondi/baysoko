from celery import Celery

app = Celery('delivery')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks(['delivery.integration'])

# Schedule tasks
app.conf.beat_schedule = {
    'sync-orders-every-5-minutes': {
        'task': 'delivery.integration.tasks.sync_all_platforms',
        'schedule': 300.0,  # 5 minutes
    },
    'retry-failed-webhooks-hourly': {
        'task': 'delivery.integration.tasks.retry_failed_webhooks',
        'schedule': 3600.0,  # 1 hour
    },
}
