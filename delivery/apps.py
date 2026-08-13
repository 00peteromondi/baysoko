from django.apps import AppConfig


class DeliveryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'delivery'
    
    def ready(self):
        # Import signals
        import delivery.signals
        # Also import integration signals (hooks into listings.Order) if available
        try:
            import delivery.integration.signals  # may not exist in some deployments
        except Exception:
            pass