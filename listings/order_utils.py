from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Order, OrderItem, Activity
from notifications.utils import (
    notify_order_shipped, notify_delivery_assigned,
    notify_delivery_confirmed, create_notification, notify_order_status_update,
    notify_delivery_status, notify_order_delivered
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

        # Statuses controlled by the delivery system should go through
        # `Order.set_delivery_status` so guards in the model are respected.
        delivery_controlled = {
            'shipped', 'delivered', 'in_transit', 'out_for_delivery',
            'picked_up', 'failed', 'cancelled'
        }

        with transaction.atomic():
            old_status = order.status

            if new_status in delivery_controlled:
                # Use delivery-controlled setter which will save the order
                order.set_delivery_status(new_status)
                # Refresh to get any timestamps set by the model
                order.refresh_from_db()
            else:
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
    def cancel_order(order, cancelling_user, reason=None):
        """
        Cancel an order — only allowed before any seller has started
        fulfilment (i.e. before anything has shipped). If the order was
        already paid, this also refunds the buyer via M-Pesa and restores
        listing stock.

        Returns a dict: {'refunded': bool} so the caller can tell the user
        whether a refund was actually issued.
        """
        if cancelling_user != order.user and not getattr(cancelling_user, 'is_staff', False):
            raise ValidationError("Only the buyer can cancel this order")

        if order.status not in ('pending', 'paid'):
            raise ValidationError(
                "This order can no longer be cancelled — the seller has already "
                "started processing it. Please open a dispute instead if there's an issue."
            )

        # Belt-and-suspenders: even if status is still 'paid', don't allow
        # cancellation once any item has actually been shipped.
        if order.order_items.filter(shipped=True).exists():
            raise ValidationError(
                "This order can no longer be cancelled — one or more items have "
                "already shipped. Please open a dispute instead if there's an issue."
            )

        refunded = False
        refund_attempted = False

        with transaction.atomic():
            was_paid = order.status == 'paid'

            if was_paid:
                # Restore stock for each item, undoing what mark_as_paid() deducted.
                for order_item in order.order_items.select_related('listing'):
                    listing = order_item.listing
                    if not listing:
                        continue
                    listing.stock += order_item.quantity
                    if listing.is_sold and listing.stock > 0:
                        listing.is_sold = False
                    listing.save(update_fields=['stock', 'is_sold'])

                # Refund the buyer if a completed payment exists.
                payment = getattr(order, 'payment', None)
                if payment and payment.status == 'completed':
                    refund_attempted = True
                    refunded = payment.refund_via_mpesa(reason=reason or 'Order cancelled by buyer')
                    escrow = getattr(order, 'escrow', None)
                    if refunded and escrow and escrow.status == 'held':
                        escrow.refund_funds()

            OrderManager.update_order_status(
                order,
                'cancelled',
                actor=cancelling_user,
                notes={'reason': reason, 'refunded': refunded}
            )

            Activity.objects.create(
                user=cancelling_user,
                action=f"Order #{order.id} cancelled" + (f" — reason: {reason}" if reason else "")
            )

        return {'refunded': refunded, 'refund_attempted': refund_attempted}


    @staticmethod
    def confirm_delivery(order, confirming_user):
        """
        Confirm order delivery and release funds
        """
        # Only allow user confirmation once the delivery system marks the
        # order as delivered. The Delivery app is authoritative for delivery
        # state transitions.
        if order.status != 'delivered':
            raise ValidationError("Delivery has not been confirmed by the delivery provider yet")

        if confirming_user != order.user:
            raise ValidationError("Only the buyer can confirm delivery")

        with transaction.atomic():
            # The order is already 'delivered' (set by the Delivery app via
            # set_delivery_status()) — this step is the buyer's own
            # acknowledgement, not a further status transition, so it does
            # NOT go through update_order_status()/validate_order_status_transition().
            # A 'delivered' -> 'delivered' transition isn't a listed valid
            # move there and would always raise, breaking every confirmation.
            Activity.objects.create(
                user=confirming_user,
                action=f"Buyer confirmed delivery for Order #{order.id}"
            )

            # Mark escrow ready for admin approval (do not release immediately)
            if getattr(order, 'escrow', None):
                order.escrow.ready_for_release = True
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
            sellers = {item.listing.seller for item in order.order_items.select_related('listing__seller') if getattr(item.listing, 'seller', None)}
            for seller in sellers:
                notify_delivery_status(seller, order, f'Order #{order.id} has been marked as shipped. Keep tracking fulfilment and buyer delivery progress.')
            notify_order_status_update(order.user, order, 'shipped')

        elif new_status == 'delivered':
            # Notify all sellers
            for item in order.order_items.all():
                notify_delivery_confirmed(
                    item.listing.seller,
                    order.user,
                    order
                )
            notify_order_delivered(order.user, order)
            notify_order_status_update(order.user, order, 'delivered')

        elif new_status == 'disputed':
            # Notify all parties
            recipients = [order.user] + list(
                set(item.listing.seller for item in order.order_items.all())
            )
            for recipient in recipients:
                create_notification(
                    recipient=recipient,
                    notification_type='system',
                    title='Order Disputed',
                    message=f'Order #{order.id} has been marked as disputed',
                    related_object_id=order.id,
                    related_content_type='order'
                )
        elif new_status in {'paid', 'cancelled'}:
            notify_order_status_update(order.user, order, new_status)
            sellers = {item.listing.seller for item in order.order_items.select_related('listing__seller') if getattr(item.listing, 'seller', None)}
            for seller in sellers:
                seller_message = (
                    f'Order #{order.id} has been {new_status}. '
                    + ('Please stop fulfilment and review the order.' if new_status == 'cancelled' else 'The buyer payment is confirmed.')
                )
                notify_delivery_status(seller, order, seller_message)
