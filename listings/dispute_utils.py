from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Order, Escrow, Activity
from notifications.utils import create_notification

class DisputeManager:
    DISPUTE_REASONS = [
        'item_not_received',
        'item_not_as_described',
        'wrong_item',
        'damaged_item',
        'other'
    ]

    @staticmethod
    def create_dispute(order, reason, description, evidence_files=None):
        """
        Create a new dispute for an order
        """
        if order.status not in ['shipped', 'delivered']:
            raise ValidationError("Can only dispute shipped or delivered orders")

        if reason not in DisputeManager.DISPUTE_REASONS:
            raise ValidationError("Invalid dispute reason")

        with transaction.atomic():
            # Update order status
            order.status = 'disputed'
            order.save()

            # Update escrow status
            order.escrow.status = 'disputed'
            order.escrow.save()

            # Create activity log
            Activity.objects.create(
                user=order.user,
                action=f"Dispute created for Order #{order.id}: {reason}"
            )

            # Notify all sellers involved
            for item in order.order_items.all():
                seller = item.listing.seller
                create_notification(
                    recipient=seller,
                    notification_type='dispute',
                    title='Order Disputed',
                    message=f'Order #{order.id} has been disputed. Reason: {reason}',
                    related_object_id=order.id,
                    related_content_type='order'
                )

    @staticmethod
    def resolve_dispute(order, resolution, refund_amount=None, seller_penalty=None):
        """
        Resolve a dispute with optional refund and seller penalty
        """
        if order.status != 'disputed':
            raise ValidationError("Can only resolve disputed orders")

        with transaction.atomic():
            if refund_amount:
                # Process refund to buyer
                DisputeManager._process_refund(order, refund_amount)

            if seller_penalty:
                # Apply penalty to seller(s)
                DisputeManager._apply_seller_penalty(order, seller_penalty)

            # Update order status
            order.status = 'resolved'
            order.save()

            # Update escrow status
            order.escrow.status = 'refunded' if refund_amount else 'released'
            order.escrow.dispute_resolved_at = timezone.now()
            order.escrow.save()

            # Create activity log
            Activity.objects.create(
                user=order.user,
                action=f"Dispute resolved for Order #{order.id}"
            )

            # Notify all parties
            create_notification(
                recipient=order.user,
                notification_type='dispute_resolved',
                title='Dispute Resolved',
                message=f'Your dispute for Order #{order.id} has been resolved.',
                related_object_id=order.id,
                related_content_type='order'
            )

            for item in order.order_items.all():
                seller = item.listing.seller
                create_notification(
                    recipient=seller,
                    notification_type='dispute_resolved',
                    title='Dispute Resolved',
                    message=f'The dispute for Order #{order.id} has been resolved.',
                    related_object_id=order.id,
                    related_content_type='order'
                )

    @staticmethod
    def mediate_dispute(order, mediator_notes, proposed_solution):
        """
        Record mediator intervention in a dispute
        """
        if order.status != 'disputed':
            raise ValidationError("Can only mediate disputed orders")

        # Record mediation attempt
        Activity.objects.create(
            user=mediator_notes.get('mediator'),
            action=f"Dispute mediation for Order #{order.id}: {proposed_solution}"
        )

        # Notify both parties
        for party in [order.user] + list(set(item.listing.seller for item in order.order_items.all())):
            create_notification(
                recipient=party,
                notification_type='dispute_mediation',
                title='Dispute Mediation Update',
                message=f'New mediation update for Order #{order.id}',
                related_object_id=order.id,
                related_content_type='order'
            )

    @staticmethod
    def _process_refund(order, amount):
        """
        Process refund to buyer
        """
        # Implementation would depend on your payment gateway
        pass

    @staticmethod
    def _apply_seller_penalty(order, penalty):
        """
        Apply penalties to seller account
        """
        # Implementation would depend on your seller management system
        pass