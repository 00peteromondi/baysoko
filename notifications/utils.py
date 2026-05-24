import logging

import requests
from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import get_connection, send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import strip_tags

from baysoko.utils.email_helpers import _send_email_threaded
from baysoko.utils.sms import send_sms

from .models import Notification, NotificationPreference

logger = logging.getLogger(__name__)
User = get_user_model()


def _preference(recipient):
    pref, _ = NotificationPreference.objects.get_or_create(user=recipient)
    return pref


def _user_settings(recipient):
    try:
        return getattr(recipient, 'settings', None)
    except Exception:
        return None


def _sms_allowed(recipient, category='system'):
    settings_obj = _user_settings(recipient)
    if settings_obj is not None and not getattr(settings_obj, 'sms_notifications', True):
        return False
    if not getattr(settings, 'ENABLE_SMS_NOTIFICATIONS', False) and not getattr(settings, 'SMS_ENABLED', False):
        return False
    return True


def _email_allowed(recipient, category='system'):
    pref = _preference(recipient)
    settings_obj = _user_settings(recipient)
    if settings_obj is not None and not getattr(settings_obj, 'email_notifications', True):
        if category != 'promotional':
            return False
    attr = {
        'message': 'email_messages',
        'order': 'email_orders',
        'review': 'email_reviews',
        'promotional': 'email_promotional',
        'system': 'email_orders',
    }.get(category, 'email_orders')
    return getattr(pref, attr, True)


def _push_allowed(recipient, notification_type):
    pref = _preference(recipient)
    prefix = (notification_type or 'system').split('_')[0]
    return getattr(pref, f'push_{prefix}', True)


def _phone_for(recipient, fallback_order=None):
    order_phone = getattr(fallback_order, 'phone_number', None) if fallback_order else None
    recipient_phone = getattr(recipient, 'phone_number', None)
    return order_phone or recipient_phone or ''


def _recipient_email(recipient, fallback_order=None):
    order_email = getattr(fallback_order, 'email', None) if fallback_order else None
    return order_email or getattr(recipient, 'email', '') or ''


def _send_sms_if_allowed(recipient, message, category='system', fallback_order=None):
    phone = _phone_for(recipient, fallback_order=fallback_order)
    if not phone or not _sms_allowed(recipient, category=category):
        return False
    result = send_sms(phone, str(message))
    return bool(result.get('success'))


def _send_email_message(to_email, subject, plain_message, html_message=None):
    if not to_email:
        return False
    try:
        _send_email_threaded(subject, plain_message, html_message or plain_message, [to_email])
        return True
    except Exception:
        try:
            final_conn = get_connection(backend='django.core.mail.backends.smtp.EmailBackend')
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to_email],
                html_message=html_message,
                connection=final_conn,
                fail_silently=False,
            )
            return True
        except Exception:
            logger.exception('Failed sending fallback email to %s', to_email)
            return False


def create_notification(
    recipient,
    notification_type,
    title,
    message,
    sender=None,
    related_object_id=None,
    related_content_type='',
    action_url='',
    action_text='',
):
    try:
        if not recipient or not _push_allowed(recipient, notification_type):
            return None
        notification = Notification.objects.create(
            recipient=recipient,
            sender=sender,
            notification_type=notification_type[:20],
            title=title,
            message=message,
            related_object_id=related_object_id,
            related_content_type=related_content_type,
            action_url=action_url,
            action_text=action_text,
        )
        try:
            async_to_sync(broadcast_notification_via_websocket)(notification)
        except Exception:
            logger.debug('WebSocket broadcast skipped for notification %s', notification.id)
        try:
            NotificationService.send_push_notification(
                recipient,
                title,
                message,
                data={
                    'notification_id': notification.id,
                    'action_url': action_url,
                    'notification_type': notification.notification_type,
                },
            )
        except Exception:
            logger.debug('Push notification skipped for %s', recipient)
        logger.info('Notification created for %s: %s', recipient.username, title)
        return notification
    except Exception:
        logger.exception('Error creating notification')
        return None


def create_and_broadcast_notification(*args, **kwargs):
    return create_notification(*args, **kwargs)


class NotificationService:
    @staticmethod
    def send_sms(phone_number, message):
        try:
            result = send_sms(phone_number, message)
            return bool(result.get('success'))
        except Exception:
            logger.exception('SMS sending failed')
            return False

    @staticmethod
    def send_email(to_email, subject, template_name, context):
        try:
            html_message = render_to_string(template_name, context)
            plain_message = strip_tags(html_message)
            return _send_email_message(to_email, subject, plain_message, html_message)
        except Exception:
            logger.exception('Email sending failed')
            return False

    @staticmethod
    def send_push_notification(user, title, message, data=None):
        try:
            app_id = getattr(settings, 'ONESIGNAL_APP_ID', '')
            api_key = getattr(settings, 'ONESIGNAL_API_KEY', '')
            rest_url = getattr(settings, 'ONESIGNAL_REST_URL', 'https://onesignal.com/api/v1/notifications')
            if not app_id or not api_key:
                return False
            payload = {
                'app_id': app_id,
                'include_external_user_ids': [str(user.id)],
                'headings': {'en': title},
                'contents': {'en': message},
                'data': data or {},
            }
            headers = {
                'Authorization': f'Basic {api_key}',
                'Content-Type': 'application/json',
            }
            resp = requests.post(rest_url, json=payload, headers=headers, timeout=8)
            return resp.status_code in (200, 201)
        except Exception:
            logger.exception('Push send failed')
            return False


