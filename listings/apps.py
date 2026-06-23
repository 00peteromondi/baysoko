from django.apps import AppConfig


class ListingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'listings'
    
    def ready(self):
        # Import signals
        import listings.webhooks
        from listings import signals  # If you have other signals
        
        # Connect webhook signals
        from listings.models import Order
        from listings.webhooks import handle_order_created, handle_order_status_change
        
        from django.db.models.signals import post_save
        
        post_save.connect(handle_order_created, sender=Order)
        post_save.connect(handle_order_status_change, sender=Order)

