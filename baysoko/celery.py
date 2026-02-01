import os
from celery import Celery
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'baysoko.settings')

app = Celery('baysoko')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

app.conf.update(
    broker_url=getattr(settings, 'CELERY_BROKER_URL', None),
    result_backend=getattr(settings, 'CELERY_RESULT_BACKEND', None),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone=getattr(settings, 'TIME_ZONE', 'UTC'),
    enable_utc=True,
)

__all__ = ('app',)