def _notify_user(recipient, *, notification_type, title, message, category='system', sender=None, action_url='', action_text='View details', related_object_id=None, related_content_type='', email_subject=None, fallback_order=None):
    notification = create_notification(
        recipient=recipient,
        notification_type=notification_type,
        title=title,
        message=message,
        sender=sender,
        related_object_id=related_object_id,
        related_content_type=related_content_type,
        action_url=action_url,
        action_text=action_text,
    )
    email_addr = _recipient_email(recipient, fallback_order=fallback_order)
    if email_addr and _email_allowed(recipient, category=category):
        _send_email_message(email_addr, email_subject or title, message, f'<p>{message}</p>')
    _send_sms_if_allowed(recipient, message, category=category, fallback_order=fallback_order)
    return notification


def notify_store_created(user, store):
    try:
        store_url = store.get_absolute_url()
    except Exception:
        store_url = ''
    message = f'Your store "{store.name}" is ready. You can now add listings and start selling on Baysoko.'
    return _notify_user(
        user,
        notification_type='system',
        title='Store Created',
        message=message,
        category='system',
        action_url=store_url,
        action_text='View store',
        related_object_id=store.id,
        related_content_type='store',
        email_subject=f'Store created: {store.name}',
    )


def notify_listing_saved(seller, listing, created=True):
    action = 'created' if created else 'updated'
    message = f'Your listing "{listing.title}" was {action} successfully and is ready for buyers.'
    return _notify_user(
        seller,
        notification_type='system',
        title=f'Listing {"Created" if created else "Updated"}',
        message=message,
        category='system',
        action_url=reverse('listing-detail', args=[listing.pk]) if listing.pk else '',
        action_text='View listing',
        related_object_id=listing.pk,
        related_content_type='listing',
        email_subject=f'Listing {action}: {listing.title}',
    )


def notify_new_order(seller, buyer, order):
    seller_message = (
        f'New paid order #{order.id} from {buyer.get_full_name() or buyer.username}. '
        f'Total: KSh {order.total_price}. Please prepare the items for fulfillment.'
    )
    return _notify_user(
        seller,
        notification_type='order_placed',
        title='New Order Received',
        message=seller_message,
        category='order',
        sender=buyer,
        action_url=reverse('order_detail', kwargs={'order_id': order.id}),
        action_text='View order',
        related_object_id=order.id,
        related_content_type='order',
        email_subject=f'New paid order #{order.id}',
        fallback_order=order,
    )


def notify_order_created(buyer, order):
    message = f'Order #{order.id} has been placed successfully. Complete payment to confirm your purchase.'
    return _notify_user(
        buyer,
        notification_type='order_placed',
        title='Order Placed Successfully',
        message=message,
        category='order',
        action_url=reverse('order_detail', kwargs={'order_id': order.id}),
        action_text='View order',
        related_object_id=order.id,
        related_content_type='order',
        email_subject=f'Order #{order.id} created',
        fallback_order=order,
    )


def notify_order_paid(buyer, order):
    message = f'Payment for order #{order.id} has been confirmed. The seller has been notified and your order is now being processed.'
    return _notify_user(
        buyer,
        notification_type='payment_received',
        title='Payment Confirmed',
        message=message,
        category='order',
        action_url=reverse('order_detail', kwargs={'order_id': order.id}),
        action_text='Track order',
        related_object_id=order.id,
        related_content_type='order',
        email_subject=f'Payment confirmed for order #{order.id}',
        fallback_order=order,
    )


def notify_payment_received(seller, buyer, order):
    message = f'Payment received for order #{order.id}. Amount: KSh {order.total_price}. Please prepare the order for shipping.'
    return _notify_user(
        seller,
        notification_type='payment_received',
        title='Payment Received',
        message=message,
        category='order',
        sender=buyer,
        action_url=reverse('order_detail', kwargs={'order_id': order.id}),
        action_text='Manage order',
        related_object_id=order.id,
        related_content_type='order',
        email_subject=f'Payment received for order #{order.id}',
        fallback_order=order,
    )


def notify_order_shipped(buyer, seller, order, tracking_number=None):
    message = f'Your order #{order.id} has been shipped.'
    if tracking_number:
        message += f' Tracking number: {tracking_number}.'
    return _notify_user(
        buyer,
        notification_type='order_shipped',
        title='Order Shipped',
        message=message,
        category='order',
        sender=seller,
        action_url=reverse('order_detail', kwargs={'order_id': order.id}),
        action_text='Track order',
        related_object_id=order.id,
        related_content_type='order',
        email_subject=f'Order #{order.id} shipped',
        fallback_order=order,
    )


