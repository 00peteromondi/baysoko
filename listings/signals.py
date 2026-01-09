# listings/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Cart

User = get_user_model()

@receiver(post_save, sender=User)
def create_user_cart(sender, instance, created, **kwargs):
    if created:
        Cart.objects.create(user=instance)

"""
Automated webhook triggers using Django signals
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order, Payment
from .webhook_service import webhook_service

@receiver(post_save, sender=Order)
def trigger_order_webhook(sender, instance, created, **kwargs):
    """
    Automatically send webhook when order status changes
    """
    if created:
        # New order created
        webhook_service.send_order_event(instance, 'order_created')
    else:
        # Order updated - check status changes
        try:
            # Get original state if available
            if hasattr(instance, '_original_status'):
                original_status = instance._original_status
                new_status = instance.status
                
                if original_status != new_status:
                    if new_status == 'paid':
                        webhook_service.send_order_event(instance, 'order_paid')
                    elif new_status == 'shipped':
                        webhook_service.send_order_event(instance, 'order_shipped')
                    elif new_status == 'delivered':
                        webhook_service.send_order_event(instance, 'order_delivered')
        except:
            pass

@receiver(post_save, sender=Payment)
def trigger_payment_webhook(sender, instance, created, **kwargs):
    """
    Send webhook when payment is completed
    """
    if instance.status == 'completed' and instance.order:
        webhook_service.send_order_event(instance.order, 'order_paid')