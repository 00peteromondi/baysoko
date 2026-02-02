"""Celery application for Baysoko project.

This defines the project Celery app using the installed ``celery`` package.
It replaces the previous proxy module which caused import-time recursion.
Make sure Celery is installed in the project's virtualenv before running.
"""
import os
from celery import Celery

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'baysoko.settings')

app = Celery('baysoko')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
