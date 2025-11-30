from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Order, OrderItem, Activity
from notifications.utils import (
    notify_order_shipped, notify_delivery_assigned,
    notify_delivery_confirmed, create_notification
)
from .dispute_utils import DisputeManager

class OrderManager:
    """
    Manages order state transitions and validations
    """

    @staticmethod
    def validate_order_status_transition(order, new_status):
        """
        Validate if the order can transition to the new status
        """
        valid_transitions = {
            'pending': ['paid', 'cancelled'],
            'paid': ['shipped', 'partially_shipped', 'cancelled', 'disputed'],
            'partially_shipped': ['shipped', 'disputed'],
            'shipped': ['delivered', 'disputed'],
            'delivered': ['disputed'],
            'disputed': ['resolved'],
            'cancelled': [],  # No transitions from cancelled
            'resolved': []  # No transitions from resolved
        }

        if new_status not in valid_transitions.get(order.status, []):
            raise ValidationError(
                f"Invalid status transition from {order.status} to {new_status}"
            )

    @staticmethod
    def update_order_status(order, new_status, actor=None, notes=None):
        """
        Update order status with validation and notifications
        """
        OrderManager.validate_order_status_transition(order, new_status)

        with transaction.atomic():
            old_status = order.status
            order.status = new_status
            
            if new_status == 'shipped':
                order.shipped_at = timezone.now()
            elif new_status == 'delivered':
                order.delivered_at = timezone.now()
            
            order.save()

            # Log the activity
            Activity.objects.create(
                user=actor or order.user,
                action=f"Order #{order.id} status changed from {old_status} to {new_status}"
            )

            # Send appropriate notifications
            OrderManager._send_status_notifications(order, old_status, new_status, notes)

    @staticmethod
    def mark_items_shipped(order, seller, tracking_number=None):
        """
        Mark items as shipped for a specific seller
        """
        if order.status not in ['paid', 'partially_shipped']:
            raise ValidationError("Can only mark items shipped for paid orders")

        seller_items = order.order_items.filter(
            listing__seller=seller,
            shipped=False
        )

        if not seller_items.exists():
            raise ValidationError("No unshipped items found for this seller")

        with transaction.atomic():
            now = timezone.now()
            
            # Mark items as shipped
            for item in seller_items:
                item.shipped = True
                item.shipped_at = now
                if tracking_number:
                    item.tracking_number = tracking_number
                item.save()

            # Update order status
            unshipped_items = order.order_items.filter(shipped=False)
            new_status = 'shipped' if not unshipped_items.exists() else 'partially_shipped'
            
            # Update order status if changed
            if order.status != new_status:
                OrderManager.update_order_status(
                    order, 
                    new_status,
                    actor=seller,
                    notes={'tracking_number': tracking_number}
                )

    @staticmethod
    def confirm_delivery(order, confirming_user):
        """
        Confirm order delivery and release funds
        """
        if order.status != 'shipped':
            raise ValidationError("Can only confirm delivery for shipped orders")

        if confirming_user != order.user:
            raise ValidationError("Only the buyer can confirm delivery")

        with transaction.atomic():
            OrderManager.update_order_status(
                order,
                'delivered',
                actor=confirming_user
            )

            # Release escrow
            order.escrow.status = 'released'
            order.escrow.released_at = timezone.now()
            order.escrow.save()

            # Notify sellers
            for item in order.order_items.all():
                notify_delivery_confirmed(
                    item.listing.seller,
                    confirming_user,
                    order
                )

    @staticmethod
    def create_dispute(order, reason, description, evidence_files=None):
        """
        Create a dispute for an order
        """
        return DisputeManager.create_dispute(
            order,
            reason,
            description,
            evidence_files
        )

    @staticmethod
    def _send_status_notifications(order, old_status, new_status, notes=None):
        """
        Send notifications based on status change
        """
        if new_status == 'shipped':
            # Notify buyer of shipment
            notify_order_shipped(
                order.user,
                None,  # No specific seller for multi-seller orders
                order,
                notes.get('tracking_number') if notes else None
            )

        elif new_status == 'delivered':
            # Notify all sellers
            for item in order.order_items.all():
                notify_delivery_confirmed(
                    item.listing.seller,
                    order.user,
                    order
                )

        elif new_status == 'disputed':
            # Notify all parties
            recipients = [order.user] + list(
                set(item.listing.seller for item in order.order_items.all())
            )
            for recipient in recipients:
                create_notification(
                    recipient=recipient,
                    notification_type='dispute',
                    title='Order Disputed',
                    message=f'Order #{order.id} has been marked as disputed',
                    related_object_id=order.id,
                    related_content_type='order'
                )