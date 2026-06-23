from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notifications'
    def ready(self):
        """Register signal handlers when app is ready."""
        import notifications.signals  # noqa