from django.contrib.auth import get_user_model
from .models import Notification, NotificationPreference

User = get_user_model()

def create_notification(recipient, notification_type, title, message, 
                       sender=None, related_object_id=None, 
                       related_content_type='', action_url='', action_text=''):
    """
    Utility function to create notifications
    """
    # Get or create notification preferences
    preferences, created = NotificationPreference.objects.get_or_create(user=recipient)
    
    # Check if user wants this type of notification
    push_enabled = getattr(preferences, f'push_{notification_type.split("_")[0]}', True)
    
    if push_enabled:
        notification = Notification.objects.create(
            recipient=recipient,
            sender=sender,
            notification_type=notification_type,
            title=title,
            message=message,
            related_object_id=related_object_id,
            related_content_type=related_content_type,
            action_url=action_url,
            action_text=action_text
        )
        return notification
    return None


# notifications/utils.py
import requests
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    @staticmethod
    def send_sms(phone_number, message):
        """Send SMS notification using Africa's Talking or similar service"""
        try:
            if settings.SMS_ENABLED:
                # Example with Africa's Talking
                import africastalking
                
                africastalking.initialize(
                    settings.AFRICASTALKING_USERNAME,
                    settings.AFRICASTALKING_API_KEY
                )
                sms = africastalking.SMS
                
                response = sms.send(message, [phone_number])
                logger.info(f"SMS sent to {phone_number}: {response}")
                return True
        except Exception as e:
            logger.error(f"SMS sending failed: {str(e)}")
        return False

    @staticmethod
    def send_email(to_email, subject, template_name, context):
        """Send HTML email notification"""
        try:
            html_message = render_to_string(template_name, context)
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to_email],
                html_message=html_message,
                fail_silently=False,
            )
            return True
        except Exception as e:
            logger.error(f"Email sending failed: {str(e)}")
            return False

    @staticmethod
    def send_push_notification(user, title, message, data=None):
        """Send push notification (implement based on your push service)"""
        # Implementation for Firebase Cloud Messaging or similar
        pass

def notify_new_order(seller, buyer, order):
    """Notify seller about new order"""
    notification_service = NotificationService()
    
    # SMS to seller
    sms_message = f"New order #{order.id} from {buyer.get_full_name() or buyer.username}. Total: KSh {order.total_price}. Please process within 24 hours."
    notification_service.send_sms(seller.user.phone_number, sms_message)
    
    # Email to seller
    email_context = {
        'seller': seller,
        'buyer': buyer,
        'order': order,
        'order_items': order.order_items.all()
    }
    
    notification_service.send_email(
        seller.email,
        f"New Order #{order.id} - HomaBay Souq",
        'emails/new_order_seller.html',
        email_context
    )
    
    # In-app notification
    from notifications.models import Notification
    Notification.objects.create(
        user=seller,
        title="New Order Received",
        message=f"You have a new order #{order.id} from {buyer.get_full_name() or buyer.username}",
        notification_type='new_order',
        data={'order_id': order.id}
    )

def notify_order_shipped(buyer, seller, order, tracking_number=None):
    """Notify buyer that order has been shipped"""
    notification_service = NotificationService()
    
    # SMS to buyer
    sms_message = f"Your order #{order.id} has been shipped."
    if tracking_number:
        sms_message += f" Track your delivery: {tracking_number}"
    
    notification_service.send_sms(order.phone_number, sms_message)
    
    # Email to buyer
    email_context = {
        'buyer': buyer,
        'seller': seller,
        'order': order,
        'tracking_number': tracking_number
    }
    
    notification_service.send_email(
        buyer.email,
        f"Order #{order.id} Shipped - HomaBay Souq",
        'emails/order_shipped.html',
        email_context
    )

def notify_payment_received(seller, buyer, order):
    """Notify seller that payment was received"""
    notification_service = NotificationService()
    
    # SMS to seller
    sms_message = f"Payment received for order #{order.id}. Amount: KSh {order.total_price}. Please prepare the order for shipping."
    notification_service.send_sms(seller.phone_number, sms_message)
    
    # This will trigger the new order notification as well
    notify_new_order(seller, buyer, order)

def notify_delivery_assigned(order, driver_name, estimated_delivery):
    """Notify buyer about delivery assignment"""
    notification_service = NotificationService()
    
    sms_message = f"Delivery assigned for order #{order.id}. Driver: {driver_name}. Estimated delivery: {estimated_delivery}"
    notification_service.send_sms(order.phone_number, sms_message)

def notify_delivery_confirmed(seller, buyer, order):
    """Notify seller that delivery was confirmed and funds released"""
    notification_service = NotificationService()
    
    sms_message = f"Delivery confirmed for order #{order.id}. Funds of KSh {order.total_price} have been released to your account."
    notification_service.send_sms(seller.phone_number, sms_message)

def notify_order_delivered(buyer, order):
    """Notify buyer that order has been delivered"""
    notification_service = NotificationService()
    
    sms_message = f"Your order #{order.id} has been delivered. Thank you for shopping with us!"
    notification_service.send_sms(order.phone_number, sms_message)

def notify_new_review(recipient, reviewer, review, listing=None):
    """Notify about new review"""
    if listing:
        title = f"New Review on {listing.title}"
        message = f"{reviewer.username} left a {review.rating}-star review"
    else:
        title = "New Seller Review"
        message = f"{reviewer.username} left you a {review.rating}-star review"
    
    return create_notification(
        recipient=recipient,
        sender=reviewer,
        notification_type='review_received',
        title=title,
        message=message,
        related_object_id=review.id,
        related_content_type='review',
        action_url=f'/profile/{recipient.id}/' if not listing else f'/listing/{listing.id}/',
        action_text='View Review'
    )

def notify_listing_favorited(seller, user, listing):
    """Notify seller about favorite"""
    return create_notification(
        recipient=seller,
        sender=user,
        notification_type='favorite',
        title="Listing Favorited",
        message=f"{user.username} added your listing '{listing.title}' to favorites",
        related_object_id=listing.id,
        related_content_type='listing',
        action_url=f'/listing/{listing.id}/',
        action_text='View Listing'
    )

def notify_system_message(recipient, title, message, action_url=''):
    """Send system notification"""
    return create_notification(
        recipient=recipient,
        notification_type='system',
        title=title,
        message=message,
        related_content_type='system',
        action_url=action_url,
        action_text='View Details'
    )