def notify_order_delivered(buyer, order):
    message = f'Your order #{order.id} has been delivered. Please confirm receipt if everything is okay.'
    return _notify_user(
        buyer,
        notification_type='order_delivered',
        title='Order Delivered',
        message=message,
        category='order',
        action_url=reverse('order_detail', kwargs={'order_id': order.id}),
        action_text='View order',
        related_object_id=order.id,
        related_content_type='order',
        email_subject=f'Order #{order.id} delivered',
        fallback_order=order,
    )


def notify_order_status_update(buyer, order, status):
    status_messages = {
        'processing': 'Your order is being prepared by the seller.',
        'paid': 'Your payment has been confirmed and your order is being prepared.',
        'shipped': 'Your order has been shipped and is on its way.',
        'delivered': 'Your order has been delivered successfully.',
        'cancelled': 'Your order has been cancelled.',
        'refunded': 'Your order has been refunded.',
        'disputed': 'Your order is under review due to a dispute.',
    }
    message = status_messages.get(status, f'Your order #{order.id} status has been updated to {status}.')
    return _notify_user(
        buyer,
        notification_type='system',
        title=f'Order #{order.id} Update',
        message=message,
        category='order',
        action_url=reverse('order_detail', kwargs={'order_id': order.id}),
        action_text='View details',
        related_object_id=order.id,
        related_content_type='order',
        email_subject=f'Order #{order.id} status update',
        fallback_order=order,
    )


def notify_delivery_assigned(order, driver_name, estimated_delivery):
    message = f'Delivery assigned for order #{order.id}. Driver: {driver_name}. Estimated delivery: {estimated_delivery}.'
    return _notify_user(
        order.user,
        notification_type='system',
        title='Delivery Assigned',
        message=message,
        category='order',
        action_url=reverse('order_detail', kwargs={'order_id': order.id}),
        action_text='Track order',
        related_object_id=order.id,
        related_content_type='order',
        email_subject=f'Delivery assigned for order #{order.id}',
        fallback_order=order,
    )


def notify_delivery_status(recipient, order, message):
    return _notify_user(
        recipient,
        notification_type='system',
        title='Delivery Update',
        message=str(message),
        category='order',
        action_url=reverse('order_detail', kwargs={'order_id': order.id}) if getattr(order, 'id', None) else '',
        action_text='View order',
        related_object_id=getattr(order, 'id', None),
        related_content_type='order',
        email_subject=f'Delivery update for order #{getattr(order, "id", "")}',
        fallback_order=order,
    )


def notify_delivery_confirmed(seller, buyer, order):
    message = f'Delivery confirmed for order #{order.id}. Funds of KSh {order.total_price} are now ready for seller settlement.'
    return _notify_user(
        seller,
        notification_type='system',
        title='Delivery Confirmed',
        message=message,
        category='order',
        sender=buyer,
        action_url=reverse('order_detail', kwargs={'order_id': order.id}),
        action_text='View order',
        related_object_id=order.id,
        related_content_type='order',
        email_subject=f'Delivery confirmed for order #{order.id}',
        fallback_order=order,
    )


def notify_new_review(seller, user, review, listing=None, review_type=None):
    if review_type == 'seller':
        title = f'New Seller Review from {user.username}'
        message = f'{user.username} has reviewed you as a seller.'
    elif review_type == 'order':
        title = f'New Order Review from {user.username}'
        message = f'{user.username} has reviewed their order experience.'
    else:
        title = f'New Review on {listing.title}' if listing else f'New Review from {user.username}'
        message = f'{user.username} has reviewed {listing.title if listing else "your item"}.'
    return _notify_user(
        seller,
        notification_type='review_received',
        title=title,
        message=message,
        category='review',
        sender=user,
        related_object_id=getattr(review, 'id', None),
        related_content_type='review',
        email_subject=title,
    )


def notify_listing_favorited(seller, user, listing):
    return create_notification(
        recipient=seller,
        sender=user,
        notification_type='favorite',
        title='Listing Favorited',
        message=f"{user.username} added your listing '{listing.title}' to favorites",
        related_object_id=listing.id,
        related_content_type='listing',
        action_url=reverse('listing-detail', args=[listing.pk]) if listing.pk else '',
        action_text='View listing',
    )


def notify_system_message(recipient, title, message, action_url=''):
    return _notify_user(
        recipient,
        notification_type='system',
        title=title,
        message=message,
        category='system',
        action_url=action_url,
        action_text='View details',
        email_subject=title,
    )


async def broadcast_notification_via_websocket(notification):
    try:
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        group_name = f'notifications_user_{notification.recipient_id}'
        notification_data = {
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'type': notification.notification_type,
            'is_read': notification.is_read,
            'time_since': notification.time_since,
            'action_url': notification.action_url,
            'action_text': notification.action_text,
            'created_at': notification.created_at.isoformat(),
            'sender': notification.sender.username if notification.sender else None,
        }
        await channel_layer.group_send(
            group_name,
            {
                'type': 'notification.created',
                'notification': notification_data,
            },
        )
    except Exception:
        logger.exception('Failed to broadcast notification via WebSocket')
