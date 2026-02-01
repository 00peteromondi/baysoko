"""
ASGI config for homabaysoqou project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'baysoko.settings')

django_asgi_app = get_asgi_application()

# Import delivery websocket routing lazily
import delivery.routing

application = ProtocolTypeRouter({
	'http': django_asgi_app,
	'websocket': AuthMiddlewareStack(
		URLRouter(
			delivery.routing.websocket_urlpatterns
		)
	),
})
