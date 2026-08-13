from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/bulk/jobs/(?P<slug>[-\w]+)/(?P<job_id>\d+)/progress/$', consumers.BulkJobProgressConsumer.as_asgi()),
]
